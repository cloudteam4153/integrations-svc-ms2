from fastapi import Request
from typing import List
from models.hateoas import HATEOASLink

from models.user import User, UserRead
from models.connection import Connection, ConnectionRead
from models.message import Message, MessageRead
from models.sync import Sync, SyncRead




# -----------------------------------------------------------------------------
# User HATEOAS
# -----------------------------------------------------------------------------
def build_user_links(request: Request, user: User) -> List[HATEOASLink]:
    return [
        HATEOASLink(
            rel="self",
            href=str(request.url_for("get_user", user_id=user.id)),
            method="GET",
        ),
        HATEOASLink(
            rel="update",
            href=str(request.url_for("update_user", user_id=user.id)),
            method="PATCH",
        ),
        HATEOASLink(
            rel="delete",
            href=str(request.url_for("delete_user", user_id=user.id)),
            method="DELETE",
        ),
        HATEOASLink(
            rel="collection",
            href=str(request.url_for("list_users")),
            method="GET",
        ),
    ]

def hateoas_user(request: Request, user: User):
    links: List[HATEOASLink] = build_user_links(request, user)

    user_read = UserRead.model_validate(user)
    if links:
        user_read = user_read.model_copy(update={"links": links})

    return user_read


# -----------------------------------------------------------------------------
# Connection HATEOAS
# -----------------------------------------------------------------------------
def build_connection_links(request: Request, connection: Connection) -> List[HATEOASLink]:
    return [
        HATEOASLink(
            rel="create",
            href=str(request.url_for("create_connection")),
            method="POST"
        ),
        HATEOASLink(
            rel="get",
            href=str(request.url_for("get_connection", connection_id=connection.id)),
            method="GET",
        ),
        HATEOASLink(
            rel="update",
            href=str(request.url_for("update_connection", connection_id=connection.id)),
            method="PATCH",
        ),
        HATEOASLink(
            rel="delete",
            href=str(request.url_for("delete_connection", connection_id=connection.id)),
            method="DELETE",
        ),
        HATEOASLink(
            rel="collection",
            href=str(request.url_for("list_connections")),
            method="GET",
        ),
        HATEOASLink(
            rel="test",
            href=str(request.url_for("test_connection", connection_id=connection.id)),
            method="POST",
        ),
        HATEOASLink(
            rel="refresh/reconnect",
            href=str(request.url_for("refresh_connection", connection_id=connection.id)),
            method="POST",
        ),
    ]

def hateoas_connection(request: Request, connection: Connection):
    links: List[HATEOASLink] = build_connection_links(request, connection)

    conn_read = ConnectionRead.model_validate(connection)
    if links:
        conn_read = conn_read.model_copy(update={"links": links})

    return conn_read


# -----------------------------------------------------------------------------
# Message HATEOAS
# -----------------------------------------------------------------------------
def build_message_links(request: Request, message: Message) -> List[HATEOASLink]:
    return [
        HATEOASLink(
            rel="self",
            href=str(request.url_for("get_message", message_id=message.id)),
            method="GET",
        ),
        HATEOASLink(
            rel="update",
            href=str(request.url_for("update_message", message_id=message.id)),
            method="PATCH",
        ),
        HATEOASLink(
            rel="delete",
            href=str(request.url_for("delete_message", message_id=message.id)),
            method="DELETE",
        ),
        HATEOASLink(
            rel="collection",
            href=str(request.url_for("list_messages")),
            method="GET",
        ),
        HATEOASLink(
            rel="create",
            href=str(request.url_for("create_message")),
            method="POST",
        ),
    ]

def hateoas_message(request: Request, message: Message):
    links: List[HATEOASLink] = build_message_links(request, message)

    message_read = MessageRead.model_validate(message)
    if links:
        message_read = message_read.model_copy(update={"links": links})

    return message_read


# -----------------------------------------------------------------------------
# Sync HATEOAS
# -----------------------------------------------------------------------------
def build_sync_links(request: Request, sync: Sync) -> List[HATEOASLink]:
    return [
        HATEOASLink(
            rel="self",
            href=str(request.url_for("get_sync", sync_id=sync.id)),
            method="GET",
        ),
        HATEOASLink(
            rel="status",
            href=str(request.url_for("get_sync_status", sync_id=sync.id)),
            method="GET",
        ),
        HATEOASLink(
            rel="update",
            href=str(request.url_for("update_sync", sync_id=sync.id)),
            method="PATCH",
        ),
        HATEOASLink(
            rel="delete",
            href=str(request.url_for("delete_sync", sync_id=sync.id)),
            method="DELETE",
        ),
        HATEOASLink(
            rel="collection",
            href=str(request.url_for("list_syncs")),
            method="GET",
        ),
        HATEOASLink(
            rel="create",
            href=str(request.url_for("create_sync")),
            method="POST",
        ),
    ]

def hateoas_sync(request: Request, sync: Sync):
    links: List[HATEOASLink] = build_sync_links(request, sync)

    sync_read = SyncRead.model_validate(sync)
    if links:
        sync_read = sync_read.model_copy(update={"links": links})

    return sync_read