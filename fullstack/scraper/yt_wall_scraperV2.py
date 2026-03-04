"""
YouTube Home Wall Scraper
--------------------------
Scrapes video metadata (channel name, video title, channel page URL)
from the authenticated YouTube home feed using Playwright.

- Skips channels already present in the known-channels list (input_file).
- Skips Shorts (identified by missing duration badge or badge <= 60s).
- Stops after MAX_VIDEOS new videos are collected.
- Appends new results to output_file (CSV).
- Updates input_file with newly discovered channels for future runs.

Requirements:
    pip install playwright pandas
    playwright install chromium
"""

import asyncio
import csv
import os
import re
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright

import requests

# ──────────────────────────────────────────────
# USER-CONFIGURABLE VARIABLES
# ──────────────────────────────────────────────

# Path to the CSV file that tracks already-seen channel names.
# On first run create an empty file or let the script create it.
# Expected columns: channel_name
input_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\known_channels.csv"

# Path where the scraped results CSV will be written / appended.
# Columns: channel_name, video_title, channel_url
output_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\scraped_channels.csv"

# Maximum number of NEW videos to collect in this run.
MAX_VIDEOS = 50

# How many seconds to wait for you to log in before giving up.
# Increase this if you need more time (e.g. 300 for 5 minutes).
LOGIN_WAIT_SECONDS = 60

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

YOUTUBE_HOME = "https://www.youtube.com"

# A duration string like "23:51" means it's NOT a short (> 60 s).
# Shorts either have no badge or a badge ≤ "1:00".
def _is_short(duration_text: str | None) -> bool:
    """Return True if the video looks like a Short."""
    if not duration_text:
        return True  # No badge → likely a Short card
    parts = duration_text.strip().split(":")
    try:
        if len(parts) == 1:                         # "SS"
            return int(parts[0]) <= 60
        elif len(parts) == 2:                       # "MM:SS"
            total = int(parts[0]) * 60 + int(parts[1])
            return total <= 60
        else:                                       # "HH:MM:SS" – definitely not a Short
            return False
    except ValueError:
        return False


def _load_known_channels(path: str) -> set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    try:
        df = pd.read_csv(p)
        if "channel_name" in df.columns:
            return set(df["channel_name"].dropna().str.strip().str.lower())
    except Exception:
        pass
    return set()


def _save_known_channels(path: str, channels: set[str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(sorted(channels), columns=["channel_name"])
    df.to_csv(p, index=False)


def _append_results(path: str, rows: list[dict]) -> None:
    # ... existing CSV logic ...
    
    # NEW: Send to the Pipeline Registry for deduplication and processing
    for row in rows:
        try:
            requests.post("http://127.0.0.1:8000/ingestion/channels", json={
                "channel_name": row["channel_name"],
                "channel_url": row["channel_url"]
            })
        except Exception as e:
            print(f"Backend offline: {e}")


# ──────────────────────────────────────────────
# MAIN SCRAPER
# ──────────────────────────────────────────────

async def scrape_youtube_home():
    known_channels = _load_known_channels(input_file)
    print(f"[INFO] Loaded {len(known_channels)} known channel(s) from input file.")

    new_videos: list[dict] = []
    newly_seen_channels: set[str] = set()

    async with async_playwright() as p:
        # Launch a persistent browser context so your Google login is remembered.
        # On first run, Playwright will open the browser and you can log in manually.
        # The session is stored in the user_data_dir so subsequent runs skip login.
        user_data_dir = str(Path(input_file).parent / "playwright_profile")

        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,          # Keep visible so you can log in on first run
            slow_mo=100,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        print("[INFO] Navigating to YouTube home …")
        # Use "load" so we wait for the full page including any auto-redirects
        # that Google triggers before the DOM settles.
        await page.goto(YOUTUBE_HOME, wait_until="load", timeout=60_000)
        # Extra buffer for any JS-driven redirects (e.g. consent screens)
        await page.wait_for_timeout(3000)

        # ── Manual login window ──────────────────────────────────────────────
        # Helper that safely queries the avatar button even if the page is
        # mid-navigation (returns None instead of raising).
        async def check_avatar() -> bool:
            try:
                # Wait for the page to be in a stable state first
                await page.wait_for_load_state("domcontentloaded", timeout=10_000)
                el = await page.query_selector("button#avatar-btn")
                return el is not None
            except Exception:
                return False

        logged_in = await check_avatar()
        if not logged_in:
            print("\n" + "="*60)
            print("  ACTION REQUIRED: Please log in to your Google account")
            print("  in the browser window that just opened.")
            print(f"  You have {LOGIN_WAIT_SECONDS} seconds.")
            print("="*60 + "\n")
            waited = 0
            while waited < LOGIN_WAIT_SECONDS:
                await page.wait_for_timeout(2000)
                waited += 2
                if await check_avatar():
                    # After login Google redirects back to YouTube — wait for it to settle
                    await page.wait_for_load_state("load", timeout=30_000)
                    await page.wait_for_timeout(2000)
                    print("[INFO] Login detected! Continuing …")
                    logged_in = True
                    break

            if not logged_in:
                print("[ERROR] Login was not detected within the timeout. Exiting.")
                await browser.close()
                return
        else:
            print("[INFO] Already logged in. Continuing …")

        await page.wait_for_timeout(2000)

        print("[INFO] Starting to scrape …")

        scrolls_without_new = 0
        max_idle_scrolls = 8   # Stop if no new eligible videos found after N scrolls

        while len(new_videos) < MAX_VIDEOS and scrolls_without_new < max_idle_scrolls:
            video_cards = await page.query_selector_all("div.yt-lockup-view-model")

            found_new_this_scroll = False

            for card in video_cards:
                if len(new_videos) >= MAX_VIDEOS:
                    break

                # ── Duration badge (filter Shorts) ──
                badge_el = await card.query_selector("div.yt-badge-shape__text")
                duration_text = (await badge_el.inner_text()).strip() if badge_el else None
                if _is_short(duration_text):
                    continue

                # ── Video title ──
                title_el = await card.query_selector("h3.yt-lockup-metadata-view-model__heading-reset > a")
                if not title_el:
                    continue
                video_title = (await title_el.get_attribute("title") or await title_el.inner_text()).strip()

                # ── Channel link (first <a> inside metadata with href starting /@) ──
                channel_el = await card.query_selector(
                    "div.yt-lockup-metadata-view-model__text-container a.yt-core-attributed-string__link"
                )
                if not channel_el:
                    continue
                channel_name = (await channel_el.inner_text()).strip()
                channel_href = (await channel_el.get_attribute("href") or "").strip()
                channel_url = f"https://www.youtube.com{channel_href}" if channel_href.startswith("/") else channel_href

                if not channel_name or not channel_href:
                    continue

                channel_key = channel_name.lower()

                # ── Skip already-known channels ──
                if channel_key in known_channels or channel_key in newly_seen_channels:
                    continue

                # ── Record new video ──
                new_videos.append({
                    "channel_name": channel_name,
                    "video_title": video_title,
                    "channel_url": channel_url,
                })
                newly_seen_channels.add(channel_key)
                found_new_this_scroll = True
                print(f"  [{len(new_videos):03d}] {channel_name} — {video_title[:60]}")

            if found_new_this_scroll:
                scrolls_without_new = 0
            else:
                scrolls_without_new += 1

            if len(new_videos) < MAX_VIDEOS:
                # Scroll down to load more videos
                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                await page.wait_for_timeout(2000)

        await browser.close()

    # ── Persist results ──
    if new_videos:
        _append_results(output_file, new_videos)
        print(f"\n[DONE] Saved {len(new_videos)} new video(s) → {output_file}")

        # Update known channels list
        known_channels.update(newly_seen_channels)
        _save_known_channels(input_file, known_channels)
        print(f"[DONE] Updated known channels list → {input_file}")
    else:
        print("\n[DONE] No new videos found.")


if __name__ == "__main__":
    asyncio.run(scrape_youtube_home())