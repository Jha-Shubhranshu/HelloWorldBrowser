"""
YouTube Vector DB Ingestion Pipeline
======================================
Reads the final video_details CSV (output of the transcript extractor),
chunks transcripts, embeds them with OpenAI, and upserts into Pinecone.

Production features:
  - Idempotent: skips videos already in Pinecone (by vector ID)
  - Batched upserts with configurable batch size
  - Rich metadata stored alongside every chunk so the frontend can filter
    on channel, date, length, etc. without re-fetching the DB
  - Structured logging + progress file for resume-on-failure
  - Config-driven via environment variables (.env)
"""

import csv
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

# ──────────────────────────────────────────────
# CONFIG  (override via .env or environment)
# ──────────────────────────────────────────────
INPUT_CSV       = os.getenv("INPUT_CSV",       "tools/video_details3.csv")
PROGRESS_FILE   = os.getenv("PROGRESS_FILE",   "ingestion_progress.json")
LOG_FILE        = os.getenv("LOG_FILE",        "ingestion.log")

OPENAI_API_KEY  = os.environ["OPENAI_API_KEY"]
PINECONE_API_KEY = os.environ["PINECONE_API_KEY"]
PINECONE_INDEX  = os.getenv("PINECONE_INDEX",  "youtube-semantic-search")
PINECONE_CLOUD  = os.getenv("PINECONE_CLOUD",  "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")

EMBED_MODEL     = os.getenv("EMBED_MODEL",     "text-embedding-3-small")
EMBED_DIMS      = int(os.getenv("EMBED_DIMS",  "1536"))

CHUNK_SIZE      = int(os.getenv("CHUNK_SIZE",  "600"))
CHUNK_OVERLAP   = int(os.getenv("CHUNK_OVERLAP","80"))
UPSERT_BATCH    = int(os.getenv("UPSERT_BATCH","100"))

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def load_progress() -> dict:
    if Path(PROGRESS_FILE).exists():
        try:
            return json.loads(Path(PROGRESS_FILE).read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"ingested_video_ids": [], "failed_video_ids": []}


def save_progress(prog: dict) -> None:
    prog["last_updated"] = datetime.utcnow().isoformat()
    Path(PROGRESS_FILE).write_text(json.dumps(prog, indent=2), encoding="utf-8")


def extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url or "")
    return m.group(1) if m else None


def parse_duration_seconds(length: str) -> int:
    """Convert 'HH:MM:SS' / 'MM:SS' / 'SS' to total seconds."""
    parts = (length or "").strip().split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(parts[0])
    except ValueError:
        return 0


def build_metadata(row: dict, video_id: str, chunk_index: int, total_chunks: int) -> dict:
    """
    Build the Pinecone metadata dict for a single chunk.
    All filter-able fields are stored here so the frontend never needs
    to go back to the CSV — every semantic hit carries its own context.
    """
    return {
        # ── identifiers ──────────────────────────────────────────────────
        "video_id":             video_id,
        "video_url":            row.get("video_url", ""),
        "chunk_index":          chunk_index,
        "total_chunks":         total_chunks,
        # ── channel ──────────────────────────────────────────────────────
        "channel_name":         row.get("channel_name", ""),
        "channel_joining_date": row.get("channel_joining_date", ""),
        # ── video ────────────────────────────────────────────────────────
        "video_title":          row.get("video_title", ""),
        "video_thumbnail_url":  row.get("video_thumbnail_url", ""),
        "video_length":         row.get("video_length", ""),
        "video_length_seconds": parse_duration_seconds(row.get("video_length", "")),
        "video_upload_date":    row.get("video_upload_date", ""),
        # ── transcript ───────────────────────────────────────────────────
        "transcript_language":  row.get("transcript_language", ""),
        "transcript_available": row.get("transcript_available", "No"),
        # ── ingestion bookkeeping ─────────────────────────────────────────
        "ingested_at":          datetime.utcnow().isoformat(),
    }


def chunk_transcript(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


# ──────────────────────────────────────────────
# PINECONE SETUP
# ──────────────────────────────────────────────

def get_or_create_index(pc: Pinecone) -> Any:
    existing = [idx.name for idx in pc.list_indexes()]
    if PINECONE_INDEX not in existing:
        log.info(f"Creating Pinecone index '{PINECONE_INDEX}' …")
        pc.create_index(
            name=PINECONE_INDEX,
            dimension=EMBED_DIMS,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )
        # Wait until ready
        while not pc.describe_index(PINECONE_INDEX).status["ready"]:
            time.sleep(2)
        log.info("Index ready.")
    else:
        log.info(f"Index '{PINECONE_INDEX}' already exists.")
    return pc.Index(PINECONE_INDEX)


# ──────────────────────────────────────────────
# MAIN INGESTION LOOP
# ──────────────────────────────────────────────

def ingest():
    log.info("=" * 60)
    log.info("YouTube → Pinecone Ingestion Pipeline")
    log.info("=" * 60)

    # ── Load CSV ──
    input_path = Path(INPUT_CSV)
    if not input_path.exists():
        log.error(f"Input file not found: {INPUT_CSV}")
        return

    with open(input_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    log.info(f"Loaded {len(rows)} rows from {INPUT_CSV}")

    # ── Resume state ──
    prog = load_progress()
    ingested_ids: set[str] = set(prog.get("ingested_video_ids", []))
    failed_ids:   set[str] = set(prog.get("failed_video_ids",   []))

    # ── Clients ──
    embedder = OpenAIEmbeddings(
        model=EMBED_MODEL,
        openai_api_key=OPENAI_API_KEY,
    )
    pc    = Pinecone(api_key=PINECONE_API_KEY)
    index = get_or_create_index(pc)

    # ── Process videos ──
    pending_vectors: list[tuple[str, list[float], dict]] = []  # (id, vec, meta)

    def flush_batch():
        if not pending_vectors:
            return
        index.upsert(
            vectors=[{"id": vid, "values": vec, "metadata": meta}
                     for vid, vec, meta in pending_vectors],
        )
        log.info(f"  ↑ Upserted batch of {len(pending_vectors)} vectors.")
        pending_vectors.clear()

    total_chunks_ingested = 0

    for row_num, row in enumerate(rows, 1):
        url      = (row.get("video_url") or "").strip()
        video_id = extract_video_id(url)
        transcript = (row.get("video_caption") or "").strip()

        if not video_id:
            log.warning(f"Row {row_num}: Could not parse video ID from '{url}' — skipping.")
            continue

        if video_id in ingested_ids:
            log.debug(f"Row {row_num}: {video_id} already ingested — skipping.")
            continue

        if not transcript:
            log.info(f"Row {row_num}: {video_id} has no transcript — storing metadata-only vector.")
            # Create a stub text so the video still appears in the index
            transcript = (
                f"{row.get('video_title','')} "
                f"{row.get('channel_name','')} "
                f"{row.get('video_description','')}"
            ).strip()
            if not transcript:
                log.warning(f"Row {row_num}: {video_id} completely empty — skipping.")
                continue

        log.info(f"[{row_num}/{len(rows)}] {video_id} — {row.get('video_title','')[:60]}")

        try:
            chunks = chunk_transcript(transcript)
            log.info(f"  Chunked into {len(chunks)} piece(s).")

            texts   = chunks
            vectors = embedder.embed_documents(texts)

            for i, (text, vec) in enumerate(zip(texts, vectors)):
                chunk_id = f"{video_id}_chunk_{i}"
                meta     = build_metadata(row, video_id, i, len(chunks))
                meta["chunk_text"] = text          # store the text too for display
                pending_vectors.append((chunk_id, vec, meta))
                total_chunks_ingested += 1

            if len(pending_vectors) >= UPSERT_BATCH:
                flush_batch()

            ingested_ids.add(video_id)
            if video_id in failed_ids:
                failed_ids.discard(video_id)

        except Exception as exc:
            log.error(f"  ERROR processing {video_id}: {exc}", exc_info=True)
            failed_ids.add(video_id)

        # Save progress after every video
        prog["ingested_video_ids"] = list(ingested_ids)
        prog["failed_video_ids"]   = list(failed_ids)
        save_progress(prog)

    # Flush any remaining
    flush_batch()

    log.info("=" * 60)
    log.info(f"Done. {total_chunks_ingested} chunks across {len(ingested_ids)} videos ingested.")
    log.info(f"Failed videos: {len(failed_ids)}")
    log.info("=" * 60)


if __name__ == "__main__":
    ingest()