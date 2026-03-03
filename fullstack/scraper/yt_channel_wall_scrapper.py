"""
YouTube Channel Videos Scraper
--------------------------------
Takes the output CSV from yt_wall_scraperV2.py (which contains channel_name,
video_title, channel_url) and for every unique channel:

  1. Visits the channel's /videos page
  2. Scrapes channel description + joining date from the About section
  3. Scrapes every video's title, URL, thumbnail URL, and length

Output CSV columns:
  channel_name | channel_description | channel_joining_date |
  video_title  | video_url           | video_thumbnail_url  | video_length

Requirements:
    pip install playwright pandas
    playwright install chromium

NOTE: Uses the same persistent Playwright profile as yt_wall_scraperV2.py
      so login is preserved. On first run a browser window opens — log in
      if prompted.
"""

import asyncio
import csv
import re
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright, Page

# ──────────────────────────────────────────────
# USER-CONFIGURABLE VARIABLES
# ──────────────────────────────────────────────

# Output CSV from yt_wall_scraperV2.py — must contain a "channel_url" column.
input_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\scraped_channels.csv"

# Where to save the final enriched CSV.
output_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\tools\channel_wall_videos.csv"

# Reuse the same Playwright profile folder as the wall scraper (keeps login).
playwright_profile = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\playwright_profile"

# Seconds to wait for manual login if not already logged in.
LOGIN_WAIT_SECONDS = 120

# Max videos to collect PER CHANNEL (set to 0 for unlimited).
MAX_VIDEOS_PER_CHANNEL = 50

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _is_short(duration_text: str | None) -> bool:
    """Return True if duration suggests a Short (≤ 60 s or missing)."""
    if not duration_text:
        return True
    parts = duration_text.strip().split(":")
    try:
        if len(parts) == 1:
            return int(parts[0]) <= 60
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1]) <= 60
        return False
    except ValueError:
        return False


def _normalise_channel_url(url: str) -> str:
    """Strip trailing slashes and ensure full URL."""
    url = url.strip().rstrip("/")
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return "https://www.youtube.com" + url
    return url


async def _check_avatar(page: Page) -> bool:
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10_000)
        el = await page.query_selector("button#avatar-btn")
        return el is not None
    except Exception:
        return False


async def _wait_for_login(page: Page) -> bool:
    logged_in = await _check_avatar(page)
    if logged_in:
        print("[INFO] Already logged in.")
        return True

    print("\n" + "=" * 60)
    print("  ACTION REQUIRED: Please log in to your Google account")
    print("  in the browser window that just opened.")
    print(f"  You have {LOGIN_WAIT_SECONDS} seconds.")
    print("=" * 60 + "\n")

    for _ in range(LOGIN_WAIT_SECONDS // 2):
        await page.wait_for_timeout(2000)
        if await _check_avatar(page):
            await page.wait_for_load_state("load", timeout=30_000)
            await page.wait_for_timeout(2000)
            print("[INFO] Login detected! Continuing …")
            return True

    print("[ERROR] Login not detected. Exiting.")
    return False


# ──────────────────────────────────────────────
# CHANNEL ABOUT SCRAPER
# ──────────────────────────────────────────────

async def _scrape_channel_about(page: Page, channel_base_url: str) -> tuple[str, str]:
    """
    Navigate to the channel About tab, click 'more' if present, and extract
    the channel description and joining date.
    Returns (description, joining_date).
    """
    about_url = channel_base_url + "/about"
    try:
        await page.goto(about_url, wait_until="load", timeout=30_000)
        await page.wait_for_timeout(2000)
    except Exception as e:
        print(f"    [WARN] Could not load about page: {e}")
        return "", ""

    # Click "more" / "Show more" button if present to expand the description
    for btn_selector in [
        "tp-yt-paper-button#expand",
        "button[aria-label='Show more']",
        "#description-container tp-yt-paper-button",
        "yt-description-preview-view-model button",
    ]:
        try:
            btn = await page.query_selector(btn_selector)
            if btn:
                await btn.click()
                await page.wait_for_timeout(1000)
                break
        except Exception:
            pass

    # ── Description ──
    description = ""
    for desc_sel in [
        "yt-attributed-string#description-container span.yt-core-attributed-string",
        "#description-container span.yt-core-attributed-string",
        "ytd-about-channel-renderer #description span",
    ]:
        try:
            el = await page.query_selector(desc_sel)
            if el:
                description = (await el.inner_text()).strip()
                if description:
                    break
        except Exception:
            pass

    # ── Joining date ──
    joining_date = ""
    try:
        # All description-item rows
        rows = await page.query_selector_all("tr.description-item")
        for row in rows:
            text = (await row.inner_text()).strip()
            if "Joined" in text:
                # Extract just the date portion e.g. "Joined 4 Jul 2025"
                match = re.search(r"Joined\s+(.+)", text)
                joining_date = match.group(1).strip() if match else text
                break
    except Exception:
        pass

    return description, joining_date


# ──────────────────────────────────────────────
# CHANNEL VIDEOS SCRAPER
# ──────────────────────────────────────────────

async def _scrape_channel_videos(page: Page, channel_base_url: str, max_videos: int) -> list[dict]:
    """
    Navigate to the channel /videos page and scrape all (non-Short) videos.
    Scrolls until no more videos load or max_videos reached.
    """
    videos_url = channel_base_url + "/videos"
    try:
        await page.goto(videos_url, wait_until="load", timeout=30_000)
        await page.wait_for_timeout(2500)
    except Exception as e:
        print(f"    [WARN] Could not load videos page: {e}")
        return []

    collected: list[dict] = []
    seen_urls: set[str] = set()
    idle_scrolls = 0
    max_idle = 6

    while idle_scrolls < max_idle:
        if max_videos and len(collected) >= max_videos:
            break

        cards = await page.query_selector_all("ytd-rich-grid-media")
        added_this_scroll = 0

        for card in cards:
            if max_videos and len(collected) >= max_videos:
                break

            try:
                # ── Video URL ──
                link_el = await card.query_selector("a#video-title-link")
                if not link_el:
                    continue
                href = (await link_el.get_attribute("href") or "").strip()
                if not href:
                    continue
                video_url = "https://www.youtube.com" + href if href.startswith("/") else href

                if video_url in seen_urls:
                    continue

                # ── Video length (filter Shorts) ──
                badge_el = await card.query_selector("div.yt-badge-shape__text")
                length_text = (await badge_el.inner_text()).strip() if badge_el else None
                if _is_short(length_text):
                    continue

                # ── Video title ──
                title = (await link_el.get_attribute("title") or "").strip()
                if not title:
                    title_el = await card.query_selector("yt-formatted-string#video-title")
                    title = (await title_el.inner_text()).strip() if title_el else ""

                # ── Thumbnail URL ──
                thumb_el = await card.query_selector("ytd-thumbnail a#thumbnail img")
                thumbnail_url = (await thumb_el.get_attribute("src") or "").strip() if thumb_el else ""

                seen_urls.add(video_url)
                collected.append({
                    "video_title":         title,
                    "video_url":           video_url,
                    "video_thumbnail_url": thumbnail_url,
                    "video_length":        length_text or "",
                })
                added_this_scroll += 1

            except Exception:
                continue

        if added_this_scroll == 0:
            idle_scrolls += 1
        else:
            idle_scrolls = 0

        if not (max_videos and len(collected) >= max_videos):
            await page.evaluate("window.scrollBy(0, window.innerHeight * 3)")
            await page.wait_for_timeout(2000)

    return collected


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

async def main():
    # ── Load input CSV ──
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_file}")
        return

    df = pd.read_csv(input_path)
    if "channel_url" not in df.columns:
        print("[ERROR] Input CSV must contain a 'channel_url' column.")
        return

    # Deduplicate channels
    channel_rows = (
        df[["channel_name", "channel_url"]]
        .drop_duplicates(subset="channel_url")
        .dropna(subset=["channel_url"])
        .reset_index(drop=True)
    )
    print(f"[INFO] Found {len(channel_rows)} unique channel(s) to process.")

    # ── Prepare output file ──
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "channel_name", "channel_description", "channel_joining_date",
        "video_title", "video_url", "video_thumbnail_url", "video_length",
    ]
    out_f = open(output_path, "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
    writer.writeheader()

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=playwright_profile,
            headless=False,
            slow_mo=80,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # Navigate to YouTube and ensure login
        await page.goto("https://www.youtube.com", wait_until="load", timeout=60_000)
        await page.wait_for_timeout(2000)

        if not await _wait_for_login(page):
            out_f.close()
            await browser.close()
            return

        total_videos = 0

        for idx, row in channel_rows.iterrows():
            channel_name = str(row.get("channel_name", "")).strip()
            channel_url  = _normalise_channel_url(str(row["channel_url"]))

            print(f"\n[{idx+1}/{len(channel_rows)}] Processing: {channel_name} → {channel_url}")

            # ── About page ──
            print("    Fetching channel description and joining date …")
            description, joining_date = await _scrape_channel_about(page, channel_url)
            print(f"    Joining date : {joining_date or '(not found)'}")
            print(f"    Description  : {description[:80] + '…' if len(description) > 80 else description or '(not found)'}")

            # ── Videos page ──
            print("    Fetching videos …")
            videos = await _scrape_channel_videos(page, channel_url, MAX_VIDEOS_PER_CHANNEL)
            print(f"    Found {len(videos)} video(s).")

            if not videos:
                # Write one placeholder row so the channel still appears in output
                writer.writerow({
                    "channel_name":        channel_name,
                    "channel_description": description,
                    "channel_joining_date": joining_date,
                    "video_title":         "",
                    "video_url":           "",
                    "video_thumbnail_url": "",
                    "video_length":        "",
                })
            else:
                for v in videos:
                    writer.writerow({
                        "channel_name":        channel_name,
                        "channel_description": description,
                        "channel_joining_date": joining_date,
                        **v,
                    })
                total_videos += len(videos)

            out_f.flush()  # Write to disk after each channel

        await browser.close()

    out_f.close()
    print(f"\n[DONE] Scraped {total_videos} video(s) across {len(channel_rows)} channel(s).")
    print(f"[DONE] Output saved → {output_file}")


if __name__ == "__main__":
    asyncio.run(main())