from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Request

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, and_, or_, func

from uuid import UUID
from datetime import datetime, timezone
from typing import Optional, List

from models.sync import (
    Sync,
    SyncCreate, 
    SyncRead,
    SyncUpdate,
    SyncStatus,
    SyncType,
    SyncStatusUpdate,
    SyncListResponse
)
from models.connection import Connection, ConnectionStatus
from models.user import User, UserRead

from services.database import get_db
from utils.auth import get_current_user
from utils.hateoas import hateoas_sync
from services.sync.worker import process_sync_job



router = APIRouter(
    prefix="/syncs",
    tags=["Syncs"],
)


# -----------------------------------------------------------------------------
# GET Endpoints
# -----------------------------------------------------------------------------

@router.get("/", response_model=SyncListResponse, status_code=200, name="list_syncs")
async def list_syncs(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    status: Optional[SyncStatus] = Query(None, description="Filter by sync status"),
    sync_type: Optional[SyncType] = Query(None, description="Filter by sync type"),
    connection_id: Optional[UUID] = Query(None, description="Filter by connection ID"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    created_after: Optional[datetime] = Query(None, description="Filter syncs created after this date"),
    created_before: Optional[datetime] = Query(None, description="Filter syncs created before this date"),
    sort_by: str = Query(
        "created_at",
        regex="^(created_at|time_start|time_end|status)$",
        description="Sort field",
    ),
    sort_order: str = Query(
        "desc",
        regex="^(asc|desc)$",
        description="Sort order",
    ),
    db: AsyncSession = Depends(get_db),
):
    """List sync jobs with filtering and pagination"""

    # Build filters
    filters = []
    if status is not None:
        filters.append(Sync.status == status)
    if sync_type is not None:
        filters.append(Sync.sync_type == sync_type)
    if connection_id is not None:
        filters.append(Sync.connection_id == connection_id)
    if user_id is not None:
        filters.append(Sync.user_id == user_id)
    if created_after is not None:
        filters.append(Sync.created_at >= created_after)
    if created_before is not None:
        filters.append(Sync.created_at <= created_before)

    combined_filter = and_(*filters) if filters else None

    # Base query
    query = select(Sync)
    count_query = select(func.count()).select_from(Sync)

    if combined_filter is not None:
        query = query.where(combined_filter)
        count_query = count_query.where(combined_filter)

    # Sorting
    sort_column = getattr(Sync, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Total count (for pagination metadata)
    total_result = await db.execute(count_query)
    total_items: int = total_result.scalar_one() or 0

    # Apply pagination to main query
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    syncs = result.scalars().all()

    # HATEOAS wrapping
    data: List[SyncRead] = [hateoas_sync(request, sync) for sync in syncs]

    # Compute pagination fields
    page = (skip // limit) + 1 if limit > 0 else 1
    size = len(data)
    total_pages = (total_items + limit - 1) // limit if total_items > 0 else 0
    has_next = page < total_pages

    return SyncListResponse(
        data=data,
        page=page,
        size=size,
        total_pages=total_pages,
        has_next=has_next,
    )


@router.get("/{sync_id}", response_model=SyncRead, status_code=200, name="get_sync")
async def get_sync(
    sync_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get specific sync job details"""
    result = await db.execute(
        select(Sync).where(
            Sync.id == sync_id
        )
    )
    sync_job = result.scalar_one_or_none()
    
    if not sync_job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    return hateoas_sync(request, sync_job)


@router.get("/{sync_id}/status", response_model=SyncStatusUpdate, status_code=200, name="get_sync_status")
async def get_sync_status(
    sync_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Polling endpoint to check sync job status"""
    result = await db.execute(
        select(Sync).where(
            Sync.id == sync_id
        )
    )
    sync_job = result.scalar_one_or_none()
    
    if not sync_job:
        raise HTTPException(status_code=404, detail="Sync job not found")
        
    return SyncStatusUpdate(
        id=sync_job.id,
        connection_id=sync_job.connection_id,
        user_id=sync_job.user_id,
        sync_type=sync_job.sync_type,
        status=sync_job.status,
        time_start=sync_job.time_start,
        progress_percentage=sync_job.progress_percentage,
        current_operation=sync_job.current_operation
    )

# -----------------------------------------------------------------------------
# POST Endpoints
# -----------------------------------------------------------------------------

# Async endpoint for sync job
@router.post("/", response_model=List[SyncRead], status_code=202, name="create_sync")
async def create_sync(
    sync_data: SyncCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create sync jobs for ALL active connections for the given user_id (async kickoff)."""

    target_user_id = sync_data.user_id

    # Pull all ACTIVE connections for that user and any existing PENDING/RUNNING sync
    query = (
        select(Connection, Sync)
        .outerjoin(
            Sync,
            and_(
                Sync.connection_id == Connection.id,
                Sync.status.in_([SyncStatus.PENDING, SyncStatus.RUNNING]),
            ),
        )
        .where(
            Connection.user_id == target_user_id,
            Connection.status == ConnectionStatus.ACTIVE,
        )
    )

    result = await db.execute(query)
    rows = result.all()  # List[Tuple[Connection, Optional[Sync]]]

    sync_jobs: list[tuple[Sync, Connection]] = []

    for connection, existing_sync in rows:
        if existing_sync is not None:
            # Reuse existing in-flight sync
            sync_jobs.append((existing_sync, connection))
            continue

        new_sync = Sync(
            connection_id=connection.id,
            user_id=target_user_id,
            status=SyncStatus.PENDING,
            sync_type=sync_data.sync_type,
        )

        db.add(new_sync)

        try:
            await db.flush()  # get new_sync.id without committing yet
            sync_jobs.append((new_sync, connection))

        except IntegrityError:
            # Another request may have created a PENDING/RUNNING sync concurrently.
            await db.rollback()

            res2 = await db.execute(
                select(Sync).where(
                    Sync.connection_id == connection.id,
                    Sync.status.in_([SyncStatus.PENDING, SyncStatus.RUNNING]),
                )
            )
            existing_sync = res2.scalar_one()
            sync_jobs.append((existing_sync, connection))

    await db.commit()

    # Kick off background processing ONLY for newly created PENDING syncs
    for sync_job, connection in sync_jobs:
        if sync_job.status == SyncStatus.PENDING:
            background_tasks.add_task(
                process_sync_job,
                sync_job.id,
                connection,
            )

    return [hateoas_sync(request, job) for job, _ in sync_jobs]

# -----------------------------------------------------------------------------
# PATCH Endpoints
# -----------------------------------------------------------------------------

@router.patch("/{sync_id}", response_model=SyncRead, status_code=200, name="update_sync")
async def update_sync(
    sync_id: UUID,
    sync_update: SyncUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UUID = Depends(get_current_user)
):
    """Update sync job (mainly for status updates)"""
    result = await db.execute(
        select(Sync).where(
            Sync.id == sync_id,
            Sync.user_id == current_user
        )
    )
    sync_job = result.scalar_one_or_none()
    
    if not sync_job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    # Update fields
    update_data = sync_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sync_job, field, value)
    
    sync_job.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(sync_job)
    
    return hateoas_sync(request, sync_job)

# -----------------------------------------------------------------------------
# DELETE Endpoints
# -----------------------------------------------------------------------------

@router.delete("/{sync_id}", status_code=204, name="delete_sync")
async def delete_sync(
    sync_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UUID = Depends(get_current_user)
):
    """Delete sync job (cancel if running)"""
    result = await db.execute(
        select(Sync).where(
            Sync.id == sync_id,
            Sync.user_id == current_user
        )
    )
    sync_job = result.scalar_one_or_none()
    
    if not sync_job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    # If running, mark as cancelled instead of deleting
    if sync_job.status == SyncStatus.RUNNING:
        sync_job.status = SyncStatus.CANCELLED
        sync_job.time_end = datetime.now(timezone.utc)
        sync_job.current_operation = "Sync cancelled by user"
        await db.commit()
    else:
        await db.delete(sync_job)
        await db.commit()
    
    return None