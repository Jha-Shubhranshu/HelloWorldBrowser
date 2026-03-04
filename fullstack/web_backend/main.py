"""
main.py
-------
FastAPI application entry point.

Run:
    uvicorn main:app --host 127.0.0.1 --port 8000 --reload

Install:
    pip install fastapi uvicorn[standard] langchain-openai pinecone \
                langchain-text-splitters python-dotenv pydantic-settings \
                sqlmodel asyncpg "sqlalchemy[asyncio]"
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.database import init_db
from search.router import router as search_router
from search.service import SearchService
from spaces.router import router as spaces_router
from prompts.router import router as prompts_router
from ingestion.router import router as ingestion_router

# Import models so SQLModel registers them before create_all
import spaces.models      # noqa: F401
import prompts.models     # noqa: F401
import ingestion.models   # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("Initialising database …")
    await init_db()
    log.info("Initialising SearchService …")
    app.state.search_service = SearchService(settings)
    log.info("Startup complete.")
    yield
    log.info("Shutting down.")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Channel Scout API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(search_router)
    app.include_router(spaces_router)
    app.include_router(prompts_router)
    app.include_router(ingestion_router)

    return app


app = create_app()
