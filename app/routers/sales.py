from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from .. import crud, schemas, database

router = APIRouter(prefix="/sales", tags=["sales"])

@router.get("/", response_model=List[schemas.SaleResponse])
def read_sales(
    username: Optional[str] = None, 
    supplier_name: Optional[str] = None,
    db: Session = Depends(database.get_app_db),
    requester_role: Optional[str] = Header("user", alias="user-role"),
    requester_name: Optional[str] = Header(None, alias="admin-name")
):
    if requester_role == "admin":
        if username: return crud.get_user_sales(db, username)
        if supplier_name: return crud.get_supplier_sales(db, supplier_name)
        return crud.get_all_sales(db)
    
    if requester_role == "supplier":
        return crud.get_supplier_sales(db, requester_name)
        
    if requester_role == "user":
        return crud.get_user_sales(db, requester_name)
    
    return []

@router.post("/", response_model=schemas.SaleResponse)
def create_sale(
    sale: schemas.SaleCreate, 
    db: Session = Depends(database.get_app_db)
):
    res = crud.create_sale(db=db, sale=sale)
    if res == "OUT_OF_STOCK":
        raise HTTPException(status_code=400, detail="Insufficient stock")
    if not res:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return res

@router.get("/audit", response_model=List[schemas.AuditLogResponse])
def read_audit_logs(
    db: Session = Depends(database.get_app_db),
    requester_role: str = Header("user", alias="user-role")
):
    if requester_role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access only.")
    return crud.get_audit_logs(db)