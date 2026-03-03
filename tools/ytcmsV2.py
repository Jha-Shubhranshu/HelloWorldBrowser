"""
YouTube Channel Scraper using Playwright
Extracts channel details from YouTube video URLs in a CSV file
"""

import csv
import time
import os
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ============= CONFIGURATION =============
# Set your input and output file paths here
input_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\youtube_videos.csv"  # Change this
output_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\output_channels.csv"  # Change this

# Column name in your CSV that contains the YouTube URLs
URL_COLUMN = "video_url"  # Change this if your column has a different name
# =========================================


def extract_channel_url_from_video(page):
    """Get channel URL from video page"""
    try:
        link = page.wait_for_selector('ytd-channel-name a', timeout=10000)
        if link:
            href = link.get_attribute("href")
            return "https://www.youtube.com" + href
    except PlaywrightTimeout:
        # Try alternative selector
        try:
            link = page.query_selector('a.yt-simple-endpoint[href*="/@"]')
            if link:
                return "https://www.youtube.com" + link.get_attribute("href")
        except:
            pass
    return None


def scrape_channel_details(page, channel_url):
    """Extract channel information"""
    details = {
        'channel_name': '',
        'genre': '',
        'subscribers': '',
        'date_created': '',
        'description': ''
    }
    
    try:
        # Go to About page
        about_url = channel_url.rstrip('/') + '/about'
        page.goto(about_url, wait_until='networkidle', timeout=30000)
        time.sleep(2)
        
        # Channel name
        try:
            name_elem = page.query_selector('ytd-channel-name #text')
            if name_elem:
                details['channel_name'] = name_elem.inner_text().strip()
        except:
            pass
        
        # Subscribers
        try:
            subs_elem = page.query_selector('#subscriber-count')
            if subs_elem:
                details['subscribers'] = subs_elem.inner_text().strip()
        except:
            pass
        
        # Description
        try:
            desc_elem = page.query_selector('#description-container #description')
            if desc_elem:
                details['description'] = desc_elem.inner_text().strip()
        except:
            pass
        
        # Date created (Joined date)
        try:
            stats_elems = page.query_selector_all('#right-column yt-formatted-string')
            for elem in stats_elems:
                text = elem.inner_text().strip()
                if 'Joined' in text or 'joined' in text:
                    details['date_created'] = text
                    break
        except:
            pass
        
        # Genre (try to extract from links or metadata)
        try:
            links = page.query_selector_all('#links-section a')
            for link in links:
                href = link.get_attribute('href')
                if href and 'youtube.com' not in href:
                    details['genre'] = link.inner_text().strip()
                    break
        except:
            pass
        
        # If no genre found, try metadata
        if not details['genre']:
            try:
                meta = page.query_selector('meta[name="keywords"]')
                if meta:
                    keywords = meta.get_attribute('content')
                    if keywords:
                        details['genre'] = keywords.split(',')[0].strip()
            except:
                pass
        
    except Exception as e:
        print(f"Error scraping {channel_url}: {e}")
    
    return details


def process_videos(input_path, output_path, url_col):
    """Main processing function"""
    
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at {input_path}")
        return
    
    # Read video URLs
    video_urls = []
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if url_col not in reader.fieldnames:
                print(f"Error: Column '{url_col}' not found in CSV")
                print(f"Available columns: {reader.fieldnames}")
                return
            
            for row in reader:
                url = row.get(url_col, '').strip()
                if url:
                    video_urls.append(url)
    except Exception as e:
        print(f"Error reading input CSV: {e}")
        return
    
    print(f"Found {len(video_urls)} video URLs to process")
    
    processed_channels = set()
    channel_data = []
    
    with sync_playwright() as p:
        # Launch browser (set headless=True to hide browser window)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        for idx, video_url in enumerate(video_urls, 1):
            print(f"\n[{idx}/{len(video_urls)}] Processing: {video_url}")
            
            try:
                # Navigate to video page
                page.goto(video_url, wait_until='networkidle', timeout=30000)
                time.sleep(2)
                
                # Get channel URL
                channel_url = extract_channel_url_from_video(page)
                
                if not channel_url:
                    print("  ⚠ Could not find channel URL")
                    continue
                
                # Skip if already processed
                if channel_url in processed_channels:
                    print("  ℹ Channel already processed, skipping...")
                    continue
                
                print(f"  📺 Found channel: {channel_url}")
                processed_channels.add(channel_url)
                
                # Scrape channel details
                details = scrape_channel_details(page, channel_url)
                details['channel_url'] = channel_url
                channel_data.append(details)
                
                print(f"  ✓ Scraped: {details['channel_name']} - {details['subscribers']}")
                
                # Delay between requests
                time.sleep(3)
                
            except Exception as e:
                print(f"  ✗ Error: {e}")
        
        browser.close()
    
    # Save results to CSV
    if channel_data:
        try:
            # Create output directory if needed
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                fields = ['channel_url', 'channel_name', 'genre', 'subscribers', 
                         'date_created', 'description']
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(channel_data)
            
            print(f"\n✓ Successfully saved {len(channel_data)} channel details to {output_path}")
        except Exception as e:
            print(f"\n✗ Error writing output CSV: {e}")
    else:
        print("\n⚠ No channel data collected")


if __name__ == "__main__":
    print("=" * 60)
    print("YouTube Channel Scraper")
    print("=" * 60)
    print(f"Input file:  {input_file}")
    print(f"Output file: {output_file}")
    print(f"URL Column:  '{URL_COLUMN}'")
    print("=" * 60)
    
    process_videos(input_file, output_file, URL_COLUMN)
    
    print("\nDone!")