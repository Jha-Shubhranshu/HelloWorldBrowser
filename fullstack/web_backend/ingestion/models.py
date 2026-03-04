"""
ingestion/models.py
-------------------
SQLModel table definitions for Channels and Videos to track processing status.
"""
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
import uuid

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Channel(SQLModel, table=True):
    __tablename__ = "ingestion_channels"

    id:             str      = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    channel_name:   str      = Field(index=True, unique=True)
    channel_url:    str      = Field(unique=True)
    description:    Optional[str] = None
    joining_date:   Optional[str] = None
    
    # Processing status
    status:         str      = Field(default="discovered")  # discovered, scraping_videos, scraped, failed
    last_scraped:   Optional[datetime] = None
    created_at:     datetime = Field(default_factory=utcnow)
    
    videos: List["Video"] = Relationship(back_populates="channel")

class Video(SQLModel, table=True):
    __tablename__ = "ingestion_videos"

    id:             str      = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    channel_id:     str      = Field(foreign_key="ingestion_channels.id", index=True)
    video_id:       str      = Field(index=True, unique=True)  # YouTube's 11-char ID
    title:          str
    url:            str      = Field(unique=True)
    thumbnail_url:  Optional[str] = None
    length:         Optional[str] = None
    upload_date:    Optional[str] = None
    
    # Processing status
    status:         str      = Field(default="discovered")  # discovered, processing_transcript, processed, failed
    transcript:     Optional[str] = None
    vector_id:      Optional[str] = None  # Reference to Pinecone ID
    
    last_attempt:   Optional[datetime] = None
    created_at:     datetime = Field(default_factory=utcnow)
    
    channel: Channel = Relationship(back_populates="videos")
