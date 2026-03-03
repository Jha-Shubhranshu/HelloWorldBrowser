# """
# query_engine.py
# ---------------
# Production-grade query engine.

# The frontend sends a QueryRequest (natural-language description + optional
# metadata filters) and gets back a ranked list of matching videos with snippets.

# Install dependencies:
#     pip install openai pinecone langchain langchain-openai python-dotenv pydantic
# """

# import os
# import logging
# from typing import Any, Dict, List, Optional

# from dotenv import load_dotenv
# from pydantic import BaseModel, Field

# from langchain_openai import ChatOpenAI, OpenAIEmbeddings
# from langchain_core.documents import Document
# from pinecone import Pinecone
# import asyncio
# from functools import partial


# load_dotenv()

# # ──────────────────────────────────────────────────────────────────────────────
# # CONFIG
# # ──────────────────────────────────────────────────────────────────────────────

# PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "YOUR_PINECONE_API_KEY")
# OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY",   "YOUR_OPENAI_API_KEY")
# INDEX_NAME       = os.getenv("PINECONE_INDEX",    "youtube-transcripts")
# EMBEDDING_MODEL  = os.getenv("EMBEDDING_MODEL",   "text-embedding-3-small")
# CHAT_MODEL       = os.getenv("CHAT_MODEL",        "gpt-4o-mini")
# TOP_K_DEFAULT    = int(os.getenv("TOP_K_DEFAULT", "5"))

# log = logging.getLogger(__name__)


# # ──────────────────────────────────────────────────────────────────────────────
# # REQUEST / RESPONSE SCHEMAS
# # ──────────────────────────────────────────────────────────────────────────────

# class MetadataFilters(BaseModel):
#     channel_name:          Optional[str]       = Field(None, description="Exact channel name")
#     channel_name_in:       Optional[List[str]] = Field(None, description="One of these channel names")
#     transcript_language:   Optional[str]       = Field(None, description="e.g. 'English'")
#     video_upload_date_gte: Optional[str]       = Field(None, description="ISO date lower bound e.g. '2024-01-01'")
#     video_upload_date_lte: Optional[str]       = Field(None, description="ISO date upper bound")


# class QueryRequest(BaseModel):
#     query:        str             = Field(..., description="Natural-language description of desired videos")
#     filters:      MetadataFilters = Field(default_factory=MetadataFilters)
#     top_k:        int             = Field(TOP_K_DEFAULT, ge=1, le=50)
#     use_llm:      bool            = Field(True, description="Whether to run LLM summarisation on results")
#     llm_question: Optional[str]   = Field(None, description="Custom question for the LLM (defaults to query)")


# class VideoResult(BaseModel):
#     video_url:           str
#     video_title:         str
#     channel_name:        str
#     video_thumbnail_url: str
#     video_upload_date:   str
#     video_length:        str
#     score:               float
#     snippet:             str
#     channel_joining_date: str
#     transcript_language: str


# class QueryResponse(BaseModel):
#     query:         str
#     results:       List[VideoResult]
#     llm_answer:    Optional[str] = None
#     total_matches: int


# # ──────────────────────────────────────────────────────────────────────────────
# # ENGINE
# # ──────────────────────────────────────────────────────────────────────────────

# class YouTubeQueryEngine:
#     """
#     Singleton-friendly engine. Instantiate once at app startup and reuse.

#     Example:
#         engine = YouTubeQueryEngine()
#         response = engine.query(QueryRequest(query="tutorials on machine learning"))
#     """

#     def __init__(self):
#         self._embeddings = OpenAIEmbeddings(
#             model=EMBEDDING_MODEL,
#             openai_api_key=OPENAI_API_KEY,
#         )
#         pc = Pinecone(api_key=PINECONE_API_KEY)
#         self._index = pc.Index(INDEX_NAME)
#         self._llm = ChatOpenAI(
#             model=CHAT_MODEL,
#             temperature=0.3,
#             openai_api_key=OPENAI_API_KEY,
#         )
#         log.info("YouTubeQueryEngine initialised.")

#     def query(self, req: QueryRequest) -> QueryResponse:
#         """Main entry point."""
#         log.info(f"Query: '{req.query}' | filters: {req.filters.model_dump(exclude_none=True)}")

#         # 1. Embed the query
#         query_vector = self._embeddings.embed_query(req.query)

#         # 2. Build Pinecone filter dict
#         pinecone_filter = self._build_filter(req.filters)
#         log.debug(f"Pinecone filter: {pinecone_filter}")

#         # 3. Vector search
#         loop = asyncio.get_event_loop()
#         raw = await loop.run_in_executor(
#             None,
#             partial(
#                 self._index.query,
#                 vector=query_vector,
#                 top_k=req.top_k,
#                 include_metadata=True,
#                 filter=pinecone_filter if pinecone_filter else None,
#             )
#         )


#         matches = raw.get("matches", [])
#         log.info(f"Pinecone returned {len(matches)} match(es)")

#         # 4. De-duplicate by video_url (keep highest score per video)
#         seen_urls: Dict[str, VideoResult] = {}
#         for m in matches:
#             meta  = m.get("metadata", {})
#             score = float(m.get("score", 0.0))
#             vurl  = meta.get("video_url", "")

#             vr = VideoResult(
#                 video_url=           vurl,
#                 video_title=         meta.get("video_title", ""),
#                 channel_name=        meta.get("channel_name", ""),
#                 video_thumbnail_url= meta.get("video_thumbnail_url", ""),
#                 video_upload_date=   meta.get("video_upload_date", ""),
#                 video_length=        meta.get("video_length", ""),
#                 score=               score,
#                 snippet=             meta.get("text", "")[:500],
#                 channel_joining_date=meta.get("channel_joining_date", ""),
#                 transcript_language= meta.get("transcript_language", ""),
#             )

#             if vurl not in seen_urls or seen_urls[vurl].score < score:
#                 seen_urls[vurl] = vr

#         results = sorted(seen_urls.values(), key=lambda x: x.score, reverse=True)

#         # 5. Optional LLM answer
#         llm_answer: Optional[str] = None
#         if req.use_llm and results:
#             question = req.llm_question or req.query
#             context  = "\n\n".join([r.snippet for r in results])
#             try:
#                 llm_answer = self._llm.invoke(
#                     f"Based on these YouTube video transcript excerpts:\n\n{context}\n\nAnswer this: {question}"
#                 ).content
#             except Exception as e:
#                 log.warning(f"LLM call failed: {e}")
#                 llm_answer = None

#         return QueryResponse(
#             query=req.query,
#             results=results,
#             llm_answer=llm_answer,
#             total_matches=len(results),
#         )

#     @staticmethod
#     def _build_filter(f: MetadataFilters) -> Dict[str, Any]:
#         pf: Dict[str, Any] = {}

#         if f.channel_name:
#             pf["channel_name"] = {"$eq": f.channel_name}

#         if f.channel_name_in:
#             pf["channel_name"] = {"$in": f.channel_name_in}

#         if f.transcript_language:
#             pf["transcript_language"] = {"$eq": f.transcript_language}

#         date_filter: Dict[str, str] = {}
#         if f.video_upload_date_gte:
#             date_filter["$gte"] = f.video_upload_date_gte
#         if f.video_upload_date_lte:
#             date_filter["$lte"] = f.video_upload_date_lte
#         if date_filter:
#             pf["video_upload_date"] = date_filter

#         return pf


# # ──────────────────────────────────────────────────────────────────────────────
# # QUICK CLI TEST  (python query_engine.py)
# # ──────────────────────────────────────────────────────────────────────────────

# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     engine = YouTubeQueryEngine()

#     test_req = QueryRequest(
#         query="channels explaining machine learning for beginners",
#         filters=MetadataFilters(
#             transcript_language="English",
#         ),
#         top_k=5,
#         use_llm=True,
#     )

#     resp = engine.query(test_req)
#     print(f"\n{'='*60}")
#     print(f"Query        : {resp.query}")
#     print(f"Total matches: {resp.total_matches}")
#     print(f"{'='*60}")
#     for i, r in enumerate(resp.results, 1):
#         print(f"\n[{i}] {r.video_title}  (score: {r.score:.4f})")
#         print(f"    Channel : {r.channel_name}")
#         print(f"    URL     : {r.video_url}")
#         print(f"    Snippet : {r.snippet[:200]}…")
#     if resp.llm_answer:
#         print(f"\n{'='*60}")
#         print("LLM Answer:")
#         print(resp.llm_answer)