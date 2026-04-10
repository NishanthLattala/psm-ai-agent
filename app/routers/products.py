from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import crud, schemas, database

router = APIRouter(prefix="/products", tags=["products"])

@router.get("/", response_model=List[schemas.ProductResponse])
def read_products(
    only_store: bool = False,
    supplier_name: Optional[str] = None,
    db: Session = Depends(database.get_app_db)
):
    return crud.get_products(db, only_store=only_store, supplier_name=supplier_name)

@router.post("/", response_model=schemas.ProductResponse)
def create_product(
    product: schemas.ProductCreate, 
    db: Session = Depends(database.get_app_db),
    creator_name: str = Header(..., alias="admin-name"),
    creator_role: str = Header("user", alias="user-role")
):
    is_sup = (creator_role == "supplier")
    res = crud.create_product(db=db, product=product, creator_name=creator_name, is_supplier=is_sup)
    
    return res

@router.post("/procurement/request", response_model=schemas.ProcurementResponse)
def request_procurement(
    payload: schemas.ProcurementRequest,
    db: Session = Depends(database.get_app_db),
    admin_name: str = Header(..., alias="admin-name")
):
    """Admin requests a product from a supplier."""
    return crud.create_procurement_request(db, payload, admin_name)

@router.get("/procurement/pending", response_model=List[schemas.ProcurementResponse])
def read_pending_procurements(
    db: Session = Depends(database.get_app_db),
    supplier_name: Optional[str] = Header(None, alias="admin-name"), # Reusing header for simplicity
    user_role: str = Header("user", alias="user-role")
):
    """Suppliers see their pending requests, Admins see their sent requests."""
    if user_role == "supplier":
        return crud.get_procurements(db, supplier_name=supplier_name, status="requested")
    elif user_role == "admin":
        return crud.get_procurements(db, admin_name=supplier_name, status="requested")
    return []

@router.post("/procurement/accept/{order_id}", response_model=schemas.ProcurementResponse)
def accept_procurement_order(
    order_id: int,
    payload: schemas.ProcurementAccept,
    db: Session = Depends(database.get_app_db),
    supplier_name: str = Header(..., alias="admin-name")
):
    """Supplier accepts the request and selects payment method."""
    order = crud.accept_procurement(db, order_id, payload, supplier_name)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or unauthorized")
    
    return order

@router.post("/procurement/reject/{order_id}", response_model=schemas.ProcurementResponse)
def reject_procurement_order(
    order_id: int,
    db: Session = Depends(database.get_app_db),
    supplier_name: str = Header(..., alias="admin-name")
):
    """Supplier rejects the request."""
    order = crud.reject_procurement(db, order_id, supplier_name)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or unauthorized")
    return order

@router.patch("/{product_id}", response_model=schemas.ProductResponse)
def update_product(
    product_id: int, 
    product_update: schemas.ProductUpdate, 
    db: Session = Depends(database.get_app_db),
    admin_name: str = Header(..., alias="admin-name")
):
    db_product = crud.update_product(db, product_id, product_update, admin_name)
    if not db_product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return db_product

@router.delete("/{product_id}")
def delete_product(
    product_id: int, 
    db: Session = Depends(database.get_app_db),
    admin_name: str = Header(..., alias="admin-name")
):
    success = crud.delete_product(db, product_id, admin_name)
    if not success:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return {"message": "Product deleted"}