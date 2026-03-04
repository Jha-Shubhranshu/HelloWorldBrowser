"""
ingestion/schemas.py
--------------------
Pydantic schemas for Ingestion API.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

class VideoBase(BaseModel):
    video_id: str
    title: str
    url: str
    thumbnail_url: Optional[str] = None
    length: Optional[str] = None
    upload_date: Optional[str] = None

class VideoCreate(VideoBase):
    channel_id: str

class VideoRead(VideoBase):
    id: str
    channel_id: str
    status: str
    transcript: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChannelBase(BaseModel):
    channel_name: str
    channel_url: str
    description: Optional[str] = None
    joining_date: Optional[str] = None

class ChannelCreate(ChannelBase):
    pass

class ChannelRead(ChannelBase):
    id: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True
