from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field



class ConnectionBase(BaseModel):
    """Base model definition for an external resource connection."""
    pass

class ConnectionCreate(ConnectionBase):
    """Creation payload for an connection"""
    pass

class ConnectionRead(ConnectionBase):
    """Read information about an external resource connection"""
    pass

class ConnectionUpdate(BaseModel):
    """Partial update of a connection; ID is taken from path"""
    pass

