"""
SQLAlchemy Models for the PSM system.
Phase 3: Added stock_quantity to Product, user_id to Sale, and a new AuditLog model.
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from .database import auth_engine, app_engine

Base = declarative_base()

# --- Auth Model (Stored in loginV1 DB) ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="user") # 'user' or 'admin'

# --- App Models (Stored in rag_demo DB) ---
class Product(Base):
    """Represents an item in the store inventory."""
    __tablename__ = "products"
    product_id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, nullable=False)
    category = Column(String)
    price = Column(Float, nullable=False)
    stock_quantity = Column(Integer, default=0)
    supplier_username = Column(String, nullable=True) # New field for Phase 8

class Sale(Base):
    """Represents a transaction record. Linked to specific products and users."""
    __tablename__ = "sales"
    sale_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.product_id"))
    username = Column(String) # For simplicity, store the username directly in the sale record
    quantity = Column(Integer, nullable=False)
    total_price = Column(Float)
    payment_method = Column(String, nullable=True) # New field for Phase 11
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ProcurementOrder(Base):
    """Tracks pending procurement requests between Admin and Supplier."""
    __tablename__ = "procurement_orders"
    id = Column(Integer, primary_key=True, index=True)
    supplier_product_id = Column(Integer, ForeignKey("products.product_id"))
    admin_name = Column(String)
    quantity = Column(Integer, nullable=False)
    store_price = Column(Float, nullable=False)
    status = Column(String, default="requested") # 'requested', 'accepted', 'rejected'
    payment_method = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditLog(Base):
    """Tracks administrative actions (adds, deletes, updates)."""
    __tablename__ = "audit_logs"
    log_id = Column(Integer, primary_key=True, index=True)
    admin_name = Column(String)
    action = Column(String) # e.g., "DELETE_PRODUCT"
    details = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

def create_tables():
    """Initializes/Updates the database tables."""
    # Auth DB
    User.__table__.create(bind=auth_engine, checkfirst=True)
    
    # App DB
    Product.__table__.create(bind=app_engine, checkfirst=True)
    Sale.__table__.create(bind=app_engine, checkfirst=True)
    ProcurementOrder.__table__.create(bind=app_engine, checkfirst=True)
    AuditLog.__table__.create(bind=app_engine, checkfirst=True)

    # Note: If columns were added (like stock_quantity), SQLAlchemy create_all won't add them to existing tables.
    # We may need to run manual ALTER TABLE commands if the user already has data.
