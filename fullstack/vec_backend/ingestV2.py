"""
ingest.py
---------
Production-grade ingestion pipeline.

Reads the final scraped CSV (video_details.csv produced by your third script),
chunks every transcript, embeds chunks with OpenAI, and upserts them into
Pinecone with rich metadata so the frontend can filter semantically.

Usage:
    python ingest.py

Install dependencies first:
    pip install openai pinecone-client langchain langchain-openai langchain-community \
                tiktoken pandas python-dotenv tqdm
"""

import os
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

# LangChain
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

# Pinecone v3+
from pinecone import Pinecone, ServerlessSpec

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG  (override via .env or environment variables)
# ──────────────────────────────────────────────────────────────────────────────

load_dotenv()

INPUT_CSV         = os.getenv("INPUT_CSV", "video_details.csv")
PINECONE_API_KEY  = os.getenv("PINECONE_API_KEY", "YOUR_PINECONE_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY",   "YOUR_OPENAI_API_KEY")
INDEX_NAME        = os.getenv("PINECONE_INDEX",    "youtube-transcripts")
EMBEDDING_MODEL   = os.getenv("EMBEDDING_MODEL",   "text-embedding-3-small")
EMBEDDING_DIM     = int(os.getenv("EMBEDDING_DIM", "1536"))  # 1536 for text-embedding-3-small

# Chunking
CHUNK_SIZE        = int(os.getenv("CHUNK_SIZE",    "800"))
CHUNK_OVERLAP     = int(os.getenv("CHUNK_OVERLAP", "100"))

# Pinecone upsert batch
UPSERT_BATCH_SIZE = int(os.getenv("UPSERT_BATCH_SIZE", "100"))

# Pinecone cloud / region (Serverless)
PINECONE_CLOUD    = os.getenv("PINECONE_CLOUD",  "aws")
PINECONE_REGION   = os.getenv("PINECONE_REGION", "us-east-1")

# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("ingest.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _stable_id(video_url: str, chunk_index: int) -> str:
    """Deterministic vector ID: sha256 of (url + chunk index)."""
    raw = f"{video_url}::chunk::{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:48]


def _clean(text: Any) -> str:
    if not text or (isinstance(text, float)):
        return ""
    return str(text).strip()


def _safe_metadata(value: Any, fallback: str = "") -> str:
    """Pinecone metadata values must be strings / numbers / booleans."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return fallback
    return str(value).strip()


# ──────────────────────────────────────────────────────────────────────────────
# STEP 1 – LOAD CSV
# ──────────────────────────────────────────────────────────────────────────────

def load_csv(path: str) -> pd.DataFrame:
    log.info(f"Loading input CSV: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    log.info(f"  Rows loaded       : {len(df)}")
    log.info(f"  Columns           : {list(df.columns)}")

    # Keep only rows that have a transcript
    mask = df["transcript_available"].str.strip().str.lower() == "yes"
    df = df[mask].reset_index(drop=True)
    log.info(f"  Rows with transcript: {len(df)}")
    return df


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 – CHUNK TRANSCRIPTS
# ──────────────────────────────────────────────────────────────────────────────

def build_chunks(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Split every transcript into overlapping chunks.
    Each chunk carries full metadata for Pinecone filtering.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks: List[Dict[str, Any]] = []

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Chunking"):
        transcript = _clean(row.get("video_caption", ""))
        if not transcript:
            continue

        video_url       = _clean(row.get("video_url", ""))
        channel_name    = _clean(row.get("channel_name", ""))
        video_title     = _clean(row.get("video_title", ""))
        channel_desc    = _clean(row.get("channel_description", ""))
        joining_date    = _clean(row.get("channel_joining_date", ""))
        video_desc      = _clean(row.get("video_description", ""))
        video_length    = _clean(row.get("video_length", ""))
        video_thumb     = _clean(row.get("video_thumbnail_url", ""))
        upload_date     = _clean(row.get("video_upload_date", ""))
        trans_lang      = _clean(row.get("transcript_language", ""))

        pieces = splitter.split_text(transcript)

        for i, piece in enumerate(pieces):
            chunk_id = _stable_id(video_url, i)

            all_chunks.append({
                "id":   chunk_id,
                "text": piece,
                "metadata": {
                    # ── Identifiers ──────────────────────────────────────
                    "video_url":               video_url,
                    "video_title":             video_title,
                    "channel_name":            channel_name,
                    # ── Channel info ─────────────────────────────────────
                    "channel_description":     channel_desc[:500],   # Pinecone metadata cap
                    "channel_joining_date":    joining_date,
                    # ── Video info ───────────────────────────────────────
                    "video_description":       video_desc[:500],
                    "video_length":            video_length,
                    "video_thumbnail_url":     video_thumb,
                    "video_upload_date":       upload_date,
                    "transcript_language":     trans_lang,
                    # ── Chunk position ───────────────────────────────────
                    "chunk_index":             i,
                    "total_chunks":            len(pieces),
                },
            })

    log.info(f"Total chunks produced: {len(all_chunks)}")
    return all_chunks


# ──────────────────────────────────────────────────────────────────────────────
# STEP 3 – EMBED + UPSERT
# ──────────────────────────────────────────────────────────────────────────────

def get_or_create_index(pc: Pinecone) -> Any:
    existing = [idx.name for idx in pc.list_indexes()]
    if INDEX_NAME not in existing:
        log.info(f"Creating Pinecone index '{INDEX_NAME}' …")
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud=PINECONE_CLOUD, region=PINECONE_REGION),
        )
        log.info("Index created.")
    else:
        log.info(f"Index '{INDEX_NAME}' already exists.")
    return pc.Index(INDEX_NAME)


def embed_and_upsert(chunks: List[Dict[str, Any]], index: Any) -> None:
    embeddings_model = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
    )

    # Process in batches to respect OpenAI rate limits
    for batch_start in tqdm(
        range(0, len(chunks), UPSERT_BATCH_SIZE),
        desc="Embedding & upserting",
    ):
        batch = chunks[batch_start : batch_start + UPSERT_BATCH_SIZE]
        texts = [c["text"] for c in batch]

        try:
            vectors = embeddings_model.embed_documents(texts)
        except Exception as e:
            log.error(f"Embedding failed for batch starting at {batch_start}: {e}")
            continue

        upsert_payload = [
            {
                "id":       chunk["id"],
                "values":   vec,
                "metadata": {**chunk["metadata"], "text": chunk["text"]},
            }
            for chunk, vec in zip(batch, vectors)
        ]

        try:
            index.upsert(vectors=upsert_payload)
        except Exception as e:
            log.error(f"Upsert failed for batch starting at {batch_start}: {e}")

    log.info("All chunks embedded and upserted.")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 60)
    log.info("YouTube Transcript Ingestion Pipeline")
    log.info("=" * 60)

    # Validate secrets
    for var, val in [("PINECONE_API_KEY", PINECONE_API_KEY), ("OPENAI_API_KEY", OPENAI_API_KEY)]:
        if "YOUR_" in val:
            raise EnvironmentError(f"Please set {var} in your .env file or environment.")

    # 1. Load
    df = load_csv(INPUT_CSV)
    if df.empty:
        log.error("No transcripts found in CSV. Exiting.")
        return

    # 2. Chunk
    chunks = build_chunks(df)
    if not chunks:
        log.error("No chunks produced. Check that 'video_caption' column has content.")
        return

    # 3. Connect to Pinecone
    pc    = Pinecone(api_key=PINECONE_API_KEY)
    index = get_or_create_index(pc)

    # 4. Embed + upsert
    embed_and_upsert(chunks, index)

    log.info("=" * 60)
    log.info("Ingestion complete.")
    log.info(f"Index '{INDEX_NAME}' stats: {index.describe_index_stats()}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()