from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from typing import Optional, List
from services.sync.gmail import build_google_flow, Flow

from services.database import get_db
from models.connection import (
    Connection,
    ConnectionRead, 
    ConnectionUpdate,
    ConnectionInitiateRequest,
    ConnectionInitiateResponse,
    ConnectionStatus,
    ConnectionTest
)
from config.settings import settings
from models.user import UserRead
from models.oauth import OAuth
from utils.auth import validate_session
from models.oauth import OAuthProvider
from utils.hateoas import hateoas_connection, build_connection_links



router = APIRouter(
    prefix="/connections",
    tags=["Connections"],
)

# -----------------------------------------------------------------------------
# POST/PATCH Endpoints
# -----------------------------------------------------------------------------

# POST new Connection (starts OAuth flow to /oauth/callback/ starting with authorization_url
# that the frontend must redirect to)
@router.post("/", response_model=ConnectionInitiateResponse, status_code=201, name="create_connection")
async def create_connection(
    request: Request, 
    connection: ConnectionInitiateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    # temporary for now until we figure out user authentication inside app
    # user_info = validate_session(session_token="")

    # Create connection record in DB
    conn = Connection(
        user_id=current_user.id,
        provider=OAuthProvider.GMAIL,
        status=ConnectionStatus.PENDING
    )
    db.add(conn)
    await db.flush()

    current_redirect_uri = str(request.url_for("google_oauth_callback"))
    if current_redirect_uri not in settings.GOOGLE_REDIRECT_URIS:
        raise ValueError(f"Redirect URI not allowed: {current_redirect_uri}")
    flow: Flow = build_google_flow(current_redirect_uri)
    
    authorization_url, state = flow.authorization_url(
        access_type="offline",
    )

    # Store OAuth temp record
    oauth_state = OAuth(
        state_token=state,
        connection_id=conn.id,
        user_id=current_user.id,
        provider=OAuthProvider.GMAIL,
        expires_at=datetime.now() + timedelta(minutes=5)
    )
    db.add(oauth_state)
    await db.commit()

    # Return to frontend (no HATEOAS since its a specific redirect)
    return ConnectionInitiateResponse(auth_url=authorization_url)



# PATCH Connection update (technically this endpoint may never be used)
@router.patch("/{connection_id}", response_model=ConnectionRead, status_code=200, name="update_connection")
async def update_connection(
    request: Request,
    connection_id: UUID,
    connection_update: ConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Updates the details of a connection"""

    result = await db.execute(
        select(Connection).where(
            Connection.user_id == current_user.id,
            Connection.id == connection_id
        ).limit(1)
    )
    connection = result.scalar_one_or_none()
    
    if connection is None:
        raise HTTPException(status_code=404, detail="No active connection found to update")
    
    # Update only provided fields
    for field, value in connection_update.model_dump(exclude_unset=True).items():
        setattr(connection, field, value)
    
    await db.commit()
    await db.refresh(connection)
    
    # return ConnectionRead.model_validate(connection)
    return hateoas_connection(request, connection)


# -----------------------------------------------------------------------------
# GET Endpoints
# -----------------------------------------------------------------------------

# GET Connections (list) with pagination and filtering
@router.get("/", response_model=List[ConnectionRead], status_code=200, name="list_connections")
async def list_connections(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    status: Optional[ConnectionStatus] = Query(None, description="Filter by status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status")
):
    """Get list of connections with filtering and pagination"""
    query = select(Connection).where(Connection.user_id == current_user.id)
    
    # Apply filters
    if provider:
        query = query.where(Connection.provider == provider)
    if status:
        query = query.where(Connection.status == status)
    if is_active is not None:
        query = query.where(Connection.is_active == is_active)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    connections = result.scalars().all()
    resources: List[ConnectionRead] = []
    for connection in connections:
        resources.append(hateoas_connection(request, connection))

    # return [ConnectionRead.model_validate(conn) for conn in connections]
    return resources



# GET Connection specific
@router.get("/{connection_id}", response_model=ConnectionRead, status_code=200, name="get_connection")
async def get_connection(
    request: Request,
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
        # return ConnectionRead.model_validate(connection)
        return hateoas_connection(request, connection)



# -----------------------------------------------------------------------------
# DELETE Endpoints
# -----------------------------------------------------------------------------

# DELETE Connection Specific
@router.delete("/{connection_id}", status_code=204, name="delete_connection")
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

# Test Connection
@router.post("/{connection_id}/test", response_model=ConnectionTest, status_code=200, name="test_connection")
async def test_connection(
    request: Request,
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Test if the connection is valid and working"""
    # Get the connection
    result = await db.execute(
        select(Connection).where(
            Connection.user_id == current_user.id,
            Connection.id == connection_id
        )
    )
    connection = result.scalar_one_or_none()
    
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Create function to actually check the status via API call
    try:
        conn_test = ConnectionTest(
            id=connection.id,
            user_id=current_user.id,
            provider=connection.provider,
            status=connection.status,
            detail=connection.last_error if connection.last_error else None,
            links=build_connection_links(request, connection)
        )
        return conn_test
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection test failed: {e}")


# Refresh/reconnect (using code 200 instead of 201 since we're not creating a new record)
@router.post("/{connection_id}/refresh", response_model=ConnectionRead, status_code=200, name="refresh_connection")
async def refresh_connection(
    request: Request,
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Refresh authentication tokens for the connection"""
    # Get the connection
    result = await db.execute(
        select(Connection).where(
            Connection.user_id == current_user.id,
            Connection.id == connection_id
        )
    )
    connection = result.scalar_one_or_none()
    
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    if not connection.refresh_token:
        raise HTTPException(status_code=400, detail="No refresh token available")
    
    try:
        # here do actual logic of refreshing the connection via external API


        connection.status = ConnectionStatus.ACTIVE
        connection.last_error = ""
        connection.updated_at = datetime.now()
        # update connection with new access_token, refresh_token, and expiry
        
        await db.commit()
        await db.refresh(connection)
        
        # return ConnectionRead.model_validate(connection)
        return hateoas_connection(request, connection)
        
    except Exception as e:
        connection.status = ConnectionStatus.FAILED
        connection.last_error = f"Token refresh failed: {str(e)}"
        await db.commit()
        await db.refresh(connection)
        
        raise HTTPException(status_code=500, detail=f"Failed to refresh connection: {str(e)}")
