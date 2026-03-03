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
output_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\youtube_wall_videos.csv"

# Number of videos to scrape
video_limit = 200

# Scroll delay in seconds (respectful rate limiting)
scroll_delay = 2

# Maximum wait time for elements (seconds)
element_wait_time = 10

# ============================================================================
# END CONFIGURATION SECTION
# ============================================================================


# Setup logging
logging.basicConfig(
    level=logging.INFO,
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
    
    def scroll_page(self):
        """Scroll down the page to load more videos"""
        self.driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(scroll_delay)
    
    def extract_video_metadata(self, video_element):
        """Extract metadata from a single video element"""
        try:
            metadata = {}
            
            # Video ID (from URL)
            try:
                link_element = video_element.find_element(By.CSS_SELECTOR, "a#thumbnail")
                video_url = link_element.get_attribute("href")
                if video_url and "/watch?v=" in video_url:
                    video_id = video_url.split("/watch?v=")[1].split("&")[0]
                    metadata['video_id'] = video_id
                else:
                    return None  # Skip if not a regular video
            except:
                return None
            
            # Check if already processed
            if video_id in self.seen_video_ids:
                return None
            
            # Video Title
            try:
                title_element = video_element.find_element(By.CSS_SELECTOR, "a#video-title")
                metadata['title'] = title_element.get_attribute("title") or title_element.text
            except:
                metadata['title'] = "N/A"
            
            # Channel Name
            try:
                channel_element = video_element.find_element(By.CSS_SELECTOR, "a.yt-simple-endpoint.style-scope.yt-formatted-string")
                metadata['channel_name'] = channel_element.text
            except:
                try:
                    # Alternative selector for channel name
                    channel_element = video_element.find_element(By.CSS_SELECTOR, "ytd-channel-name#channel-name a")
                    metadata['channel_name'] = channel_element.text
                except:
                    metadata['channel_name'] = "N/A"
            
            # Video URL
            metadata['video_url'] = f"https://www.youtube.com/watch?v={video_id}"
            
            # Views
            try:
                metadata_line = video_element.find_element(By.CSS_SELECTOR, "#metadata-line")
                spans = metadata_line.find_elements(By.TAG_NAME, "span")
                if len(spans) >= 1:
                    metadata['views'] = spans[0].text
                else:
                    metadata['views'] = "N/A"
            except:
                metadata['views'] = "N/A"
            
            # Upload Time
            try:
                metadata_line = video_element.find_element(By.CSS_SELECTOR, "#metadata-line")
                spans = metadata_line.find_elements(By.TAG_NAME, "span")
                if len(spans) >= 2:
                    metadata['upload_time'] = spans[1].text
                else:
                    metadata['upload_time'] = "N/A"
            except:
                metadata['upload_time'] = "N/A"
            
            # Duration
            try:
                duration_element = video_element.find_element(By.CSS_SELECTOR, "span.style-scope.ytd-thumbnail-overlay-time-status-renderer")
                metadata['duration'] = duration_element.text
            except:
                metadata['duration'] = "N/A"
            
            # Thumbnail URL
            try:
                thumbnail_element = video_element.find_element(By.CSS_SELECTOR, "img#img")
                metadata['thumbnail_url'] = thumbnail_element.get_attribute("src")
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
                
                for video_element in video_elements:
                    if len(self.videos_data) >= self.max_videos:
                        break
                    
                    # Filter out shorts by checking the URL
                    try:
                        link = video_element.find_element(By.CSS_SELECTOR, "a#thumbnail")
                        href = link.get_attribute("href")
                        if href and "/shorts/" in href:
                            continue  # Skip shorts
                    except:
                        pass
                    
                    metadata = self.extract_video_metadata(video_element)
                    
                    if metadata and metadata['video_id'] not in self.seen_video_ids:
                        self.videos_data.append(metadata)
                        self.seen_video_ids.add(metadata['video_id'])
                        
                        if len(self.videos_data) % 50 == 0:
                            logger.info(f"Progress: {len(self.videos_data)}/{self.max_videos} videos scraped")
                
                videos_after = len(self.videos_data)
                
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
    
    def save_to_csv(self):
        """Save scraped data to CSV file"""
        if not self.videos_data:
            logger.warning("No data to save")
            return
        
        logger.info(f"Saving {len(self.videos_data)} videos to CSV...")
        
        # Ensure output directory exists
        output_dir = os.path.dirname(self.output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
        
        # Define CSV columns
        fieldnames = [
            'video_id', 'title', 'channel_name', 'video_url', 
            'views', 'upload_time', 'duration', 'thumbnail_url', 
            'description', 'scraped_at'
        ]
        
        try:
            with open(self.output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.videos_data)
            
            logger.info(f"Successfully saved data to: {self.output_path}")
            logger.info(f"Total records: {len(self.videos_data)}")
        except Exception as e:
            logger.error(f"Failed to save CSV: {e}")
            raise
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            logger.info("Closing browser...")
            self.driver.quit()
    
    def run(self):
        """Execute the complete scraping workflow"""
        try:
            self.setup_driver()
            self.navigate_to_youtube_home()
            self.scrape_videos()
            self.save_to_csv()
        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user")
            if self.videos_data:
                logger.info("Saving partial data...")
                self.save_to_csv()
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