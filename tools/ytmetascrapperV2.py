import csv
import time
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup
from xml.etree import ElementTree

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
    """Get English transcript for a video"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(watch_url, headers=headers)
        response.raise_for_status()
        
        caption_tracks = re.search(r'"captionTracks":(\[.*?\])', response.text)
        if not caption_tracks:
            return None
        
        import json
        tracks = json.loads(caption_tracks.group(1))
        
        english_track = None
        for track in tracks:
            if track.get('languageCode', '').startswith('en'):
                english_track = track
                break
        
        if not english_track:
            return None
        
        transcript_url = english_track['baseUrl']
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
        
        return ' '.join(transcript_parts)
    
    except Exception as e:
        print(f"Error getting transcript for {video_id}: {e}")
        return None


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
        print(f"Processing video {idx}/{len(video_ids)}: {video_id}")
        
        transcript = get_transcript(video_id)
        
        if transcript is None:
            print(f"Skipping {video_id} - No English transcript available")
            time.sleep(VIDEO_DELAY)
            continue
        
        metadata = get_video_metadata(video_id)
        
        if metadata:
            metadata['transcript'] = transcript
            metadata['source_channel_name'] = channel_name
            metadata['scraped_at'] = datetime.now().isoformat()
            results.append(metadata)
            print(f"Successfully processed {video_id}")
        else:
            print(f"Failed to get metadata for {video_id}")
        
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
        print(f"\n--- Processing channel {idx}/{len(channels)} ---")
        results = process_channel(channel)
        all_results.extend(results)
        print(f"Completed channel {idx}/{len(channels)}: {len(results)} videos with English transcripts")
        
        if idx < len(channels):
            time.sleep(REQUEST_DELAY)
    
    if all_results:
        fieldnames = [
            'video_id', 'url', 'title', 'description', 'upload_date', 
            'view_count', 'like_count', 'duration', 'tags', 'category',
            'channel_id', 'thumbnail_url', 'transcript', 
            'source_channel_name', 'scraped_at'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)
        
        print(f"\nCompleted! Saved {len(all_results)} videos to {output_file}")
    else:
        print("\nNo videos with English transcripts found")


if __name__ == "__main__":
    main()