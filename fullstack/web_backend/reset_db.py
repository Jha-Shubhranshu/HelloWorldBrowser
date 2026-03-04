import asyncio
from sqlmodel import select, update
from ingestion.models import Channel
from core.database import AsyncSessionLocal

async def reset_channels():
    async with AsyncSessionLocal() as session:
        # Reset failed channels to discovered
        await session.execute(
            update(Channel)
            .where(Channel.status == "failed")
            .values(status="discovered")
        )
        await session.commit()
        print("Reset failed channels to 'discovered'.")

if __name__ == "__main__":
    asyncio.run(reset_channels())
