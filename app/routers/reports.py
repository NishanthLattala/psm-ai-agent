from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
import csv
import io
from fpdf import FPDF
from datetime import datetime
from typing import List

from .. import database, models, crud, schemas

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/sales/csv")
def export_sales_csv(db: Session = Depends(database.get_app_db)):
    """
    Generates a CSV report of all sales in the system.
    Returns a downloadable file.
    """
    sales = crud.get_all_sales(db) # This already includes product_name
    
    # Create an in-memory string buffer
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow(["Sale ID", "Username", "Product Name", "Quantity", "Total Price (INR)", "Date"])
    
    for s in sales:
        dt = s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else "N/A"
        writer.writerow([s.sale_id, s.username, s.product_name, s.quantity, f"Rs.{s.total_price:.2f}", dt])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sales_report.csv"}
    )
