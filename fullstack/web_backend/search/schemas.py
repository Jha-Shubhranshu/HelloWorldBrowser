"""
search/schemas.py
-----------------
Request and response models for the /search endpoint.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class MetadataFilters(BaseModel):
    channel_name:          Optional[str]       = Field(None, description="Exact channel name match")
    channel_name_in:       Optional[List[str]] = Field(None, description="Match any of these channel names")
    transcript_language:   Optional[str]       = Field(None, description="e.g. 'English'")
    video_upload_date_gte: Optional[str]       = Field(None, description="ISO date lower bound e.g. '2024-01-01'")
    video_upload_date_lte: Optional[str]       = Field(None, description="ISO date upper bound")


class SearchRequest(BaseModel):
    query:        str             = Field(...,  description="Natural-language description of desired videos")
    filters:      MetadataFilters = Field(default_factory=MetadataFilters)
    top_k:        int             = Field(5, ge=1, le=50)
    use_llm:      bool            = Field(False)
    llm_question: Optional[str]   = Field(None)


class VideoResult(BaseModel):
    video_url:            str
    video_title:          str
    channel_name:         str
    video_thumbnail_url:  str
    video_upload_date:    str
    video_length:         str
    score:                float
    snippet:              str
    channel_joining_date: str
    transcript_language:  str


class SearchResponse(BaseModel):
    query:         str
    results:       List[VideoResult]
    llm_answer:    Optional[str] = None
    total_matches: int