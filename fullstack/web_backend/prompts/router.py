"""
prompts/router.py
-----------------
REST endpoints for Prompt creation and retrieval under a Space.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from prompts.schemas import PromptCreate, PromptList, PromptRead
from prompts.service import prompt_service
from search.service import SearchService
from spaces.service import space_service

router = APIRouter(prefix="/spaces/{space_id}/prompts", tags=["Prompts"])


def get_search_service(request: Request) -> SearchService:
    return request.app.state.search_service


@router.post("", response_model=PromptRead, status_code=201)
async def create_prompt(
    space_id: str,
    data: PromptCreate,
    db: AsyncSession = Depends(get_session),
    search_svc: SearchService = Depends(get_search_service),
):
    space = await space_service.get_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    return await prompt_service.create(db, space_id, data, search_svc)


@router.get("", response_model=PromptList)
async def list_prompts(
    space_id: str,
    db: AsyncSession = Depends(get_session),
):
    space = await space_service.get_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    prompts = await prompt_service.get_by_space(db, space_id)
    return PromptList(prompts=prompts, total=len(prompts))


@router.delete("/{prompt_id}", status_code=204)
async def delete_prompt(
    space_id: str,
    prompt_id: str,
    db: AsyncSession = Depends(get_session),
):
    deleted = await prompt_service.delete(db, prompt_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Prompt not found")
