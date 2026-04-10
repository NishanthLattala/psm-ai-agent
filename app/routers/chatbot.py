from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import database, schemas
from ..services import agent_service

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

@router.post("/query", response_model=schemas.ChatResponse)
def query_chat(query_data: schemas.ChatQuery, db: Session = Depends(database.get_app_db)):
    """
    Endpoint for querying the AI Agent.
    """
    try:
        response = agent_service.query_agent(
            db,
            query_data.message, 
            query_data.username,
            query_data.role
        )
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

@router.post("/sync")
def sync_chatbot(user_role: str, db: Session = Depends(database.get_app_db)):
    """
    Sync endpoint (No-op in agent version, or can be implemented if needed).
    """
    return {"message": "Agent memory sync is handled automatically."}

@router.get("/cart/{username}")
def get_chatbot_cart(username: str):
    """
    Retrieve the current shopping cart (Not used in the agentic version yet).
    """
    return {"cart": []}
