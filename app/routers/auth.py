"""
Authentication Router.
Handles user registration and login endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import crud, schemas, database

router = APIRouter(prefix="/auth", tags=["auth"])
 
@router.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_auth_db)):
    """
    Registers a new user. 
    Checks if the username is taken before creating a new record in the Auth DB.
    """
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@router.post("/login", response_model=schemas.UserResponse)
def login_user(user: schemas.UserLogin, db: Session = Depends(database.get_auth_db)):
    """
    Authenticates a user.
    Verifies credentials against the Auth DB and returns user info (including role).
    """
    db_user = crud.get_user_by_username(db, username=user.username)
    if not db_user or db_user.password != user.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return db_user
