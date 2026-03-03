"""
spaces/schemas.py
-----------------
Pydantic schemas for Space API.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SpaceCreate(BaseModel):
    title:       str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="")


class SpaceUpdate(BaseModel):
    title:       Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = None


class SpaceRead(BaseModel):
    id:          str
    user_id:     str
    title:       str
    description: str
    created_at:  datetime
    updated_at:  datetime

    model_config = {"from_attributes": True}


class SpaceList(BaseModel):
    spaces: list[SpaceRead]
    total:  int