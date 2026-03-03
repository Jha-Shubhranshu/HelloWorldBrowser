"""
YouTube Video Metadata Extractor with Resume Capability
Fixed version with correct transcript API and better metadata extraction
"""

import csv
import json
import os
import time
import random
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

class YouTubeExtractor:
    """Main extractor class with comprehensive error handling."""
    
    def __init__(self, input_file: str, output_file: str, 
                 progress_file: str = "progress.json",
                 delay_range: Tuple[float, float] = (2, 4),
                 log_file: str = "extraction.log"):
        
        self.input_file = input_file
        self.output_file = output_file
        self.progress_file = progress_file
        self.delay_range = delay_range
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def detect_encoding(self, file_path: str) -> str:
        """Detect the encoding of a file."""
        try:
            import chardet
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)
                result = chardet.detect(raw_data)
                encoding = result['encoding'] if result['encoding'] else 'utf-8'
                self.logger.info(f"Detected file encoding: {encoding} (confidence: {result['confidence']:.2f})")
                return encoding
        except Exception as e:
            self.logger.warning(f"Encoding detection failed: {e}. Falling back to utf-8")
            return 'utf-8'
    
    def extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from various YouTube URL formats."""
        try:
            # Clean the URL
            url = url.strip()
            
            # Handle different URL formats
            patterns = [
                r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
                r'youtube\.com\/watch\?.*[&?]v=([a-zA-Z0-9_-]{11})',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            return None
        except Exception as e:
            self.logger.error(f"Error extracting video ID from {url}: {e}")
            return None
    
    def fetch_page(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Fetch YouTube page with retry logic."""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=15)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.logger.error(f"Failed to fetch {url} after {max_retries} attempts")
        return None
    
    def extract_metadata(self, html: str, url: str) -> Tuple[str, str]:
        """
        Extract description and upload date from YouTube page.
        """
        soup = BeautifulSoup(html, 'html.parser')
        description = ""
        upload_date = ""
        
        # Method 1: Try JSON-LD data (most reliable)
        json_ld = soup.find('script', {'type': 'application/ld+json'})
        if json_ld and json_ld.string:
            try:
                data = json.loads(json_ld.string)
                if isinstance(data, dict):
                    description = data.get('description', '')
                    # Try to get upload date
                    for prop in ['uploadDate', 'datePublished']:
                        if prop in data:
                            upload_date = data[prop]
                            break
            except:
                pass
        
        # Method 2: Try meta tags
        if not description:
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                description = meta_desc['content']
        
        if not upload_date:
            meta_date = soup.find('meta', {'itemprop': 'uploadDate'})
            if meta_date and meta_date.get('content'):
                upload_date = meta_date['content']
            else:
                meta_date = soup.find('meta', {'itemprop': 'datePublished'})
                if meta_date and meta_date.get('content'):
                    upload_date = meta_date['content']
        
        # Method 3: Parse from the page structure
        if not description:
            # Look for description in various containers
            desc_selectors = [
                '#description-inline-expander #expanded',
                '#description-inline-expander #snippet-text',
                'ytd-text-inline-expander #expanded',
                'ytd-text-inline-expander #snippet-text',
                'yt-formatted-string#description-placeholder',
                'yt-attributed-string span.yt-core-attributed-string'
            ]
            
            for selector in desc_selectors:
                elem = soup.select_one(selector)
                if elem:
                    description = elem.get_text(strip=True)
                    if description:
                        break
        
        # Method 4: Get date from watch-info-text
        if not upload_date:
            # Try to find in the info text
            info_selectors = [
                'ytd-watch-info-text yt-formatted-string#info',
                '#info-container yt-formatted-string',
                '.ytd-watch-info-text span',
                '#date-text yt-formatted-string'
            ]
            
            for selector in info_selectors:
                elem = soup.select_one(selector)
                if elem:
                    text = elem.get_text()
                    # Look for date pattern (e.g., "Feb 16, 2026" or "16 Feb 2026")
                    date_patterns = [
                        r'\d{1,2}\s+[A-Za-z]+\s+\d{4}',  # 16 Feb 2026
                        r'[A-Za-z]+\s+\d{1,2},?\s+\d{4}'  # Feb 16, 2026
                    ]
                    for pattern in date_patterns:
                        match = re.search(pattern, text)
                        if match:
                            upload_date = match.group(0)
                            break
                    if upload_date:
                        break
        
        return description.strip(), upload_date.strip()
    
    def get_transcript(self, video_id: str) -> Optional[str]:
        """
        Get English transcript - compatible with youtube-transcript-api 1.x
        """
        try:
            api = YouTubeTranscriptApi()  # must instantiate in 1.x
            transcript_list = api.list(video_id)  # renamed from list_transcripts()

            # Strategy 1: manually created English transcript
            try:
                transcript = transcript_list.find_manually_created_transcript(['en'])
                pieces = transcript.fetch()
                return ' '.join([item.text for item in pieces])  # item is now an object, not dict
            except Exception:
                pass

            # Strategy 2: auto-generated English transcript
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
                pieces = transcript.fetch()
                return ' '.join([item.text for item in pieces])
            except Exception:
                pass

            # Strategy 3: any transcript, translated to English
            for t in transcript_list:
                try:
                    if t.is_translatable:
                        pieces = t.translate('en').fetch()
                        return ' '.join([item.text for item in pieces])
                except Exception:
                    continue

            self.logger.info(f"No English transcript available for {video_id}")
            return None

        except (NoTranscriptFound, TranscriptsDisabled):
            self.logger.info(f"No transcript available for {video_id}")
            return None
        except VideoUnavailable:
            self.logger.warning(f"Video {video_id} is unavailable")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching transcript for {video_id}: {e}")
            return None
        
    def load_progress(self) -> Dict:
        """Load progress tracking data."""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.warning("Progress file corrupted, starting fresh")
                return {'completed': [], 'failed': [], 'last_updated': None}
        return {'completed': [], 'failed': [], 'last_updated': None}
    
    def save_progress(self, progress: Dict):
        """Save progress tracking data."""
        progress['last_updated'] = datetime.now().isoformat()
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2)
    
    def read_input_csv(self) -> List[Dict]:
        """Read input CSV with automatic encoding detection."""
        videos = []
        
        # First, detect the file encoding
        encoding = self.detect_encoding(self.input_file)
        
        # List of encodings to try
        encodings_to_try = [encoding, 'utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for enc in encodings_to_try:
            try:
                self.logger.info(f"Trying to read with encoding: {enc}")
                with open(self.input_file, 'r', encoding=enc) as f:
                    # Read sample to detect delimiter
                    sample = f.read(4096)
                    f.seek(0)
                    
                    if '\t' in sample:
                        delimiter = '\t'
                        self.logger.info("Detected tab-delimited input file")
                    else:
                        delimiter = ','
                        self.logger.info("Detected comma-delimited input file")
                    
                    reader = csv.DictReader(f, delimiter=delimiter)
                    videos = list(reader)
                    
                    if videos:
                        self.logger.info(f"Successfully read {len(videos)} videos with {enc} encoding")
                        return videos
                    
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.error(f"Error reading with {enc} encoding: {e}")
                continue
        
        self.logger.error("Failed to read input file with any encoding")
        return []
    
    def write_output_header(self):
        """Write header to output file if it doesn't exist."""
        if not os.path.exists(self.output_file):
            headers = [
                'channel_name', 'channel_description', 'channel_joining_date',
                'video_title', 'video_url', 'video_thumbnail_url', 'video_length',
                'video_description', 'video_upload_date', 'video_caption',
                'extraction_date', 'transcript_available'
            ]
            with open(self.output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
    
    def clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace and normalizing."""
        if not text:
            return ''
        # Replace multiple newlines with single newline
        text = re.sub(r'\n\s*\n', '\n\n', text)
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        return text.strip()
    
    def process_video(self, video: Dict) -> Optional[Dict]:
        """Process a single video and extract all metadata."""
        url = video.get('video_url', '').strip()
        title = video.get('video_title', '').strip()
        
        if not url:
            self.logger.warning("Skipping row with no URL")
            return None
        
        video_id = self.extract_video_id(url)
        if not video_id:
            self.logger.error(f"Could not extract video ID from: {url}")
            return None
        
        self.logger.info(f"Processing: {title} (ID: {video_id})")
        
        # Fetch page content
        html = self.fetch_page(url)
        if not html:
            self.logger.error(f"Failed to fetch page for {url}")
            return None
        
        # Extract metadata
        description, upload_date = self.extract_metadata(html, url)
        description = self.clean_text(description)
        
        # Get transcript
        transcript = self.get_transcript(video_id)
        if transcript:
            transcript = self.clean_text(transcript)
            self.logger.info(f"✓ English transcript found ({len(transcript)} chars)")
        else:
            self.logger.info("✗ No English transcript available")
        
        # Prepare result
        result = {
            'channel_name': self.clean_text(video.get('channel_name', '')),
            'channel_description': self.clean_text(video.get('channel_description', '')),
            'channel_joining_date': video.get('channel_joining_date', '').strip(),
            'video_title': title,
            'video_url': url,
            'video_thumbnail_url': video.get('video_thumbnail_url', '').strip(),
            'video_length': video.get('video_length', '').strip(),
            'video_description': description,
            'video_upload_date': upload_date,
            'video_caption': transcript if transcript else '',
            'extraction_date': datetime.now().isoformat(),
            'transcript_available': 'Yes' if transcript else 'No'
        }
        
        return result
    
    def run(self):
        """Main execution loop with resume capability."""
        self.logger.info("=" * 60)
        self.logger.info("Starting YouTube Video Extraction")
        self.logger.info(f"Input: {self.input_file}")
        self.logger.info(f"Output: {self.output_file}")
        self.logger.info(f"Progress: {self.progress_file}")
        self.logger.info("=" * 60)
        
        # Load progress and videos
        progress = self.load_progress()
        videos = self.read_input_csv()
        
        if not videos:
            self.logger.error("No videos to process. Exiting.")
            return
        
        # Create sets for quick lookup
        completed = set(progress.get('completed', []))
        failed = set(progress.get('failed', []))
        
        # Filter videos to process
        to_process = []
        for v in videos:
            url = v.get('video_url', '').strip()
            if url and url not in completed:
                to_process.append(v)
        
        self.logger.info(f"Total videos: {len(videos)}")
        self.logger.info(f"Already completed: {len(completed)}")
        self.logger.info(f"Previously failed: {len(failed)}")
        self.logger.info(f"Remaining to process: {len(to_process)}")
        
        if not to_process:
            self.logger.info("All videos processed successfully!")
            return
        
        # Ensure output file has header
        self.write_output_header()
        
        # Process videos
        for i, video in enumerate(to_process, 1):
            url = video.get('video_url', '').strip()
            
            self.logger.info(f"\n[{i}/{len(to_process)}] Processing video {i}")
            
            try:
                result = self.process_video(video)
                
                if result:
                    # Append to output file
                    with open(self.output_file, 'a', newline='', encoding='utf-8-sig') as f:
                        writer = csv.DictWriter(f, fieldnames=result.keys())
                        writer.writerow(result)
                    
                    # Update progress
                    completed.add(url)
                    progress['completed'] = list(completed)
                    if url in failed:
                        failed.remove(url)
                        progress['failed'] = list(failed)
                    
                    self.logger.info(f"✓ Successfully processed and saved")
                else:
                    # Mark as failed
                    failed.add(url)
                    progress['failed'] = list(failed)
                    self.logger.error(f"✗ Failed to process")
                
                # Save progress after each video
                self.save_progress(progress)
                
                # Random delay to be nice to YouTube
                if i < len(to_process):
                    delay = random.uniform(*self.delay_range)
                    self.logger.info(f"Waiting {delay:.1f} seconds...")
                    time.sleep(delay)
                
            except KeyboardInterrupt:
                self.logger.info("\n\nInterrupted by user. Saving progress...")
                self.save_progress(progress)
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}", exc_info=True)
                failed.add(url)
                progress['failed'] = list(failed)
                self.save_progress(progress)
        
        # Final summary
        self.logger.info("\n" + "=" * 60)
        self.logger.info("Extraction Complete!")
        self.logger.info(f"Successfully processed: {len(completed)} videos")
        self.logger.info(f"Failed: {len(failed)} videos")
        self.logger.info(f"Results saved to: {self.output_file}")
        self.logger.info("=" * 60)


def main():
    """Main function with clearly defined paths."""
    
    # ===== CONFIGURE YOUR PATHS HERE =====
    INPUT_FILE = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\tools\channel_wall_videos2.csv"
    OUTPUT_FILE = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\tools\video_details2.csv"
    # ======================================
    
    # Install chardet if not already installed
    try:
        import chardet
    except ImportError:
        print("Installing chardet for encoding detection...")
        os.system("pip install chardet")
        import chardet
    
    # Create extractor and run
    extractor = YouTubeExtractor(
        input_file=INPUT_FILE,
        output_file=OUTPUT_FILE,
        delay_range=(2, 4)
    )
    
    extractor.run()


if __name__ == "__main__":
    main()