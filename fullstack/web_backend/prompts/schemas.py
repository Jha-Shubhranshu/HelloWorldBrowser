"""
prompts/schemas.py
------------------
Pydantic schemas for Prompt API.
"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field


class PromptCreate(BaseModel):
    query_text:     str  = Field(..., min_length=1, max_length=1000)
    top_k:          int  = Field(5, ge=1, le=50)
    scoped_results: bool = Field(False)


class PromptRead(BaseModel):
    id:         str
    space_id:   str
    query_text: str
    results:    Optional[Any] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PromptList(BaseModel):
    prompts: list[PromptRead]
    total:   int