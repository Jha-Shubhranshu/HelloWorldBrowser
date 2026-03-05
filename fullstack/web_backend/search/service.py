"""
search/service.py
-----------------
All vector-search logic lives here.
Instantiated once at app startup and injected via FastAPI dependency.
"""
import logging
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pinecone import Pinecone

from core.config import Settings
from search.schemas import (
    MetadataFilters,
    SearchRequest,
    SearchResponse,
    VideoResult,
)

log = logging.getLogger(__name__)


class SearchService:
    def __init__(self, settings: Settings):
        self._embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key,
        )
        pc = Pinecone(api_key=settings.pinecone_api_key)
        self._index = pc.Index(settings.pinecone_index)
        self._llm = ChatOpenAI(
            model=settings.chat_model,
            temperature=0.3,
            openai_api_key=settings.openai_api_key,
        )
        log.info("SearchService initialised.")

    # ── public ────────────────────────────────────────────────────────────────

    async def search(self, req: SearchRequest) -> SearchResponse:
        log.info(f"Search: '{req.query}' (Scoped: {req.scoped_results})")

        # 1. Embed query
        query_vector = self._embeddings.embed_query(req.query)

        # 2. Build filter
        pinecone_filter = self._build_filter(req.filters)
        
        # 2.5 Scoped Results LLM categorization
        if req.scoped_results:
            try:
                cat_prompt = f"""
                Categorize the following user query into exactly one of these categories:
                1. News (present developments, timestamping, events, adverts, sponsors)
                2. Education (laws, generalities, facts, documentation, academics)
                3. Entertainment (music, sports, events)
                4. Self Knowledge (philosophy, etymologies, epistemologies, stories, dohas)

                Query: {req.query}

                Respond with ONLY the category name.
                """
                resp = self._llm.invoke(cat_prompt)
                category = resp.content.strip()
                
                # Simple validation/normalization
                valid_categories = ["News", "Education", "Entertainment", "Self Knowledge"]
                for valid in valid_categories:
                    if valid.lower() in category.lower():
                        category = valid
                        break
                else:
                    category = None

                if category:
                    log.info(f"Query scoped to category: {category}")
                    if not pinecone_filter:
                        pinecone_filter = {}
                    pinecone_filter["category"] = {"$eq": category}
            except Exception as e:
                log.warning(f"Query categorization failed: {e}")

        # 3. Vector search
        raw = self._index.query(
            vector=query_vector,
            top_k=req.top_k,
            include_metadata=True,
            filter=pinecone_filter if pinecone_filter else None,
        )
        matches = raw.get("matches", [])
        log.info(f"Pinecone returned {len(matches)} match(es)")

        # 4. De-duplicate by video_url (keep highest score per video)
        seen: Dict[str, VideoResult] = {}
        for m in matches:
            meta  = m.get("metadata", {})
            score = float(m.get("score", 0.0))
            vurl  = meta.get("video_url", "")

            vr = VideoResult(
                video_url=            vurl,
                video_title=          meta.get("video_title", ""),
                channel_name=         meta.get("channel_name", ""),
                video_thumbnail_url=  meta.get("video_thumbnail_url", ""),
                video_upload_date=    meta.get("video_upload_date", ""),
                video_length=         meta.get("video_length", ""),
                score=                score,
                snippet=              meta.get("text", "")[:500],
                channel_joining_date= meta.get("channel_joining_date", ""),
                transcript_language=  meta.get("transcript_language", ""),
                category=             meta.get("category"),
            )
            if vurl not in seen or seen[vurl].score < score:
                seen[vurl] = vr

        results = sorted(seen.values(), key=lambda x: x.score, reverse=True)

        # 5. Optional LLM answer
        llm_answer: Optional[str] = None
        if req.use_llm and results:
            question = req.llm_question or req.query
            context  = "\n\n".join([r.snippet for r in results])
            try:
                llm_answer = self._llm.invoke(
                    f"Based on these YouTube video transcript excerpts:\n\n{context}\n\nAnswer this: {question}"
                ).content
            except Exception as e:
                log.warning(f"LLM call failed: {e}")

        return SearchResponse(
            query=req.query,
            results=results,
            llm_answer=llm_answer,
            total_matches=len(results),
        )

    # ── private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_filter(f: MetadataFilters) -> Dict[str, Any]:
        pf: Dict[str, Any] = {}
        if f.channel_name:
            pf["channel_name"] = {"$eq": f.channel_name}
        if f.channel_name_in:
            pf["channel_name"] = {"$in": f.channel_name_in}
        if f.transcript_language:
            pf["transcript_language"] = {"$eq": f.transcript_language}
        date_f: Dict[str, str] = {}
        if f.video_upload_date_gte:
            date_f["$gte"] = f.video_upload_date_gte
        if f.video_upload_date_lte:
            date_f["$lte"] = f.video_upload_date_lte
        if date_f:
            pf["video_upload_date"] = date_f
        return pf