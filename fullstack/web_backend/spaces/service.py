"""
spaces/service.py
-----------------
Business logic for Space CRUD.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from spaces.models import Space
from spaces.schemas import SpaceCreate, SpaceUpdate


ANONYMOUS_USER = "anonymous"   # replaced when auth is added


class SpaceService:

    async def create(self, db: AsyncSession, data: SpaceCreate) -> Space:
        space = Space(
            user_id=ANONYMOUS_USER,
            title=data.title,
            description=data.description,
        )
        db.add(space)
        await db.commit()
        await db.refresh(space)
        return space

    async def get_all(self, db: AsyncSession) -> List[Space]:
        result = await db.execute(
            select(Space).order_by(Space.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_id(self, db: AsyncSession, space_id: str) -> Optional[Space]:
        result = await db.execute(select(Space).where(Space.id == space_id))
        return result.scalar_one_or_none()

    async def update(self, db: AsyncSession, space_id: str, data: SpaceUpdate) -> Optional[Space]:
        space = await self.get_by_id(db, space_id)
        if not space:
            return None
        if data.title is not None:
            space.title = data.title
        if data.description is not None:
            space.description = data.description
        space.updated_at = datetime.now(timezone.utc)
        db.add(space)
        await db.commit()
        await db.refresh(space)
        return space

    async def delete(self, db: AsyncSession, space_id: str) -> bool:
        space = await self.get_by_id(db, space_id)
        if not space:
            return False
        await db.delete(space)
        await db.commit()
        return True


space_service = SpaceService()