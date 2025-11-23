from __future__ import annotations
from enum import Enum as PyEnum
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import Optional

from services.database import Base
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel


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
    Temporary storage for OAuth state tokens.
    Used to prevent CSRF attacks and link callback to original request.
    
    These records are short-lived (5 minutes) and deleted after use.
    """
    __tablename__ = "oauth_states"
    
    state_token: Mapped[str] = mapped_column(String(64), primary_key=True)
    connection_id: Mapped[UUID] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    provider: Mapped[OAuthProvider] = mapped_column(SQLEnum(OAuthProvider), nullable=False)
    
    __table_args__ = (
        Index('ix_oauth_states_expires_at', 'expires_at'),  # For cleanup queries
    )

class OAuthStateCreate(BaseModel):
    """Pydantic model for creating OAuth state records"""
    state_token: str
    connection_id: UUID
    user_id: UUID
    provider: str
    expires_at: datetime