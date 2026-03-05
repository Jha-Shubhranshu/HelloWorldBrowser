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
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

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

                # Extract upload date and description (metadata)
                metadata_el = await card.query_selector("div#metadata-line")
                upload_date = None
                if metadata_el:
                    spans = await metadata_el.query_selector_all("span")
                    if len(spans) >= 2:
                        upload_date = await spans[1].inner_text()

                results.append({
                    "video_id": video_id,
                    "title": title or "Untitled",
                    "url": video_url,
                    "thumbnail_url": thumb,
                    "length": length,
                    "upload_date": upload_date,
                    "description": None # Usually not on the grid page
                })
            
            await browser.close()
            return results

class VideoProcessor:
    """Stage 3: Transcript + Vector storage (Real)."""
    def __init__(self, profile: str):
        self.profile = profile
        self.pc = Pinecone(api_key=PINECONE_API_KEY)
        self.index = self._get_or_create_index()
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=OPENAI_API_KEY)
        self.llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=OPENAI_API_KEY)
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

    async def categorize_video(self, description: str) -> str:
        """Use LLM to categorize the video based on its description."""
        if not description:
            return "Entertainment"  # Default
        
        prompt = f"""
        Categorize the following YouTube video description into exactly one of these categories:
        1. News (present developments, timestamping, events, adverts, sponsors)
        2. Education (laws, generalities, facts, documentation, academics)
        3. Entertainment (music, sports, events)
        4. Self Knowledge (philosophy, etymologies, epistemologies, stories, dohas)

        Description: {description[:2000]}

        Respond with ONLY the category name.
        """
        try:
            resp = await self.llm.ainvoke([
                SystemMessage(content="You are a video categorization expert."),
                HumanMessage(content=prompt)
            ])
            category = resp.content.strip()
            # Validation
            valid_categories = ["News", "Education", "Entertainment", "Self Knowledge"]
            for valid in valid_categories:
                if valid.lower() in category.lower():
                    return valid
            return "Entertainment"
        except Exception as e:
            logger.error(f"Categorization failed: {e}")
            return "Entertainment"

    async def scrape_video_details(self, video_url: str) -> Dict[str, str]:
        """Scrape description and exact upload date from the video page."""
        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=self.profile,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = await browser.new_page()
            try:
                logger.info(f"Scraping extra details for {video_url}")
                await page.goto(video_url, wait_until="load", timeout=60000)
                await page.wait_for_timeout(2000)

                # Click "more" in description if needed
                more_btn = await page.query_selector("tp-yt-paper-button#expand")
                if more_btn: await more_btn.click()

                description_el = await page.query_selector("div#description-inner")
                description = await description_el.inner_text() if description_el else None
                
                # Exact date is usually in the description area or info line
                date_el = await page.query_selector("div#info-container span:last-child")
                if not date_el:
                    date_el = await page.query_selector("div#formatted-description-contents span:first-child")
                
                upload_date = await date_el.inner_text() if date_el else None

                return {
                    "description": description,
                    "upload_date": upload_date
                }
            except Exception as e:
                logger.error(f"Failed to scrape video details for {video_url}: {e}")
                return {}
            finally:
                await browser.close()

    def get_transcript_info(self, video_id: str) -> Optional[str]:
        """
        Check for available transcripts and return the language code if English is found.
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            # Try to find an English transcript (manual or auto-generated)
            try:
                t = transcript_list.find_transcript(['en'])
                logger.info(f"✓ English transcript found for {video_id} ({t.language_code})")
                return t.language_code
            except:
                logger.info(f"✗ No English transcript found for {video_id}")
                return None
        except Exception as e:
            logger.error(f"Error checking transcript availability for {video_id}: {e}")
            return None

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
        # 1. Scraping Extra Details (if missing)
        description = video.get('description')
        upload_date = video.get('upload_date')
        category = video.get('category')
        
        if not description or not upload_date:
            details = await self.scrape_video_details(video['url'])
            description = details.get('description') or description
            upload_date = details.get('upload_date') or upload_date
        
        # 1.5 Categorization (if missing)
        if not category and description:
            category = await self.categorize_video(description)
            logger.info(f"Categorized {video['title']} as {category}")

        # Update DB with new details (if any change)
        requests.patch(f"{API_BASE_URL}/videos/{video['id']}/status", params={
            "status": "processing",
            "description": description,
            "upload_date": upload_date,
            "category": category
        })

        # 2. Transcript Acquisition
        transcript = video.get('transcript')
        lang_code = video.get('transcript_language')
        if transcript:
            logger.info(f"Using existing transcript from DB for {video['title']}")
        else:
            # Check for English transcript availability
            lang_code = self.get_transcript_info(video['video_id'])
            if not lang_code:
                logger.info(f"Skipping {video['video_id']} - no English transcript available.")
                return "no_transcript"

            transcript = await self.fetch_transcript(video['url'])
            if not transcript: 
                return "failed"

            # ATOMIC SAVE: Save transcript to SQL DB immediately after fetching, before vectorizing
            try:
                requests.patch(f"{API_BASE_URL}/videos/{video['id']}/status", params={
                    "status": "transcript_fetched",
                    "transcript": transcript,
                    "transcript_language": lang_code,
                    "category": category
                })
                logger.info(f"✓ Saved transcript to DB for {video['title']} (Lang: {lang_code})")
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
                        "video_description": description[:2000] if description else None,
                        "upload_date": upload_date,
                        "transcript_language": lang_code,
                        "category": category,
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
        VideoProcessor(PROFILE)
    )
    asyncio.run(pipeline.start())
