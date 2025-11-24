import asyncio
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional, List

from services.database import get_db
from models.sync import (
    Sync,
    SyncCreate, 
    SyncRead,
    SyncUpdate,
    SyncStatus,
    SyncType
)
from models.connection import Connection, ConnectionStatus
from models.user import UserRead
from utils.auth import validate_session
from utils.hateoas import hateoas_sync



router = APIRouter(
    prefix="/syncs",
    tags=["Syncs"],
)

# Background task for async sync processing
async def process_sync_job(sync_id: UUID, db: AsyncSession):
    """Background task to process sync job"""
    # Get sync job
    result = await db.execute(select(Sync).where(Sync.id == sync_id))
    sync_job = result.scalar_one_or_none()
    
    if not sync_job:
        return
    
    try:
        # Update status to running
        sync_job.status = SyncStatus.RUNNING
        sync_job.time_start = datetime.now()
        sync_job.current_operation = "Starting sync"
        await db.commit()
        
        # Get connection for this sync
        result = await db.execute(
            select(Connection).where(Connection.id == sync_job.connection_id)
        )
        connection = result.scalar_one_or_none()
        
        if not connection or connection.status != ConnectionStatus.ACTIVE:
            raise Exception("Connection not active or not found")
        
        # here do the actual sync job logic with Gmail or whatever external service
        
        # Simulate sync work with progress updates
        for progress in [25, 50, 75, 100]:
            sync_job.progress_percentage = progress
            sync_job.current_operation = f"Syncing messages... {progress}%"
            await db.commit()
            # Simulate work (replace with actual Gmail API calls)
            await asyncio.sleep(1)
        
        # Mark as completed and update all the relevant information
        # sync_job.status = SyncStatus.COMPLETED
        # sync_job.time_end = datetime.now()
        # sync_job.progress_percentage = 
        # sync_job.current_operation = "Sync completed"
        # sync_job.messages_synced = 
        # sync_job.messages_new = 
        # sync_job.messages_updated = 
        
    except Exception as e:
        sync_job.status = SyncStatus.FAILED
        sync_job.time_end = datetime.now()
        sync_job.error_message = str(e)
        sync_job.current_operation = "Sync failed"
        
    finally:
        await db.commit()

# -----------------------------------------------------------------------------
# GET Endpoints
# -----------------------------------------------------------------------------

@router.get("/", response_model=List[SyncRead], status_code=200, name="list_syncs")
async def list_syncs(
    request: Request,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    status: Optional[SyncStatus] = Query(None, description="Filter by sync status"),
    sync_type: Optional[SyncType] = Query(None, description="Filter by sync type"),
    connection_id: Optional[UUID] = Query(None, description="Filter by connection ID"),
    created_after: Optional[datetime] = Query(None, description="Filter syncs created after this date"),
    created_before: Optional[datetime] = Query(None, description="Filter syncs created before this date"),
    sort_by: str = Query("created_at", regex="^(created_at|time_start|time_end|status)$", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """List sync jobs with filtering and pagination"""
    query = select(Sync).where(Sync.user_id == current_user.id)
    
    # Apply filters
    filters = []
    if status:
        filters.append(Sync.status == status)
    if sync_type:
        filters.append(Sync.sync_type == sync_type)
    if connection_id:
        filters.append(Sync.connection_id == connection_id)
    if created_after:
        filters.append(Sync.created_at >= created_after)
    if created_before:
        filters.append(Sync.created_at <= created_before)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Apply sorting
    sort_column = getattr(Sync, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    syncs = result.scalars().all()
    
    resource_list: List[SyncRead] = []
    for sync in syncs:
        resource_list.append(hateoas_sync(request, sync))
    
    return resource_list


@router.get("/{sync_id}", response_model=SyncRead, status_code=200, name="get_sync")
async def get_sync(
    sync_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Get specific sync job details"""
    result = await db.execute(
        select(Sync).where(
            Sync.id == sync_id,
            Sync.user_id == current_user.id
        )
    )
    sync_job = result.scalar_one_or_none()
    
    if not sync_job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    return hateoas_sync(request, sync_job)

@router.get("/{sync_id}/status", response_model=SyncRead, status_code=200, name="get_sync_status")
async def get_sync_status(
    sync_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Polling endpoint to check sync job status"""
    result = await db.execute(
        select(Sync).where(
            Sync.id == sync_id,
            Sync.user_id == current_user.id
        )
    )
    sync_job = result.scalar_one_or_none()
    
    if not sync_job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    return hateoas_sync(request, sync_job)

# -----------------------------------------------------------------------------
# POST Endpoints
# -----------------------------------------------------------------------------

# Async endpoint for sync job
@router.post("/", response_model=SyncRead, status_code=202, name="create_sync")
async def create_sync(
    sync_data: SyncCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Create and start new sync job asynchronously"""
    result = await db.execute(
        select(Connection).where(
            Connection.id == sync_data.connection_id,
            Connection.user_id == current_user.id
        )
    )
    connection = result.scalar_one_or_none()
    
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    if connection.status != ConnectionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Connection is not active")
    
    # Create sync job
    sync_job = Sync(
        connection_id=sync_data.connection_id,
        user_id=current_user.id,
        sync_type=sync_data.sync_type,
        status=SyncStatus.PENDING
    )
    
    db.add(sync_job)
    await db.commit()
    await db.refresh(sync_job)
    
    # Start background task
    background_tasks.add_task(process_sync_job, sync_job.id, db)
    
    return hateoas_sync(request, sync_job)

# -----------------------------------------------------------------------------
# PATCH Endpoints
# -----------------------------------------------------------------------------

@router.patch("/{sync_id}", response_model=SyncRead, status_code=200, name="update_sync")
async def update_sync(
    sync_id: UUID,
    sync_update: SyncUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: UserRead = Depends(validate_session)
):
    """Update sync job (mainly for status updates)"""
    result = await db.execute(
        select(Sync).where(
            Sync.id == sync_id,
            Sync.user_id == current_user.id
        )
    )
    sync_job = result.scalar_one_or_none()
    
    if not sync_job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    # Update fields
    update_data = sync_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sync_job, field, value)
    
    sync_job.updated_at = datetime.now()
    
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
    current_user: UserRead = Depends(validate_session)
):
    """Delete sync job (cancel if running)"""
    result = await db.execute(
        select(Sync).where(
            Sync.id == sync_id,
            Sync.user_id == current_user.id
        )
    )
    sync_job = result.scalar_one_or_none()
    
    if not sync_job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    # If running, mark as cancelled instead of deleting
    if sync_job.status == SyncStatus.RUNNING:
        sync_job.status = SyncStatus.CANCELLED
        sync_job.time_end = datetime.now()
        sync_job.current_operation = "Sync cancelled by user"
        await db.commit()
    else:
        await db.delete(sync_job)
        await db.commit()
    
    return None