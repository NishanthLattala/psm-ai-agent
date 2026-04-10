"""
Pydantic schemas for the PSM system.
Phase 3: Added stock to Product, user logic to Sale, and new AuditLog schemas.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# --- Auth Schemas ---
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "user"

class UserLogin(BaseModel): # Login only needs username/password
    username: str
    password: str

class UserResponse(UserBase):
    id: int
    role: str
    class Config:
        from_attributes = True

# --- Product Schemas ---
class ProductBase(BaseModel):
    product_name: str
    category: Optional[str] = "Other"
    price: float
    stock_quantity: Optional[int] = 0
    supplier_username: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    stock_quantity: Optional[int] = None

class ProductResponse(ProductBase):
    product_id: int
    class Config:
        from_attributes = True

class ProductProcure(BaseModel):
    supplier_product_id: int
    quantity: int
    store_price: float

# --- Sale / Order Schemas ---
class SaleBase(BaseModel):
    product_id: int
    quantity: int

class SaleCreate(SaleBase):
    username: str # Required to link the sale to a user

class SaleResponse(SaleBase):
    sale_id: int
    product_name: Optional[str] = "Unknown Product"
    username: Optional[str] = "Unknown"
    total_price: Optional[float] = 0.0
    payment_method: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

# --- Procurement Schemas (Phase 11) ---
class ProcurementRequest(BaseModel):
    supplier_product_id: int
    quantity: int
    store_price: float

class ProcurementAccept(BaseModel):
    payment_method: str

class ProcurementResponse(BaseModel):
    id: int
    supplier_product_id: int
    admin_name: str
    quantity: int
    store_price: float
    status: str
    payment_method: Optional[str] = None
    product_name: Optional[str] = "Unknown Product"
    created_at: datetime
    class Config:
        from_attributes = True

# --- Audit Log Schemas ---
class AuditLogResponse(BaseModel):
    log_id: int
    admin_name: str
    action: str
    details: str
    created_at: datetime
    class Config:
        from_attributes = True

# --- Chatbot Schemas ---
class ChatQuery(BaseModel):
    message: str
    username: str
    role: str

class ChatResponse(BaseModel):
    response: str
