from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List

from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base
from models.hateoas import HATEOASLink

# -----------------------------------------------------------------------------
# SQLAlchemy Model
# -----------------------------------------------------------------------------
class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("user_id", "external_id", name="uq_user_external_message"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[UUID] = mapped_column(
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
    
    from_address: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    to_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cc_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class MessageBase(BaseModel):
    user_id: UUID = Field(
        ..., 
        description="ID of the user who owns this message"
    )   
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
    from_address: Optional[str] = Field(
        None, 
        description="Sender email address"
    )
    to_address: Optional[str] = Field(
        None,
        description="Recipient email addresses"
    )
    cc_address: Optional[str] = Field(
        None, 
        description="CC email addresses"
    )
    subject: Optional[str] = Field(
        None, description="Email subject line"
    )
    body: Optional[str] = Field(
        None, 
        description="Decoded email message body"
    )

    model_config = ConfigDict(from_attributes=True)

class MessageCreate(BaseModel):
    user_id: UUID = Field(
        ..., 
        description="ID of the user who owns this message"
    )
    connection_id: UUID = Field(
        ..., 
        description="Connection ID to use for sending (must belong to the user)"
    )
    to_address: str = Field(
        ..., 
        description="Recipient email addresses"
    )
    from_address: str = Field(
        ..., 
        description="Sender email address"
    )
    cc_address: Optional[str] = Field(
        None, 
        description="CC email addresses"
    )
    subject: Optional[str] = Field(
        None, description="Email subject line"
    )
    body: Optional[str] = Field(
        None, 
        description="Decoded email message body"
    )
    thread_id: Optional[str] = Field(
        None, 
        description="Thread to attach the message to"
    )
    label_ids: Optional[list[str]] = Field(
        None, 
        description="Labels to apply when sending the message"
    )
    raw: Optional[str] = Field(
        None, 
        description="Base64-encoded raw message content including headers and body"
    )

    model_config = ConfigDict(from_attributes=True)

class MessageUpdate(BaseModel):
    user_id: UUID = Field(
        ..., 
        description="ID of the user who owns this message"
    )
    connection_id: UUID = Field(
        ..., 
        description="Connection ID to use (Gmail)"
    )
    label_ids: Optional[list[str]] = Field(
        None, 
        description="Labels to apply when sending the message"
    )

class MessageRead(MessageBase):
    id: UUID = Field(
        ..., 
        description="Internal unique identifier for this message record"
    )
    created_at: datetime = Field(
        ..., 
        description="Timestamp when this message record was created in our system"
    )
    updated_at: datetime = Field(
        ..., 
        description="Timestamp when this message record was last updated"
    )
    links: Optional[List[HATEOASLink]] = Field(
        None,
        description="HATEOAS links."
    )

    model_config = ConfigDict(from_attributes=True)
