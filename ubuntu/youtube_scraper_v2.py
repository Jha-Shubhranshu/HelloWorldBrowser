"""
YouTube Channel Metadata Scraper - ROBUST VERSION
With verbose logging and better error handling
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
# CONFIGURATION
# ============================================================================

output_file = "/home/ubuntu/youtube_channels.csv"
progress_file = "/home/ubuntu/youtube_scraper_progress.json"
max_size_mb = 1024
cc_index = "CC-MAIN-2026-04"
results_per_pattern = 5000  # Reduced for faster initial results
max_workers = 50  # Reduced to be more conservative
batch_size = 100

# ============================================================================
# SCRAPER CLASS
# ============================================================================

class YouTubeScraper:
    def __init__(self):
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
        
        self.write_lock = Lock()
        self.progress_lock = Lock()
        self.counter_lock = Lock()
        
        self.cdx_api_url = f"https://index.commoncrawl.org/{cc_index}-index"
        self.session = self.create_session()
        self.start_time = None
        
        print(f"[INIT] Scraper initialized")
        print(f"[INIT] CDX API: {self.cdx_api_url}")
        
    def create_session(self):
        print("[INIT] Creating HTTP session with connection pooling...")
        session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        print("[INIT] Session created successfully")
        return session
        
    def load_progress(self):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.bytes_downloaded = data.get('bytes_downloaded', 0)
                    self.channels_scraped = data.get('channels_scraped', 0)
                    print(f"[PROGRESS] Loaded: {self.channels_scraped} channels, {self.bytes_downloaded / (1024*1024):.2f} MB")
                    return data
            except Exception as e:
                print(f"[WARNING] Could not load progress: {e}")
        return {'processed_urls': set(), 'bytes_downloaded': 0, 'channels_scraped': 0}
    
    def save_progress(self):
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
        print(f"\n{'='*70}")
        print(f"[SEARCH] Starting search in Common Crawl index: {self.cc_index}")
        print(f"[SEARCH] Fetching up to {self.results_per_pattern} results per pattern")
        print(f"{'='*70}\n")
        
        all_results = []
        seen_urls = set()
        
        patterns = [
            ("youtube.com/channel/*", "Channel IDs"),
            ("youtube.com/@*", "Handles"),
            ("youtube.com/c/*", "Custom URLs"),
            ("youtube.com/user/*", "User pages"),
        ]
        
        for pattern, desc in patterns:
            print(f"\n[SEARCH] Pattern: {pattern} ({desc})")
            print(f"[SEARCH] Querying CDX API...")
            
            try:
                params = {
                    'url': pattern,
                    'output': 'json',
                    'limit': self.results_per_pattern,
                    'filter': 'status:200'
                }
                
                print(f"[SEARCH] Making request to {self.cdx_api_url}")
                response = self.session.get(self.cdx_api_url, params=params, stream=True, timeout=120)
                print(f"[SEARCH] Response status: {response.status_code}")
                
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
                            
                            # Show progress every 1000 results
                            if count % 1000 == 0:
                                print(f"[SEARCH] Progress: {count} results found so far...")
                            
                        except (json.JSONDecodeError, ValueError) as e:
                            continue
                    
                    print(f"[SEARCH] ✓ Found {count} unique results for {desc}")
                else:
                    print(f"[SEARCH] ✗ Failed with HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"[SEARCH] ✗ Error: {e}")
        
        print(f"\n{'='*70}")
        print(f"[SEARCH] TOTAL: {len(all_results)} unique channel URLs found")
        print(f"{'='*70}\n")
        return all_results
    
    def fetch_and_process_channel(self, record):
        url = record.get('url', '')
        filename = record.get('filename', '')
        offset = int(record.get('offset', 0))
        length = int(record.get('length', 0))
        
        with self.progress_lock:
            if url in self.progress_data['processed_urls']:
                return None
            if self.bytes_downloaded >= self.max_size_bytes:
                return None
        
        warc_url = f"https://data.commoncrawl.org/{filename}"
        byte_range = f"bytes={offset}-{offset + length - 1}"
        
        try:
            headers = {'Range': byte_range}
            response = self.session.get(warc_url, headers=headers, timeout=30)
            
            if response.status_code not in [200, 206]:
                return None
            
            warc_content = response.content
            
            with self.counter_lock:
                self.bytes_downloaded += len(warc_content)
            
            if warc_content[:2] == b'\x1f\x8b':
                warc_content = gzip.decompress(warc_content)
            
            parts = warc_content.split(b'\r\n\r\n', 2)
            html_content = parts[2] if len(parts) >= 3 else warc_content
            
            metadata = self.extract_channel_metadata(html_content, url)
            
            with self.progress_lock:
                self.progress_data['processed_urls'].add(url)
            
            return metadata
            
        except Exception as e:
            with self.progress_lock:
                self.progress_data['processed_urls'].add(url)
            return None
    
    def extract_channel_metadata(self, html_content, url):
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
        
        # Channel ID
        channel_id_match = re.search(r'/channel/([a-zA-Z0-9_-]+)', url)
        if channel_id_match:
            metadata['channel_id'] = channel_id_match.group(1)
        else:
            for pattern in [r'"channelId":"([^"]+)"', r'"externalId":"([^"]+)"']:
                id_match = re.search(pattern, html_str)
                if id_match:
                    metadata['channel_id'] = id_match.group(1)
                    break
        
        # Handle
        handle_match = re.search(r'/@([a-zA-Z0-9_-]+)', url)
        if handle_match:
            metadata['handle'] = '@' + handle_match.group(1)
        
        # Name
        for pattern in [r'"channelName":"([^"]+)"', r'<meta property="og:title" content="([^"]+)"', r'<title>([^<]+)</title>']:
            name_match = re.search(pattern, html_str)
            if name_match:
                name = name_match.group(1).strip()
                name = re.sub(r'\s*-\s*YouTube\s*$', '', name)
                if name and len(name) > 0 and len(name) < 200:
                    metadata['channel_name'] = name
                    break
        
        # Description
        for pattern in [r'"description":"([^"]+)"', r'<meta property="og:description" content="([^"]+)"']:
            desc_match = re.search(pattern, html_str)
            if desc_match:
                desc = desc_match.group(1).strip()
                if desc and len(desc) > 5:
                    metadata['description'] = desc[:500]
                    break
        
        # Subscribers
        sub_match = re.search(r'([\d,\.]+[KMB]?)\s*subscriber', html_str, re.IGNORECASE)
        if sub_match:
            metadata['subscriber_count'] = sub_match.group(1).strip()
        
        # Genre
        genre_match = re.search(r'"genre":"([^"]+)"', html_str)
        if genre_match:
            metadata['genre'] = genre_match.group(1)
        
        if metadata['channel_id'] or metadata['channel_name']:
            return metadata
        
        return None
    
    def save_to_csv_batch(self, channel_data_list):
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
                print(f"[ERROR] CSV write failed: {e}")
    
    def run(self):
        print("\n" + "="*70)
        print("YOUTUBE CHANNEL SCRAPER - ROBUST VERSION")
        print("="*70)
        print(f"Output: {self.output_file}")
        print(f"Size limit: {self.max_size_mb} MB")
        print(f"Workers: {self.max_workers}")
        print("="*70)
        
        self.start_time = time.time()
        
        search_results = self.search_youtube_channels()
        
        if not search_results:
            print("[ERROR] No results found. Exiting.")
            return
        
        print(f"\n[PROCESSING] Starting parallel download with {self.max_workers} workers")
        print(f"[PROCESSING] Processing {len(search_results)} channel pages\n")
        
        if not isinstance(self.progress_data.get('processed_urls'), set):
            self.progress_data['processed_urls'] = set(self.progress_data.get('processed_urls', []))
        
        processed_count = 0
        batch_buffer = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_record = {executor.submit(self.fetch_and_process_channel, record): record 
                               for record in search_results}
            
            for future in as_completed(future_to_record):
                if self.bytes_downloaded >= self.max_size_bytes:
                    print(f"\n[LIMIT] Reached {self.max_size_mb} MB limit. Stopping.")
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
                        
                        if len(batch_buffer) >= self.batch_size:
                            self.save_to_csv_batch(batch_buffer)
                            batch_buffer = []
                            self.save_progress()
                            
                            elapsed = time.time() - self.start_time
                            rate = self.channels_scraped / elapsed if elapsed > 0 else 0
                            mb = self.bytes_downloaded / (1024 * 1024)
                            print(f"[PROGRESS] {self.channels_scraped} channels | {mb:.1f} MB | {rate:.1f} ch/sec | {processed_count} processed")
                    else:
                        with self.counter_lock:
                            self.failed_count += 1
                    
                except Exception as e:
                    with self.counter_lock:
                        self.failed_count += 1
        
        if batch_buffer:
            self.save_to_csv_batch(batch_buffer)
        
        self.save_progress()
        
        elapsed = time.time() - self.start_time
        rate = self.channels_scraped / elapsed if elapsed > 0 else 0
        
        print("\n" + "="*70)
        print("SCRAPING COMPLETE!")
        print(f"Channels scraped: {self.channels_scraped}")
        print(f"Data downloaded: {self.bytes_downloaded / (1024*1024):.2f} MB")
        print(f"Failed: {self.failed_count}")
        print(f"Time: {elapsed:.1f} seconds")
        print(f"Speed: {rate:.1f} channels/second")
        print(f"Output: {self.output_file}")
        print("="*70)


if __name__ == "__main__":
    print("[START] Initializing scraper...")
    scraper = YouTubeScraper()
    
    try:
        scraper.run()
    except KeyboardInterrupt:
        print("\n[STOP] Interrupted. Saving progress...")
        scraper.save_progress()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        scraper.save_progress()
