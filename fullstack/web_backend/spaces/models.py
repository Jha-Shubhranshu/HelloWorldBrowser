"""
spaces/models.py
----------------
SQLModel table definitions for Space.
"""
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
import uuid

if TYPE_CHECKING:
    from prompts.models import Prompt


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Space(SQLModel, table=True):
    __tablename__ = "spaces"

    id:          str      = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id:     str      = Field(index=True)          # placeholder for future auth
    title:       str      = Field(max_length=120)
    description: str      = Field(default="")
    created_at:  datetime = Field(default_factory=utcnow)
    updated_at:  datetime = Field(default_factory=utcnow)

    prompts: List["Prompt"] = Relationship(back_populates="space")