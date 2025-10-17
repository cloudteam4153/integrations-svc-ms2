from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field



class SyncBase(BaseModel):
    """Base model definition for a sync operation."""
    pass

class SyncCreate(SyncBase):
    """Creation payload for sync job"""
    pass

class SyncRead(SyncBase):
    """Read information about sync history and status."""
    pass
