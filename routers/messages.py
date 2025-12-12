from fastapi import APIRouter, HTTPException, Depends, Query, Request, Response, status
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional, List, Union

from services.database import get_db
from models.message import (
    Message,
    MessageCreate,
    MessageRead,
    MessageUpdate
)
from models.oauth import OAuthProvider
from models.connection import Connection, ConnectionStatus
from models.user import UserRead
from utils.auth import get_current_user
from utils.hateoas import hateoas_message
from utils.etag import handle_conditional_request, set_etag_headers
from services.sync.gmail import (
    gmail_create_message,
    gmail_update_message,
    gmail_delete_message,
    validate_gmail_connection,
    connection_to_creds
)


router = APIRouter(
    prefix="/messages",
    tags=["Messages"],
)



# -----------------------------------------------------------------------------
# GET Endpoints
# -----------------------------------------------------------------------------

@router.get("/", response_model=List[MessageRead], status_code=200, name="list_messages",)
async def list_messages(
    request: Request,
    db: AsyncSession = Depends(get_db),

    # Core filters
    user_id: Optional[UUID] = Query(None),
    external_id: Optional[str] = Query(None),
    thread_id: Optional[str] = Query(None),
    label_ids: Optional[List[str]] = Query(None),

    # Direct text fields
    from_address: Optional[str] = Query(None),
    to_address: Optional[str] = Query(None),
    cc_address: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    body: Optional[str] = Query(None),
    snippet: Optional[str] = Query(None),

    # Broad search
    search: Optional[str] = Query(None),

    # Dates
    created_after: Optional[datetime] = Query(None),
    created_before: Optional[datetime] = Query(None),

    # Sorting
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),

    # Pagination
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
):
    """List messages with full filtering, sorting, and pagination."""

    query = select(Message)
    filters = []

    # ----------------------------
    # 1. CORE FILTERS
    # ----------------------------
    if user_id is not None:
        filters.append(Message.user_id == user_id)

    if external_id is not None:
        filters.append(Message.external_id == external_id)

    if thread_id is not None:
        filters.append(Message.thread_id == thread_id)

    if label_ids is not None:
        # message must contain ANY of the given label IDs
        filters.append(
            or_(*[Message.label_ids.contains([lbl]) for lbl in label_ids])
        )

    # ----------------------------
    # 2. ATTRIBUTE-LEVEL FILTERS
    # ----------------------------
    if from_address is not None:
        filters.append(Message.from_address.ilike(f"%{from_address}%"))

    if to_address is not None:
        filters.append(Message.to_address.ilike(f"%{to_address}%"))

    if cc_address is not None:
        filters.append(Message.cc_address.ilike(f"%{cc_address}%"))

    if subject is not None:
        filters.append(Message.subject.ilike(f"%{subject}%"))

    if body is not None:
        filters.append(Message.body.ilike(f"%{body}%"))

    if snippet is not None:
        filters.append(Message.snippet.ilike(f"%{snippet}%"))

    # ----------------------------
    # 3. FREE-TEXT SEARCH
    # ----------------------------
    if search is not None:
        like = f"%{search}%"
        filters.append(
            or_(
                Message.snippet.ilike(like),
                Message.subject.ilike(like),
                Message.body.ilike(like),
                Message.external_id.ilike(like),
                Message.from_address.ilike(like),
                Message.to_address.ilike(like),
                Message.cc_address.ilike(like),
            )
        )

    # ----------------------------
    # 4. DATE FILTERS
    # ----------------------------
    if created_after is not None:
        filters.append(Message.created_at >= created_after)

    if created_before is not None:
        filters.append(Message.created_at <= created_before)

    # ----------------------------
    # APPLY FILTERS
    # ----------------------------
    if filters:
        query = query.where(and_(*filters))

    # ----------------------------
    # SORTING
    # ----------------------------
    sort_column = getattr(Message, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # ----------------------------
    # PAGINATION
    # ----------------------------
    query = query.offset(skip).limit(limit)

    # ----------------------------
    # EXECUTE
    # ----------------------------
    result = await db.execute(query)
    messages = result.scalars().all()

    # ----------------------------
    # HATEOAS WRAP
    # ----------------------------
    return [hateoas_message(request, m) for m in messages]


# Get Message by specific ID (eTAG support)
@router.get("/{message_id}", response_model=MessageRead, status_code=200, name="get_message")
async def get_message(
    request: Request,
    response: Response,
    message_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> Union[MessageRead, FastAPIResponse]:
    """Get specific message details with ETag support"""
    result = await db.execute(
        select(Message).where(
            Message.id == message_id,
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
        return FastAPIResponse(status_code=304, headers={"ETag": etag, "Cache-Control": "private, max-age=0, must-revalidate"})
    
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
    db: AsyncSession = Depends(get_db)
):
    """Create new message record"""
    def safe_int(value: Optional[Union[str, int]]) -> Optional[int]:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    # 2) Load connection owned by this user + active gmail
    result = await db.execute(
        select(Connection).where(
            Connection.id == message_data.connection_id,
            Connection.user_id == message_data.user_id,
            Connection.provider == OAuthProvider.GMAIL,
            Connection.status == ConnectionStatus.ACTIVE,
        )
    )
    gmail_connection = result.scalar_one_or_none()
    if not gmail_connection:
        raise HTTPException(status_code=400, detail="Invalid or inactive Gmail connection")

    # 3) Get valid creds (refreshes & persists if needed)
    creds = connection_to_creds(gmail_connection)
    # 4) Send via Gmail
    try:
        gmail_response = await gmail_create_message(creds, message_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send via Gmail API: {str(e)}")

    external_id = gmail_response.get("id")
    if not external_id:
        raise HTTPException(status_code=502, detail="Gmail API did not return a message id")

    # 5) Store record
    message = Message(
        external_id=external_id,
        user_id=message_data.user_id,
        thread_id=gmail_response.get("threadId") or message_data.thread_id,
        label_ids=gmail_response.get("labelIds") or message_data.label_ids,
        snippet=gmail_response.get("snippet"),
        history_id=safe_int(gmail_response.get("historyId")),
        internal_date=safe_int(gmail_response.get("internalDate")),
        size_estimate=safe_int(gmail_response.get("sizeEstimate")),
        from_address=message_data.from_address,
        to_address=message_data.to_address,
        cc_address=message_data.cc_address,
        subject=message_data.subject,
        body=message_data.body,
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
):

    result = await db.execute(
        select(Message).where(Message.id == message_id).limit(1)
    )
    message = result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    conn_result = await db.execute(
        select(Connection).where(
            Connection.id == message_update.connection_id,
            Connection.provider == OAuthProvider.GMAIL,
            Connection.status == ConnectionStatus.ACTIVE,
        ).limit(1)
    )
    gmail_connection = conn_result.scalar_one_or_none()
    if not gmail_connection:
        raise HTTPException(status_code=400, detail="Invalid or inactive Gmail connection")


    try:
        gmail_update_message(
            gmail_connection=gmail_connection,
            external_message_id=message.external_id,
            message_update=message_update,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to update message via Gmail API: {str(e)}",
        )

    # 6) Update your local DB row (only fields you actually store/allow)
    update_data = message_update.model_dump(exclude_unset=True)

    # strongly recommended: prevent overwriting identifiers / foreign keys
    blocked = {"id", "external_id", "user_id", "connection_id", "message_id"}
    for k in blocked:
        update_data.pop(k, None)

    for field, value in update_data.items():
        setattr(message, field, value)

    message.updated_at = datetime.now(timezone.utc)

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
):
    """Downstream delete: resolve user via message → find Gmail connection → delete."""

    # 1) Load message
    result = await db.execute(
        select(Message).where(Message.id == message_id).limit(1)
    )
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # 2) Find user's Gmail connection (assume 1 per user)
    conn_result = await db.execute(
        select(Connection).where(
            Connection.user_id == message.user_id,
            Connection.provider == "gmail",
            Connection.status == ConnectionStatus.ACTIVE,
        ).limit(1)
    )
    gmail_connection = conn_result.scalar_one_or_none()

    if not gmail_connection:
        raise HTTPException(
            status_code=400,
            detail="No active Gmail connection found for message owner",
        )

    # 3) Validate / refresh connection (if your helper does refresh)
    if not await validate_gmail_connection(gmail_connection):
        raise HTTPException(
            status_code=400,
            detail="Gmail connection is no longer valid",
        )

    # 4) Delete from Gmail (blocking or async — match your implementation)
    try:
        success = gmail_delete_message(
            connection=gmail_connection,
            external_message_id=message.external_id,
        )
        if not success:
            raise HTTPException(
                status_code=502,
                detail="Failed to delete message via Gmail API",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to delete message via Gmail API: {str(e)}",
        )

    # 5) Delete from DB
    await db.delete(message)
    await db.commit()
    