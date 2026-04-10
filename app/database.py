"""
Database configuration for the PSM system.
This module handles connections to two separate PostgreSQL databases:
1. loginV1: For user authentication and role management.
2. rag_demo: For product inventory and sales data.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- Database 1: Authentication (loginV1) --- 
# Stores usernames, hashed passwords, and roles (admin/user).
AUTH_URL = "postgresql://postgres:Nishanth@localhost:5432/loginV1"
auth_engine = create_engine(AUTH_URL)
AuthSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=auth_engine)

# --- Database 2: App Data (rag_demo) ---
# Stores product information and sales transactions.
APP_URL = "postgresql://postgres:Nishanth@localhost:5432/rag_demo"
app_engine = create_engine(APP_URL)
AppSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=app_engine)

# Dependency injection for the Auth database
def get_auth_db():
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency injection for the App database (Products/Sales)
def get_app_db():
    db = AppSessionLocal()
    try:
        yield db
    finally:
        db.close()
