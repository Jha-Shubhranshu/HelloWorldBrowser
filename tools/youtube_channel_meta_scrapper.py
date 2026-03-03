"""
YouTube Channel Metadata Scraper
Reads a CSV of videos, extracts unique channels, and scrapes channel metadata
Outputs channel details including subscriber count, video count, description, etc.
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging

# ============================================================================
# CONFIGURATION SECTION - MODIFY THESE VARIABLES AS NEEDED
# ============================================================================

# Input CSV file path - the CSV containing video data with channel names
input_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\youtube_videos.csv"

# Output CSV file path - where the channel metadata will be saved
output_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\youtube_channels.csv"

# Delay between channel page loads (seconds) - be respectful
page_load_delay = 3

# Enable debug logging
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


class YouTubeChannelScraper:
    def __init__(self, input_path, output_path):
        self.input_path = input_path
        self.output_path = output_path
        self.driver = None
        self.channels_data = []
        self.processed_channels = set()
        self.csv_file = None
        self.csv_writer = None
        self.csv_initialized = False
        
    def setup_driver(self):
        """Initialize Chrome WebDriver"""
        logger.info("Setting up Chrome WebDriver...")
        
        chrome_options = Options()
        
        # Use separate profile
        script_dir = os.path.dirname(os.path.abspath(__file__))
        selenium_profile = os.path.join(script_dir, "selenium_chrome_profile")
        
        if not os.path.exists(selenium_profile):
            os.makedirs(selenium_profile)
        
        chrome_options.add_argument(f"user-data-dir={selenium_profile}")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Chrome WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Chrome WebDriver: {e}")
            raise
    
    def read_channels_from_csv(self):
        """Read unique channel names from input CSV"""
        logger.info(f"Reading channels from: {self.input_path}")
        
        unique_channels = set()
        
        try:
            with open(self.input_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                for row in reader:
                    channel_name = row.get('channel_name', '').strip()
                    if channel_name and channel_name != 'N/A':
                        unique_channels.add(channel_name)
            
            logger.info(f"Found {len(unique_channels)} unique channels")
            return list(unique_channels)
            
        except Exception as e:
            logger.error(f"Failed to read input CSV: {e}")
            raise
    
    def initialize_output_csv(self):
        """Initialize output CSV file and write headers"""
        try:
            output_dir = os.path.dirname(self.output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            self.csv_file = open(self.output_path, 'w', newline='', encoding='utf-8')
            
            fieldnames = [
                'channel_name', 'channel_handle', 'channel_url', 
                'subscriber_count', 'video_count', 'description',
                'join_date', 'country', 'links',
                'scraped_at'
            ]
            
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
            self.csv_writer.writeheader()
            self.csv_file.flush()
            self.csv_initialized = True
            
            logger.info(f"Output CSV initialized: {self.output_path}")
        except Exception as e:
            logger.error(f"Failed to initialize output CSV: {e}")
            raise
    
    def write_channel_to_csv(self, metadata):
        """Write channel metadata to CSV immediately"""
        try:
            if not self.csv_initialized:
                self.initialize_output_csv()
            
            self.csv_writer.writerow(metadata)
            self.csv_file.flush()
        except Exception as e:
            logger.error(f"Failed to write channel to CSV: {e}")
    
    def search_channel(self, channel_name):
        """Search for a channel and navigate to its page"""
        try:
            search_url = f"https://www.youtube.com/results?search_query={channel_name.replace(' ', '+')}"
            self.driver.get(search_url)
            time.sleep(2)
            
            # Look for channel result
            channel_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/@']")
            
            for link in channel_links:
                href = link.get_attribute("href")
                if "/@" in href and "/watch" not in href and "/shorts" not in href:
                    # Check if link text matches channel name
                    link_text = link.text or link.get_attribute("textContent")
                    if link_text and channel_name.lower() in link_text.lower():
                        logger.debug(f"Found channel link: {href}")
                        return href
            
            # Try alternative search
            channel_renderers = self.driver.find_elements(By.CSS_SELECTOR, "ytd-channel-renderer")
            if channel_renderers:
                first_channel = channel_renderers[0]
                link = first_channel.find_element(By.CSS_SELECTOR, "a#main-link")
                href = link.get_attribute("href")
                logger.debug(f"Found channel via renderer: {href}")
                return href
            
            logger.warning(f"Could not find channel page for: {channel_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error searching for channel {channel_name}: {e}")
            return None
    
    def scrape_channel_metadata(self, channel_name):
        """Scrape metadata from a channel page"""
        try:
            metadata = {
                'channel_name': channel_name,
                'channel_handle': 'N/A',
                'channel_url': 'N/A',
                'subscriber_count': 'N/A',
                'video_count': 'N/A',
                'description': 'N/A',
                'join_date': 'N/A',
                'country': 'N/A',
                'links': 'N/A',
                'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Search for channel
            channel_url = self.search_channel(channel_name)
            if not channel_url:
                return metadata
            
            # Navigate to channel page
            self.driver.get(channel_url)
            time.sleep(page_load_delay)
            
            metadata['channel_url'] = channel_url
            
            # Extract channel handle from URL
            if "/@" in channel_url:
                handle = channel_url.split("/@")[1].split("/")[0].split("?")[0]
                metadata['channel_handle'] = f"@{handle}"
            
            # Subscriber count
            try:
                subscriber_elements = self.driver.find_elements(By.CSS_SELECTOR, "#subscriber-count")
                if subscriber_elements:
                    metadata['subscriber_count'] = subscriber_elements[0].text.strip()
                else:
                    # Alternative selector
                    sub_text_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'subscriber')]")
                    if sub_text_elements:
                        metadata['subscriber_count'] = sub_text_elements[0].text.strip()
            except Exception as e:
                logger.debug(f"Could not extract subscriber count: {e}")
            
            # Navigate to About tab
            try:
                about_tab = self.driver.find_element(By.XPATH, "//yt-tab-shape[@tab-title='About']")
                about_tab.click()
                time.sleep(2)
            except:
                try:
                    about_link = self.driver.find_element(By.XPATH, "//a[contains(@href, '/about')]")
                    about_link.click()
                    time.sleep(2)
                except Exception as e:
                    logger.warning(f"Could not navigate to About tab: {e}")
            
            # Description
            try:
                description_elements = self.driver.find_elements(By.CSS_SELECTOR, "#description-container #description")
                if description_elements:
                    metadata['description'] = description_elements[0].text.strip()
                else:
                    description_elements = self.driver.find_elements(By.CSS_SELECTOR, "yt-formatted-string#description")
                    if description_elements:
                        metadata['description'] = description_elements[0].text.strip()
            except Exception as e:
                logger.debug(f"Could not extract description: {e}")
            
            # Statistics from About page
            try:
                # Look for all table rows in about section
                about_rows = self.driver.find_elements(By.CSS_SELECTOR, "ytd-about-channel-renderer tr, #right-column yt-formatted-string")
                
                for row in about_rows:
                    text = row.text
                    
                    # Video count
                    if "video" in text.lower() and metadata['video_count'] == 'N/A':
                        metadata['video_count'] = text.strip()
                    
                    # Join date
                    if "joined" in text.lower() or "Joined" in text:
                        metadata['join_date'] = text.replace("Joined", "").strip()
                    
                    # Country
                    if len(text) > 0 and text[0].isupper() and len(text.split()) <= 3:
                        # Likely a country name
                        if metadata['country'] == 'N/A' and "joined" not in text.lower() and "video" not in text.lower():
                            potential_country = text.strip()
                            if len(potential_country) > 2:
                                metadata['country'] = potential_country
            except Exception as e:
                logger.debug(f"Could not extract about page stats: {e}")
            
            # Links
            try:
                link_elements = self.driver.find_elements(By.CSS_SELECTOR, "ytd-about-channel-renderer a[href^='http']")
                if link_elements:
                    links = [elem.get_attribute("href") for elem in link_elements[:5]]  # First 5 links
                    metadata['links'] = " | ".join(links)
            except Exception as e:
                logger.debug(f"Could not extract links: {e}")
            
            logger.info(f"Successfully scraped: {channel_name}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error scraping channel {channel_name}: {e}")
            return metadata
    
    def scrape_all_channels(self, channels):
        """Scrape metadata for all channels"""
        total = len(channels)
        logger.info(f"Starting to scrape {total} channels...")
        
        self.initialize_output_csv()
        
        for idx, channel_name in enumerate(channels, 1):
            if channel_name in self.processed_channels:
                logger.info(f"[{idx}/{total}] Skipping already processed: {channel_name}")
                continue
            
            logger.info(f"[{idx}/{total}] Scraping: {channel_name}")
            
            metadata = self.scrape_channel_metadata(channel_name)
            
            self.channels_data.append(metadata)
            self.processed_channels.add(channel_name)
            
            # Write to CSV immediately
            self.write_channel_to_csv(metadata)
            
            # Progress update
            if idx % 5 == 0:
                logger.info(f"Progress: {idx}/{total} channels processed")
        
        logger.info(f"Scraping complete. Total channels processed: {len(self.channels_data)}")
    
    def cleanup(self):
        """Clean up resources"""
        if self.csv_file:
            try:
                self.csv_file.close()
                logger.info(f"Output CSV closed: {self.output_path}")
            except Exception as e:
                logger.error(f"Error closing CSV: {e}")
        
        if self.driver:
            logger.info("Closing browser...")
            self.driver.quit()
    
    def run(self):
        """Execute the complete scraping workflow"""
        try:
            channels = self.read_channels_from_csv()
            
            if not channels:
                logger.warning("No channels found in input CSV")
                return
            
            self.setup_driver()
            self.scrape_all_channels(channels)
            
        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user")
            logger.info(f"Partial data saved to: {self.output_path}")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            raise
        finally:
            self.cleanup()


def main():
    """Main entry point"""
    logger.info("=" * 70)
    logger.info("YouTube Channel Metadata Scraper")
    logger.info("=" * 70)
    logger.info(f"Configuration:")
    logger.info(f"  Input file: {input_file}")
    logger.info(f"  Output file: {output_file}")
    logger.info(f"  Page load delay: {page_load_delay}s")
    logger.info("=" * 70)
    
    # Validate paths
    if not os.path.exists(input_file):
        logger.error(f"Input file not found: {input_file}")
        logger.error("Please update the 'input_file' variable with the correct path")
        return
    
    scraper = YouTubeChannelScraper(input_file, output_file)
    scraper.run()
    
    logger.info("=" * 70)
    logger.info("Channel scraping completed")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
