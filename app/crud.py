"""
CRUD Operations for PSM - Phase 11.
Includes inventory management, user-linked orders, multi-step procurement, and admin audit logs.
"""
from sqlalchemy.orm import Session
from . import models, schemas
from datetime import datetime

# --- Audit Logging Helper ---
def log_action(db: Session, admin_name: str, action: str, details: str):
    """Helper to record administrative actions in the audit_logs table."""
    db_log = models.AuditLog(
        admin_name=admin_name,
        action=action,
        details=details
    )
    db.add(db_log)
    db.commit()

# --- User CRUD (Auth DB) ---
def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate):
    """Adds a new user record to the authentication database."""
    db_user = models.User(
        username=user.username,
        password=user.password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- Product CRUD (App DB) ---
def get_products(db: Session, only_store: bool = False, supplier_name: str = None):
    query = db.query(models.Product)
    if only_store:
        query = query.filter(models.Product.supplier_username == None)
    if supplier_name:
        query = query.filter(models.Product.supplier_username == supplier_name)
    return query.all()

def create_product(db: Session, product: schemas.ProductCreate, creator_name: str, is_supplier: bool = False):
    db_product = models.Product(
        product_name=product.product_name,
        category=product.category,
        price=product.price,
        stock_quantity=product.stock_quantity if not is_supplier else 0,
        supplier_username=creator_name if is_supplier else None
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    action = "SUPPLIER_ADD" if is_supplier else "ADD_PRODUCT"
    log_action(db, creator_name, action, f"Added {db_product.product_name}")
    return db_product

# --- Procurement CRUD (Phase 11) ---

def create_procurement_request(db: Session, request: schemas.ProcurementRequest, admin_name: str):
    """Admin requests an order from a supplier."""
    db_order = models.ProcurementOrder(
        supplier_product_id=request.supplier_product_id,
        admin_name=admin_name,
        quantity=request.quantity,
        store_price=request.store_price,
        status="requested"
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # Log the request
    prod = db.query(models.Product).filter(models.Product.product_id == request.supplier_product_id).first()
    item_name = prod.product_name if prod else f"ID:{request.supplier_product_id}"
    log_action(db, admin_name, "PROCUREMENT_REQUEST", f"Requested {request.quantity} units of '{item_name}'")
    return db_order

def get_procurements(db: Session, supplier_name: str = None, admin_name: str = None, status: str = None):
    """View procurement orders based on role."""
    query = db.query(models.ProcurementOrder, models.Product.product_name)\
        .join(models.Product, models.ProcurementOrder.supplier_product_id == models.Product.product_id)
    
    if supplier_name:
        query = query.filter(models.Product.supplier_username == supplier_name)
    if admin_name:
        query = query.filter(models.ProcurementOrder.admin_name == admin_name)
    if status:
        query = query.filter(models.ProcurementOrder.status == status)
    
    results = query.order_by(models.ProcurementOrder.created_at.desc()).all()
    
    procurements = []
    for order, name in results:
        order.product_name = name
        procurements.append(order)
    return procurements

def accept_procurement(db: Session, order_id: int, accept_data: schemas.ProcurementAccept, supplier_name: str):
    """Supplier accepts the order, resulting in actual inventory update and sale record."""
    # 1. Verify order exists and belongs to this supplier
    order = db.query(models.ProcurementOrder).filter(models.ProcurementOrder.id == order_id).first()
    if not order or order.status != "requested":
        return None
    
    sup_prod = db.query(models.Product).filter(models.Product.product_id == order.supplier_product_id).first()
    if not sup_prod or sup_prod.supplier_username != supplier_name:
        return None
    
    # 2. Finalize Procurement Order
    order.status = "accepted"
    order.payment_method = accept_data.payment_method
    
    # 3. Update Store Inventory
    store_prod = db.query(models.Product).filter(
        models.Product.product_name == sup_prod.product_name,
        models.Product.supplier_username == None
    ).first()
    
    if store_prod:
        store_prod.stock_quantity += order.quantity
        store_prod.price = order.store_price
    else:
        store_prod = models.Product(
            product_name=sup_prod.product_name,
            category=sup_prod.category,
            price=order.store_price,
            stock_quantity=order.quantity,
            supplier_username=None
        )
        db.add(store_prod)
    
    # 4. Create Sale Record (Suppliers order view)
    procure_sale = models.Sale(
        product_id=order.supplier_product_id,
        username=order.admin_name,
        quantity=order.quantity,
        total_price=order.quantity * sup_prod.price,
        payment_method=accept_data.payment_method # Link payment to the sale
    )
    db.add(procure_sale)
    
    db.commit()
    db.refresh(order)
    
    # 5. Audit Log (Admin view)
    log_action(db, order.admin_name, "PROCUREMENT_ACCEPTED", 
               f"Supplier '{supplier_name}' accepted order. Method: {accept_data.payment_method}. "
               f"Inventory updated for '{sup_prod.product_name}'. Total Cost: ₹{procure_sale.total_price}")
    
    return order

def reject_procurement(db: Session, order_id: int, supplier_name: str):
    """Supplier rejects the procurement request."""
    order = db.query(models.ProcurementOrder).filter(models.ProcurementOrder.id == order_id).first()
    if not order or order.status != "requested":
        return None
    
    sup_prod = db.query(models.Product).filter(models.Product.product_id == order.supplier_product_id).first()
    if not sup_prod or sup_prod.supplier_username != supplier_name:
        return None
    
    order.status = "rejected"
    db.commit()
    db.refresh(order)
    return order

# --- Standard Product Management ---

def update_product(db: Session, product_id: int, product_update: schemas.ProductUpdate, requester_name: str):
    db_product = db.query(models.Product).filter(models.Product.product_id == product_id).first()
    if not db_product:
        return None
    
    # Check permissions (Owner or Admin)
    from app.database import AuthSessionLocal
    db_auth = AuthSessionLocal()
    requester = db_auth.query(models.User).filter(models.User.username == requester_name).first()
    db_auth.close()
    
    is_admin = requester and requester.role == "admin"
    is_owner = db_product.supplier_username == requester_name
    
    if not is_admin and not is_owner:
        return None

    changes = []
    for var, value in vars(product_update).items():
        if value is not None:
            old_val = getattr(db_product, var)
            setattr(db_product, var, value)
            changes.append(f"{var}: {old_val} -> {value}")
    
    db.commit()
    db.refresh(db_product)
    log_action(db, requester_name, "UPDATE_PRODUCT", f"Updated product {product_id}: {'; '.join(changes)}")
    return db_product

def delete_product(db: Session, product_id: int, requester_name: str):
    db_product = db.query(models.Product).filter(models.Product.product_id == product_id).first()
    if not db_product:
        return False
    
    # Check if the requester is an admin
    from app.database import AuthSessionLocal
    db_auth = AuthSessionLocal()
    requester = db_auth.query(models.User).filter(models.User.username == requester_name).first()
    db_auth.close()
    
    is_admin = requester and requester.role == "admin"
    is_owner = db_product.supplier_username == requester_name
    
    if not is_admin and not is_owner:
        return False

    item_name = db_product.product_name
    db.delete(db_product)
    db.commit()
    log_action(db, requester_name, "DELETE_PRODUCT", f"Deleted product: {item_name} (ID: {product_id})")
    return True

# --- Sale / Order CRUD (App DB) ---
def get_all_sales(db: Session):
    # Join with Product to get the product_name and filter for retail only
    results = db.query(models.Sale, models.Product.product_name)\
        .join(models.Product, models.Sale.product_id == models.Product.product_id)\
        .filter(models.Product.supplier_username == None)\
        .order_by(models.Sale.created_at.desc()).all()
    
    # Flatten results to match the schema
    sales = []
    for sale, name in results:
        sale.product_name = name if name else "Deleted Product"
        sales.append(sale)
    return sales

def get_user_sales(db: Session, username: str):
    # Join with Product to get the product_name
    results = db.query(models.Sale, models.Product.product_name)\
        .outerjoin(models.Product, models.Sale.product_id == models.Product.product_id)\
        .filter(models.Sale.username == username)\
        .order_by(models.Sale.created_at.desc()).all()
    
    sales = []
    for sale, name in results:
        sale.product_name = name if name else "Deleted Product"
        sales.append(sale)
    return sales

def get_supplier_sales(db: Session, supplier_username: str):
    # Join Sale with Product to find sales where the product is owned by the supplier
    results = db.query(models.Sale, models.Product.product_name)\
        .join(models.Product, models.Sale.product_id == models.Product.product_id)\
        .filter(models.Product.supplier_username == supplier_username)\
        .order_by(models.Sale.created_at.desc()).all()
    
    sales = []
    for sale, name in results:
        sale.product_name = name if name else "Deleted Product"
        sales.append(sale)
    return sales

def create_sale(db: Session, sale: schemas.SaleCreate):
    """
    Records a new sale and decrements stock.
    """
    product = db.query(models.Product).filter(models.Product.product_id == sale.product_id).first()
    if not product:
        return None
    
    # Check and decrement stock
    if product.stock_quantity < sale.quantity:
        return "OUT_OF_STOCK"
    
    product.stock_quantity -= sale.quantity
    total = product.price * sale.quantity
    
    db_sale = models.Sale(
        product_id=sale.product_id,
        username=sale.username,
        quantity=sale.quantity,
        total_price=total,
        payment_method="Cash" # Default for store sales
    )
    db.add(db_sale)
    db.commit()
    db.refresh(db_sale)
    
    # Attach product name for the response schema
    db_sale.product_name = product.product_name
    return db_sale

# --- Audit Log CRUD ---
def get_audit_logs(db: Session):
    return db.query(models.AuditLog).order_by(models.AuditLog.created_at.desc()).all()
