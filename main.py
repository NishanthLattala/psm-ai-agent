"""
Main Application Entry Point for the PSM System.
This file initializes the FastAPI app, configures CORS, and registers all API routers.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import models
from app.routers import auth, products, sales, reports, analytics, chatbot

# --- Startup: Database Table Creation ---
# This ensures that both loginV1 (auth) and rag_demo (app) tables are ready before the server starts.
models.create_tables()

app = FastAPI(title="PSM Auth & Store System")

# --- Middleware: Cross-Origin Resource Sharing (CORS) ---
# Allows the frontend HTML pages (potentially running on a different port) to access the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Router Registration ---
# We split the API into logical modules (Authentication, Products, and Sales).
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(sales.router)
app.include_router(reports.router)
app.include_router(analytics.router)
app.include_router(chatbot.router)

from fastapi.staticfiles import StaticFiles
import os

# Serve the HTML files from the psm directory at /psm path
# This assumes the HTML files are in the same directory as main.py (c:\Users\latta\Desktop\AIML\LLM\psm)
current_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/psm", StaticFiles(directory=current_dir, html=True), name="psm")

@app.get("/")
def root():
    """Health check endpoint."""
    return {"message": "Welcome to PSM API"}
