"""
ingestion/service.py
--------------------
Business logic for Ingestion — handles deduplication and status tracking.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from ingestion.models import Channel, Video
from ingestion.schemas import ChannelCreate, VideoCreate

class IngestionService:

    async def register_channel(self, db: AsyncSession, data: ChannelCreate) -> Channel:
        # Deduplicate by channel_url
        result = await db.execute(
            select(Channel).where(Channel.channel_url == data.channel_url)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        channel = Channel(
            channel_name=data.channel_name,
            channel_url=data.channel_url,
            description=data.description,
            joining_date=data.joining_date,
            status="discovered"
        )
        db.add(channel)
        await db.commit()
        await db.refresh(channel)
        return channel

    async def register_video(self, db: AsyncSession, data: VideoCreate) -> Video:
        # Deduplicate by video_id
        result = await db.execute(
            select(Video).where(Video.video_id == data.video_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        video = Video(
            channel_id=data.channel_id,
            video_id=data.video_id,
            title=data.title,
            url=data.url,
            thumbnail_url=data.thumbnail_url,
            length=data.length,
            upload_date=data.upload_date,
            description=data.description,
            status="discovered"
        )
        db.add(video)
        await db.commit()
        await db.refresh(video)
        return video

    async def get_next_channel_to_scrape(self, db: AsyncSession) -> Optional[Channel]:
        # Randomly pick a channel to scrape to avoid bias towards one topic
        result = await db.execute(
            select(Channel)
            .where(Channel.status == "discovered")
            .order_by(func.random())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_next_video_to_process(self, db: AsyncSession) -> Optional[Video]:
        # Randomly pick a video to process for diverse transcript fetching
        result = await db.execute(
            select(Video)
            .where(Video.status.in_(["discovered", "failed"]))
            .order_by(func.random())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_channel_status(self, db: AsyncSession, channel_id: str, status: str) -> None:
        result = await db.execute(select(Channel).where(Channel.id == channel_id))
        channel = result.scalar_one_or_none()
        if channel:
            channel.status = status
            if status == "scraped":
                channel.last_scraped = datetime.now()
            db.add(channel)
            await db.commit()

    async def update_video_status(
        self, 
        db: AsyncSession, 
        video_id: str, 
        status: str, 
        transcript: Optional[str] = None, 
        transcript_language: Optional[str] = None,
        description: Optional[str] = None,
        upload_date: Optional[str] = None,
        category: Optional[str] = None
    ) -> None:
        result = await db.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()
        if video:
            video.status = status
            if transcript:
                video.transcript = transcript
            if transcript_language:
                video.transcript_language = transcript_language
            if description:
                video.description = description
            if upload_date:
                video.upload_date = upload_date
            if category:
                video.category = category
            video.last_attempt = datetime.now()
            db.add(video)
            await db.commit()

ingestion_service = IngestionService()
