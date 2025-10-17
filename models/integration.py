from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field



class IntegrationBase(BaseModel):
    """Base model definition for an external resource integration."""
    pass

class IntegrationCreate(IntegrationBase):
    """Creation payload for an integration"""
    pass

class IntegrationRead(IntegrationBase):
    """Read information about an external resource integration"""
    pass

class IntegrationUpdate(BaseModel):
    """Partial update of an integration; ID is taken from path"""
    pass

