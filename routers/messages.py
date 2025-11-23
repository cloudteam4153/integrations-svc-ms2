from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from fastapi.responses import RedirectResponse

from services.database import get_db
from models.connection import (
    Connection,
    ConnectionInitiateRequest,
    ConnectionRead, 
    ConnectionUpdate
)
from config.settings import settings
from models.connection import ConnectionStatus
from models.user import UserRead
from models.oauth import OAuthStateCreate
from utils.auth import validate_session



router = APIRouter(
    prefix="/messages",
    tags=["Messages"],
)

# -----------------------------------------------------------------------------
# Message Endpoints
# -----------------------------------------------------------------------------

# GET Messages (list)
@app.get("/messages", response_model=List[MessageRead], status_code=200)
async def list_messages(limit: int = 50):
    """Returns list of all messages with an optional limit"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# GET Messages (specific)
@app.get("/messages/{message_id}", response_model=MessageRead, status_code=200)
async def get_message(message_id: UUID):
    """Gets a specific message"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# POST new Message
@app.post("/messages", response_model=MessageRead, status_code=201)
async def create_message(message: MessageCreate):
    """Create/send a message"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# PATCH existing Message (if supported)
@app.patch("/messages/{message_id}", response_model=MessageRead, status_code=200)
async def update_message(message_id: UUID, message: MessageUpdate):
    """Update an existing message (if supported)"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# DELETE Message
@app.delete("/messages/{message_id}", status_code=204)
async def delete_message(message_id: UUID):
    """Deletes a specific message from our service and propogates via API for external service"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")