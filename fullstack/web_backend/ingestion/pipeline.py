"""
ingestion/pipeline.py
---------------------
The Orchestrator for the Ingestion Pipeline.
Handles Wall Scraping, Channel Scraping, and Video Processing.
"""
import asyncio
import logging
import os
import hashlib
import requests
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

load_dotenv()

# Logging setup early
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Pinecone & LangChain
from pinecone import Pinecone, ServerlessSpec
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

# Constants
API_BASE_URL = "http://127.0.0.1:8000/ingestion"
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX", "youtube-transcripts")
SCRAPECREATORS_API_KEY = os.getenv("SCRAPECREATORS_API_KEY")

# ── HELPERS ──────────────────────────────────────────────────────────────────

def _is_short(duration_text: str | None) -> bool:
    if not duration_text: return True
    parts = duration_text.strip().split(":")
    try:
        if len(parts) == 1: return int(parts[0]) <= 60
        if len(parts) == 2: return int(parts[0]) * 60 + int(parts[1]) <= 60
        return False
    except ValueError: return False

def _stable_id(video_url: str, chunk_index: int) -> str:
    raw = f"{video_url}::chunk::{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:48]

# ── SCRAPER CLASSES ───────────────────────────────────────────────────────────

class WallScraper:
    """Stage 1: Wall Discovery (Placeholder)."""
    async def scrape(self) -> List[Dict]:
        return []

class ChannelScraper:
    """Stage 2: Channel Expansion (Real)."""
    def __init__(self, profile: str):
        self.profile = profile

    async def scrape(self, channel_url: str) -> List[Dict]:
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=self.profile,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = await browser.new_page()
            
            videos_url = channel_url.rstrip("/") + "/videos"
            logger.info(f"Scraping videos from {videos_url}")
            await page.goto(videos_url, wait_until="load", timeout=60000)
            await page.wait_for_timeout(3000)

            # Scroll to load more
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 2000)")
                await page.wait_for_timeout(1500)

            cards = await page.query_selector_all("ytd-rich-grid-media")
            results = []
            for card in cards:
                link_el = await card.query_selector("a#video-title-link")
                if not link_el: continue
                
                href = await link_el.get_attribute("href")
                video_url = "https://www.youtube.com" + href
                video_id = href.split("v=")[-1] if "v=" in href else href.split("/")[-1]
                
                badge_el = await card.query_selector("div.yt-badge-shape__text")
                length = await badge_el.inner_text() if badge_el else None
                if _is_short(length): continue

                title = await link_el.get_attribute("title")
                thumb_el = await card.query_selector("img")
                thumb = await thumb_el.get_attribute("src") if thumb_el else None

                results.append({
                    "video_id": video_id,
                    "title": title or "Untitled",
                    "url": video_url,
                    "thumbnail_url": thumb,
                    "length": length
                })
            
            await browser.close()
            return results

class VideoProcessor:
    """Stage 3: Transcript + Vector storage (Real)."""
    def __init__(self):
        self.pc = Pinecone(api_key=PINECONE_API_KEY)
        self.index = self._get_or_create_index()
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=OPENAI_API_KEY)
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)

    def _get_or_create_index(self):
        existing = [idx.name for idx in self.pc.list_indexes()]
        if INDEX_NAME not in existing:
            self.pc.create_index(
                name=INDEX_NAME,
                dimension=1536,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        return self.pc.Index(INDEX_NAME)

    def has_english_transcript(self, video_id: str) -> bool:
        """
        Check if the video has an English transcript available for free.
        This helps save ScrapeCreators API credits.
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # Check for manually created or auto-generated English transcripts
            try:
                transcript_list.find_transcript(['en'])
                logger.info(f"✓ English transcript available for {video_id}")
                return True
            except:
                logger.info(f"✗ No English transcript found for {video_id}")
                return False
        except Exception as e:
            logger.error(f"Error checking transcript availability for {video_id}: {e}")
            return False

    async def fetch_transcript(self, video_url: str) -> Optional[str]:
        """Fetch transcript using ScrapeCreators API if available, else mock."""
        if not SCRAPECREATORS_API_KEY:
            return "Mock transcript for: " + video_url
        
        try:
            resp = requests.get(
                "https://api.scrapecreators.com/v1/youtube/video/transcript",
                headers={"x-api-key": SCRAPECREATORS_API_KEY},
                params={"url": video_url, "language": "en"}
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("transcript_only_text") or " ".join([t["text"] for t in data.get("transcript", [])])
            else:
                logger.error(f"API returned unexpected status code: {resp.status_code}")
                logger.error(f"Response Body: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Transcript API failed: {e}")
        return None

    async def process(self, video: Dict[str, Any]) -> str:
        """
        Process a video: check transcript, fetch it, and vector storage.
        Returns the new status for the video.
        """
        # 1. Transcript Acquisition
        transcript = video.get('transcript')
        if transcript:
            logger.info(f"Using existing transcript from DB for {video['title']}")
        else:
            # Check if English transcript is available before calling paid API
            if not self.has_english_transcript(video['video_id']):
                logger.info(f"Skipping {video['video_id']} - no English transcript available.")
                return "no_transcript"

            transcript = await self.fetch_transcript(video['url'])
            if not transcript: 
                return "failed"

            # ATOMIC SAVE: Save transcript to SQL DB immediately after fetching, before vectorizing
            try:
                requests.patch(f"{API_BASE_URL}/videos/{video['id']}/status", params={
                    "status": "transcript_fetched",
                    "transcript": transcript
                })
                logger.info(f"✓ Saved transcript to DB for {video['title']}")
            except Exception as e:
                logger.error(f"Failed to save transcript to DB: {e}")
                return "failed"

        # Stage 3.5: Vectorize and Upsert to Pinecone
        try:
            chunks = self.splitter.split_text(transcript)
            vectors = self.embeddings.embed_documents(chunks)

            payload = []
            for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
                payload.append({
                    "id": _stable_id(video['url'], i),
                    "values": vec,
                    "metadata": {
                        "text": chunk,
                        "video_url": video['url'],
                        "video_title": video['title'],
                        "video_id": video['video_id'],
                        "chunk_index": i,
                        "total_chunks": len(chunks)
                    }
                })
            
            self.index.upsert(vectors=payload)
            logger.info(f"✓ Upserted {len(chunks)} chunks to Pinecone for {video['title']}")
            return "processed"
        except Exception as e:
            logger.error(f"Vector processing failed for {video['title']}: {e}")
            # The transcript is already safe in the SQL DB, so we can retry vectorization later
            return "failed"

# ── ORCHESTRATOR ──────────────────────────────────────────────────────────────

class IngestionPipeline:
    def __init__(self, wall_scraper, channel_scraper, video_processor):
        self.wall_scraper = wall_scraper
        self.channel_scraper = channel_scraper
        self.video_processor = video_processor

    async def run_wall_scrape(self):
        logger.info("Stage 1: Wall Scraping...")
        channels = await self.wall_scraper.scrape()
        for c in channels:
            requests.post(f"{API_BASE_URL}/channels", json=c)

    async def run_channel_scrape(self):
        logger.info("Stage 2: Channel Scraping...")
        while True:
            resp = requests.get(f"{API_BASE_URL}/channels/next")
            if resp.status_code != 200 or not resp.json():
                break
            
            channel = resp.json()
            logger.info(f"Expanding Channel: {channel['channel_name']}")
            requests.patch(f"{API_BASE_URL}/channels/{channel['id']}/status?status=scraping")
            
            try:
                videos = await self.channel_scraper.scrape(channel['channel_url'])
                for v in videos:
                    v['channel_id'] = channel['id']
                    requests.post(f"{API_BASE_URL}/videos", json=v)
                requests.patch(f"{API_BASE_URL}/channels/{channel['id']}/status?status=scraped")
            except Exception as e:
                logger.error(f"Channel {channel['channel_name']} failed: {e}")
                requests.patch(f"{API_BASE_URL}/channels/{channel['id']}/status?status=failed")

    async def run_video_processing(self):
        logger.info("Stage 3: Video Processing...")
        while True:
            resp = requests.get(f"{API_BASE_URL}/videos/next")
            if resp.status_code != 200 or not resp.json():
                break
            
            video = resp.json()
            logger.info(f"Processing Video: {video['title']}")
            requests.patch(f"{API_BASE_URL}/videos/{video['id']}/status?status=processing")
            
            try:
                status = await self.video_processor.process(video)
                requests.patch(f"{API_BASE_URL}/videos/{video['id']}/status?status={status}")
            except Exception as e:
                logger.error(f"Video {video['title']} failed: {e}")
                requests.patch(f"{API_BASE_URL}/videos/{video['id']}/status?status=failed")

    async def start(self):
        await self.run_wall_scrape()
        await self.run_channel_scrape()
        await self.run_video_processing()

if __name__ == "__main__":
    PROFILE = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\playwright_profile"
    
    pipeline = IngestionPipeline(
        WallScraper(),
        ChannelScraper(PROFILE),
        VideoProcessor()
    )
    asyncio.run(pipeline.start())
