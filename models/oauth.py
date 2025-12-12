from __future__ import annotations
from enum import Enum as PyEnum
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Optional

from services.database import Base
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel, ConfigDict, Field


class OAuthProvider(PyEnum):
    """Supported OAuth providers"""
    GMAIL = "gmail"
    GOOGLE = "google"
    SLACK = "slack"
    OUTLOOK = "outlook"

# -----------------------------------------------------------------------------
# SQLAlchemy Model
# -----------------------------------------------------------------------------
class OAuth(Base):
    """
    Temporary storage for OAuth state tokens. (~5 mins)
    """
    __tablename__ = "oauth_states"
    
    state_token: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    redirect_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    # connection_id: Mapped[UUID] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    
    provider: Mapped[OAuthProvider] = mapped_column(SQLEnum(OAuthProvider), nullable=False)
    
    __table_args__ = (
        Index('ix_oauth_states_expires_at', 'expires_at'),  # For cleanup queries
    )

# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------

class OAuthStateCreate(BaseModel):
    """Pydantic model for creating OAuth state records"""
    state_token: str = Field(
        ...,
        description="Unique CSRF token to prevent OAuth attacks",
        min_length=16,
        max_length=64
    )
    user_id: UUID = Field(
        ...,
        description="ID of the user initiating the OAuth flow"
    )
    provider: OAuthProvider = Field(
        ...,
        description="OAuth provider for this authentication flow"
    )
    expires_at: datetime = Field(
        ...,
        description="When this OAuth state token expires (typically 5 minutes)"
    )

class OAuthStateRead(BaseModel):
    """Pydantic model for reading OAuth state records"""
    state_token: str = Field(
        ...,
        description="Unique CSRF token used for OAuth verification"
    )
    user_id: Optional[UUID] = Field(
        None,
        description="ID of the user who initiated this OAuth flow"
    )
    provider: OAuthProvider = Field(
        ...,
        description="OAuth provider name"
    )
    created_at: datetime = Field(
        ...,
        description="When this OAuth state was created"
    )
    expires_at: datetime = Field(
        ...,
        description="When this OAuth state expires"
    )
    
    model_config = ConfigDict(from_attributes=True)

class OAuthRedirectURL(BaseModel):
    url: str = Field(
        ...,
        description="OAuthURL to redirect user to OAuth provider for sign in."
    )