from __future__ import annotations
from typing import Dict, List, Optional, Any
from uuid import UUID
from fastapi.exceptions import HTTPException
from fastapi import Request, status
from datetime import timezone
import base64
from email.mime.text import MIMEText
from email.message import EmailMessage

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError

from security import token_cipher
from config.settings import settings

from models.connection import Connection, ConnectionStatus
from models.message import MessageCreate, MessageUpdate
from models.sync import SyncType

# -----------------------------------------------------------------------------
# Gmail Helper Functions
# -----------------------------------------------------------------------------

def build_google_flow(active_redirect_uri: str, gmail_scopes: bool = False) -> Flow:
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

    all_scopes = []
    all_scopes.extend(settings.GOOGLE_LOGIN_SCOPES)
    if gmail_scopes: all_scopes.extend(settings.GMAIL_OAUTH_SCOPES)

    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=all_scopes
    )
    flow.redirect_uri = active_redirect_uri

    return flow


def connection_to_creds(conn: Connection) -> Credentials:
   
    token_row = {
        "token": token_cipher.decrypt(conn.access_token),
        "refresh_token": token_cipher.decrypt(conn.refresh_token),
        "token_uri": settings.GOOGLE_TOKEN_URI,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "scopes": conn.scopes,
    }
    if conn.access_token_expiry:
        expiry_dt = conn.access_token_expiry

        # Ensure tz-aware and in UTC
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        else:
            expiry_dt = expiry_dt.astimezone(timezone.utc)

        token_row["expiry"] = expiry_dt.isoformat().replace("+00:00", "Z")

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
    

def gmail_update_message(
    gmail_connection: Connection,
    external_message_id: str,
    message_update: MessageUpdate,
) -> dict[str, Any]:
    """
    Downstream blind executor.
    Takes message_update.label_ids and makes Gmail match it exactly.
    """

    if message_update.label_ids:
        desired_labels = message_update.label_ids

    try:
        creds = connection_to_creds(gmail_connection)
        gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)

        # 1) Get current labels from Gmail
        current_msg = gmail.users().messages().get(
            userId="me",
            id=external_message_id,
            format="minimal",
        ).execute()

        current_labels = set(current_msg.get("labelIds", []))
        desired_labels = set(desired_labels)

        # 2) Compute delta (required by Gmail API)
        add_ids = list(desired_labels - current_labels)
        remove_ids = list(current_labels - desired_labels)

        # 3) Apply delta
        return gmail.users().messages().modify(
            userId="me",
            id=external_message_id,
            body={
                "addLabelIds": add_ids,
                "removeLabelIds": remove_ids,
            },
        ).execute()

    except HttpError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gmail API error while modifying labels: {e}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while modifying labels: {e}",
        )


def gmail_delete_message(
    connection: Connection,
    external_message_id: str,
) -> bool:
    """
    Soft delete: move message to Trash via Gmail API.
    """
    try:
        creds = connection_to_creds(connection)
        gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)

        gmail.users().messages().trash(
            userId="me",
            id=external_message_id,
        ).execute()

        return True

    except HttpError as e:
        # Idempotent behavior: already trashed / missing
        if e.resp.status == 404:
            return True

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gmail API error while trashing message: {e}",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while trashing message: {e}",
        )


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


def gmail_create_message(
    creds: Credentials, 
    message_data: MessageCreate
):
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    def build_rfc5322_message(message_data) -> str:
        msg = EmailMessage()
        msg["To"] = message_data.to_address
        msg["From"] = message_data.from_address
        if getattr(message_data, "cc_address", None):
            msg["Cc"] = message_data.cc_address
        msg["Subject"] = message_data.subject or ""

        # Body (plain text). If you want HTML: msg.add_alternative(message_data.body, subtype="html")
        msg.set_content(message_data.body or "")

        raw_bytes = msg.as_bytes()
        return base64.urlsafe_b64encode(raw_bytes).decode("utf-8")

    raw = build_rfc5322_message(message_data)

    # Send from authenticated user ("me")
    resp = service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    return resp
