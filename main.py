from __future__ import annotations

import os
import socket
from datetime import datetime

from typing import Dict, List
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi import Query, Path
from typing import Optional

from models.health import Health
from routers import connections, oauth
from models.message import MessageCreate, MessageRead, MessageUpdate
from models.sync import SyncCreate, SyncRead
from models.user import User, UserCreate, UserRead, UserUpdate
from services.database import get_db, init_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import Depends
from contextlib import asynccontextmanager

port = int(os.environ.get("FASTAPIPORT", 8000))


app = FastAPI(
    title="Integrations Microservice",
    description="FastAPI microservice handling external resource integration, ingest, and management.",
    version="0.1.0",
)

# -----------------------------------------------------------------------------
# Health endpoints
# -----------------------------------------------------------------------------

def make_health(echo: Optional[str], path_echo: Optional[str]=None) -> Health:
    return Health(
        status=200,
        status_message="OK",
        timestamp=datetime.utcnow().isoformat() + "Z",
        ip_address=socket.gethostbyname(socket.gethostname()),
        echo=echo,
        path_echo=path_echo
    )

@app.get("/health", response_model=Health)
def get_health_no_path(echo: str | None = Query(None, description="Optional echo string")):
    # Works because path_echo is optional in the model
    return make_health(echo=echo, path_echo=None)

@app.get("/health/{path_echo}", response_model=Health)
def get_health_with_path(
    path_echo: str = Path(..., description="Required echo in the URL path"),
    echo: str | None = Query(None, description="Optional echo string"),
):
    return make_health(echo=echo, path_echo=path_echo)

# -----------------------------------------------------------------------------
# Connections endpoints
# -----------------------------------------------------------------------------

app.include_router(router=connections.router)
app.include_router(router=oauth.router)

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

# -----------------------------------------------------------------------------
# Sync Endpoints
# -----------------------------------------------------------------------------

# GET sync job (list)
@app.get("/syncs", response_model=List[SyncRead], status_code=200)
async def list_syncs():
    """Lists all sync jobs. can filter later by active/complete"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# GET sync job (specific)
@app.get("/syncs/{sync_id}", response_model=SyncRead, status_code=200)
async def get_sync(sync_id: UUID):
    """Gets details/log of a specific sync job"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# POST new manual sync job
@app.post("/syncs", response_model=SyncRead, status_code=201)
async def create_sync(sync: SyncCreate):
    """Creates a new sync job"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# DELETE sync job
@app.delete("/syncs/{sync_id}", status_code=204)
async def delete_sync(sync_id: UUID):
    """Deletes a specific sync job"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# -----------------------------------------------------------------------------
# User Endpoints (Test)
# -----------------------------------------------------------------------------

@app.post("/users", response_model=UserRead, status_code=201)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    db_user = User(last_name=user.last_name, 
                   first_name=user.first_name,
                   email=user.email)
    db.add(db_user)
    try:
        await db.commit()
        await db.refresh(db_user)
        return db_user
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/users", response_model=List[UserRead])
async def list_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()

@app.get("/users/{user_id}", response_model=UserRead)
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/users/{user_id}", response_model=UserRead)
async def update_user(user_id: UUID, user_update: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_update.last_name is not None:
        user.last_name = user_update.last_name
    if user_update.first_name is not None:
        user.first_name = user_update.first_name
    if user_update.email is not None:
        user.email = user_update.email
    
    await db.commit()
    await db.refresh(user)
    return user

@app.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(user)
    await db.commit()

# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the Integrations API. See /docs for OpenAPI UI."}

# -----------------------------------------------------------------------------
# Entrypoint for `python main.py`
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
