from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.concurrency import run_in_threadpool
from datetime import datetime
from typing import Optional, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from services.database import get_db

from google.oauth2.credentials import Credentials
from google.auth.exceptions import GoogleAuthError
from googleapiclient.discovery import build
from google.auth.transport.requests import Request as GoogleRequest

from services.sync.gmail import get_account_id
from services.sync.gmail import build_google_flow, Flow
from security import token_cipher
from config.settings import settings

from models.oauth import OAuthProvider, OAuth
from models.connection import Connection, ConnectionStatus


router = APIRouter(
    prefix="/oauth/callback",
    tags=["OAuth (Internal Use Only)"],
)

# Google Callback GET Endpoint (defined as per Google API spec; internal only)
@router.get("/google", status_code=200, name="google_oauth_callback")
async def google_oauth_callback(
    request: Request,
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

    current_redirect_uri = str(request.url_for("google_oauth_callback"))
    if current_redirect_uri not in settings.GOOGLE_REDIRECT_URIS:
        raise HTTPException(status_code=500, detail=f"Redirect URI not allowed: {current_redirect_uri}")
    flow: Flow = build_google_flow(current_redirect_uri)

    try:
        flow.fetch_token(code=code)
        credentials: Credentials = cast(Credentials, flow.credentials)
    except GoogleAuthError as e:
        await db.delete(oauth_state)
        await db.commit()
        raise HTTPException(status_code=400, detail=f"Failed to authenticate with Google. {e}")
    except Exception as e:
        await db.delete(oauth_state)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Unknown authentication error occured. {e}")


    # make sure token is good
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(GoogleRequest())

    # api request to get account email
    gmail = await run_in_threadpool(get_account_id, credentials)

    if gmail is None:
        raise HTTPException(status_code=404, detail="Failed to get Gmail account ID.")
    
    # add to db record
    connection.provider_account_id = gmail
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