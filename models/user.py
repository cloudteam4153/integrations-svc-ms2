from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List
from enum import Enum

from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from sqlalchemy import String, Boolean, DateTime, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base
from models.hateoas import HATEOASLink

# -----------------------------------------------------------------------------
# SQLAlchemy Model
# -----------------------------------------------------------------------------
class UserLoginMethod(str, Enum):
    CREDENTIALS = "CREDENTIALS"
    GOOGLE_OAUTH = "GOOGLE_OAUTH"
    

class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # unique identifier
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    
    # Credentials, or OAuth provider
    login_method: Mapped[UserLoginMethod] = mapped_column(String(50), nullable=False)
    
    # For CREDENTIALS login only
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # For ANY OAuth provider (Google ID, Microsoft ID, Apple ID, etc.)
    oauth_provider_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    
    hashed_refresh_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    refresh_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Constraints
    __table_args__ = (
        # Ensure credentials users have password
        CheckConstraint(
            "(login_method != 'CREDENTIALS') OR (hashed_password IS NOT NULL)",
            name="credentials_require_password"
        ),
        # Ensure OAuth users have provider ID
        CheckConstraint(
            "(login_method = 'CREDENTIALS') OR (oauth_provider_id IS NOT NULL)",
            name="oauth_require_provider_id"
        ),
    )


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class UserBase(BaseModel):
    """Base user fields shared across schemas"""
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's first name"
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's last name"
    )
    email: str = Field(
        ...,
        max_length=255,
        pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        description="User's email address (must be unique and valid)",
        examples=["email@domain.com"]
    )


class UserCreate(UserBase):
    """Create user with either credentials or OAuth"""
    # login_method: LoginMethod = Field(
    #     ...,
    #     description="Authentication method for this user",
    #     examples=[LoginMethod.CREDENTIALS, LoginMethod.GOOGLE_OAUTH]
    # )
    plaintext_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User's password in plain text (required for CREDENTIALS login)",
        examples=["strongpassword123"]
    )

class UserLoginCredentials(BaseModel):
    email: str = Field(
        ...,
        max_length=255,
        pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        description="User's email address (must be unique and valid)",
        examples=["email@domain.com"]
    )
    plaintext_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User's password in plain text (required for CREDENTIALS login)",
        examples=["strongpassword123"]
    )

class UserUpdate(BaseModel):
    """Update user information"""
    first_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Updated first name"
    )
    last_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Updated last name"
    )
    email: Optional[str] = Field(
        None,
        max_length=255,
        pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        description="Only updatable if user created with credentials and not Oauth provider. Updated email address (must be unique and valid)"
    )
    current_password: Optional[str] = Field(
        ...,
        min_length=1,
        description="Current password for verification"
    )
    new_password: Optional[str] = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password to set"
    )
    @model_validator(mode='after')
    def validate_password_update(self):
        """Ensure both current and new password are provided together"""
        has_current = self.current_password is not None
        has_new = self.new_password is not None
        
        if has_current != has_new:
            raise ValueError(
                "Both current_password and new_password must be provided together"
            )
        
        return self
    
    @field_validator('first_name', 'last_name', 'email')
    @classmethod
    def reject_empty_strings(cls, v: Optional[str]) -> Optional[str]:
        """Ensure if provided, fields are not empty strings"""
        if v is not None and v.strip() == "":
            raise ValueError("Field cannot be empty string")
        return v



class UserRead(UserBase):
    """User data returned to clients"""
    id: UUID = Field(
        ...,
        description="Internal unique identifier for this user"
    )
    login_method: UserLoginMethod = Field(
        ...,
        description="Authentication method used by this user",
        examples=[UserLoginMethod.CREDENTIALS, UserLoginMethod.GOOGLE_OAUTH]
    )
    is_active: bool = Field(
        ...,
        description="Whether this user account is active and can log in"
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when this user account was created"
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp when this user account was last updated"
    )
    links: Optional[List[HATEOASLink]] = Field(
        None,
        description="HATEOAS links for available actions"
    )

    model_config = ConfigDict(from_attributes=True)


class UserReadInternal(UserRead):
    """Extended user data for internal service use (includes sensitive fields)"""
    hashed_password: Optional[str] = Field(
        None,
        description="Hashed password (only for credentials users)"
    )
    oauth_provider_id: Optional[str] = Field(
        None,
        description="OAuth provider unique identifier"
    )
    hashed_refresh_token: Optional[str] = Field(
        None,
        description="Hashed refresh token for JWT refresh"
    )

    model_config = ConfigDict(from_attributes=True)