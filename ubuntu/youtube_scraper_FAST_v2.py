"""
YouTube Channel Metadata Scraper from Common Crawl - HIGH SPEED VERSION
Uses parallel processing, connection pooling, and batch operations for maximum speed
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import gzip
import json
import csv
import os
import sys
from datetime import datetime
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time

# ============================================================================
# CONFIGURATION VARIABLES
# ============================================================================

# Output file path for final CSV results
output_file = "/home/ubuntu/youtube_channels_Fast.csv"

# Progress tracking file (keeps track of what's been scraped)
progress_file = "/home/ubuntu/youtube_scraper_progress.json"

# Maximum data to download in megabytes (set your limit here)
max_size_mb = 10240

# Common Crawl index - Use latest: CC-MAIN-2026-04
cc_index = "CC-MAIN-2026-04"

# Number of results to fetch per pattern (higher = more channels)
results_per_pattern = 50000

# SPEED SETTINGS - Adjust these for performance
max_workers = 200  # Number of parallel download threads (10-100)
batch_size = 200  # Save progress every N channels
connection_pool_size = 50  # HTTP connection pool size

# ============================================================================
# SCRIPT LOGIC
# ============================================================================

class YouTubeChannelScraperFast:
    def __init__(self, output_file, progress_file, max_size_mb, cc_index, results_per_pattern, max_workers, batch_size):
        self.output_file = output_file
        self.progress_file = progress_file
        self.max_size_mb = max_size_mb
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.cc_index = cc_index
        self.results_per_pattern = results_per_pattern
        self.max_workers = max_workers
        self.batch_size = batch_size
        
        self.bytes_downloaded = 0
        self.channels_scraped = 0
        self.failed_count = 0
        self.progress_data = self.load_progress()
        
        # Thread-safe locks
        self.write_lock = Lock()
        self.progress_lock = Lock()
        self.counter_lock = Lock()
        
        # Common Crawl CDX API endpoint
        self.cdx_api_url = f"https://index.commoncrawl.org/{cc_index}-index"
        
        # Create optimized session with connection pooling
        self.session = self.create_session()
        
        # Stats
        self.start_time = None
        
    def create_session(self):
        """Create a session with connection pooling and retry logic"""
        session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        # Mount with connection pooling
        adapter = HTTPAdapter(
            pool_connections=connection_pool_size,
            pool_maxsize=connection_pool_size,
            max_retries=retry_strategy
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
        
    def load_progress(self):
        """Load progress from previous runs"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.bytes_downloaded = data.get('bytes_downloaded', 0)
                    self.channels_scraped = data.get('channels_scraped', 0)
                    print(f"[INFO] Resuming: {self.channels_scraped} channels, {self.bytes_downloaded / (1024*1024):.2f} MB")
                    return data
            except Exception as e:
                print(f"[WARNING] Could not load progress: {e}")
                return {'processed_urls': set(), 'bytes_downloaded': 0, 'channels_scraped': 0}
        return {'processed_urls': set(), 'bytes_downloaded': 0, 'channels_scraped': 0}
    
    def save_progress(self):
        """Save current progress - thread safe"""
        with self.progress_lock:
            try:
                save_data = {
                    'processed_urls': list(self.progress_data.get('processed_urls', set())),
                    'bytes_downloaded': self.bytes_downloaded,
                    'channels_scraped': self.channels_scraped,
                    'last_updated': datetime.now().isoformat()
                }
                with open(self.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, indent=2)
            except Exception as e:
                print(f"[ERROR] Could not save progress: {e}")
    
    def search_youtube_channels(self):
        """Search Common Crawl index for YouTube channel pages"""
        print(f"[INFO] Searching Common Crawl index: {self.cc_index}")
        print(f"[INFO] Fetching up to {self.results_per_pattern} results per pattern...")
        
        all_results = []
        seen_urls = set()
        
        search_patterns = [
            ("youtube.com/channel/*", "Channel IDs"),
            ("youtube.com/@*", "Handle format"),
            ("youtube.com/c/*", "Custom URLs"),
            ("youtube.com/user/*", "User pages"),
        ]
        
        for pattern, desc in search_patterns:
            print(f"[INFO] Searching for {desc}: {pattern}")
            
            try:
                params = {
                    'url': pattern,
                    'output': 'json',
                    'limit': self.results_per_pattern,
                    'filter': 'status:200'
                }
                
                response = self.session.get(self.cdx_api_url, params=params, stream=True, timeout=120)
                
                if response.status_code == 200:
                    count = 0
                    
                    for line in response.iter_lines(decode_unicode=True):
                        if not line:
                            continue
                        
                        try:
                            result = json.loads(line)
                            
                            if isinstance(result, dict):
                                url = result.get('url', '')
                                filename = result.get('filename', '')
                                offset = result.get('offset', 0)
                                length = result.get('length', 0)
                                timestamp = result.get('timestamp', '')
                            elif isinstance(result, list) and len(result) >= 4:
                                url = result[0] if len(result) > 0 else ''
                                timestamp = result[1] if len(result) > 1 else ''
                                length = int(result[6]) if len(result) > 6 else 0
                                offset = int(result[7]) if len(result) > 7 else 0
                                filename = result[8] if len(result) > 8 else ''
                            else:
                                continue
                            
                            if not any(x in url for x in ['/channel/', '/user/', '/@', '/c/']):
                                continue
                            
                            if url in seen_urls:
                                continue
                            seen_urls.add(url)
                            
                            record = {
                                'url': url,
                                'filename': filename,
                                'offset': offset,
                                'length': length,
                                'timestamp': timestamp
                            }
                            
                            all_results.append(record)
                            count += 1
                            
                        except (json.JSONDecodeError, ValueError):
                            continue
                    
                    print(f"    Found {count} unique results")
                    
            except Exception as e:
                print(f"[ERROR] Error searching {pattern}: {e}")
        
        print(f"\n[INFO] Total: {len(all_results)} unique channel URLs found")
        return all_results
    
    def fetch_and_process_channel(self, record):
        """Fetch WARC record and extract metadata - runs in parallel"""
        url = record.get('url', '')
        filename = record.get('filename', '')
        offset = int(record.get('offset', 0))
        length = int(record.get('length', 0))
        
        # Check if already processed
        with self.progress_lock:
            if url in self.progress_data['processed_urls']:
                return None
            
            # Check size limit
            if self.bytes_downloaded >= self.max_size_bytes:
                return None
        
        # Fetch WARC record
        warc_url = f"https://data.commoncrawl.org/{filename}"
        byte_range = f"bytes={offset}-{offset + length - 1}"
        
        try:
            headers = {'Range': byte_range}
            response = self.session.get(warc_url, headers=headers, timeout=30)
            
            if response.status_code not in [200, 206]:
                return None
            
            warc_content = response.content
            
            # Update bytes downloaded
            with self.counter_lock:
                self.bytes_downloaded += len(warc_content)
            
            # Decompress if gzipped
            if warc_content[:2] == b'\x1f\x8b':
                warc_content = gzip.decompress(warc_content)
            
            # Split WARC header from content
            parts = warc_content.split(b'\r\n\r\n', 2)
            html_content = parts[2] if len(parts) >= 3 else warc_content
            
            # Extract metadata
            metadata = self.extract_channel_metadata(html_content, url)
            
            # Mark as processed
            with self.progress_lock:
                self.progress_data['processed_urls'].add(url)
            
            return metadata
            
        except Exception as e:
            # Mark as processed even if failed
            with self.progress_lock:
                self.progress_data['processed_urls'].add(url)
            return None
    
    def extract_channel_metadata(self, html_content, url):
        """Extract channel metadata from HTML content"""
        try:
            html_str = html_content.decode('utf-8', errors='ignore')
        except:
            return None
        
        metadata = {
            'url': url,
            'channel_id': None,
            'channel_name': None,
            'handle': None,
            'genre': None,
            'subscriber_count': None,
            'description': None
        }
        
        # Extract channel ID
        channel_id_match = re.search(r'/channel/([a-zA-Z0-9_-]+)', url)
        if channel_id_match:
            metadata['channel_id'] = channel_id_match.group(1)
        else:
            id_patterns = [
                r'"channelId":"([^"]+)"',
                r'"externalId":"([^"]+)"',
                r'\"externalChannelId\":\"([^\"]+)\"'
            ]
            for pattern in id_patterns:
                id_match = re.search(pattern, html_str)
                if id_match:
                    metadata['channel_id'] = id_match.group(1)
                    break
        
        # Extract handle
        handle_match = re.search(r'/@([a-zA-Z0-9_-]+)', url)
        if handle_match:
            metadata['handle'] = '@' + handle_match.group(1)
        
        # Extract channel name
        name_patterns = [
            r'"channelName":"([^"]+)"',
            r'"title":"([^"]+)"',
            r'<meta property="og:title" content="([^"]+)"',
            r'"author":"([^"]+)"',
            r'<title>([^<]+)</title>'
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, html_str)
            if name_match:
                name = name_match.group(1).strip()
                name = re.sub(r'\s*-\s*YouTube\s*$', '', name)
                if name and len(name) > 0 and len(name) < 200:
                    metadata['channel_name'] = name
                    break
        
        # Extract description
        desc_patterns = [
            r'"description":{"simpleText":"([^"]+)"}',
            r'"description":"([^"]+)"',
            r'<meta property="og:description" content="([^"]+)"',
            r'<meta name="description" content="([^"]+)"'
        ]
        for pattern in desc_patterns:
            desc_match = re.search(pattern, html_str)
            if desc_match:
                desc = desc_match.group(1).strip()
                if desc and len(desc) > 5:
                    metadata['description'] = desc[:500]
                    break
        
        # Extract subscriber count
        sub_patterns = [
            r'([\d,\.]+[KMB]?)\s*subscriber',
            r'"subscriberCountText":.*?"simpleText":"([^"]+)"',
            r'"subscriberCountText":"([^"]+)"'
        ]
        for pattern in sub_patterns:
            sub_match = re.search(pattern, html_str, re.IGNORECASE)
            if sub_match:
                metadata['subscriber_count'] = sub_match.group(1).strip()
                break
        
        # Extract genre
        genre_patterns = [
            r'"genre":"([^"]+)"',
            r'"category":"([^"]+)"'
        ]
        for pattern in genre_patterns:
            genre_match = re.search(pattern, html_str)
            if genre_match:
                metadata['genre'] = genre_match.group(1)
                break
        
        if metadata['channel_id'] or metadata['channel_name']:
            return metadata
        
        return None
    
    def save_to_csv_batch(self, channel_data_list):
        """Append multiple channel data to CSV file - thread safe"""
        if not channel_data_list:
            return
        
        with self.write_lock:
            file_exists = os.path.exists(self.output_file)
            
            try:
                os.makedirs(os.path.dirname(self.output_file) or '.', exist_ok=True)
                
                with open(self.output_file, 'a', newline='', encoding='utf-8') as f:
                    fieldnames = ['channel_id', 'channel_name', 'handle', 'url', 'genre', 
                                 'subscriber_count', 'description', 'scraped_at']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    
                    if not file_exists:
                        writer.writeheader()
                    
                    timestamp = datetime.now().isoformat()
                    for channel_data in channel_data_list:
                        channel_data['scraped_at'] = timestamp
                        writer.writerow(channel_data)
                    
            except Exception as e:
                print(f"[ERROR] Failed to write to CSV: {e}")
    
    def run(self):
        """Main scraping logic with parallel processing"""
        print("="*70)
        print("YouTube Channel Metadata Scraper - HIGH SPEED VERSION")
        print("="*70)
        print(f"Output file: {self.output_file}")
        print(f"Progress file: {self.progress_file}")
        print(f"Size limit: {self.max_size_mb} MB")
        print(f"Common Crawl index: {self.cc_index}")
        print(f"Parallel workers: {self.max_workers}")
        print(f"Results per pattern: {self.results_per_pattern}")
        print("="*70)
        
        self.start_time = time.time()
        
        # Search for YouTube channel pages
        search_results = self.search_youtube_channels()
        
        if not search_results:
            print("\n[ERROR] No YouTube channel pages found")
            return
        
        print(f"\n[INFO] Starting PARALLEL processing with {self.max_workers} workers...")
        print(f"[INFO] Processing {len(search_results)} channel pages...")
        
        # Convert to set if needed
        if not isinstance(self.progress_data.get('processed_urls'), set):
            self.progress_data['processed_urls'] = set(self.progress_data.get('processed_urls', []))
        
        processed_count = 0
        batch_buffer = []
        
        # Process in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_record = {executor.submit(self.fetch_and_process_channel, record): record 
                               for record in search_results}
            
            # Process completed tasks
            for future in as_completed(future_to_record):
                # Check size limit
                if self.bytes_downloaded >= self.max_size_bytes:
                    print(f"\n[INFO] Reached size limit of {self.max_size_mb} MB")
                    # Cancel remaining tasks
                    for f in future_to_record:
                        f.cancel()
                    break
                
                try:
                    metadata = future.result()
                    
                    if metadata:
                        batch_buffer.append(metadata)
                        
                        with self.counter_lock:
                            self.channels_scraped += 1
                            processed_count += 1
                        
                        # Save batch when buffer is full
                        if len(batch_buffer) >= self.batch_size:
                            self.save_to_csv_batch(batch_buffer)
                            batch_buffer = []
                            self.save_progress()
                            
                            # Show stats
                            elapsed = time.time() - self.start_time
                            rate = self.channels_scraped / elapsed if elapsed > 0 else 0
                            mb = self.bytes_downloaded / (1024 * 1024)
                            print(f"[PROGRESS] {self.channels_scraped} channels | {mb:.1f} MB | {rate:.1f} channels/sec")
                    else:
                        with self.counter_lock:
                            self.failed_count += 1
                    
                except Exception as e:
                    with self.counter_lock:
                        self.failed_count += 1
        
        # Save remaining buffer
        if batch_buffer:
            self.save_to_csv_batch(batch_buffer)
        
        # Final save
        self.save_progress()
        
        # Final stats
        elapsed = time.time() - self.start_time
        rate = self.channels_scraped / elapsed if elapsed > 0 else 0
        
        print("\n" + "="*70)
        print("Scraping completed!")
        print(f"Total channels scraped: {self.channels_scraped}")
        print(f"Total data downloaded: {self.bytes_downloaded / (1024*1024):.2f} MB")
        print(f"Failed to extract: {self.failed_count}")
        print(f"Total time: {elapsed:.1f} seconds")
        print(f"Average speed: {rate:.1f} channels/second")
        print(f"Results saved to: {self.output_file}")
        print("="*70)


if __name__ == "__main__":
    scraper = YouTubeChannelScraperFast(
        output_file=output_file,
        progress_file=progress_file,
        max_size_mb=max_size_mb,
        cc_index=cc_index,
        results_per_pattern=results_per_pattern,
        max_workers=max_workers,
        batch_size=batch_size
    )
    
    try:
        scraper.run()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user. Progress has been saved.")
        scraper.save_progress()
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        scraper.save_progress()
        sys.exit(1)
