import csv
import time
import json
from datetime import datetime
import yt_dlp
import requests
from xml.etree import ElementTree

# Configuration
input_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\ubuntu\channellist.csv"
output_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\ubuntu\output_videos.csv"

# Delay between requests in seconds
REQUEST_DELAY = 2
VIDEO_DELAY = 1

def get_channel_videos(channel_url):
    """Get all video IDs from a channel using yt-dlp"""
    
    # Configure yt-dlp to get ALL videos from channel
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',  # Don't download, just get video IDs
        'playlistend': None,  # No limit on playlist items
        'ignoreerrors': True,
    }
    
    try:
        # Make sure we're using the /videos URL
        if not channel_url.endswith('/videos'):
            if channel_url.endswith('/'):
                channel_url = channel_url + 'videos'
            else:
                channel_url = channel_url + '/videos'
        
        print(f"  Extracting video list from: {channel_url}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(channel_url, download=False)
            
            if result and 'entries' in result:
                video_ids = []
                for entry in result['entries']:
                    if entry and entry.get('id'):
                        video_ids.append(entry['id'])
                
                print(f"  ✓ Found {len(video_ids)} videos")
                return video_ids
            else:
                print(f"  ⚠ No entries found in channel")
                return []
    except Exception as e:
        print(f"  ✗ Error fetching channel videos: {e}")
        return []

def download_and_parse_subtitle(url):
    """Download and parse subtitle file"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        content = response.text
        
        # Check if it's JSON format (json3)
        if 'json3' in url or url.endswith('.json3'):
            try:
                data = json.loads(content)
                # Extract text from JSON3 format
                if 'events' in data:
                    text_parts = []
                    for event in data['events']:
                        if 'segs' in event:
                            for seg in event['segs']:
                                if 'utf8' in seg:
                                    text_parts.append(seg['utf8'])
                    return ' '.join(text_parts)
            except:
                pass
        
        # Try parsing as XML (standard subtitle format)
        try:
            root = ElementTree.fromstring(content)
            text_parts = []
            for text_elem in root.findall('.//text'):
                text = text_elem.text or ''
                text = text.replace('\n', ' ').strip()
                if text:
                    text_parts.append(text)
            if text_parts:
                return ' '.join(text_parts)
        except:
            pass
        
        # If plain text, return as is
        return content.strip()
        
    except Exception as e:
        print(f"    Error downloading subtitle: {e}")
        return None

def get_video_data_with_transcript(video_id):
    """Get video metadata and transcript using yt-dlp"""
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'skip_download': True,
        'ignoreerrors': False,
    }
    
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                print(f"  ✗ Could not extract video info")
                return None
            
            # Extract metadata
            metadata = {
                'video_id': video_id,
                'url': url,
                'title': info.get('title', ''),
                'description': info.get('description', ''),
                'upload_date': info.get('upload_date', ''),
                'view_count': str(info.get('view_count', '')),
                'like_count': str(info.get('like_count', '')),
                'duration': str(info.get('duration', '')),
                'tags': ';'.join(info.get('tags', [])) if info.get('tags') else '',
                'category': info.get('category', ''),
                'channel_id': info.get('channel_id', ''),
                'channel_name': info.get('channel', ''),
                'thumbnail_url': info.get('thumbnail', ''),
            }
            
            # Get subtitles/captions
            subtitles = info.get('subtitles', {})
            automatic_captions = info.get('automatic_captions', {})
            
            transcript = None
            transcript_type = None
            
            # Try to get manual English subtitles first
            if 'en' in subtitles and subtitles['en']:
                transcript_type = 'manual'
                for sub_format in subtitles['en']:
                    if 'url' in sub_format:
                        transcript = download_and_parse_subtitle(sub_format['url'])
                        if transcript:
                            print(f"  ✓ Manual English transcript found")
                            break
            
            # Fall back to auto-generated English captions
            if not transcript and 'en' in automatic_captions and automatic_captions['en']:
                transcript_type = 'auto-generated'
                for sub_format in automatic_captions['en']:
                    if 'url' in sub_format:
                        transcript = download_and_parse_subtitle(sub_format['url'])
                        if transcript:
                            print(f"  ✓ Auto-generated English transcript found")
                            break
            
            if not transcript:
                print(f"  ⚠ No English transcript available")
                return None
            
            metadata['transcript'] = transcript
            metadata['transcript_type'] = transcript_type
            print(f"  ✓ Transcript extracted ({len(transcript)} characters)")
            
            return metadata
            
    except Exception as e:
        print(f"  ✗ Error processing video: {e}")
        return None

def process_channel(channel_data):
    """Process all videos from a channel"""
    channel_url = channel_data['url']
    channel_name = channel_data['channel_name']
    
    print(f"Processing channel: {channel_name}")
    print(f"URL: {channel_url}")
    
    # Get all video IDs from channel
    video_ids = get_channel_videos(channel_url)
    
    if not video_ids:
        print(f"⚠ No videos found in channel\n")
        return []
    
    print(f"Found {len(video_ids)} videos in {channel_name}\n")
    
    results = []
    
    for idx, video_id in enumerate(video_ids, 1):
        print(f"[{idx}/{len(video_ids)}] Processing video ID: {video_id}")
        
        # Get video data with transcript
        video_data = get_video_data_with_transcript(video_id)
        
        if video_data:
            if video_data.get('title'):
                print(f"  Title: {video_data['title']}")
            
            video_data['source_channel_name'] = channel_name
            video_data['scraped_at'] = datetime.now().isoformat()
            results.append(video_data)
            print(f"  ✓ SUCCESS - Video processed and saved\n")
        else:
            print(f"  ✗ SKIPPED - No usable English transcript\n")
        
        time.sleep(VIDEO_DELAY)
    
    return results

def main():
    print("="*60)
    print("YouTube Channel Scraper (yt-dlp)")
    print("="*60)
    print(f"Input file: {input_file}")
    print(f"Output file: {output_file}\n")
    
    channels = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            channels.append(row)
    
    print(f"Loaded {len(channels)} channels\n")
    
    all_results = []
    
    for idx, channel in enumerate(channels, 1):
        print(f"\n{'='*60}")
        print(f"CHANNEL {idx}/{len(channels)}: {channel['channel_name']}")
        print(f"{'='*60}\n")
        
        results = process_channel(channel)
        all_results.extend(results)
        
        print(f"\n{'='*60}")
        print(f"Completed channel {idx}/{len(channels)}: {len(results)} videos with English transcripts")
        print(f"{'='*60}\n")
        
        if idx < len(channels):
            print(f"Waiting {REQUEST_DELAY} seconds before next channel...\n")
            time.sleep(REQUEST_DELAY)
    
    if all_results:
        fieldnames = [
            'video_id', 'url', 'title', 'description', 'upload_date', 
            'view_count', 'like_count', 'duration', 'tags', 'category',
            'channel_id', 'channel_name', 'thumbnail_url', 'transcript', 
            'transcript_type', 'source_channel_name', 'scraped_at'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"\n{'='*60}")
        print(f"✓ SCRAPING COMPLETED!")
        print(f"{'='*60}")
        print(f"Total videos processed: {len(all_results)}")
        print(f"Output saved to: {output_file}")
        print(f"{'='*60}\n")
    else:
        print("\n⚠ No videos with English transcripts found")

if __name__ == "__main__":
    main()