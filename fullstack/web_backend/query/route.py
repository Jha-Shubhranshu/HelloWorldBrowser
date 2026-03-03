"""
YouTube Semantic Search — Query API
=====================================
FastAPI backend that the frontend hits to retrieve semantically relevant
YouTube videos based on user-defined filters and a natural-language query.

Endpoints
---------
POST /search
    Body: { "query": str, "filters": {...}, "top_k": int }
    Returns ranked video chunks with metadata.

GET /health
    Simple liveness check.

Filter schema (all optional, ANDed together via Pinecone metadata filters)
--------------------------------------------------------------------------
{
  "channel_name":          "MrBeast",
  "transcript_language":   "English",
  "min_duration_seconds":  300,
  "max_duration_seconds":  3600,
  "upload_date_after":     "2024-01-01",   // ISO date string
  "upload_date_before":    "2025-01-01",
  "transcript_available":  true
}

Run
---
  uvicorn query_api:app --host 0.0.0.0 --port 8000 --reload
"""

import os
from datetime import datetime
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone
from pydantic import BaseModel, Field

load_dotenv()

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
OPENAI_API_KEY   = os.environ["OPENAI_API_KEY"]
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
PINECONE_INDEX   = os.getenv("PINECONE_INDEX", "youtube-semantic-search")
EMBED_MODEL      = os.getenv("EMBED_MODEL",    "text-embedding-3-small")
DEFAULT_TOP_K    = int(os.getenv("DEFAULT_TOP_K", "10"))

# ──────────────────────────────────────────────
# STARTUP  (clients instantiated once)
# ──────────────────────────────────────────────
embedder = OpenAIEmbeddings(model=EMBED_MODEL, openai_api_key=OPENAI_API_KEY)
pc       = Pinecone(api_key=PINECONE_API_KEY)
index    = pc.Index(PINECONE_INDEX)

app = FastAPI(
    title="YouTube Semantic Search API",
    description="Query YouTube video transcripts stored in Pinecone via natural language + structured filters.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# PYDANTIC MODELS
# ──────────────────────────────────────────────

class FilterParams(BaseModel):
    channel_name:          Optional[str]   = Field(None, description="Exact channel name match")
    transcript_language:   Optional[str]   = Field(None, description="e.g. 'English'")
    min_duration_seconds:  Optional[int]   = Field(None, ge=0)
    max_duration_seconds:  Optional[int]   = Field(None, ge=0)
    upload_date_after:     Optional[str]   = Field(None, description="ISO date string, e.g. '2024-01-01'")
    upload_date_before:    Optional[str]   = Field(None, description="ISO date string")
    transcript_available:  Optional[bool]  = Field(None)


class SearchRequest(BaseModel):
    query:   str            = Field(..., min_length=1, max_length=2000)
    filters: FilterParams   = Field(default_factory=FilterParams)
    top_k:   int            = Field(DEFAULT_TOP_K, ge=1, le=100)


class VideoChunkResult(BaseModel):
    video_id:             str
    video_url:            str
    video_title:          str
    channel_name:         str
    video_thumbnail_url:  str
    video_upload_date:    str
    video_length:         str
    transcript_language:  str
    chunk_text:           str
    chunk_index:          int
    total_chunks:         int
    score:                float


class SearchResponse(BaseModel):
    query:       str
    total_hits:  int
    results:     list[VideoChunkResult]
    latency_ms:  float


# ──────────────────────────────────────────────
# FILTER BUILDER
# ──────────────────────────────────────────────

def build_pinecone_filter(f: FilterParams) -> dict | None:
    """
    Translate FilterParams into a Pinecone metadata filter dict.
    Pinecone supports: $eq, $ne, $gt, $gte, $lt, $lte, $in, $and, $or
    """
    clauses: list[dict] = []

    if f.channel_name:
        clauses.append({"channel_name": {"$eq": f.channel_name}})

    if f.transcript_language:
        clauses.append({"transcript_language": {"$eq": f.transcript_language}})

    if f.transcript_available is not None:
        clauses.append({"transcript_available": {"$eq": "Yes" if f.transcript_available else "No"}})

    if f.min_duration_seconds is not None:
        clauses.append({"video_length_seconds": {"$gte": f.min_duration_seconds}})

    if f.max_duration_seconds is not None:
        clauses.append({"video_length_seconds": {"$lte": f.max_duration_seconds}})

    if f.upload_date_after:
        clauses.append({"video_upload_date": {"$gte": f.upload_date_after}})

    if f.upload_date_before:
        clauses.append({"video_upload_date": {"$lte": f.upload_date_before}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


# ──────────────────────────────────────────────
# DEDUPLICATION  (one result per video, best chunk)
# ──────────────────────────────────────────────

def deduplicate_by_video(matches: list[dict]) -> list[dict]:
    """
    When a query matches multiple chunks from the same video, keep only
    the highest-scoring chunk for that video so the result list is diverse.
    """
    seen: dict[str, dict] = {}
    for m in matches:
        vid = m["metadata"].get("video_id", m["id"])
        if vid not in seen or m["score"] > seen[vid]["score"]:
            seen[vid] = m
    # Re-sort by score descending
    return sorted(seen.values(), key=lambda x: x["score"], reverse=True)


# ──────────────────────────────────────────────
# ENDPOINTS
# ──────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    t0 = datetime.utcnow()

    # 1. Embed the query
    try:
        query_vector = embedder.embed_query(req.query)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Embedding failed: {exc}")

    # 2. Build metadata filter
    pinecone_filter = build_pinecone_filter(req.filters)

    # 3. Query Pinecone
    # We fetch more than top_k so deduplication still leaves enough results
    fetch_k = min(req.top_k * 4, 200)
    try:
        response = index.query(
            vector=query_vector,
            top_k=fetch_k,
            include_metadata=True,
            filter=pinecone_filter,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Pinecone query failed: {exc}")

    matches = response.get("matches", [])

    # 4. Deduplicate to one chunk per video
    deduped = deduplicate_by_video(matches)[: req.top_k]

    # 5. Shape results
    results: list[VideoChunkResult] = []
    for m in deduped:
        meta = m.get("metadata", {})
        results.append(
            VideoChunkResult(
                video_id=meta.get("video_id", ""),
                video_url=meta.get("video_url", ""),
                video_title=meta.get("video_title", ""),
                channel_name=meta.get("channel_name", ""),
                video_thumbnail_url=meta.get("video_thumbnail_url", ""),
                video_upload_date=meta.get("video_upload_date", ""),
                video_length=meta.get("video_length", ""),
                transcript_language=meta.get("transcript_language", ""),
                chunk_text=meta.get("chunk_text", ""),
                chunk_index=int(meta.get("chunk_index", 0)),
                total_chunks=int(meta.get("total_chunks", 1)),
                score=round(float(m.get("score", 0)), 4),
            )
        )

    latency = (datetime.utcnow() - t0).total_seconds() * 1000

    return SearchResponse(
        query=req.query,
        total_hits=len(results),
        results=results,
        latency_ms=round(latency, 1),
    )