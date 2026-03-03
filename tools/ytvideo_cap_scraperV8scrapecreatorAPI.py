"""
YouTube Video Metadata Extractor with Resume Capability
Using ScrapeCreators API for reliable transcript extraction
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


class YouTubeExtractor:
    """Main extractor class using ScrapeCreators API for transcripts."""
    
    def __init__(self, input_file: str, output_file: str, 
                 api_key: str,
                 progress_file: str = "progress.json",
                 delay_range: Tuple[float, float] = (2, 4),
                 log_file: str = "extraction.log"):
        
        self.input_file = input_file
        self.output_file = output_file
        self.api_key = api_key
        self.progress_file = progress_file
        self.delay_range = delay_range
        
        # API endpoint
        self.api_url = "https://api.scrapecreators.com/v1/youtube/video/transcript"
        
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
            url = url.strip()
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
        """Extract description and upload date."""
        soup = BeautifulSoup(html, 'html.parser')
        description = ""
        upload_date = ""
        
        # Try JSON-LD data
        json_ld = soup.find('script', {'type': 'application/ld+json'})
        if json_ld and json_ld.string:
            try:
                data = json.loads(json_ld.string)
                if isinstance(data, dict):
                    description = data.get('description', '')
                    for prop in ['uploadDate', 'datePublished']:
                        if prop in data:
                            upload_date = data[prop]
                            break
            except:
                pass
        
        # Try meta tags
        if not description:
            meta_desc = soup.find('meta', {'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                description = meta_desc['content']
        
        if not upload_date:
            meta_date = soup.find('meta', {'itemprop': 'uploadDate'})
            if meta_date and meta_date.get('content'):
                upload_date = meta_date['content']
        
        return description.strip(), upload_date.strip()
    
    def get_transcript_api(self, video_id: str, url: str) -> Tuple[Optional[str], str]:
        """
        Get transcript using ScrapeCreators API.
        Returns (transcript_text, language)
        """
        try:
            self.logger.info(f"Fetching transcript from API for {video_id}...")
            
            # Prepare API request
            api_headers = {
                "x-api-key": self.api_key
            }
            
            params = {
                "url": url,
                "language": "en"  # Request English
            }
            
            # Make API request
            response = requests.get(
                self.api_url, 
                headers=api_headers, 
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if transcript exists
                if data.get('transcript') and len(data['transcript']) > 0:
                    # Use the concatenated text if available
                    if data.get('transcript_only_text'):
                        transcript_text = data['transcript_only_text']
                    else:
                        # Otherwise combine individual entries
                        transcript_text = ' '.join([item['text'] for item in data['transcript']])
                    
                    language = data.get('language', 'English')
                    self.logger.info(f"✓ API returned transcript ({len(transcript_text)} chars) in {language}")
                    return transcript_text, language
                else:
                    self.logger.info("API returned no transcript")
                    return None, ""
            
            elif response.status_code == 400:
                self.logger.info(f"API returned 400: Transcript not available or invalid request")
                return None, ""
            elif response.status_code == 401:
                self.logger.error("Invalid API key. Please check your ScrapeCreators API key.")
                return None, ""
            elif response.status_code == 429:
                self.logger.warning("Rate limit exceeded. Waiting longer...")
                time.sleep(10)  # Wait longer on rate limit
                return None, ""
            else:
                self.logger.error(f"API returned unexpected status code: {response.status_code}")
                self.logger.debug(f"Response: {response.text[:200]}")
                return None, ""
                
        except requests.exceptions.Timeout:
            self.logger.error("API request timed out")
            return None, ""
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {e}")
            return None, ""
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse API response: {e}")
            return None, ""
        except Exception as e:
            self.logger.error(f"Unexpected error in API call: {e}")
            return None, ""
    
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
        encoding = self.detect_encoding(self.input_file)
        encodings_to_try = [encoding, 'utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for enc in encodings_to_try:
            try:
                self.logger.info(f"Trying to read with encoding: {enc}")
                with open(self.input_file, 'r', encoding=enc) as f:
                    sample = f.read(4096)
                    f.seek(0)
                    
                    delimiter = '\t' if '\t' in sample else ','
                    self.logger.info(f"Detected {delimiter}-delimited input file")
                    
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
                'transcript_language', 'extraction_date', 'transcript_available'
            ]
            with open(self.output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
    
    def clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace and normalizing."""
        if not text:
            return ''
        text = re.sub(r'\n\s*\n', '\n\n', text)
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
        
        # Fetch page content for metadata
        html = self.fetch_page(url)
        if not html:
            self.logger.error(f"Failed to fetch page for {url}")
            return None
        
        # Extract metadata
        description, upload_date = self.extract_metadata(html, url)
        description = self.clean_text(description)
        
        # Get transcript using API
        transcript, transcript_language = self.get_transcript_api(video_id, url)
        
        if transcript:
            transcript = self.clean_text(transcript)
            self.logger.info(f"✓ Transcript found ({len(transcript)} chars)")
        else:
            self.logger.info("✗ No transcript available")
            transcript_language = ""
        
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
            'transcript_language': transcript_language,
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
        
        # Validate API key
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            self.logger.error("Please set your ScrapeCreators API key in the script!")
            self.logger.error("Get one from: https://scrapecreators.com")
            return
        
        progress = self.load_progress()
        videos = self.read_input_csv()
        
        if not videos:
            self.logger.error("No videos to process. Exiting.")
            return
        
        completed = set(progress.get('completed', []))
        failed = set(progress.get('failed', []))
        
        to_process = []
        for v in videos:
            url = v.get('video_url', '').strip()
            if url and url not in completed:
                to_process.append(v)
        
        self.logger.info(f"Total videos: {len(videos)}")
        self.logger.info(f"Already completed: {len(completed)}")
        self.logger.info(f"Previously failed: {len(failed)}")
        self.logger.info(f"Remaining to process: {len(to_process)}")
        self.logger.info(f"API credits: 1 per video")
        
        if not to_process:
            self.logger.info("All videos processed successfully!")
            return
        
        # Confirm before starting (for large batches)
        if len(to_process) > 100:
            self.logger.warning(f"This will use {len(to_process)} API credits!")
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                self.logger.info("Aborted by user")
                return
        
        self.write_output_header()
        
        for i, video in enumerate(to_process, 1):
            url = video.get('video_url', '').strip()
            
            self.logger.info(f"\n[{i}/{len(to_process)}] Processing video {i}")
            
            try:
                result = self.process_video(video)
                
                if result:
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            with open(self.output_file, 'a', newline='', encoding='utf-8-sig') as f:
                                writer = csv.DictWriter(f, fieldnames=result.keys())
                                writer.writerow(result)
                            break
                        except PermissionError:
                            if attempt < max_retries - 1:
                                self.logger.warning(f"File locked, retrying in 2 seconds...")
                                time.sleep(2)
                            else:
                                self.logger.error(f"Cannot write to output file")
                                raise
                    
                    completed.add(url)
                    progress['completed'] = list(completed)
                    if url in failed:
                        failed.remove(url)
                        progress['failed'] = list(failed)
                    
                    self.logger.info(f"✓ Successfully processed and saved")
                else:
                    failed.add(url)
                    progress['failed'] = list(failed)
                    self.logger.error(f"✗ Failed to process")
                
                self.save_progress(progress)
                
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
        self.logger.info(f"API credits used: {len(completed)}")
        self.logger.info(f"Results saved to: {self.output_file}")
        self.logger.info("=" * 60)


def main():
    """Main function with clearly defined paths."""
    
    # ===== CONFIGURE YOUR PATHS AND API KEY HERE =====
    INPUT_FILE = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\tools\channel_wall_videos3.csv"
    OUTPUT_FILE = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\tools\video_details3.csv"
    API_KEY = "qem4nknNPreyEImSM4FxUMJVI643"  # Get from https://scrapecreators.com
    # =================================================
    
    # Install chardet if not already installed
    try:
        import chardet
    except ImportError:
        print("Installing chardet for encoding detection...")
        os.system("pip install chardet")
        import chardet
    
    extractor = YouTubeExtractor(
        input_file=INPUT_FILE,
        output_file=OUTPUT_FILE,
        api_key=API_KEY,
        delay_range=(2, 4)
    )
    
    extractor.run()


if __name__ == "__main__":
    main()