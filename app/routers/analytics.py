from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import datetime, timedelta
from typing import Optional, List

from .. import database, models

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/summary")
def get_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    username: Optional[str] = None,
    db: Session = Depends(database.get_app_db)
):
    """
    Returns high-level KPIs: Total Revenue, Total Orders, Average Order Value.
    """
    query = db.query(
        func.sum(models.Sale.total_price).label("revenue"),
        func.count(models.Sale.sale_id).label("orders"),
        func.sum(models.Sale.quantity).label("items")
    ).join(models.Product, models.Sale.product_id == models.Product.product_id)\
     .filter(models.Product.supplier_username == None) # Only retail sales
    
    # Apply Filters
    if start_date:
        query = query.filter(models.Sale.created_at >= start_date)
    if end_date:
        query = query.filter(models.Sale.created_at <= end_date)
    if username:
        query = query.filter(models.Sale.username == username)
        
    res = query.first()
    
    revenue = res.revenue if res.revenue else 0
    orders = res.orders if res.orders else 0
    items = res.items if res.items else 0
    avg_value = revenue / orders if orders > 0 else 0
    
    return {
        "total_revenue": round(revenue, 2),
        "total_orders": orders,
        "total_items": items,
        "avg_order_value": round(avg_value, 2)
    }

@router.get("/trends")
def get_trends(
    days: int = 7,
    db: Session = Depends(database.get_app_db)
):
    """
    Returns daily revenue and order counts for the last X days.
    Perfect for Line Charts.
    """
    # Group by date part of timestamp
    trends = db.query(
        cast(models.Sale.created_at, Date).label("day"),
        func.sum(models.Sale.total_price).label("revenue"),
        func.count(models.Sale.sale_id).label("orders")
    ).join(models.Product, models.Sale.product_id == models.Product.product_id)\
     .filter(models.Product.supplier_username == None)\
     .group_by(cast(models.Sale.created_at, Date))\
     .order_by("day").all()
     
    return [{"date": str(t.day), "revenue": round(t.revenue, 2), "orders": t.orders} for t in trends]

@router.get("/products")
def get_product_performance(db: Session = Depends(database.get_app_db)):
    """
    Returns sales volume and revenue per product.
    Used for Bar Charts.
    """
    perf = db.query(
        models.Product.product_name,
        func.sum(models.Sale.quantity).label("total_qty"),
        func.sum(models.Sale.total_price).label("total_rev")
    ).join(models.Sale, models.Product.product_id == models.Sale.product_id)\
     .filter(models.Product.supplier_username == None)\
     .group_by(models.Product.product_name)\
     .order_by(func.sum(models.Sale.quantity).desc()).all()
     
    return [{"name": p.product_name, "quantity": p.total_qty, "revenue": round(p.total_rev, 2)} for p in perf]

@router.get("/categories")
def get_category_distribution(db: Session = Depends(database.get_app_db)):
    """
    Returns revenue breakdown by category.
    Used for Pie Charts.
    """
    dist = db.query(
        models.Product.category,
        func.sum(models.Sale.total_price).label("revenue")
    ).join(models.Sale, models.Product.product_id == models.Sale.product_id)\
     .filter(models.Product.supplier_username == None)\
     .group_by(models.Product.category).all()
     
    return [{"category": d.category, "revenue": round(d.revenue, 2)} for d in dist]
