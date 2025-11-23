from __future__ import annotations
from datetime import datetime

from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from services.database import Base

# -----------------------------------------------------------------------------
# SQLAlchemy Model
# -----------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    last_name: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(255))
    
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class UserBase(BaseModel):
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
        description="User's email address (must be unique and valid)"
    )

class UserCreate(UserBase):
    plaintext_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User's password in plain text (will be hashed before storage)"
    )

class UserUpdate(BaseModel):
    # id: UUID = Field(
    #     ...,
    #     description="ID of the user to update (for validation purposes)"
    # )
    first_name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Updated first name"
    )
    last_name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Updated last name"
    )
    email: str | None = Field(
        None,
        max_length=255,
        pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        description="Updated email address (must be unique and valid)"
    )
    plaintext_password: str | None = Field(
        None,
        min_length=8,
        max_length=128,
        description="Updated password in plain text (will be hashed before storage)"
    )

class UserRead(UserBase):
    id: UUID = Field(
        ...,
        description="Internal unique identifier for this user"
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

    model_config = ConfigDict(from_attributes=True)
