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