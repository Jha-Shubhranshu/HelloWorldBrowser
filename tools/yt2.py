"""
Simple YouTube Text Extractor
Shows all visible text from video elements to help identify channel names
"""

import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

print("=" * 70)
print("YouTube Text Extraction Tool")
print("=" * 70)

# Setup Chrome
chrome_options = Options()
script_dir = os.path.dirname(os.path.abspath(__file__))
selenium_profile = os.path.join(script_dir, "selenium_chrome_profile")

if not os.path.exists(selenium_profile):
    os.makedirs(selenium_profile)

chrome_options.add_argument(f"user-data-dir={selenium_profile}")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

print("Opening Chrome...")
driver = webdriver.Chrome(options=chrome_options)
driver.maximize_window()

print("Navigating to YouTube...")
driver.get("https://www.youtube.com")
time.sleep(5)

# Check if logged in
sign_in_buttons = driver.find_elements(By.XPATH, "//a[contains(@href, 'accounts.google.com')]")
if sign_in_buttons:
    print("\nNOT LOGGED IN - Please login in the browser")
    input("Press ENTER after logging in...")
    time.sleep(3)

print("\n" + "=" * 70)
print("Extracting text from video elements...")
print("=" * 70)

# Get video elements
all_video_elements = driver.find_elements(By.CSS_SELECTOR, "ytd-rich-item-renderer")
print(f"\nFound {len(all_video_elements)} video elements")

# Analyze first 3 non-ad videos
videos_analyzed = 0
for idx, element in enumerate(all_video_elements):
    if videos_analyzed >= 3:
        break
    
    # Check if it's an ad
    ad_indicators = element.find_elements(By.CSS_SELECTOR, "ytd-ad-slot-renderer")
    if ad_indicators:
        print(f"\nElement {idx}: SKIPPED (Ad)")
        continue
    
    # Check URL
    try:
        link = element.find_element(By.CSS_SELECTOR, "a[href*='/watch?v=']")
        href = link.get_attribute("href")
        if "googleadservices.com" in href or "/aclk?" in href:
            print(f"\nElement {idx}: SKIPPED (Ad URL)")
            continue
    except:
        print(f"\nElement {idx}: SKIPPED (No video link)")
        continue
    
    videos_analyzed += 1
    
    print("\n" + "=" * 70)
    print(f"VIDEO #{videos_analyzed} (Element index: {idx})")
    print("=" * 70)
    
    # Get video URL
    try:
        link = element.find_element(By.CSS_SELECTOR, "a[href*='/watch?v=']")
        video_url = link.get_attribute("href")
        print(f"URL: {video_url}")
    except:
        print("URL: Not found")
    
    # Get all text content
    print("\nAll visible text in this element:")
    print("-" * 70)
    all_text = element.text
    if all_text:
        lines = all_text.split('\n')
        for i, line in enumerate(lines, 1):
            if line.strip():
                print(f"{i:2d}. {line}")
    else:
        print("(No text found)")
    
    # Look for specific elements
    print("\nSearching for channel-specific elements:")
    print("-" * 70)
    
    # Try to find ytd-channel-name
    try:
        channel_containers = element.find_elements(By.CSS_SELECTOR, "ytd-channel-name, #channel-name")
        print(f"Found {len(channel_containers)} channel-name container(s)")
        for i, container in enumerate(channel_containers, 1):
            text = container.text or container.get_attribute("textContent")
            print(f"  Container {i}: '{text}'")
    except Exception as e:
        print(f"Channel containers: ERROR - {e}")
    
    # Look for @ links
    try:
        all_links = element.find_elements(By.TAG_NAME, "a")
        channel_links = []
        for link in all_links:
            href = link.get_attribute("href")
            if href and "/@" in href:
                text = link.text or link.get_attribute("textContent")
                channel_links.append((text, href))
        
        if channel_links:
            print(f"\nFound {len(channel_links)} channel link(s):")
            for text, href in channel_links:
                print(f"  '{text}' -> {href}")
        else:
            print("\nNo channel links (/@) found")
    except Exception as e:
        print(f"Channel links: ERROR - {e}")

print("\n" + "=" * 70)
print("Analysis complete. Browser will remain open.")
print("Press ENTER to close browser and exit...")
print("=" * 70)
input()

driver.quit()
print("Done!")