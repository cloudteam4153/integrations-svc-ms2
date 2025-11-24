from fastapi import Request
from typing import List
from models.hateoas import HATEOASLink
from models import User, ConnectionModel, Sync, Message
from models.user import UserRead


# User HATEOAS Link Builder
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


# # Connection HATEOAS Link Builder
# def build_connection_links(request: Request, connection: ConnectionModel) -> List[Link]:
#     return [
#         Link(
#             rel="self",
#             href=str(request.url_for("get_user", user_id=user.id)),
#             method="GET",
#         ),
#         Link(
#             rel="update",
#             href=str(request.url_for("update_user", user_id=user.id)),
#             method="PUT",
#         ),
#         Link(
#             rel="delete",
#             href=str(request.url_for("delete_user", user_id=user.id)),
#             method="DELETE",
#         ),
#         Link(
#             rel="collection",
#             href=str(request.url_for("list_users")),
#             method="GET",
#         ),
#     ]