"""
spaces/router.py
----------------
REST endpoints for Space CRUD.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from spaces.schemas import SpaceCreate, SpaceList, SpaceRead, SpaceUpdate
from spaces.service import space_service

router = APIRouter(prefix="/spaces", tags=["Spaces"])


@router.post("", response_model=SpaceRead, status_code=201)
async def create_space(
    data: SpaceCreate,
    db: AsyncSession = Depends(get_session),
):
    return await space_service.create(db, data)


@router.get("", response_model=SpaceList)
async def list_spaces(db: AsyncSession = Depends(get_session)):
    spaces = await space_service.get_all(db)
    return SpaceList(spaces=spaces, total=len(spaces))


@router.get("/{space_id}", response_model=SpaceRead)
async def get_space(space_id: str, db: AsyncSession = Depends(get_session)):
    space = await space_service.get_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    return space


@router.patch("/{space_id}", response_model=SpaceRead)
async def update_space(
    space_id: str,
    data: SpaceUpdate,
    db: AsyncSession = Depends(get_session),
):
    space = await space_service.update(db, space_id, data)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    return space


@router.delete("/{space_id}", status_code=204)
async def delete_space(space_id: str, db: AsyncSession = Depends(get_session)):
    deleted = await space_service.delete(db, space_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Space not found")