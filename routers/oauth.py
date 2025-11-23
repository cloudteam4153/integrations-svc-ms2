from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from config.settings import settings
from security import token_cipher

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from services.database import get_db

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.exceptions import GoogleAuthError
from googleapiclient.discovery import build

from models.oauth import OAuthProvider, OAuth
from models.connection import Connection, ConnectionStatus


router = APIRouter(
    prefix="/oauth/callback",
    tags=["OAuth"],
)

@router.get("/google")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    
    if error:
        raise HTTPException(status_code=400, detail=f"Authorization failed: {error}")

    result = await db.execute(
        select(OAuth).where(OAuth.state_token == state)
    )

    oauth_state = result.scalar_one_or_none()
    
    if oauth_state is None:
        raise HTTPException(status_code=400, detail="Invalid state token.")
    
    if oauth_state.expires_at < datetime.now():
        await db.delete(oauth_state)
        await db.commit()
        raise HTTPException(status_code=400, detail="State token expired.")
    
    result = await db.execute(
        select(Connection).where(Connection.id == oauth_state.connection_id) 
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found.")

    flow = Flow.from_client_secrets_file(
        settings.GOOGLE_CLIENT_SECRETS_FILE,
        scopes=settings.GMAIL_OAUTH_SCOPES,
        state=state
    )
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI

    try:
        flow.fetch_token(code=code)
        credentials: Credentials = Credentials(flow.credentials)
    except GoogleAuthError as e:
        await db.delete(oauth_state)
        await db.commit()
        raise HTTPException(status_code=400, detail=f"Failed to authenticate with Google. {e}")
    except Exception as e:
        await db.delete(oauth_state)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Unknown authentication error occured. {e}")
    

    connection.provider_account_id = credentials.account
    connection.status = ConnectionStatus.ACTIVE

    try:
        connection.access_token = token_cipher.encrypt(str(credentials.token))
        connection.refresh_token = token_cipher.encrypt(str(credentials.refresh_token))
    except Exception as e:
        raise Exception(e)
    
    connection.scopes = list(credentials.granted_scopes) if credentials.granted_scopes else []
    if credentials.expiry: # If none, assume token never expires (https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.credentials.html#google.oauth2.credentials.Credentials)
        connection.access_token_expiry = credentials.expiry

    connection.updated_at = datetime.now()
    connection.is_active = True


    await db.delete(oauth_state)
    await db.commit()
    await db.refresh(connection)

    return {
        "status": "success",
        "connection_id": connection.id
    }