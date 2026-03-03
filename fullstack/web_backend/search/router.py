"""
search/router.py
----------------
FastAPI router for all /search endpoints.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request

from search.schemas import SearchRequest, SearchResponse
from search.service import SearchService

log = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])


def get_search_service(request: Request) -> SearchService:
    """Pull the singleton SearchService from app state."""
    return request.app.state.search_service


@router.post("", response_model=SearchResponse)
async def search_videos(
    req: SearchRequest,
    service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """
    Semantic video search.

    Send a natural-language query plus optional metadata filters.
    Returns ranked video results with transcript snippets.
    """
    try:
        return await service.search(req)
    except Exception as e:
        log.exception(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", tags=["Meta"])
async def health():
    return {"status": "ok"}
