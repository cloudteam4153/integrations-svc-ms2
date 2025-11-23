from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import Flow
from fastapi.responses import RedirectResponse

from services.database import get_db
from models.sync import (
    SyncCreate,
    SyncRead
)
from config.settings import settings
from models.connection import ConnectionStatus
from models.user import UserRead
from models.oauth import OAuthStateCreate
from utils.auth import validate_session



router = APIRouter(
    prefix="/syncs",
    tags=["Syncs"],
)

# -----------------------------------------------------------------------------
# Sync Endpoints
# -----------------------------------------------------------------------------

# GET sync job (list)
@router.get("/", response_model=list[SyncRead], status_code=200)
async def list_syncs():
    """Lists all sync jobs. can filter later by active/complete"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# GET sync job (specific)
@router.get("/{sync_id}", response_model=SyncRead, status_code=200)
async def get_sync(sync_id: UUID):
    """Gets details/log of a specific sync job"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# POST new manual sync job
@router.post("/", response_model=SyncRead, status_code=201)
async def create_sync(sync: SyncCreate):
    """Creates a new sync job"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# DELETE sync job
@router.delete("/{sync_id}", status_code=204)
async def delete_sync(sync_id: UUID):
    """Deletes a specific sync job"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")