from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional, List

from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base
from models.oauth import OAuthProvider
from models.hateoas import HATEOASLink

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------
class ConnectionStatus(PyEnum):
    """Status of an OAuth connection"""
    PENDING = "pending"      # OAuth flow initiated but not completed
    ACTIVE = "active"        # Successfully connected and tokens are valid
    EXPIRED = "expired"      # Tokens expired and refresh failed
    REVOKED = "revoked"      # User revoked access
    FAILED = "failed"        # OAuth flow failed



# -----------------------------------------------------------------------------
# SQLAlchemy Model
# -----------------------------------------------------------------------------
class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        nullable=False, 
        index=True
    )

    # Provider information
    provider: Mapped[str] = mapped_column(
        SQLEnum(OAuthProvider), 
        nullable=False
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        SQLEnum(ConnectionStatus),
        default=ConnectionStatus.PENDING,
        nullable=False,
        index=True
    )

    provider_account_id: Mapped[str] = mapped_column(String, nullable=True)

    # access_token should be secured/encrypted
    access_token: Mapped[str] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, nullable=True)
    access_token_expiry: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # history cursor
    last_history_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)

# -----------------------------------------------------------------------------
# Pydantic Models
# -----------------------------------------------------------------------------


class ConnectionBase(BaseModel):
    """Base model definition for an external resource connection."""
    user_id: UUID = Field(
        ...,
        description="ID of the user who owns this connection"
    )
    provider: str = Field(
        ...,
        description="OAuth provider name (e.g., 'gmail', 'slack', 'outlook')"
    )
    provider_account_id: Optional[str] = Field(
        None,
        description="Account ID from the external provider"
    )

    model_config = ConfigDict(from_attributes=True)

class ConnectionCreate(ConnectionBase):
    status: ConnectionStatus = Field(
        ...,
        description="Current status of the connection"
    )
    scopes: list[str] | None = Field(
        None,
        description="List of OAuth scopes granted for this connection"
    )
    access_token: str | None = Field(
        None,
        description="Encrypted access token from OAuth provider"
    )
    refresh_token: str | None = Field(
        None,
        description="Encrypted refresh token for token renewal"
    )
    access_token_expiry: datetime | None = Field(
        None,
        description="Expiration time for the access token"
    )
    is_active: bool | None = Field(
        None,
        description="Active status of this connection"
    )

    model_config = ConfigDict(from_attributes=True)


class ConnectionRead(ConnectionBase):
    """Read information about an external resource connection"""
    id: UUID = Field(
        ...,
        description="Internal unique identifier for this connection"
    )
    user_id: UUID = Field(
        ...,
        description="ID of the user who owns this connection"
    )
    is_active: bool = Field(
        ...,
        description="Whether this connection is currently active and usable"
    )
    last_error: str | None = Field(
        None,
        description="Last error message if connection failed or encountered issues"
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when this connection was first created"
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when this connection was last updated"
    )
    access_token_expiry: datetime | None = Field(
        None,
        description="When the access token expires (if applicable)"
    )
    last_history_id: str | None = Field(
        None,
        description="Gmail history cursor used for incremental sync"
    )
    links: Optional[List[HATEOASLink]] = Field(
        None,
        description="HATEOAS links."
    )
    
    model_config = ConfigDict(from_attributes=True)
    
class ConnectionPaginated(BaseModel):
    data: List[ConnectionRead]
    page: int
    size: int
    total_pages: int
    has_next: bool

class ConnectionUpdate(BaseModel):
    """Partial update of a connection; ID is taken from path"""
    user_id: Optional[UUID] = Field(
        None,
        description="ID of the user who owns this connection"
    )
    provider: Optional[str] = Field(
        None,
        description="OAuth provider name (e.g., 'gmail', 'slack', 'outlook')"
    )
    provider_account_id: Optional[str] = Field(
        None,
        description="Account ID from the external provider"
    )
    access_token: str | None = Field(
        None,
        description="Updated encrypted access token from OAuth provider"
    )
    refresh_token: str | None = Field(
        None,
        description="Updated encrypted refresh token for token renewal"
    )
    token_type: str | None = Field(
        None,
        description="Type of token (usually 'bearer')"
    )
    scopes: list[str] | None = Field(
        None,
        description="Updated list of OAuth scopes granted for this connection"
    )
    access_token_expiry: datetime | None = Field(
        None,
        description="Updated expiration time for the access token"
    )
    is_active: bool | None = Field(
        None,
        description="Updated active status of this connection"
    )
    last_error: str | None = Field(
        None,
        description="Updated error message or None to clear errors"
    )
    last_history_id: str | None = Field(
        None,
        description="Updated Gmail history cursor after successful sync"
    )

    model_config = ConfigDict(from_attributes=True)

class ConnectionTest(BaseModel):
    id: UUID = Field(
        ...,
        description="Internal unique identifier for this connection"
    )
    user_id: UUID = Field(
        ...,
        description="ID of the user who owns this connection"
    )
    provider: str = Field(
        ...,
        description="OAuth provider name to connect to"
    )
    status: ConnectionStatus = Field(
        ...,
        description="Current status of the connection"
    )
    detail: str | None = Field(
        None,
        description="Details about the status"
    )
    links: Optional[List[HATEOASLink]] = Field(
        None,
        description="HATEOAS links."
    )

    model_config = ConfigDict(from_attributes=True)
