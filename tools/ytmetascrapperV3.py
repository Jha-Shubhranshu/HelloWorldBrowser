import csv
import time
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup
from xml.etree import ElementTree
import json

# Configuration
input_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\ubuntu\channellist.csv"
output_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\ubuntu\output_videos.csv"

# Delay between requests in seconds
REQUEST_DELAY = 2
VIDEO_DELAY = 1

def get_channel_id_from_url(url):
    """Extract channel ID from various YouTube URL formats"""
    if '/channel/' in url:
        return url.split('/channel/')[1].split('/')[0].split('?')[0]
    elif '/@' in url or '/c/' in url or '/user/' in url:
        return None
    return None

def get_channel_videos_from_page(channel_url):
    """Scrape video IDs from channel page"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    videos_url = channel_url.rstrip('/') + '/videos'
    
    try:
        response = requests.get(videos_url, headers=headers)
        response.raise_for_status()
        
        video_ids = re.findall(r'"videoId":"([^"]{11})"', response.text)
        video_ids = list(dict.fromkeys(video_ids))
        
        return video_ids
    except Exception as e:
        print(f"Error fetching channel videos: {e}")
        return []

def get_transcript(video_id):
    """Get English transcript for a video (manual or auto-generated)"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(watch_url, headers=headers)
        response.raise_for_status()
        
        html = response.text
        
        # Try multiple patterns to find caption tracks
        caption_tracks = None
        
        # Pattern 1: Standard captionTracks
        match1 = re.search(r'"captionTracks":(\[.*?\])', html)
        if match1:
            try:
                caption_tracks = json.loads(match1.group(1))
            except:
                pass
        
        # Pattern 2: Alternative format
        if not caption_tracks:
            match2 = re.search(r'"captions":\{"playerCaptionsTracklistRenderer":\{"captionTracks":(\[.*?\])', html)
            if match2:
                try:
                    caption_tracks = json.loads(match2.group(1))
                except:
                    pass
        
        if not caption_tracks:
            print(f"  ⚠ No caption tracks found in page HTML")
            return None, None
        
        print(f"  → Found {len(caption_tracks)} caption track(s)")
        
        # Debug: print all available languages
        available_langs = []
        for track in caption_tracks:
            lang_code = track.get('languageCode', 'unknown')
            is_auto = track.get('kind') == 'asr'
            lang_name = track.get('name', {}).get('simpleText', 'Unknown')
            available_langs.append(f"{lang_name} ({lang_code}){' [AUTO]' if is_auto else ''}")
        print(f"  → Available: {', '.join(available_langs)}")
        
        # First, try to find manual English transcript
        manual_track = None
        auto_track = None
        
        for track in caption_tracks:
            lang_code = track.get('languageCode', '')
            is_auto = track.get('kind') == 'asr'  # Auto Speech Recognition
            
            # Check for English language codes (en, en-US, en-GB, etc.)
            if lang_code.startswith('en') or lang_code == 'en':
                if not is_auto and manual_track is None:
                    manual_track = track
                elif is_auto and auto_track is None:
                    auto_track = track
        
        # Prefer manual transcript, fallback to auto-generated
        selected_track = manual_track if manual_track else auto_track
        
        if not selected_track:
            print(f"  ⚠ No English transcript found (manual or auto)")
            return None, None
        
        transcript_type = "manual" if manual_track else "auto-generated"
        print(f"  → Using {transcript_type} transcript")
        
        transcript_url = selected_track['baseUrl']
        time.sleep(0.5)
        
        transcript_response = requests.get(transcript_url, headers=headers)
        transcript_response.raise_for_status()
        
        root = ElementTree.fromstring(transcript_response.content)
        transcript_parts = []
        
        for text_elem in root.findall('.//text'):
            text = text_elem.text or ''
            text = text.replace('\n', ' ').strip()
            if text:
                transcript_parts.append(text)
        
        full_transcript = ' '.join(transcript_parts)
        
        if not full_transcript:
            print(f"  ⚠ Transcript fetched but empty")
            return None, None
        
        print(f"  ✓ Transcript extracted ({len(full_transcript)} characters)")
        return full_transcript, transcript_type
    
    except Exception as e:
        print(f"  ✗ Error getting transcript: {e}")
        return None, None

def get_video_metadata(video_id):
    """Get video metadata from YouTube page"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(watch_url, headers=headers)
        response.raise_for_status()
        
        html = response.text
        
        metadata = {
            'video_id': video_id,
            'url': watch_url,
            'title': '',
            'description': '',
            'upload_date': '',
            'view_count': '',
            'like_count': '',
            'duration': '',
            'tags': '',
            'category': '',
            'channel_id': '',
            'thumbnail_url': ''
        }
        
        title_match = re.search(r'"title":"([^"]*)"', html)
        if title_match:
            metadata['title'] = title_match.group(1).encode().decode('unicode_escape')
        
        desc_match = re.search(r'"shortDescription":"([^"]*)"', html)
        if desc_match:
            metadata['description'] = desc_match.group(1).encode().decode('unicode_escape')
        
        date_match = re.search(r'"uploadDate":"([^"]*)"', html)
        if date_match:
            metadata['upload_date'] = date_match.group(1)
        
        views_match = re.search(r'"viewCount":"(\d+)"', html)
        if views_match:
            metadata['view_count'] = views_match.group(1)
        
        likes_match = re.search(r'"label":"([\d,]+) likes"', html)
        if not likes_match:
            likes_match = re.search(r'accessibilityData":{"label":"([\d,]+) likes"}', html)
        if likes_match:
            metadata['like_count'] = likes_match.group(1).replace(',', '')
        
        duration_match = re.search(r'"lengthSeconds":"(\d+)"', html)
        if duration_match:
            metadata['duration'] = duration_match.group(1)
        
        keywords_match = re.search(r'"keywords":\[(.*?)\]', html)
        if keywords_match:
            metadata['tags'] = keywords_match.group(1).replace('"', '').replace(',', ';')
        
        category_match = re.search(r'"category":"([^"]*)"', html)
        if category_match:
            metadata['category'] = category_match.group(1)
        
        channel_match = re.search(r'"channelId":"([^"]*)"', html)
        if channel_match:
            metadata['channel_id'] = channel_match.group(1)
        
        thumb_match = re.search(r'"thumbnails":\[{"url":"([^"]*)"', html)
        if thumb_match:
            metadata['thumbnail_url'] = thumb_match.group(1)
        
        return metadata
    
    except Exception as e:
        print(f"Error getting metadata for {video_id}: {e}")
        return None

def process_channel(channel_data):
    """Process all videos from a channel"""
    channel_url = channel_data['url']
    channel_name = channel_data['channel_name']
    
    print(f"Processing channel: {channel_name}")
    
    video_ids = get_channel_videos_from_page(channel_url)
    print(f"Found {len(video_ids)} videos in {channel_name}")
    
    results = []
    
    for idx, video_id in enumerate(video_ids, 1):
        print(f"\n[{idx}/{len(video_ids)}] Processing video ID: {video_id}")
        
        # Get metadata first to show the title
        metadata = get_video_metadata(video_id)
        
        if metadata and metadata['title']:
            print(f"  Title: {metadata['title']}")
        else:
            print(f"  ⚠ Could not fetch title")
        
        # Get transcript
        transcript, transcript_type = get_transcript(video_id)
        
        if transcript is None:
            print(f"  ✗ SKIPPED - No usable English transcript")
            time.sleep(VIDEO_DELAY)
            continue
        
        if metadata:
            metadata['transcript'] = transcript
            metadata['transcript_type'] = transcript_type
            metadata['source_channel_name'] = channel_name
            metadata['scraped_at'] = datetime.now().isoformat()
            results.append(metadata)
            print(f"  ✓ SUCCESS - Video processed and saved")
        else:
            print(f"  ✗ FAILED - Could not get metadata")
        
        time.sleep(VIDEO_DELAY)
    
    return results

def main():
    print("Starting YouTube channel scraper")
    print(f"Input file: {input_file}")
    print(f"Output file: {output_file}")
    
    channels = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            channels.append(row)
    
    print(f"Loaded {len(channels)} channels")
    
    all_results = []
    
    for idx, channel in enumerate(channels, 1):
        print(f"\n{'='*60}")
        print(f"CHANNEL {idx}/{len(channels)}: {channel['channel_name']}")
        print(f"{'='*60}")
        results = process_channel(channel)
        all_results.extend(results)
        print(f"\nCompleted channel {idx}/{len(channels)}: {len(results)} videos with English transcripts")
        
        if idx < len(channels):
            time.sleep(REQUEST_DELAY)
    
    if all_results:
        fieldnames = [
            'video_id', 'url', 'title', 'description', 'upload_date', 
            'view_count', 'like_count', 'duration', 'tags', 'category',
            'channel_id', 'thumbnail_url', 'transcript', 'transcript_type',
            'source_channel_name', 'scraped_at'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"\n{'='*60}")
        print(f"✓ COMPLETED! Saved {len(all_results)} videos to:")
        print(f"  {output_file}")
        print(f"{'='*60}")
    else:
        print("\n⚠ No videos with English transcripts found")

if __name__ == "__main__":
    main()
