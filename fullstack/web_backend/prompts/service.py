"""
prompts/service.py
------------------
Business logic for Prompt — runs the vector search and persists results.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from prompts.models import Prompt
from prompts.schemas import PromptCreate
from search.schemas import MetadataFilters, SearchRequest
from search.service import SearchService


class PromptService:

    async def create(
        self,
        db: AsyncSession,
        space_id: str,
        data: PromptCreate,
        search_service: SearchService,
    ) -> Prompt:
        # Run vector search
        search_req = SearchRequest(
            query=data.query_text,
            filters=MetadataFilters(),
            top_k=data.top_k,
            use_llm=False,
        )
        search_resp = await search_service.search(search_req)

        # Serialise results to plain dict for JSONB storage
        results_dict = search_resp.model_dump()

        prompt = Prompt(
            space_id=space_id,
            query_text=data.query_text,
            results=results_dict,
        )
        db.add(prompt)
        await db.commit()
        await db.refresh(prompt)
        return prompt

    async def get_by_space(self, db: AsyncSession, space_id: str) -> List[Prompt]:
        result = await db.execute(
            select(Prompt)
            .where(Prompt.space_id == space_id)
            .order_by(Prompt.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_id(self, db: AsyncSession, prompt_id: str) -> Optional[Prompt]:
        result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
        return result.scalar_one_or_none()

    async def delete(self, db: AsyncSession, prompt_id: str) -> bool:
        prompt = await self.get_by_id(db, prompt_id)
        if not prompt:
            return False
        await db.delete(prompt)
        await db.commit()
        return True


prompt_service = PromptService()