from __future__ import annotations
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base
from models.oauth import OAuthProvider

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
        ForeignKey("users.id", ondelete="CASCADE"), 
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
    access_token_expiry: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.now,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.now, 
        onupdate=datetime.now,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)

# -----------------------------------------------------------------------------
# Connection Request and Response Models
# -----------------------------------------------------------------------------


class ConnectionBase(BaseModel):
    """Base model definition for an external resource connection."""
    provider: str
    provider_account_id: Optional[str] = None

class ConnectionInitiateRequest(BaseModel):
    """Internal model for creating a connection from an OAuth flow"""
    user_id: UUID
    provider: str
    status: ConnectionStatus = ConnectionStatus.PENDING

class ConnectionInitiateResponse(BaseModel):
    """Reponse model for redirect URL to OAuth provider"""
    auth_url: str = Field(
        ..., 
        description="Authorization URL for OAuth provider (e.g. Google) to redirect user for sign-in.")


class ConnectionRead(ConnectionBase):
    """Read information about an external resource connection"""
    id: UUID
    user_id: UUID
    is_active: bool
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    access_token_expiry: datetime | None = None
    
    model_config = ConfigDict(from_attributes=True)

class ConnectionUpdate(BaseModel):
    """Partial update of a connection; ID is taken from path"""
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str | None = None
    scope: list[str] | None = None
    access_token_expiry: datetime | None = None
    is_active: bool | None = None
    last_error: str | None = None
