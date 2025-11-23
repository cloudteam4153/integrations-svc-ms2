from __future__ import annotations
from typing import Dict, List, Optional, Any
from uuid import UUID
from fastapi.exceptions import HTTPException

from models.connection import Connection
from models.message import MessageCreate, MessageUpdate


# -----------------------------------------------------------------------------
# Gmail API Functions
# -----------------------------------------------------------------------------

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


async def gmail_sync_messages(
    connection: Connection,
    history_id: Optional[str] = None,
    full_sync: bool = False
):
    """
    Sync messages from Gmail API (used by sync jobs).
    """
    raise HTTPException(status_code=501, detail="Not Implemented: Gmail API Sync messages.")
    pass


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
