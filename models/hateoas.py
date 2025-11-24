from pydantic import BaseModel

class HATEOASLink(BaseModel):
    rel: str          # "self", "update", "delete"
    href: str           # absolute URL
    method: str       # "GET", "POST", "PUT", "DELETE"
