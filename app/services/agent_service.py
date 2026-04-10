"""
AI Agent Service for the PSM (Product Store Management) System.
This module implements a stateful AI agent using LangGraph and LangChain.
The agent can perform database actions, manage shopping carts, and handle
procurement based on user roles (Admin, Supplier, Customer).
"""

import logging
from typing import Annotated, Dict, List, Optional, TypedDict, Union
from sqlalchemy.orm import Session
from sqlalchemy import or_
from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from app import models, crud, schemas
from app.database import AppSessionLocal

# Setup logging for debugging and monitoring
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# The underlying LLM model used by the agent
LLM_MODEL = "gpt-oss:20b-cloud"

# --- AGENT STATE ---
class AgentState(TypedDict):
    """
    Defines the state structure maintained by the LangGraph workflow.
    - messages: A list of all conversation messages (Human, AI, System, Tool).
    - user_role: The role of the logged-in user (admin, supplier, customer).
    - username: The username of the logged-in user.
    """
    # Annotated with a lambda to ensure new messages are appended to the list
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]
    user_role: str
    username: str

# --- IN-MEMORY USER CARTS ---
# A global dictionary to store shopping carts per user during their session.
# Key: username, Value: List of product dictionaries.
user_carts: Dict[str, List[Dict]] = {}

# --- HELPER: FUZZY SEARCH ---
def find_product_by_name(db: Session, name: str, supplier_name: Optional[str] = None):
    """
    CONCEPT: Fuzzy Name Matching.
    Users often make typos or don't know the exact product name. 
    This function uses SQLAlchemy's `ilike` for case-insensitive partial matching.
    
    Logic:
    1. Filter by supplier (None means Store Inventory, provided means specific Supplier).
    2. Try an exact case-insensitive match first.
    3. If no match, try a partial "contains" match.
    """
    query = db.query(models.Product)
    if supplier_name:
        query = query.filter(models.Product.supplier_username == supplier_name)
    else:
        query = query.filter(models.Product.supplier_username == None)
    
    # Try exact match first (e.g., "Water" matches "water")
    product = query.filter(models.Product.product_name.ilike(name)).first()
    if product:
        return product
    
    # Try partial match (e.g., "wat" matches "Water")
    product = query.filter(models.Product.product_name.ilike(f"%{name}%")).first()
    return product

# --- TOOLS ---
# Tools are Python functions that the LLM can decide to execute.
# Each tool enforces Role-Based Access Control (RBAC).

@tool
def list_products(role: str, username: str):
    """
    List products based on the user's role.
    - Admins see both Store Inventory and the global Marketplace Catalog.
    - Suppliers see only their own listed products.
    - Customers see only available store products.
    """
    db = AppSessionLocal()
    try:
        if role == "admin":
            products = crud.get_products(db)
            if not products:
                return "No products found."
            
            store_items = [p for p in products if p.supplier_username is None]
            marketplace_items = [p for p in products if p.supplier_username is not None]
            
            lines = []
            if store_items:
                lines.append("🏠 **Store Inventory:**")
                for p in store_items:
                    lines.append(f"- Name: {p.product_name} | Price: ₹{p.price:.2f} | Stock: {p.stock_quantity}")
            
            if marketplace_items:
                lines.append("\n🌍 **Marketplace Catalog (Suppliers):**")
                for p in marketplace_items:
                    lines.append(f"- Name: {p.product_name} | Price: ₹{p.price:.2f} | Supplier: {p.supplier_username}")
            
            return "\n".join(lines)

        elif role == "supplier":
            products = crud.get_products(db, supplier_name=username)
            if not products:
                return "You have no products listed."
            lines = [f"📦 **Your Products ({username}):**"]
            for p in products:
                lines.append(f"- Name: {p.product_name} | Price: ₹{p.price:.2f} | Stock: {p.stock_quantity}")
            return "\n".join(lines)

        else: # customer or user
            products = crud.get_products(db, only_store=True)
            if not products:
                return "The store is currently empty."
            lines = ["🛒 **Available Products:**"]
            for p in products:
                lines.append(f"- Name: {p.product_name} | Price: ₹{p.price:.2f} | Stock: {p.stock_quantity}")
            return "\n".join(lines)
            
    finally:
        db.close()

@tool
def get_product_details(product_name: str, username: str, role: str):
    """
    Fetches comprehensive information about a product (price, stock, supplier).
    The agent is instructed to use this before performing calculations (like price increases).
    """
    db = AppSessionLocal()
    try:
        if role == "admin":
            product = db.query(models.Product).filter(models.Product.product_name.ilike(f"%{product_name}%")).first()
        elif role == "supplier":
            product = db.query(models.Product).filter(
                models.Product.product_name.ilike(f"%{product_name}%"),
                or_(models.Product.supplier_username == username, models.Product.supplier_username == None)
            ).first()
        else:
            product = find_product_by_name(db, product_name)

        if not product:
            return f"Product '{product_name}' not found or you don't have permission to view it."
        
        details = [
            f"Product: {product.product_name}",
            f"Price: ₹{product.price:.2f}",
            f"Stock: {product.stock_quantity}",
            f"Category: {product.category or 'N/A'}",
            f"Supplier: {product.supplier_username or 'Store Inventory'}"
        ]
        return "\n".join(details)
    finally:
        db.close()

@tool
def buy_product(username: str, role: str, product_name: str, quantity: Optional[int] = None):
    """
    Handles purchases. 
    CONCEPT: Role-Specific Purchasing Logic.
    - Customers: Buy from Store Inventory (decrements stock, creates sale).
    - Admins: Buy from Marketplace (creates a ProcurementRequest with 25% markup and default qty 50).
    """
    db = AppSessionLocal()
    try:
        if role == "admin":
            # Admin purchasing from Marketplace (Procurement flow)
            product = db.query(models.Product).filter(
                models.Product.supplier_username != None,
                models.Product.product_name.ilike(f"%{product_name}%")
            ).first()
            
            if not product:
                return f"Error: Supplier product '{product_name}' not found in Marketplace Catalog."
            
            # Apply Admin-specific business rules
            final_quantity = quantity if quantity and quantity > 0 else 50
            store_price = product.price * 1.25 # 25% markup for store inventory
            
            request = schemas.ProcurementRequest(
                supplier_product_id=product.product_id,
                quantity=final_quantity,
                store_price=store_price
            )
            order = crud.create_procurement_request(db, request, username)
            return (f"Successfully placed a Marketplace order for {final_quantity} units of '{product.product_name}' "
                    f"from supplier '{product.supplier_username}'. Price increased by 25% to ₹{store_price:.2f} for store inventory. "
                    f"(Procurement ID: {order.id})")

        elif role in ["customer", "user"]:
            # Customer purchasing from Retail Store
            if not quantity or quantity <= 0:
                return "Error: Please specify a valid quantity to buy."
                
            product = find_product_by_name(db, product_name)
            if not product:
                return f"Error: Product '{product_name}' not found in the store inventory."
            
            if product.stock_quantity < quantity:
                return f"Error: Insufficient stock. Only {product.stock_quantity} available for '{product.product_name}'."
            
            sale = models.Sale(
                product_id=product.product_id,
                username=username,
                quantity=quantity,
                total_price=quantity * product.price,
                payment_method="AI Agent Purchase"
            )
            product.stock_quantity -= quantity
            db.add(sale)
            db.commit()
            return f"Successfully bought {quantity} units of '{product.product_name}' for ₹{sale.total_price:.2f}."
        
        else:
            return "Error: Only customers and admins can buy products."
            
    except Exception as e:
        return f"Error during purchase: {str(e)}"
    finally:
        db.close()

@tool
def view_order_history(username: str, role: str):
    """Fetches personal sale records from the database for the current user."""
    if role != "customer" and role != "user" and role != "admin":
        return "Error: Only customers and admins can view order history."
    
    db = AppSessionLocal()
    try:
        sales = crud.get_user_sales(db, username)
        if not sales:
            return "You have no order history."
        
        lines = [f"Order History for {username}:"]
        for s in sales:
            date_str = s.created_at.strftime("%Y-%m-%d %H:%M:%S")
            lines.append(f"- {date_str} | Product: {s.product_name} | Qty: {s.quantity} | Total: ₹{s.total_price:.2f}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@tool
def create_store_product(product_name: str, category: str, price: float, stock: int, username: str, role: str):
    """Directly adds a new product to the retail store inventory. (Admin only)."""
    if role != "admin":
        return "Error: Only admins can create store products."
    
    db = AppSessionLocal()
    try:
        product_in = schemas.ProductCreate(
            product_name=product_name,
            category=category,
            price=price,
            stock_quantity=stock
        )
        new_prod = crud.create_product(db, product_in, username, is_supplier=False)
        return f"Product '{new_prod.product_name}' created successfully."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@tool
def create_supplier_product(product_name: str, category: str, price: float, username: str, role: str):
    """Adds a new product to the Marketplace Catalog. (Supplier only)."""
    if role != "supplier":
        return "Error: Only suppliers can create supplier products."
    
    db = AppSessionLocal()
    try:
        product_in = schemas.ProductCreate(
            product_name=product_name,
            category=category,
            price=price,
            stock_quantity=0
        )
        new_prod = crud.create_product(db, product_in, username, is_supplier=True)
        return f"Supplier product '{new_prod.product_name}' created successfully."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@tool
def update_product_stock(product_name: str, new_stock: int, username: str, role: str):
    """Updates the stock level of a product. Admins prioritize Store Inventory; Suppliers only their own."""
    db = AppSessionLocal()
    try:
        if role == "admin":
            # Admin priority: Store Inventory first, then Marketplace
            product = db.query(models.Product).filter(
                models.Product.product_name.ilike(f"%{product_name}%"),
                models.Product.supplier_username == None
            ).first()
            if not product:
                product = db.query(models.Product).filter(
                    models.Product.product_name.ilike(f"%{product_name}%"),
                    models.Product.supplier_username != None
                ).first()
        else:
            product = find_product_by_name(db, product_name, supplier_name=username)
            
        if not product:
            return f"Error: Product '{product_name}' not found or you don't have permission to update it."
        
        old_stock = product.stock_quantity
        product.stock_quantity = new_stock
        db.commit()
        db.refresh(product)
        
        # Log the action for audit trail
        crud.log_action(db, username, "UPDATE_STOCK", f"Updated stock for '{product.product_name}' (ID: {product.product_id}) from {old_stock} to {new_stock}")
        
        return f"Stock for '{product.product_name}' updated to {new_stock}."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@tool
def update_product_price(product_name: str, new_price: float, username: str, role: str):
    """Updates the price of a product. Admins prioritize Store Inventory; Suppliers only their own."""
    db = AppSessionLocal()
    try:
        if role == "admin":
            product = db.query(models.Product).filter(
                models.Product.product_name.ilike(f"%{product_name}%"),
                models.Product.supplier_username == None
            ).first()
            if not product:
                product = db.query(models.Product).filter(
                    models.Product.product_name.ilike(f"%{product_name}%"),
                    models.Product.supplier_username != None
                ).first()
        else:
            product = find_product_by_name(db, product_name, supplier_name=username)
            
        if not product:
            return f"Error: Product '{product_name}' not found or you don't have permission to update its price."
        
        old_price = product.price
        product.price = new_price
        db.commit()
        db.refresh(product)
        
        # Log the action for audit trail
        crud.log_action(db, username, "UPDATE_PRICE", f"Updated price for '{product.product_name}' (ID: {product.product_id}) from ₹{old_price:.2f} to ₹{new_price:.2f}")
        
        return f"Price for '{product.product_name}' updated from ₹{old_price:.2f} to ₹{new_price:.2f}."
    except Exception as e:
        return f"Error updating price: {str(e)}"
    finally:
        db.close()

@tool
def request_procurement(supplier_product_name: str, quantity: int, store_price: float, username: str, role: str):
    """Manually initiates a procurement request for a supplier item. (Admin only)."""
    if role != "admin":
        return "Error: Only admins can request procurement."
    
    db = AppSessionLocal()
    try:
        # Search across all supplier items in the marketplace
        product = db.query(models.Product).filter(
            models.Product.supplier_username != None,
            models.Product.product_name.ilike(f"%{supplier_product_name}%")
        ).first()
        
        if not product:
            return f"Error: Supplier product '{supplier_product_name}' not found."
            
        request = schemas.ProcurementRequest(
            supplier_product_id=product.product_id,
            quantity=quantity,
            store_price=store_price
        )
        order = crud.create_procurement_request(db, request, username)
        return f"Procurement request created for '{product.product_name}' (ID: {order.id})."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@tool
def list_procurements(role: str, username: str):
    """Lists current procurement orders. Suppliers see requests to them; Admins see all."""
    db = AppSessionLocal()
    try:
        if role == "admin":
            orders = crud.get_procurements(db, admin_name=username)
        elif role == "supplier":
            orders = crud.get_procurements(db, supplier_name=username)
        else:
            return "Error: Permission denied."
        
        if not orders:
            return "No procurement orders found."
        
        lines = ["Procurement Orders:"]
        for o in orders:
            lines.append(f"- ID: {o.id} | Product: {o.product_name} | Qty: {o.quantity} | Status: {o.status}")
        return "\n".join(lines)
    finally:
        db.close()

@tool
def accept_procurement_order(order_id: int, payment_method: str, username: str, role: str):
    """Supplier accepts a procurement request, fulfilling the order into store inventory."""
    if role != "supplier":
        return "Error: Only suppliers can accept procurement orders."
    
    db = AppSessionLocal()
    try:
        accept_data = schemas.ProcurementAccept(payment_method=payment_method)
        order = crud.accept_procurement(db, order_id, accept_data, username)
        if not order:
            return "Error: Order not found or permission denied."
        return f"Procurement order {order_id} accepted successfully."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@tool
def delete_product(product_name: str, username: str, role: str):
    """Removes a product from the database. Suppliers can only delete their own; Admins any."""
    db = AppSessionLocal()
    try:
        if role == "admin":
            product = db.query(models.Product).filter(models.Product.product_name.ilike(f"%{product_name}%")).first()
        else:
            product = find_product_by_name(db, product_name, supplier_name=username)

        if not product:
            return f"Error: Product '{product_name}' not found or permission denied."
        
        success = crud.delete_product(db, product.product_id, username)
        if not success:
            return f"Error: Failed to delete '{product.product_name}'."
        return f"Product '{product.product_name}' deleted successfully."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@tool
def view_audit_logs(role: str):
    """Fetches the last 10 administrative actions recorded in the audit trail. (Admin only)."""
    if role != "admin":
        return "Error: Only admins can view audit logs."
    
    db = AppSessionLocal()
    try:
        logs = db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(10).all()
        if not logs:
            return "No audit logs found."
        
        lines = ["Recent Audit Logs:"]
        for log in logs:
            lines.append(f"- {log.created_at.strftime('%Y-%m-%d %H:%M:%S')} | Admin: {log.admin_name} | Action: {log.action} | Details: {log.details}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

@tool
def add_to_cart(product_name: str, quantity: int, username: str, role: str):
    """Adds a retail item to the user's session-based shopping cart. (Username and Role are provided automatically)."""
    if role != "customer" and role != "user":
        return "Error: Only customers can add items to the cart."
    if quantity <= 0:
        return "Error: Quantity must be positive."

    db = AppSessionLocal()
    try:
        product = find_product_by_name(db, product_name)
        if not product:
            return f"Error: Product '{product_name}' not found in the store inventory."
        
        if product.stock_quantity < quantity:
            return f"Error: Insufficient stock. Only {product.stock_quantity} available for '{product.product_name}'."
        
        cart = user_carts.setdefault(username, [])
        
        # Check if product already in cart
        for item in cart:
            if item["product_id"] == product.product_id:
                item["quantity"] += quantity
                return f"Added {quantity} more of '{product.product_name}' to your cart. Total: {item['quantity']}."
        
        cart.append({
            "product_id": product.product_id,
            "product_name": product.product_name,
            "price": product.price,
            "quantity": quantity
        })
        return f"'{product.product_name}' (x{quantity}) added to your cart."
    except Exception as e:
        return f"Error adding to cart: {str(e)}"
    finally:
        db.close()

@tool
def add_multiple_to_cart(product_names: List[str], quantity: int, username: str, role: str):
    """
    Adds multiple retail items to the shopping cart at once. 
    Use this when the user says 'add all these' or 'add those'. 
    Only include product names that were JUST SHOWN to the user in the previous message.
    (Username and Role are provided automatically).
    """
    if role != "customer" and role != "user":
        return "Error: Only customers can add items to the cart."
    
    results = []
    for name in product_names:
        res = add_to_cart.invoke({"product_name": name, "quantity": quantity, "username": username, "role": role})
        results.append(res)
    
    return "\n".join(results)

@tool
def remove_from_cart(product_name: str, username: str, role: str):
    """Removes an item from the user's session-based shopping cart."""
    if role != "customer" and role != "user":
        return "Error: Only customers can remove items from the cart."
    
    cart = user_carts.setdefault(username, [])
    if not cart:
        return "Your cart is already empty."
    
    # Find product in cart using fuzzy matching
    found_item = None
    for item in cart:
        if product_name.lower() in item["product_name"].lower():
            found_item = item
            break
            
    if not found_item:
        return f"Product '{product_name}' not found in your cart."
        
    cart.remove(found_item)
    return f"'{found_item['product_name']}' removed from your cart."

@tool
def update_cart_quantity(product_name: str, quantity: int, username: str, role: str):
    """Changes the quantity of an item already in the user's shopping cart."""
    if role != "customer" and role != "user":
        return "Error: Only customers can update items in the cart."
    if quantity <= 0:
        return "Error: Quantity must be positive. To remove an item, set quantity to 0 or use the remove tool."

    db = AppSessionLocal()
    try:
        product = find_product_by_name(db, product_name)
        if not product:
            return f"Error: Product '{product_name}' not found in the store inventory."
        
        cart = user_carts.setdefault(username, [])
        
        found_item = None
        for item in cart:
            if product.product_id == item["product_id"]:
                found_item = item
                break
        
        if not found_item:
            return f"Product '{product.product_name}' is not in your cart. Use 'add to cart' to add it."
            
        if product.stock_quantity < quantity:
            return f"Error: Insufficient stock. Only {product.stock_quantity} available for '{product.product_name}'."
            
        found_item["quantity"] = quantity
        return f"Quantity of '{product.product_name}' updated to {quantity} in your cart."
    except Exception as e:
        return f"Error updating cart quantity: {str(e)}"
    finally:
        db.close()

@tool
def view_cart(username: str, role: str):
    """Displays the list of items currently in the user's shopping cart and the total price."""
    if role != "customer" and role != "user":
        return "Error: Only customers can view their cart."
    
    cart = user_carts.setdefault(username, [])
    if not cart:
        return "Your cart is empty."
    
    lines = ["🛒 **Your Current Cart:**"]
    total_price = 0.0
    for item in cart:
        subtotal = item["quantity"] * item["price"]
        total_price += subtotal
        lines.append(
            f"  • {item['product_name']} × {item['quantity']} @ ₹{item['price']:.2f} = ₹{subtotal:.2f}"
        )
    lines.append(f"\n**Total: ₹{total_price:.2f}**")
    return "\n".join(lines)

@tool
def find_products_within_budget(max_price: float, username: str, role: str):
    """Searches the retail store inventory for products at or below a certain price point."""
    if role != "customer" and role != "user" and role != "admin":
        return "Error: Only customers and admins can search for products within a budget."
    
    db = AppSessionLocal()
    try:
        products = db.query(models.Product).filter(
            models.Product.supplier_username == None,
            models.Product.price <= max_price
        ).order_by(models.Product.price).all()
        
        if not products:
            return f"No products found within the budget of ₹{max_price:.2f}."
            
        lines = [f"Products available for ₹{max_price:.2f} or less:"]
        for p in products:
            lines.append(f"- {p.product_name} (₹{p.price:.2f}) - Stock: {p.stock_quantity}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error finding products within budget: {str(e)}"
    finally:
        db.close()

@tool
def checkout_cart(username: str, role: str):
    """
    CONCEPT: Bulk Purchase Fulfillment.
    Processes all items in the user's cart as individual sales, 
    decrements stock levels, and records transactions in the database.
    """
    if role != "customer" and role != "user":
        return "Error: Only customers can checkout their cart."
    
    cart = user_carts.setdefault(username, [])
    if not cart:
        return "Your cart is empty. Add some items before checking out."
    
    db = AppSessionLocal()
    try:
        successful_purchases = []
        failed_purchases = []
        total_checkout_price = 0.0

        for item in cart:
            product_id = item["product_id"]
            quantity = item["quantity"]
            
            product = db.query(models.Product).filter(models.Product.product_id == product_id).first()
            
            if not product or product.stock_quantity < quantity:
                failed_purchases.append(f"'{item['product_name']}' (ID: {product_id}) - Insufficient stock or not found.")
                continue
            
            sale = models.Sale(
                product_id=product_id,
                username=username,
                quantity=quantity,
                total_price=quantity * product.price,
                payment_method="AI Agent Checkout"
            )
            product.stock_quantity -= quantity
            db.add(sale)
            successful_purchases.append(f"{quantity} units of '{product.product_name}'")
            total_checkout_price += sale.total_price
        
        db.commit()
        user_carts[username] = [] # Reset cart on success

        response_lines = []
        if successful_purchases:
            response_lines.append(f"Successfully purchased: {', '.join(successful_purchases)}. Total: ₹{total_checkout_price:.2f}.")
        if failed_purchases:
            response_lines.append(f"Failed to purchase: {'; '.join(failed_purchases)}.")
        
        if not response_lines:
            return "No items were processed during checkout."
            
        return "\n".join(response_lines)
    except Exception as e:
        db.rollback()
        return f"Error during checkout: {str(e)}"
    finally:
        db.close()

# --- AGENT LOGIC ---

# The complete list of tools the LLM can use to perform its duties.
TOOLS = [
    list_products, get_product_details, buy_product, view_order_history, create_store_product, 
    create_supplier_product, update_product_stock, update_product_price,
    request_procurement, list_procurements, accept_procurement_order,
    delete_product, view_audit_logs,
    add_to_cart, add_multiple_to_cart, remove_from_cart, update_cart_quantity, view_cart, checkout_cart,
    find_products_within_budget
]

def get_llm():
    """Initializes the ChatOllama model with configured parameters."""
    return ChatOllama(model=LLM_MODEL, temperature=0.2)

def chatbot_node(state: AgentState):
    """
    CONCEPT: The Agent Node.
    This node takes the current state, creates a system message with 
    strict operational instructions, and invokes the LLM with the available tools.
    """
    llm = get_llm().bind_tools(TOOLS)
    
    system_msg = SystemMessage(content=f"""
You are an intelligent AI Agent for the PSM (Product Store Management) system.
Current User Context:
- Username: {state['username']}
- Role: {state['user_role']}

IMPORTANT INSTRUCTIONS:
1. NEVER ask the user for their username, role, or IDs (product_id, supplier_id, etc.). Users do not know IDs.
2. ALWAYS perform actions based on product NAMES. If a user mentions a product (even with a typo), use the name provided.
3. Use the `get_product_details` tool to fetch current price, stock, or supplier info before performing calculations or updates. NEVER ask the user for information that you can find yourself.
4. The system handles typos and partial names automatically. Do not ask for clarification unless absolutely necessary.
5. CONTEXTUAL AWARENESS: When a user says "add all these", "add those", or refers to a group of products, they are ONLY referring to the products you JUST LISTED in your immediately preceding response. DO NOT include every product in the store database. Use the `add_multiple_to_cart` tool for this.
6. Use the 'Username' and 'Role' from the context automatically whenever a tool requires them.
7. If a tool requires an 'order_id' (like for accepting procurement), list the orders first to find it yourself.

Role-based permissions:
- Admin:
    - Full product control: Can list all products, create store products, update stock for any product, delete any product.
    - Marketplace: Can browse the 'Marketplace Catalog' (supplier products) and 'buy' products from it. Buying from the marketplace automatically creates a procurement request. For Marketplace orders, the default quantity is 50, and the store price is automatically increased by 25%.
    - Procurement: Can request procurement from suppliers, list all procurements.
    - Monitoring: Can view audit logs, view order history for any user.
- Supplier:
    - Product Management: Can list their own products, create new supplier products, update stock for their own products, update prices for their own products, and delete their own products. (Note: Once a supplier deletes a product, it is removed from the system and won't be shown to admins).
    - Procurement: Can list procurement requests made to them, accept procurement orders.
- Customer/User:
    - Shopping: Can list available store products, buy products, add/remove/update items in their shopping cart, view their cart, checkout their cart, and find products within a specific budget.
    - Personal History: Can view their own order history.

Be helpful, concise, and professional. Use name-based lookup for EVERYTHING.
""")
    
    messages = [system_msg] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

def should_continue(state: AgentState):
    """
    CONCEPT: Conditional Edge logic.
    Determines if the LLM response contains tool calls. If yes, routes to 'tools' node.
    If no, the process ends.
    """
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

# --- GRAPH ---
# CONCEPT: LangGraph workflow definition.
# 1. Initialize StateGraph with the AgentState schema.
# 2. Add 'agent' node for LLM processing.
# 3. Add 'tools' node for tool execution.
# 4. Define flow: Start -> agent -> (tools -> agent) -> End.

workflow = StateGraph(AgentState)
workflow.add_node("agent", chatbot_node)
workflow.add_node("tools", ToolNode(TOOLS))

workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

# Compile the workflow into an executable agent
agent_executor = workflow.compile()

# --- PUBLIC INTERFACE ---

def query_agent(db: Session, message: str, username: str, role: str) -> str:
    """
    CONCEPT: Entry point for the FastAPI router.
    Initializes the agent state with the user's message and context,
    runs the LangGraph workflow, and returns the final AI response.
    """
    # Initialize state with context and first human message
    state = {
        "messages": [HumanMessage(content=message)],
        "username": username,
        "user_role": role
    }
    
    # Run agent through the workflow
    final_state = agent_executor.invoke(state)
    
    # Extract the last AI message from the resulting state
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    
    return "I'm sorry, I couldn't process that request."
