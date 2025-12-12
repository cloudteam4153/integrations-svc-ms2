from __future__ import annotations
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt
from fastapi import HTTPException, status, Response
from config.settings import settings
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User


# -----------------------------------------------------------------------------
# OAuth Token Encryption
# -----------------------------------------------------------------------------

class TokenCipher:

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, plaintext_token: str) -> str:
        if plaintext_token is None:
            raise ValueError("Cannot encrypt None.")
        if plaintext_token == "":
            raise ValueError("Cannot encrypt empty string")
        
        token_bytes = plaintext_token.encode("utf-8")
        encryped = self._fernet.encrypt(token_bytes)
        return encryped.decode("utf-8")
    
    def decrypt(self, ciphertext: str) -> Optional[str]:
        
        if not ciphertext: return None
        
        try: 
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode("utf-8"))
        except InvalidToken:
            raise InvalidToken("Invalid token.")
        
        return decrypted_bytes.decode("utf-8")
    
    
def generate_key() -> str:
    return Fernet.generate_key().decode("utf-8")



# -----------------------------------------------------------------------------
# Access Token Functions (JWT)
# -----------------------------------------------------------------------------
def create_JWT_access_token(
        user_id: UUID, 
        expires_delta: Optional[timedelta] = None
) -> str:

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.now(timezone.utc) + expires_delta
    
    payload = {
        "sub": str(user_id),  # Subject (user ID)
        "exp": expire,         # Expiration time
        "iat": datetime.now(timezone.utc),  # Issued at
        "type": "access"       # Token type
    }
    
    encoded_jwt = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def decode_JWT_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify token type
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )


def get_user_id_from_token(token: str) -> UUID:

    payload = decode_JWT_access_token(token)
    user_id = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    try:
        return UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token"
        )


# -----------------------------------------------------------------------------
# Refresh Token Functions
# -----------------------------------------------------------------------------
def create_refresh_token() -> str:
    return secrets.token_urlsafe(32) 

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def verify_refresh_token(token: str, hashed_token: str) -> bool:
    return hash_refresh_token(token) == hashed_token

# -----------------------------------------------------------------------------
# Main Token Generation Flow
# -----------------------------------------------------------------------------
async def issue_tokens_and_set_cookies(
    *,
    response: Response,
    db: AsyncSession,
    user: User,
) -> tuple[str, str]:

    # 1) Create tokens
    access_token = create_JWT_access_token(user_id=user.id)
    refresh_token = create_refresh_token()

    # 2) Persist refresh token (hashed) + expiry
    user.hashed_refresh_token = hash_refresh_token(refresh_token)
    user.refresh_token_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_LIFESPAN_DAYS)
    )
    user.updated_at = datetime.now(timezone.utc)

    await db.commit()

    # 3) Set cookies
    is_prod = settings.ENVIRONMENT == "production"

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        path="/",
        max_age=60 * settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        path="/",
        max_age=60 * 60 * 24 * settings.REFRESH_TOKEN_LIFESPAN_DAYS,
    )
    
    response.headers["X-Access-Token"] = access_token
    response.headers["X-Refresh-Token"] = refresh_token

    return access_token, refresh_token
