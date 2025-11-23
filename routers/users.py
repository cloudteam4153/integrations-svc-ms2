from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from typing import Optional

from services.database import get_db
from models.user import (
    User,
    UserCreate,
    UserRead,
    UserUpdate
)
from config.settings import settings
from utils.auth import validate_session
from security.passwords import hash_password


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


# -----------------------------------------------------------------------------
# POST Endpoint
# -----------------------------------------------------------------------------

# Create new user
@router.post("/", response_model=UserRead, status_code=201)
async def create_user(
    user: UserCreate, 
    db: AsyncSession = Depends(get_db)
):

    db_user = User(
        last_name=user.last_name,
        first_name=user.first_name,
        email=user.email,
        hashed_password=hash_password(user.plaintext_password)
    )
    
    db.add(db_user)
    try:
        await db.commit()
        await db.refresh(db_user)
        return UserRead.model_validate(db_user)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to create new user. {e}")

# -----------------------------------------------------------------------------
# GET Endpoints
# -----------------------------------------------------------------------------

@router.get("/", response_model=list[UserRead], status_code=200)
async def list_users(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    created_after: Optional[datetime] = Query(None, description="Filter users created after this date"),
    created_before: Optional[datetime] = Query(None, description="Filter users created before this date"),
    sort_by: str = Query("created_at", regex="^(created_at|email|first_name|last_name)$", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: AsyncSession = Depends(get_db)
):
    query = select(User)
    
    # Apply filters
    filters = []
    if search:
        search_filter = or_(
            User.first_name.ilike(f"%{search}%"),
            User.last_name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%")
        )
        filters.append(search_filter)
    
    if is_active is not None:
        filters.append(User.is_active == is_active)
    
    if created_after:
        filters.append(User.created_at >= created_after)
    
    if created_before:
        filters.append(User.created_at <= created_before)
    
    if filters:
        query = query.where(and_(*filters))
    
    # Apply sorting
    sort_column = getattr(User, sort_by)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return [UserRead.model_validate(user) for user in users]
    

@router.get("/{user_id}", response_model=UserRead, status_code=200)
async def get_user(
    user_id: UUID,
    include_inactive: bool = Query(False, description="Include inactive users in search"),
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.id == user_id)
    
    if not include_inactive:
        query = query.where(User.is_active == True)
    
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserRead.model_validate(user)

# -----------------------------------------------------------------------------
# PATCH Endpoint
# -----------------------------------------------------------------------------

@router.patch("/{user_id}", response_model=UserRead, status_code=200)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    force_update: bool = Query(False, description="Update even if user is inactive"),
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.id == user_id)
    
    if not force_update:
        query = query.where(User.is_active == True)
    
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(status_code=404, detail="User not found or inactive")
    
    if user_update.last_name is not None:
        user.last_name = user_update.last_name
    if user_update.first_name is not None:
        user.first_name = user_update.first_name
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.plaintext_password is not None:
        user.hashed_password = hash_password(user_update.plaintext_password)
    
    user.updated_at = datetime.now()
    
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)

# -----------------------------------------------------------------------------
# DELETE Endpoint
# -----------------------------------------------------------------------------

@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    soft_delete: bool = Query(True, description="Soft delete (deactivate) instead of hard delete"),
    force_delete: bool = Query(False, description="Allow deletion of inactive users"),
    db: AsyncSession = Depends(get_db)
):
    query = select(User).where(User.id == user_id)
    
    if not force_delete:
        query = query.where(User.is_active == True)
    
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(status_code=404, detail="User not found or already inactive")
    
    if soft_delete:
        user.is_active = False
        user.updated_at = datetime.now()
        await db.commit()
    else:
        await db.delete(user)
        await db.commit()