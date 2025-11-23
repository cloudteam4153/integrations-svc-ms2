from __future__ import annotations
from datetime import datetime
from typing import Optional

from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base

# -----------------------------------------------------------------------------
# SQLAlchemy Model
# -----------------------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )

    # Gmail-specific fields (may need to make this into its own weak entity, so that messages can
    # remain lightweight and adaptable to any message format from other services)
    thread_id: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    label_ids: Mapped[list[str]] = mapped_column(JSON, nullable=True)
    snippet: Mapped[str] = mapped_column(Text, nullable=True)
    history_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    internal_date: Mapped[int] = mapped_column(BigInteger, nullable=True)  # Unix timestamp in milliseconds
    size_estimate: Mapped[int] = mapped_column(BigInteger, nullable=True)
    raw: Mapped[str] = mapped_column(Text, nullable=True)  # Base64 encoded raw message

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class MessageBase(BaseModel):
    external_id: Optional[str] = Field(
        None, 
        description="External message ID from the email service (e.g., Gmail message ID)"
    )
    thread_id: Optional[str] = Field(
        None, 
        description="Thread ID that groups related messages together"
    )
    label_ids: Optional[list[str]] = Field(
        None, 
        description="List of label IDs applied to this message (e.g., Gmail labels)"
    )
    snippet: Optional[str] = Field(
        None, 
        description="Short text preview/summary of the message content"
    )
    history_id: Optional[int] = Field(
        None, 
        description="History ID for tracking changes in the external service"
    )
    internal_date: Optional[int] = Field(
        None, 
        description="Message timestamp from the external service (Unix timestamp in milliseconds)"
    )
    size_estimate: Optional[int] = Field(
        None, 
        description="Estimated size of the message in bytes"
    )

class MessageCreate(MessageBase):
    user_id: UUID = Field(
        ..., 
        description="ID of the user who owns this message"
    )
    raw: Optional[str] = Field(
        None, 
        description="Base64-encoded raw message content including headers and body"
    )

class MessageUpdate(BaseModel):
    label_ids: Optional[list[str]] = Field(
        None, 
        description="Updated list of label IDs for this message"
    )
    snippet: Optional[str] = Field(
        None, 
        description="Updated message snippet/preview text"
    )
    history_id: Optional[int] = Field(
        None, 
        description="Updated history ID for sync tracking"
    )
    internal_date: Optional[int] = Field(
        None, 
        description="Updated message timestamp (Unix timestamp in milliseconds)"
    )
    size_estimate: Optional[int] = Field(
        None, 
        description="Updated size estimate in bytes"
    )
    raw: Optional[str] = Field(
        None, 
        description="Updated base64-encoded raw message content"
    )

class MessageRead(MessageBase):
    id: UUID = Field(
        ..., 
        description="Internal unique identifier for this message record"
    )
    user_id: UUID = Field(
        ..., 
        description="ID of the user who owns this message"
    )
    raw: Optional[str] = Field(
        None, 
        description="Base64-encoded raw message content (may be excluded for performance)"
    )
    created_at: datetime = Field(
        ..., 
        description="Timestamp when this message record was created in our system"
    )
    updated_at: datetime = Field(
        ..., 
        description="Timestamp when this message record was last updated"
    )

    model_config = ConfigDict(from_attributes=True)
