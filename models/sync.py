from __future__ import annotations
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base
from models.hateoas import HATEOASLink

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------
class SyncStatus(PyEnum):
    """Status of a sync job"""
    PENDING = "pending"         # Sync job queued but not started
    RUNNING = "running"         # Sync job currently in progress
    COMPLETED = "completed"     # Sync job finished successfully
    FAILED = "failed"           # Sync job failed with error
    CANCELLED = "cancelled"     # Sync job was cancelled by user

class SyncType(PyEnum):
    """Type of sync operation"""
    FULL = "full"               # Full sync of all messages
    INCREMENTAL = "incremental" # Only sync new/changed messages since last sync
    MANUAL = "manual"           # User-triggered sync

# -----------------------------------------------------------------------------
# SQLAlchemy Model
# -----------------------------------------------------------------------------
class Sync(Base):
    __tablename__ = "syncs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    connection_id: Mapped[UUID] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )

    # Sync job details
    status: Mapped[SyncStatus] = mapped_column(
        SQLEnum(SyncStatus),
        default=SyncStatus.PENDING,
        nullable=False,
        index=True
    )
    sync_type: Mapped[SyncType] = mapped_column(
        SQLEnum(SyncType),
        default=SyncType.MANUAL,
        nullable=False
    )

    # Timing information
    time_start: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    time_end: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Sync results and metadata
    messages_synced: Mapped[int] = mapped_column(Integer, default=0)
    messages_new: Mapped[int] = mapped_column(Integer, default=0)
    messages_updated: Mapped[int] = mapped_column(Integer, default=0)
    last_history_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Gmail history ID for incremental sync
    
    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Structured error info
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Progress tracking
    progress_percentage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-100
    current_operation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # What's currently happening

# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class SyncBase(BaseModel):
    sync_type: SyncType = Field(
        SyncType.MANUAL,
        description="Type of sync operation (full, incremental, or manual)"
    )
    status: SyncStatus = Field(
        SyncStatus.PENDING,
        description="Current status of the sync job"
    )

class SyncCreate(SyncBase):
    connection_id: UUID = Field(
        ...,
        description="ID of the connection to sync data from"
    )
    user_id: UUID = Field(
        ...,
        description="ID of the user who owns this sync job"
    )

class SyncUpdate(BaseModel):
    status: Optional[SyncStatus] = Field(
        None,
        description="Updated status of the sync job"
    )
    time_start: Optional[datetime] = Field(
        None,
        description="When the sync job started processing"
    )
    time_end: Optional[datetime] = Field(
        None,
        description="When the sync job completed or failed"
    )
    messages_synced: Optional[int] = Field(
        None,
        ge=0,
        description="Total number of messages processed in this sync"
    )
    messages_new: Optional[int] = Field(
        None,
        ge=0,
        description="Number of new messages added in this sync"
    )
    messages_updated: Optional[int] = Field(
        None,
        ge=0,
        description="Number of existing messages updated in this sync"
    )
    last_history_id: Optional[str] = Field(
        None,
        description="Latest history ID from the external service for incremental sync"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if the sync failed"
    )
    error_details: Optional[dict] = Field(
        None,
        description="Detailed error information as JSON object"
    )
    retry_count: Optional[int] = Field(
        None,
        ge=0,
        description="Number of times this sync has been retried"
    )
    progress_percentage: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Current progress of the sync job (0-100%)"
    )
    current_operation: Optional[str] = Field(
        None,
        description="Description of what the sync is currently doing"
    )

class SyncRead(SyncBase):
    id: UUID = Field(
        ...,
        description="Internal unique identifier for this sync job"
    )
    connection_id: UUID = Field(
        ...,
        description="ID of the connection that was synced"
    )
    user_id: UUID = Field(
        ...,
        description="ID of the user who owns this sync job"
    )
    time_start: Optional[datetime] = Field(
        None,
        description="When the sync job started processing"
    )
    time_end: Optional[datetime] = Field(
        None,
        description="When the sync job completed or failed"
    )
    created_at: datetime = Field(
        ...,
        description="When this sync job was created"
    )
    updated_at: datetime = Field(
        ...,
        description="When this sync job was last updated"
    )
    messages_synced: int = Field(
        ...,
        ge=0,
        description="Total number of messages processed in this sync"
    )
    messages_new: int = Field(
        ...,
        ge=0,
        description="Number of new messages added in this sync"
    )
    messages_updated: int = Field(
        ...,
        ge=0,
        description="Number of existing messages updated in this sync"
    )
    last_history_id: Optional[str] = Field(
        None,
        description="Latest history ID from the external service for incremental sync"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if the sync failed"
    )
    error_details: Optional[dict] = Field(
        None,
        description="Detailed error information as JSON object"
    )
    retry_count: int = Field(
        ...,
        ge=0,
        description="Number of times this sync has been retried"
    )
    progress_percentage: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Current progress of the sync job (0-100%)"
    )
    current_operation: Optional[str] = Field(
        None,
        description="Description of what the sync is currently doing"
    )
    links: Optional[List[HATEOASLink]] = Field(
        None,
        description="HATEOAS links."
    )

    model_config = ConfigDict(from_attributes=True)
