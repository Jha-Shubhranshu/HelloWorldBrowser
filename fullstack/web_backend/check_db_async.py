import asyncio
from sqlmodel import select
from ingestion.models import Channel, Video
from core.database import AsyncSessionLocal

async def check_db():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Channel))
        channels = result.scalars().all()
        
        result = await session.execute(select(Video))
        videos = result.scalars().all()
        
        print(f"Total Channels: {len(channels)}")
        print(f"Total Videos: {len(videos)}")
        
        for c in channels:
            print(f"Channel: {c.channel_name}, Status: {c.status}")

if __name__ == "__main__":
    asyncio.run(check_db())
