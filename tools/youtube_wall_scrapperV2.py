"""
YouTube Wall Scraper
Scrapes video metadata from YouTube home feed in a respectful manner
Saves data to CSV with configurable output path and video limit
"""

import time
import csv
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import logging

# ============================================================================
# CONFIGURATION SECTION - MODIFY THESE VARIABLES AS NEEDED
# ============================================================================

# Output file path - where the CSV will be saved
output_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\youtube_videos.csv"

# Number of videos to scrape
video_limit = 200

# Scroll delay in seconds (respectful rate limiting)
scroll_delay = 2

# Maximum wait time for elements (seconds)
element_wait_time = 10

# Enable debug logging (set to True to see detailed extraction logs)
debug_mode = False

# ============================================================================
# END CONFIGURATION SECTION
# ============================================================================


# Setup logging
log_level = logging.DEBUG if debug_mode else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class YouTubeWallScraper:
    def __init__(self, output_path, max_videos):
        self.output_path = output_path
        self.max_videos = max_videos
        self.driver = None
        self.videos_data = []
        self.seen_video_ids = set()
        self.csv_file = None
        self.csv_writer = None
        self.csv_initialized = False
        
    def setup_driver(self):
        """Initialize Chrome WebDriver with appropriate options"""
        logger.info("Setting up Chrome WebDriver...")
        
        chrome_options = Options()
        
        # Create a separate profile directory for Selenium to avoid conflicts
        # This prevents issues with existing Chrome instances
        script_dir = os.path.dirname(os.path.abspath(__file__))
        selenium_profile = os.path.join(script_dir, "selenium_chrome_profile")
        
        # Create profile directory if it doesn't exist
        if not os.path.exists(selenium_profile):
            os.makedirs(selenium_profile)
            logger.info(f"Created Selenium Chrome profile directory: {selenium_profile}")
        
        chrome_options.add_argument(f"user-data-dir={selenium_profile}")
        
        # Additional options for better performance and stability
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set user agent to avoid detection
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.maximize_window()
            logger.info("Chrome WebDriver initialized successfully")
            logger.info("NOTE: You will need to login to YouTube manually on first run")
            logger.info("The login session will be saved for future runs")
        except Exception as e:
            logger.error(f"Failed to initialize Chrome WebDriver: {e}")
            logger.info("Troubleshooting steps:")
            logger.info("1. Make sure Chrome browser is installed")
            logger.info("2. Make sure ChromeDriver is installed and in PATH")
            logger.info("3. Check that ChromeDriver version matches your Chrome version")
            logger.info("4. Close all Chrome windows and try again")
            raise
    
    def navigate_to_youtube_home(self):
        """Navigate to YouTube home page"""
        logger.info("Navigating to YouTube home page...")
        self.driver.get("https://www.youtube.com")
        time.sleep(5)  # Wait for page to load
        
        # Check if user is logged in
        try:
            # Look for sign-in button to check if not logged in
            sign_in_buttons = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'accounts.google.com')]")
            if sign_in_buttons:
                logger.info("=" * 70)
                logger.info("YOU ARE NOT LOGGED IN TO YOUTUBE")
                logger.info("Please login to YouTube in the browser window that just opened")
                logger.info("After logging in, press ENTER in this console to continue...")
                logger.info("=" * 70)
                input()  # Wait for user to press Enter
                logger.info("Continuing with scraping...")
                time.sleep(3)
        except:
            pass
        
        logger.info("YouTube home page loaded")
    
    def initialize_csv(self):
        """Initialize CSV file and write headers"""
        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(self.output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"Created output directory: {output_dir}")
            
            # Open CSV file in write mode
            self.csv_file = open(self.output_path, 'w', newline='', encoding='utf-8')
            
            # Define CSV columns
            fieldnames = [
                'video_id', 'title', 'channel_name', 'video_url', 
                'views', 'upload_time', 'duration', 'thumbnail_url', 
                'description', 'scraped_at'
            ]
            
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
            self.csv_writer.writeheader()
            self.csv_file.flush()  # Ensure header is written immediately
            self.csv_initialized = True
            
            logger.info(f"CSV file initialized: {self.output_path}")
            logger.info("Videos will be written to CSV in real-time as they are scraped")
        except Exception as e:
            logger.error(f"Failed to initialize CSV: {e}")
            raise
    
    def write_video_to_csv(self, metadata):
        """Write a single video entry to CSV immediately"""
        try:
            if not self.csv_initialized:
                self.initialize_csv()
            
            self.csv_writer.writerow(metadata)
            self.csv_file.flush()  # Force write to disk immediately
        except Exception as e:
            logger.error(f"Failed to write video to CSV: {e}")
    
    def scroll_page(self):
        """Scroll down the page to load more videos"""
        self.driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(scroll_delay)
    
    def extract_video_metadata(self, video_element):
        """Extract metadata from a single video element"""
        try:
            metadata = {}
            
            # Check if this is an ad - skip it
            try:
                ad_indicators = video_element.find_elements(By.CSS_SELECTOR, "ytd-ad-slot-renderer, ytd-in-feed-ad-layout-renderer")
                if ad_indicators:
                    logger.debug("Skipping ad element")
                    return None
            except:
                pass
            
            # Video ID (from URL)
            try:
                # Try multiple selectors for the thumbnail link
                link_element = None
                selectors = [
                    "a[href*='/watch?v=']",
                    "a#thumbnail",
                    "a.yt-simple-endpoint.inline-block",
                    "ytd-thumbnail a"
                ]
                
                for selector in selectors:
                    try:
                        link_element = video_element.find_element(By.CSS_SELECTOR, selector)
                        if link_element:
                            break
                    except:
                        continue
                
                if not link_element:
                    logger.debug("Could not find link element")
                    return None
                
                video_url = link_element.get_attribute("href")
                
                if not video_url:
                    logger.debug("Link element has no href")
                    return None
                
                # Skip shorts
                if "/shorts/" in video_url:
                    logger.debug(f"Skipping short: {video_url}")
                    return None
                
                # Skip ads (ad URLs)
                if "googleadservices.com" in video_url or "/aclk?" in video_url:
                    logger.debug("Skipping ad URL")
                    return None
                
                # Extract video ID
                if "/watch?v=" in video_url:
                    video_id = video_url.split("/watch?v=")[1].split("&")[0]
                    metadata['video_id'] = video_id
                else:
                    logger.debug(f"Not a regular video URL: {video_url}")
                    return None
            except Exception as e:
                logger.debug(f"Error extracting video ID: {e}")
                return None
            
            # Check if already processed
            if video_id in self.seen_video_ids:
                return None
            
            # Video Title - Updated selectors for new YouTube structure
            try:
                title_selectors = [
                    "h3.ytd-rich-grid-media #video-title",
                    "yt-formatted-string#video-title",
                    "a#video-title",
                    "h3 a",
                    "#video-title",
                    "h3.ytd-video-meta #video-title"
                ]
                
                for selector in title_selectors:
                    try:
                        title_element = video_element.find_element(By.CSS_SELECTOR, selector)
                        title = title_element.get_attribute("title") or title_element.get_attribute("aria-label") or title_element.text
                        if title and title.strip() and len(title.strip()) > 5:
                            metadata['title'] = title.strip()
                            break
                    except:
                        continue
                
                if 'title' not in metadata:
                    metadata['title'] = "N/A"
            except:
                metadata['title'] = "N/A"
            
            # Channel Name - CRITICAL - Try all possible methods
            try:
                channel_found = False
                
                # METHOD 1: Find channel via @ links (MOST RELIABLE based on diagnostics)
                try:
                    # First try the specific new YouTube selector
                    specific_selectors = [
                        "a.yt-core-attributed-string__link[href*='/@']",
                        "a[href*='/@'].yt-core-attributed-string__link"
                    ]
                    
                    for selector in specific_selectors:
                        try:
                            channel_links = video_element.find_elements(By.CSS_SELECTOR, selector)
                            for link in channel_links:
                                channel_text = link.text or link.get_attribute("textContent")
                                # Clean up the text (remove verified icon and extra spaces)
                                if channel_text:
                                    # Split by newline or verified icon and get first part
                                    channel_clean = channel_text.split('\n')[0].strip()
                                    if channel_clean and len(channel_clean) > 1:
                                        metadata['channel_name'] = channel_clean
                                        channel_found = True
                                        logger.debug(f"Found channel via specific selector: {channel_clean}")
                                        break
                            if channel_found:
                                break
                        except Exception as e:
                            logger.debug(f"Specific selector '{selector}' failed: {e}")
                    
                    # Fallback to generic @ link search
                    if not channel_found:
                        all_links = video_element.find_elements(By.TAG_NAME, "a")
                        for link in all_links:
                            href = link.get_attribute("href")
                            if href and "/@" in href and "/watch" not in href and "/shorts" not in href:
                                channel_text = link.text or link.get_attribute("textContent")
                                if channel_text:
                                    # Clean up the text
                                    channel_clean = channel_text.split('\n')[0].strip()
                                    if channel_clean and len(channel_clean) > 1:
                                        metadata['channel_name'] = channel_clean
                                        channel_found = True
                                        logger.debug(f"Found channel via @ link: {channel_clean}")
                                        break
                except Exception as e:
                    logger.debug(f"@ link method failed: {e}")
                
                # METHOD 2: Try CSS selectors if @ link method failed
                if not channel_found:
                    channel_selectors = [
                        # New YouTube structure
                        "ytd-channel-name.ytd-video-meta-block #text a",
                        "ytd-channel-name yt-formatted-string a",
                        "ytd-channel-name #text",
                        "ytd-channel-name a",
                        # Legacy selectors
                        "ytd-channel-name#channel-name a",
                        "yt-formatted-string.ytd-channel-name a",
                        "#channel-name a",
                        "ytd-video-meta-block #channel-name a",
                        # Alternative approaches
                        "a.yt-simple-endpoint.yt-formatted-string",
                        "#text.ytd-channel-name a",
                        "yt-formatted-string#text a",
                        # Broadest selectors (use text content)
                        "ytd-channel-name yt-formatted-string",
                        "ytd-channel-name #text",
                    ]
                    
                    for selector in channel_selectors:
                        try:
                            channel_elements = video_element.find_elements(By.CSS_SELECTOR, selector)
                            for channel_element in channel_elements:
                                channel_name = channel_element.text or channel_element.get_attribute("textContent")
                                if channel_name:
                                    # Clean up the text
                                    channel_clean = channel_name.split('\n')[0].strip()
                                    if channel_clean and len(channel_clean) > 1:
                                        # Filter out common non-channel text
                                        if channel_clean.lower() not in ['verified', 'subscribers', 'views', 'live', 'streamed']:
                                            metadata['channel_name'] = channel_clean
                                            channel_found = True
                                            logger.debug(f"Found channel via selector '{selector}': {channel_clean}")
                                            break
                            if channel_found:
                                break
                        except Exception as e:
                            logger.debug(f"Channel selector '{selector}' failed: {e}")
                            continue
                
                if not channel_found:
                    logger.warning(f"Could not find channel name for video: {metadata.get('title', 'Unknown')[:50]}")
                    metadata['channel_name'] = "N/A"
            except Exception as e:
                logger.warning(f"Channel name extraction failed: {e}")
                metadata['channel_name'] = "N/A"
            
            # Video URL
            metadata['video_url'] = f"https://www.youtube.com/watch?v={video_id}"
            
            # Views and Upload Time - Updated selectors
            try:
                # Look for metadata line
                metadata_selectors = [
                    "#metadata-line",
                    "div#metadata-line",
                    "ytd-video-meta-block #metadata-line",
                    ".ytd-video-meta-block"
                ]
                
                metadata_line = None
                for selector in metadata_selectors:
                    try:
                        metadata_line = video_element.find_element(By.CSS_SELECTOR, selector)
                        if metadata_line:
                            break
                    except:
                        continue
                
                if metadata_line:
                    spans = metadata_line.find_elements(By.TAG_NAME, "span")
                    if len(spans) >= 1:
                        views_text = spans[0].text
                        if views_text and views_text.strip():
                            metadata['views'] = views_text.strip()
                    if len(spans) >= 2:
                        time_text = spans[1].text
                        if time_text and time_text.strip():
                            metadata['upload_time'] = time_text.strip()
            except:
                pass
            
            if 'views' not in metadata:
                metadata['views'] = "N/A"
            if 'upload_time' not in metadata:
                metadata['upload_time'] = "N/A"
            
            # Duration
            try:
                duration_selectors = [
                    "ytd-thumbnail-overlay-time-status-renderer span.ytd-thumbnail-overlay-time-status-renderer",
                    "span.style-scope.ytd-thumbnail-overlay-time-status-renderer",
                    "ytd-thumbnail-overlay-time-status-renderer span",
                    "#time-status span",
                    ".ytd-thumbnail-overlay-time-status-renderer"
                ]
                
                for selector in duration_selectors:
                    try:
                        duration_element = video_element.find_element(By.CSS_SELECTOR, selector)
                        duration = duration_element.text
                        if duration and duration.strip() and ":" in duration:
                            metadata['duration'] = duration.strip()
                            break
                    except:
                        continue
                
                if 'duration' not in metadata:
                    metadata['duration'] = "N/A"
            except:
                metadata['duration'] = "N/A"
            
            # Thumbnail URL
            try:
                thumbnail_selectors = [
                    "ytd-thumbnail img#img",
                    "img#img",
                    "yt-image img",
                    "ytd-thumbnail img"
                ]
                
                for selector in thumbnail_selectors:
                    try:
                        thumbnail_element = video_element.find_element(By.CSS_SELECTOR, selector)
                        thumb_url = thumbnail_element.get_attribute("src")
                        if thumb_url:
                            metadata['thumbnail_url'] = thumb_url
                            break
                    except:
                        continue
                
                if 'thumbnail_url' not in metadata:
                    metadata['thumbnail_url'] = "N/A"
            except:
                metadata['thumbnail_url'] = "N/A"
            
            # Description/Snippet (if available)
            try:
                description_element = video_element.find_element(By.CSS_SELECTOR, "#description-text")
                metadata['description'] = description_element.text
            except:
                metadata['description'] = "N/A"
            
            # Scraped timestamp
            metadata['scraped_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Log successful extraction
            logger.debug(f"Extracted: {metadata['title'][:50]}... by {metadata['channel_name']}")
            
            return metadata
            
        except StaleElementReferenceException:
            return None
        except Exception as e:
            logger.debug(f"Error extracting metadata: {e}")
            return None
    
    def scrape_videos(self):
        """Main scraping loop"""
        logger.info(f"Starting to scrape up to {self.max_videos} videos...")
        logger.info(f"Output will be saved to: {self.output_path}")
        
        # Initialize CSV file before scraping
        self.initialize_csv()
        
        consecutive_no_new_videos = 0
        max_consecutive_no_new = 5  # Stop if no new videos found after 5 scrolls
        
        while len(self.videos_data) < self.max_videos:
            try:
                # Find all video renderers on the page
                video_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "ytd-rich-item-renderer, ytd-video-renderer, ytd-grid-video-renderer"
                )
                
                logger.info(f"Found {len(video_elements)} video elements on page")
                
                videos_before = len(self.videos_data)
                videos_processed = 0
                videos_skipped_shorts = 0
                videos_skipped_duplicate = 0
                videos_failed = 0
                
                for video_element in video_elements:
                    if len(self.videos_data) >= self.max_videos:
                        break
                    
                    videos_processed += 1
                    metadata = self.extract_video_metadata(video_element)
                    
                    if metadata:
                        if metadata['video_id'] not in self.seen_video_ids:
                            self.videos_data.append(metadata)
                            self.seen_video_ids.add(metadata['video_id'])
                            
                            # Write to CSV immediately
                            self.write_video_to_csv(metadata)
                            
                            if len(self.videos_data) % 10 == 0:
                                logger.info(f"Progress: {len(self.videos_data)}/{self.max_videos} videos scraped and saved to CSV")
                        else:
                            videos_skipped_duplicate += 1
                    else:
                        videos_failed += 1
                
                videos_after = len(self.videos_data)
                new_videos = videos_after - videos_before
                
                logger.info(f"Processed {videos_processed} elements: {new_videos} new videos, {videos_failed} failed to extract")
                
                if videos_after == videos_before:
                    consecutive_no_new_videos += 1
                    logger.info(f"No new videos found in this scroll ({consecutive_no_new_videos}/{max_consecutive_no_new})")
                else:
                    consecutive_no_new_videos = 0
                
                if consecutive_no_new_videos >= max_consecutive_no_new:
                    logger.warning("No new videos found after multiple scrolls. Stopping scrape.")
                    break
                
                if len(self.videos_data) < self.max_videos:
                    logger.info("Scrolling to load more videos...")
                    self.scroll_page()
                
            except Exception as e:
                logger.error(f"Error during scraping loop: {e}")
                time.sleep(2)
        
        logger.info(f"Scraping complete. Total videos collected: {len(self.videos_data)}")
    
    def cleanup(self):
        """Clean up resources"""
        # Close CSV file if open
        if self.csv_file:
            try:
                self.csv_file.close()
                logger.info(f"CSV file closed: {self.output_path}")
                logger.info(f"Total records saved: {len(self.videos_data)}")
            except Exception as e:
                logger.error(f"Error closing CSV file: {e}")
        
        # Close browser
        if self.driver:
            logger.info("Closing browser...")
            self.driver.quit()
    
    def run(self):
        """Execute the complete scraping workflow"""
        try:
            self.setup_driver()
            self.navigate_to_youtube_home()
            self.scrape_videos()
        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user")
            logger.info(f"Partial data has been saved to: {self.output_path}")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise
        finally:
            self.cleanup()


def main():
    """Main entry point"""
    logger.info("=" * 70)
    logger.info("YouTube Wall Scraper")
    logger.info("=" * 70)
    logger.info(f"Configuration:")
    logger.info(f"  Output file: {output_file}")
    logger.info(f"  Video limit: {video_limit}")
    logger.info(f"  Scroll delay: {scroll_delay}s")
    logger.info("=" * 70)
    
    # Validate output path
    if not output_file or output_file == r"C:\Users\YourUsername\Desktop\youtube_videos.csv":
        logger.warning("Please update the 'output_file' variable with your desired output path")
        logger.warning("Example: r'C:\\Users\\YourName\\Documents\\youtube_data.csv'")
        input("Press Enter to continue with default path or Ctrl+C to exit...")
    
    scraper = YouTubeWallScraper(output_file, video_limit)
    scraper.run()
    
    logger.info("=" * 70)
    logger.info("Scraping completed successfully")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()