from fastapi import APIRouter, HTTPException, Depends, Query, Request, status
from uuid import UUID
from math import ceil
from datetime import datetime
from typing import Optional, List


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from services.database import get_db
from utils.hateoas import hateoas_connection, build_connection_links
from services.sync.gmail import validate_gmail_connection, refresh_gmail_tokens

from models.connection import (
    Connection,
    ConnectionRead, 
    ConnectionUpdate,
    ConnectionCreate,
    ConnectionStatus,
    ConnectionTest,
    ConnectionPaginated
)
from models.oauth import OAuthProvider




router = APIRouter(
    prefix="/connections",
    tags=["Connections"],
)


# -----------------------------------------------------------------------------
# POST/PATCH Endpoints
# -----------------------------------------------------------------------------

# POST new Connection 
@router.post("/", response_model=ConnectionRead, status_code=201, name="create_connection")
async def create_connection(
    request: Request, 
    conn_req: ConnectionCreate,
    db: AsyncSession = Depends(get_db)
):
    # Normalize / validate provider
    try:
        provider_enum = OAuthProvider(conn_req.provider)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported provider: {conn_req.provider}",
        )

    # Look for existing connection for this user + provider + provider_account_id
    stmt = select(Connection).where(
        Connection.user_id == conn_req.user_id,
        Connection.provider == provider_enum,
        Connection.provider_account_id == conn_req.provider_account_id,
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()

    if connection:
        # Update existing connection (rotate tokens, scopes, status, etc.)
        connection.scopes = conn_req.scopes or connection.scopes
        connection.access_token = conn_req.access_token or connection.access_token
        connection.refresh_token = conn_req.refresh_token or connection.refresh_token
        connection.access_token_expiry = (
            conn_req.access_token_expiry or connection.access_token_expiry
        )

        if conn_req.status is not None:
            connection.status = conn_req.status
        if conn_req.is_active is not None:
            connection.is_active = conn_req.is_active

    else:
        # Create new connection
        connection = Connection(
            user_id=conn_req.user_id,
            provider=provider_enum,
            status=conn_req.status or ConnectionStatus.PENDING,
            provider_account_id=conn_req.provider_account_id,
            scopes=conn_req.scopes,
            access_token=conn_req.access_token,
            refresh_token=conn_req.refresh_token,
            access_token_expiry=conn_req.access_token_expiry,
            is_active=True if conn_req.is_active is None else conn_req.is_active,
        )
        db.add(connection)

    await db.commit()
    await db.refresh(connection)

    return hateoas_connection(request, connection)



# PATCH Connection update 
@router.patch("/{connection_id}", response_model=ConnectionRead, status_code=200, name="update_connection")
async def update_connection(
    request: Request,
    connection_id: UUID,
    connection_update: ConnectionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Updates the details of a connection"""

    # 1) Load existing connection (by ID only; upstream handles user validation)
    result = await db.execute(
        select(Connection)
        .where(Connection.id == connection_id)
        .limit(1)
    )
    connection = result.scalar_one_or_none()

    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active connection found to update",
        )

    # 2) Extract only provided fields
    update_data = connection_update.model_dump(exclude_unset=True)
    
    # Never allow changing owner of a connection
    update_data.pop("user_id", None)


    if not update_data:
        # Nothing to update; caller sent empty payload
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided for update",
        )

    # 3) Apply changes field-by-field
    for field, value in update_data.items():
        # Defensive: only set attributes that actually exist on the model
        if hasattr(connection, field):
            setattr(connection, field, value)

    # 4) Commit and refresh
    await db.commit()
    await db.refresh(connection)

    # 5) Return HATEOAS-wrapped representation
    return hateoas_connection(request, connection)


# -----------------------------------------------------------------------------
# GET Endpoints
# -----------------------------------------------------------------------------

# GET Connections (list) with pagination and filtering (user specific needs login)
@router.get("/", response_model=ConnectionPaginated, status_code=200, name="list_connections",)
async def list_connections(
    request: Request,
    db: AsyncSession = Depends(get_db),
    # Pagination
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    size: int = Query(10, ge=1, le=1000, description="Page size"),
    # Filters
    user_id: Optional[UUID] = Query(None, description="Filter by user id"),
    provider: Optional[OAuthProvider] = Query(None, description="Filter by OAuth provider"),
    status: Optional[ConnectionStatus] = Query(None, description="Filter by connection status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    provider_account_id: Optional[str] = Query(None, description="Filter by provider account id (partial match)"),
    scope: Optional[str] = Query(None, description="Filter by a single scope contained in scopes array"),
    created_from: Optional[datetime] = Query(None, description="Filter connections created on/after this datetime (ISO8601)"),
    created_to: Optional[datetime] = Query(None, description="Filter connections created on/before this datetime (ISO8601)"),
    search: Optional[str] = Query(None, description="Free-text search in provider_account_id and last_error",),
):
    """
    Internal-only endpoint to list connections with filtering and pagination.
    Searches across all users; user_id is an optional filter.
    """

    # Convert page/size -> offset/limit
    skip = (page - 1) * size
    limit = size

    # Base filtered query (no pagination yet)
    base_query = select(Connection)

    if user_id is not None:
        base_query = base_query.where(Connection.user_id == user_id)

    if provider is not None:
        base_query = base_query.where(Connection.provider == provider)

    if status is not None:
        base_query = base_query.where(Connection.status == status)

    if is_active is not None:
        base_query = base_query.where(Connection.is_active == is_active)

    if provider_account_id:
        base_query = base_query.where(
            Connection.provider_account_id.ilike(f"%{provider_account_id}%")
        )

    if scope:
        base_query = base_query.where(Connection.scopes.contains([scope]))

    if created_from is not None:
        base_query = base_query.where(Connection.created_at >= created_from)

    if created_to is not None:
        base_query = base_query.where(Connection.created_at <= created_to)

    if search:
        like_pattern = f"%{search}%"
        base_query = base_query.where(
            or_(
                Connection.provider_account_id.ilike(like_pattern),
                Connection.last_error.ilike(like_pattern),
            )
        )

    # ---- total count (before pagination) ----
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one() or 0

    total_pages = ceil(total / size) if total > 0 else 0

    # ---- apply pagination ----
    data_query = base_query.offset(skip).limit(limit)
    result = await db.execute(data_query)
    connections = result.scalars().all()

    data: List[ConnectionRead] = [
        hateoas_connection(request, connection) for connection in connections
    ]

    has_next = page < total_pages

    return {
        "data": data,
        "page": page,
        "size": size,
        "total_pages": total_pages,
        "has_next": has_next,
    }


# GET Connection specific
@router.get("/{connection_id}", response_model=ConnectionRead, status_code=200, name="get_connection")
async def get_connection(
    request: Request,
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get information about a specific connection"""
    result = await db.execute(
        select(Connection).where( 
            Connection.id == connection_id
        )
    )
    connection = result.scalar_one_or_none()

    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    else:
        return hateoas_connection(request, connection)



# -----------------------------------------------------------------------------
# DELETE Endpoints
# -----------------------------------------------------------------------------

# DELETE Connection Specific
@router.delete("/{connection_id}", status_code=204, name="delete_connection")
async def delete_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Connection).where(
            Connection.id == connection_id
        )
    )
    
    connection = result.scalar_one_or_none()
    
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    await db.delete(connection)
    await db.commit()
    

# -----------------------------------------------------------------------------
# Test/Refresh/Reconnect Endpoints
# -----------------------------------------------------------------------------

# Test Connection
@router.post("/{connection_id}/test", response_model=ConnectionTest, status_code=200, name="test_connection")
async def test_connection(
    request: Request,
    connection_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Test if the connection is valid and working"""
    # Get the connection
    result = await db.execute(
        select(Connection).where(
            Connection.id == connection_id
        ).limit(1)
    )
    connection = result.scalar_one_or_none()
    
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        await validate_gmail_connection(connection)
        # validate_gmail_connection mutates `connection` (status, last_error, tokens)
        await db.commit()
        await db.refresh(connection)

    except HTTPException as exc:
        # Persist updated status/last_error before surfacing the error
        await db.commit()
        await db.refresh(connection)
        raise exc

    # 4) Build and return the test result
    return ConnectionTest(
        id=connection.id,
        user_id=connection.user_id,
        provider=str(connection.provider),
        status=connection.status,
        detail=connection.last_error,
        links=build_connection_links(request, connection),
    )
    


# Refresh/reconnect (using code 200 instead of 201 since we're not creating a new record)
@router.post("/{connection_id}/refresh", response_model=ConnectionRead, status_code=200, name="refresh_connection")
async def refresh_connection(
    request: Request,
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Refresh authentication tokens for the connection"""
   # 1) Load connection
    result = await db.execute(
        select(Connection)
        .where(Connection.id == connection_id)
        .limit(1)
    )
    connection = result.scalar_one_or_none()

    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Optional: only support Gmail/Google connections
    if connection.provider != OAuthProvider.GMAIL:
        raise HTTPException(
            status_code=400,
            detail="Token refresh is only implemented for Gmail connections",
        )

    try:
        # 2) Refresh tokens (mutates `connection` in-place, no commit)
        await refresh_gmail_tokens(connection)

        # 3) Persist changes
        await db.commit()
        await db.refresh(connection)

    except HTTPException as exc:
        # Persist whatever status/last_error refresh_gmail_tokens may have set
        await db.commit()
        await db.refresh(connection)
        raise exc

    except Exception as e:
        # Unexpected error path
        if hasattr(connection, "status"):
            connection.status = ConnectionStatus.FAILED
        if hasattr(connection, "last_error"):
            connection.last_error = f"Unexpected error during token refresh: {e}"

        await db.commit()
        await db.refresh(connection)

        raise HTTPException(
            status_code=500,
            detail="Unexpected error while refreshing connection tokens.",
        )

    # 4) Return normal ConnectionRead with HATEOAS
    return hateoas_connection(request, connection)
