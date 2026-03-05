"""
ingestion/router.py
-------------------
REST endpoints for Ingestion — handles channel and video registration.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_session
from ingestion.schemas import ChannelCreate, VideoCreate, ChannelRead, VideoRead
from ingestion.service import ingestion_service

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])

@router.post("/channels", response_model=ChannelRead, status_code=201)
async def register_channel(
    data: ChannelCreate,
    db: AsyncSession = Depends(get_session),
):
    return await ingestion_service.register_channel(db, data)

@router.post("/videos", response_model=VideoRead, status_code=201)
async def register_video(
    data: VideoCreate,
    db: AsyncSession = Depends(get_session),
):
    return await ingestion_service.register_video(db, data)

@router.get("/channels/next", response_model=Optional[ChannelRead])
async def get_next_channel(
    db: AsyncSession = Depends(get_session),
):
    return await ingestion_service.get_next_channel_to_scrape(db)

@router.get("/videos/next", response_model=Optional[VideoRead])
async def get_next_video(
    db: AsyncSession = Depends(get_session),
):
    return await ingestion_service.get_next_video_to_process(db)

@router.patch("/channels/{channel_id}/status")
async def update_channel_status(
    channel_id: str,
    status: str,
    db: AsyncSession = Depends(get_session),
):
    await ingestion_service.update_channel_status(db, channel_id, status)
    return {"status": "ok"}

@router.patch("/videos/{video_id}/status")
async def update_video_status(
    video_id: str,
    status: str,
    transcript: Optional[str] = None,
    transcript_language: Optional[str] = None,
    description: Optional[str] = None,
    upload_date: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_session),
):
    await ingestion_service.update_video_status(
        db, video_id, status, transcript, transcript_language, description, upload_date, category
    )
    return {"status": "ok"}
