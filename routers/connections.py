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
from models.oauth import OAuth
from utils.auth import validate_session
from models.oauth import OAuthProvider



router = APIRouter(
    prefix="/connections",
    tags=["Connections"],
)

# -----------------------------------------------------------------------------
# POST/PUT Endpoints
# -----------------------------------------------------------------------------

# POST new Connection
@router.post("/", status_code=201)
async def create_connection(
    # session_token: UUID,
    
    db: AsyncSession = Depends(get_db),
    
):
    # current_user: UserRead = Depends(validate_session)
    user_info = validate_session(session_token="")

    # Create connection record in DB
    conn = Connection(
        user_id=user_info.id,
        provider=OAuthProvider.GMAIL,
        status=ConnectionStatus.PENDING
    )
    db.add(conn)
    await db.flush()

    # Build Auth URL
    flow = Flow.from_client_secrets_file(
        settings.GOOGLE_CLIENT_SECRETS_FILE,
        scopes=settings.GMAIL_OAUTH_SCOPES
    )
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    
    authorization_url, state = flow.authorization_url(
        access_type="offline",
    )

    # Store OAuth temp record
    oauth_state = OAuth(
        state_token=state,
        connection_id=conn.id,
        user_id=user_info.id,
        provider=OAuthProvider.GMAIL,
        expires_at=datetime.now() + timedelta(minutes=5)
    )
    db.add(oauth_state)
    await db.commit()

    # Return to frontend
    return {"authorization_url": authorization_url, "connection_id": str(conn.id)}



# PUT/PATCH Connection update TODO
@router.patch("/{connection_id}", response_model=ConnectionRead, status_code=200)
async def update_connection(connection_id: UUID, connection: ConnectionUpdate):
    """Updates the details of a connection"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")


# -----------------------------------------------------------------------------
# GET Endpoints
# -----------------------------------------------------------------------------

# GET Connections (list)
@router.get("/", response_model=list[ConnectionRead], status_code=200)
async def list_connections(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(validate_session),
):
    """Get list of connections, can be filtered"""
    result = await db.execute(
        select(Connection).where(Connection.user_id == current_user.id)
    )
    connections = result.scalars().all()

    return [ConnectionRead.model_validate(conn) for conn in connections]



# GET Connection specific
@router.get("/{connection_id}", response_model=ConnectionRead, status_code=200)
async def get_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(validate_session),
):
    """Get information about a specific connection"""
    result = await db.execute(
        select(Connection).where(
            Connection.user_id == current_user.id, 
            Connection.id == connection_id
        )
    )
    connection = result.scalar_one_or_none()

    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    else:
        return ConnectionRead.model_validate(connection)



# -----------------------------------------------------------------------------
# DELETE Endpoints
# -----------------------------------------------------------------------------

# DELETE Connection Specific
@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(validate_session),
):
    result = await db.execute(
        select(Connection).where(
            Connection.user_id == current_user.id,
            Connection.id == connection_id
        )
    )
    
    connection = result.scalar_one_or_none()
    
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    await db.delete(connection)
    await db.commit()
    
    return None 
    

# -----------------------------------------------------------------------------
# Test/Refresh/Reconnect Endpoints
# -----------------------------------------------------------------------------

# Test Connection TODO
@router.post("/{connection_id}/test", status_code=200)
async def test_connection(connection_id: UUID):
    """Test if the connection is valid and working"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# Refresh/reconnect TODO
@router.post("/{connection_id}/refresh", response_model=ConnectionRead, status_code=200)
async def refresh_connection(connection_id: UUID):
    """Refresh authentication tokens for the connection"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")














