from __future__ import annotations
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from services.database import get_db

from uuid import UUID
from datetime import datetime
from models.user import User, UserRead


# Cloud project test user UUID (USE THIS ONE)
test_user_UUID = "3aab3fba-9f4d-48ee-bee5-c1df257c33cc"

# Sanjay test user UUID
# test_user_UUID = "0283b6a0-f665-4041-bb21-75e5556835fc"


async def validate_session(
        db: AsyncSession = Depends(get_db)
) -> UserRead:
    """TEMPORARY FUNCTION UNTIL WE FIGURE OUT SESSION MANAGEMENT"""

    result = await db.execute(
        select(User).where(User.id == test_user_UUID)
    )
    user = result.scalar_one_or_none()

    return UserRead.model_validate(user)
