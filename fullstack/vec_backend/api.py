"""
api.py
------
Production-ready FastAPI server.

The frontend sends POST /query with a QueryRequest body and receives a
QueryResponse.  CORS, health-check, and structured error handling included.

Run:
    uvicorn api:app --host 0.0.0.0 --port 8000 --workers 2

Install extra dependencies:
    pip install fastapi uvicorn[standard]
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from query_engine import QueryRequest, QueryResponse, YouTubeQueryEngine

# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

# ── Shared engine instance (created once at startup) ──────────────────────────

_engine: YouTubeQueryEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    global _engine
    log.info("Starting up — initialising YouTubeQueryEngine …")
    _engine = YouTubeQueryEngine()
    log.info("Engine ready.")
    yield
    log.info("Shutting down.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="YouTube Semantic Search API",
    description=(
        "Vector-DB-backed semantic search over YouTube video transcripts. "
        "Send a natural-language query plus optional metadata filters to "
        "discover relevant channels and videos."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Allow your frontend origin(s) here
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # tighten in production: ["https://yourfrontend.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception(f"Unhandled exception on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs."},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
async def health():
    """Simple liveness probe."""
    return {"status": "ok"}


@app.post(
    "/query",
    response_model=QueryResponse,
    tags=["Search"],
    summary="Semantic video search",
    description="""
Search for YouTube videos by natural-language description, with optional
metadata filters.

### Filter examples
```json
{
  "query": "cooking tutorials for beginners",
  "filters": {
    "channel_name_in": ["Gordon Ramsay", "Babish Culinary Universe"],
    "transcript_language": "English",
    "video_upload_date_gte": "2023-01-01"
  },
  "top_k": 10,
  "use_llm": false
}
```

### With LLM summarisation
```json
{
  "query": "what do these channels say about sourdough bread?",
  "filters": {},
  "top_k": 5,
  "use_llm": true,
  "llm_question": "Summarise the key tips about sourdough bread from these videos."
}
```
""",
)
async def query_videos(req: QueryRequest) -> QueryResponse:
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialised yet.")
    try:
        return _engine.query(req)
    except Exception as e:
        log.exception(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/index/stats",
    tags=["Meta"],
    summary="Pinecone index statistics",
)
async def index_stats():
    """Returns vector count and namespace breakdown from Pinecone."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialised yet.")
    try:
        stats = _engine._index.describe_index_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))