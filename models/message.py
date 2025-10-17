from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field



class MessageBase(BaseModel):
    """Base model definition for a message."""
    pass

class MessageCreate(MessageBase):
    """Creation payload for a message"""
    pass

class MessageRead(MessageBase):
    """Read information about a message."""
    pass

class MessageUpdate(BaseModel):
    """Partial update of a message; ID is taken from path. Only applicable for 
        services that support editing messages."""
    pass
