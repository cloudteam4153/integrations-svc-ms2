from __future__ import annotations
from typing import Dict, List, Optional, Any
from uuid import UUID
from fastapi.exceptions import HTTPException
from fastapi import Request
from datetime import datetime, timezone
import base64

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import Flow

from security import token_cipher
from config.settings import settings

from models.connection import Connection
from models.message import MessageCreate, MessageUpdate
from models.sync import SyncType

# -----------------------------------------------------------------------------
# Gmail Helper Functions
# -----------------------------------------------------------------------------

def build_google_flow(active_redirect_uri: str) -> Flow:
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "project_id": settings.GOOGLE_PROJECT_ID,
            "auth_uri": settings.GOOGLE_AUTH_URI,
            "token_uri": settings.GOOGLE_TOKEN_URI,
            "auth_provider_x509_cert_url": settings.GOOGLE_AUTH_PROVIDER_X509_CERT_URL,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uris": settings.GOOGLE_REDIRECT_URIS,
        }
    }

    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=settings.GMAIL_OAUTH_SCOPES
    )
    flow.redirect_uri = active_redirect_uri

    return flow

def connection_to_creds(conn: Connection) -> Credentials:
    expiry = None
    if conn.access_token_expiry:
        expiry = conn.access_token_expiry.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    token_row = {
        "token": token_cipher.decrypt(conn.access_token),
        "refresh_token": token_cipher.decrypt(conn.refresh_token),
        "token_uri": settings.GOOGLE_TOKEN_URI,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "scopes": conn.scopes,
        "expiry": expiry,
    }

    creds: Credentials = Credentials.from_authorized_user_info(token_row)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        else:
            raise RuntimeError("Invalid Google credentials: cannot refresh")

    return creds


def get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return None


def extract_body(payload):
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode()

    for part in payload.get("parts", []):
        if part["mimeType"] in ("text/plain", "text/html"):
            if part["body"].get("data"):
                return base64.urlsafe_b64decode(
                    part["body"]["data"]
                ).decode()

    return None



# -----------------------------------------------------------------------------
# Gmail API Functions
# -----------------------------------------------------------------------------

def get_account_id(
    creds: Credentials
) -> str | None:
    
    service = build("gmail", "v1", credentials=creds)
    
    profile = service.users().getProfile(userId="me").execute()

    email = str(profile["emailAddress"])
    if email:
        return email
    else:
        return None 
    

async def gmail_create_message(
    connection: Connection, 
    message_data: MessageCreate
):
    """Send a new message via Gmail API"""
    raise HTTPException(status_code=501, detail="Not Implemented: Gmail API Send message.")
    pass


async def gmail_update_message(
    connection: Connection,
    external_message_id: str,
    message_update: MessageUpdate
):
    """
    Update a message via Gmail API (labels, etc.).
    """
    raise HTTPException(status_code=501, detail="Not Implemented: Gmail API Update message.")
    pass


async def gmail_delete_message(
    connection: Connection,
    external_message_id: str
):
    """
    Delete a message via Gmail API.
    """
    raise HTTPException(status_code=501, detail="Not Implemented: Gmail API Delete message.")
    pass


async def gmail_bulk_delete_messages(
    connection: Connection,
    external_message_ids: List[str]
):
    """
    Bulk delete messages via Gmail API.
    """
    raise HTTPException(status_code=501, detail="Not Implemented: Gmail API Bulk Delete messages.")
    pass


async def gmail_get_message(
    connection: Connection,
    external_message_id: str,
    format: str = "full"
):
    """
    Retrieve a specific message from Gmail API.
    """
    raise HTTPException(status_code=501, detail="Not Implemented: Gmail API Get message.")
    pass


async def gmail_list_messages(
    connection: Connection,
    query: Optional[str] = None,
    label_ids: Optional[List[str]] = None,
    max_results: int = 100,
    page_token: Optional[str] = None
):
    """
    List messages from Gmail API with optional filtering.
    """
    raise HTTPException(status_code=501, detail="Not Implemented: Gmail API List messages.")
    pass


def gmail_sync_messages(
    creds: Credentials,
    sync_type: SyncType,
    last_history_id: Optional[str] = None,
):
    """
    Sync messages from Gmail API (used by sync jobs).
    """
    service = build("gmail", "v1", credentials=creds)
    messages = []
    new_history_id = last_history_id

    # Full sync
    if sync_type == SyncType.FULL or not last_history_id:
        page_token = None

        while True:
            res = service.users().messages().list(
                userId="me",
                maxResults=500,
                pageToken=page_token,
            ).execute()

            msg_ids = res.get("messages", [])
            messages.extend(msg_ids)

            page_token = res.get("nextPageToken")
            if not page_token:
                break

        # Get newest history ID
        profile = service.users().getProfile(userId="me").execute()
        new_history_id = profile["historyId"]

    # incremental sync
    else:
        page_token = None

        while True:
            res = service.users().history().list(
                userId="me",
                startHistoryId=last_history_id,
                pageToken=page_token,
            ).execute()

            for h in res.get("history", []):
                for m in h.get("messagesAdded", []):
                    messages.append(m["message"])

            page_token = res.get("nextPageToken")
            if not page_token:
                break

            new_history_id = res.get("historyId", new_history_id)

    # get full messages
    parsed_messages = []
    for m in messages:
        full = service.users().messages().get(
            userId="me",
            id=m["id"],
            format="full"
        ).execute()

        headers = full["payload"]["headers"]

        parsed = {
            "id": full.get("id"),
            "threadId": full.get("threadId"),
            "labelIds": full.get("labelIds"),
            "snippet": full.get("snippet"),
            "historyId": full.get("historyId"),
            "internalDate": full.get("internalDate"),
            "sizeEstimate": full.get("sizeEstimate"),

            "from": get_header(headers, "From"),
            "to": get_header(headers, "To"),
            "cc": get_header(headers, "Cc"),
            "subject": get_header(headers, "Subject"),
            "body": extract_body(full["payload"]),
        }

        parsed_messages.append(parsed)

    
    return {
        "messages": parsed_messages,
        "messages_synced": len(parsed_messages),
        "messages_new": len(parsed_messages),
        "messages_updated": 0,
        "last_history_id": new_history_id,
    }


# -----------------------------------------------------------------------------
# Connection Token Management
# -----------------------------------------------------------------------------

async def refresh_gmail_tokens(connection: Connection):
    """
    Refresh expired Gmail access tokens.
    """
    raise HTTPException(status_code=501, detail="Not Implemented: Gmail API Refresh Tokens.")
    pass


async def validate_gmail_connection(connection: Connection):
    """
    Validate that a Gmail connection is still active and has valid tokens.
    """
    raise HTTPException(status_code=501, detail="Not Implemented: Gmail API validate connection.")
    pass


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def build_gmail_client(access_token: str):
    """
    Build Gmail API client with access token.
    """
    raise HTTPException(status_code=501, detail="Not Implemented: Gmail API build client.")
    pass
