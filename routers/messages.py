from fastapi import APIRouter, HTTPException, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from uuid import UUID
from datetime import datetime
from typing import Optional, List

from services.database import get_db
from models.message import (
    Message,
    MessageCreate,
    MessageRead,
    MessageUpdate
)
from models.connection import Connection, ConnectionStatus
from models.user import UserRead
from utils.auth import validate_session
from utils.hateoas import hateoas_message
from utils.etag import handle_conditional_request, set_etag_headers
from services.gmail import (
    gmail_create_message,
    gmail_update_message,
    gmail_delete_message,
    gmail_bulk_delete_messages,
    validate_gmail_connection
)


router = APIRouter(
    prefix="/messages",
    tags=["Messages"],
)

# -----------------------------------------------------------------------------
# Helper Function
# -----------------------------------------------------------------------------

async def get_user_gmail_connection(user_id: UUID, db: AsyncSession) -> Optional[Connection]:
    """Get the user's active Gmail connection for API calls"""
    result = await db.execute(
        select(Connection).where(
            Connection.user_id == user_id,
            Connection.provider == "gmail", 
            Connection.status == ConnectionStatus.ACTIVE
        )
    )
    return result.scalar_one_or_none()

# -----------------------------------------------------------------------------
# GET Endpoints
# -----------------------------------------------------------------------------

@router.get("/", response_model=List[MessageRead], status_code=200, name="list_messages")
async def list_messages(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search in message snippet or content"),
    thread_id: Optional[str] = Query(None, description="Filter by Gmail thread ID"),
    label_ids: Optional[List[str]] = Query(None, description="Filter by Gmail label IDs"),
    external_id: Optional[str] = Query(None, description="Filter by external message ID"),
    created_after: Optional[datetime] = Query(None, description="Filter messages created after this date"),
    created_before: Optional[datetime] = Query(None, description="Filter messages created before this date"),
    has_raw: Optional[bool] = Query(None, description="Filter by whether message has raw content"),
    sort_by: str = Query("created_at", regex="^(created_at|internal_date|size_estimate)$", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """List messages with filtering and pagination"""
    query = select(Message).where(Message.user_id == current_user.id)
    
    # Apply filters
    filters = []
    
    if search:
        search_filter = or_(
            Message.snippet.ilike(f"%{search}%"),
            Message.external_id.ilike(f"%{search}%")
        )
        filters.append(search_filter)
    
    if thread_id:
        filters.append(Message.thread_id == thread_id)
    
    if external_id:
        filters.append(Message.external_id == external_id)
    
    if label_ids:
        # Check if any of the provided label IDs are in the message's label_ids JSON array
        for label_id in label_ids:
            filters.append(Message.label_ids.contains([label_id]))
    
    if created_after:
        filters.append(Message.created_at >= created_after)
    
    if created_before:
        filters.append(Message.created_at <= created_before)
    
    if has_raw is not None:
        if has_raw:
            filters.append(Message.raw.isnot(None))
        else:
            filters.append(Message.raw.is_(None))
    
    if filters:
        query = query.where(and_(*filters))
    
    # Apply sorting
    sort_column = getattr(Message, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    messages = result.scalars().all()
    
    resource_list: List[MessageRead] = []
    for message in messages:
        resource_list.append(hateoas_message(request, message))
    
    return resource_list

@router.get("/{message_id}", response_model=MessageRead, status_code=200, name="get_message")
async def get_message(
    message_id: UUID,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Get specific message details with ETag support"""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.user_id == current_user.id
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Handle ETag and conditional requests
    etag, should_return_304 = handle_conditional_request(request, message)
    
    if should_return_304:
        # Return 304 Not Modified
        set_etag_headers(response, etag)
        response.status_code = 304
        return Response(status_code=304)
    
    # Set ETag headers for successful response
    set_etag_headers(response, etag)
    
    return hateoas_message(request, message)
    

# -----------------------------------------------------------------------------
# POST Endpoints
# -----------------------------------------------------------------------------

@router.post("/", response_model=MessageRead, status_code=201, name="create_message")
async def create_message(
    message_data: MessageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Create new message record"""
    if message_data.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot create message for another user")
    
    if message_data.external_id:
        existing_result = await db.execute(
            select(Message).where(
                Message.external_id == message_data.external_id,
                Message.user_id == current_user.id
            )
        )
        existing_message = existing_result.scalar_one_or_none()
    
        if existing_message:
            raise HTTPException(
                status_code=409, 
                detail=f"Message with external_id '{message_data.external_id}' already exists"
            )
    
    gmail_connection = await get_user_gmail_connection(current_user.id, db)
    if not gmail_connection:
        raise HTTPException(status_code=400, detail="No active Gmail connection found")
    
    if not await validate_gmail_connection(gmail_connection):
        raise HTTPException(status_code=400, detail="Gmail connection is no longer valid")
    
    try:
        gmail_response = await gmail_create_message(gmail_connection, message_data)
        # Update message_data with Gmail response if needed
        if gmail_response and 'id' in gmail_response:
            message_data.external_id = gmail_response['id']
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create message via Gmail API: {str(e)}")
    
    # Create new message record in our database
    message = Message(
        external_id=message_data.external_id,
        user_id=message_data.user_id,
        thread_id=message_data.thread_id,
        label_ids=message_data.label_ids,
        snippet=message_data.snippet,
        history_id=message_data.history_id,
        internal_date=message_data.internal_date,
        size_estimate=message_data.size_estimate,
        raw=message_data.raw
    )
    
    db.add(message)
    await db.commit()
    await db.refresh(message)
    
    return hateoas_message(request, message)

# -----------------------------------------------------------------------------
# PATCH Endpoints
# -----------------------------------------------------------------------------

@router.patch("/{message_id}", response_model=MessageRead, status_code=200, name="update_message")
async def update_message(
    message_id: UUID,
    message_update: MessageUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):

    """Update existing message"""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.user_id == current_user.id
        )
    )
    message = result.scalar_one_or_none()

    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    gmail_connection = await get_user_gmail_connection(current_user.id, db)
    if not gmail_connection:
        raise HTTPException(status_code=400, detail="No active Gmail connection found")
    
    if not await validate_gmail_connection(gmail_connection):
        raise HTTPException(status_code=400, detail="Gmail connection is no longer valid")
    
    try:
        await gmail_update_message(gmail_connection, message.external_id, message_update)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update message via Gmail API: {str(e)}")
    
    # Update fields in our database
    update_data = message_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(message, field, value)
    
    message.updated_at = datetime.now()
    
    await db.commit()
    await db.refresh(message)
    
    return hateoas_message(request, message)

# -----------------------------------------------------------------------------
# DELETE Endpoints
# -----------------------------------------------------------------------------

@router.delete("/{message_id}", status_code=204, name="delete_message")
async def delete_message(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Delete specific message"""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
            Message.user_id == current_user.id
        )
    )
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    gmail_connection = await get_user_gmail_connection(current_user.id, db)
    if not gmail_connection:
        raise HTTPException(status_code=400, detail="No active Gmail connection found")

    if not await validate_gmail_connection(gmail_connection):
        raise HTTPException(status_code=400, detail="Gmail connection is no longer valid")
    
    try:
        success = await gmail_delete_message(gmail_connection, message.external_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete message via Gmail API")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete message via Gmail API: {str(e)}")
    
    # Delete from database
    await db.delete(message)
    await db.commit()
    

@router.delete("/", status_code=204, name="bulk_delete_messages")
async def bulk_delete_messages(
    message_ids: List[UUID] = Query(..., description="List of message IDs to delete"),
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Bulk delete multiple messages"""
    if not message_ids:
        raise HTTPException(status_code=400, detail="No message IDs provided")
    
    if len(message_ids) > 100:
        raise HTTPException(status_code=400, detail="Cannot delete more than 100 messages at once")
    
    messages_result = await db.execute(
        select(Message).where(
            Message.id.in_(message_ids),
            Message.user_id == current_user.id
        )
    )
    messages_to_delete = messages_result.scalars().all()
    
    if not messages_to_delete:
        raise HTTPException(status_code=404, detail="No messages found to delete")
    
    gmail_connection = await get_user_gmail_connection(current_user.id, db)
    if not gmail_connection:
        raise HTTPException(status_code=400, detail="No active Gmail connection found")
    
    if not await validate_gmail_connection(gmail_connection):
        raise HTTPException(status_code=400, detail="Gmail connection is no longer valid")
    
    external_ids = [msg.external_id for msg in messages_to_delete]
    
    try:
        gmail_response = await gmail_bulk_delete_messages(gmail_connection, external_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete messages via Gmail API: {str(e)}")
    
    delete_result = await db.execute(
        delete(Message).where(
            Message.id.in_(message_ids),
            Message.user_id == current_user.id
        )
    )
    
    
    deleted_count = len(messages_to_delete) 
    await db.commit()
    