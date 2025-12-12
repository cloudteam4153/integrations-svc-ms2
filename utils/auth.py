from __future__ import annotations
from fastapi import Depends, Cookie, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from services.database import get_db

from uuid import UUID
from datetime import datetime, timezone
from models.user import User, UserRead
from security.tokens import get_user_id_from_token, hash_refresh_token, issue_tokens_and_set_cookies


# Cloud project test user UUID (USE THIS ONE)
test_user_UUID = "3aab3fba-9f4d-48ee-bee5-c1df257c33cc"

# Sanjay test user UUID
# test_user_UUID = "0283b6a0-f665-4041-bb21-75e5556835fc"

# async def get_current_user(): return test_user_UUID

# async def validate_session(
#         db: AsyncSession = Depends(get_db)
# ) -> UserRead:
#     """TEMPORARY FUNCTION UNTIL WE FIGURE OUT SESSION MANAGEMENT"""

#     result = await db.execute(
#         select(User).where(User.id == test_user_UUID)
#     )
#     user = result.scalar_one_or_none()

#     return UserRead.model_validate(user)

async def get_current_user() -> UUID:
    return UUID(test_user_UUID)

# async def get_current_user(
#     request: Request,
#     response: Response,
#     db: AsyncSession = Depends(get_db),
#     refresh_token: str | None = Cookie(None),
# ) -> UUID:
#     # --- Try ACCESS token from Authorization header ---
#     auth = request.headers.get("Authorization")
#     if auth and auth.startswith("Bearer "):
#         access_token = auth.split(" ", 1)[1]
#         try:
#             return get_user_id_from_token(access_token)
#         except HTTPException as e:
#             if e.detail != "Access token has expired":
#                 raise  # bad / invalid token

#     # --- Access expired or missing → use REFRESH token from cookie ---
#     if not refresh_token:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Missing refresh token"
#         )

#     hashed = hash_refresh_token(refresh_token)

#     user = await db.scalar(
#         select(User).where(User.hashed_refresh_token == hashed)
#     )

#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid refresh token"
#         )

#     if user.refresh_token_expires_at and user.refresh_token_expires_at < datetime.now(timezone.utc):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Refresh token expired"
#         )

#     # Issue new tokens (sets cookies + headers)
#     await issue_tokens_and_set_cookies(
#         response=response,
#         db=db,
#         user=user,
#     )

#     return user.id