"""
prompts/models.py
-----------------
SQLModel table definition for Prompt.
Results stored as JSONB for flexible video metadata.
"""
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field, Relationship
import uuid

if TYPE_CHECKING:
    from spaces.models import Space


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Prompt(SQLModel, table=True):
    __tablename__ = "prompts"

    id:          str      = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    space_id:    str      = Field(foreign_key="spaces.id", index=True)
    query_text:  str      = Field(max_length=1000)
    results:     Optional[dict] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True)
    )
    created_at:  datetime = Field(default_factory=utcnow)

    space: Optional["Space"] = Relationship(back_populates="prompts")