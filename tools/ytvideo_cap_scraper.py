"""
YouTube Video Detail Scraper
------------------------------
Takes the output CSV from yt_channel_scraper.py (which contains video_url,
video_title columns) and for each video visits the watch page to extract:

  1. video_url          – from input file
  2. video_title        – from input file
  3. video_description  – scraped from watch page
  4. video_upload_date  – scraped from watch page
  5. video_caption      – English timed-text captions (auto-generated OK),
                          fetched via YouTube's internal timedtext API

RESUME SUPPORT:
  A progress file (same folder as output_file, named output_file + ".progress")
  stores the last successfully processed video URL. On restart, the script
  skips all URLs up to and including that checkpoint and continues from the
  next one.

Requirements:
    pip install playwright pandas requests
    playwright install chromium
"""

import asyncio
import csv
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import pandas as pd
import requests
from playwright.async_api import async_playwright, Page

# ──────────────────────────────────────────────
# USER-CONFIGURABLE VARIABLES
# ──────────────────────────────────────────────

# Output CSV from yt_channel_scraper.py — must contain "video_url" column.
# "video_title" column is optional but carried over if present.
input_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\tools\channel_wall_videos.csv"

# Where to save the final enriched CSV.
output_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\tools\video_details.csv"

# Reuse the same Playwright profile folder as the previous scripts.
playwright_profile = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\playwright_profile"

# Seconds to wait for manual login if not already logged in.
LOGIN_WAIT_SECONDS = 120

# Seconds to wait after loading a watch page before scraping (let JS settle).
PAGE_SETTLE_SECONDS = 3

# ──────────────────────────────────────────────
# RESUME / PROGRESS FILE
# ──────────────────────────────────────────────

progress_file = output_file + ".progress"

def _load_last_processed() -> str | None:
    """Return the last successfully processed video URL, or None."""
    p = Path(progress_file)
    if p.exists():
        url = p.read_text(encoding="utf-8").strip()
        return url if url else None
    return None

def _save_progress(video_url: str) -> None:
    Path(progress_file).write_text(video_url, encoding="utf-8")

def _clear_progress() -> None:
    p = Path(progress_file)
    if p.exists():
        p.unlink()

# ──────────────────────────────────────────────
# LOGIN HELPER
# ──────────────────────────────────────────────

async def _check_avatar(page: Page) -> bool:
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10_000)
        el = await page.query_selector("button#avatar-btn")
        return el is not None
    except Exception:
        return False

async def _wait_for_login(page: Page) -> bool:
    if await _check_avatar(page):
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
# CAPTION FETCHER  (no browser needed)
# ──────────────────────────────────────────────

def _extract_video_id(url: str) -> str | None:
    """Pull the v= param out of any youtube watch URL."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    ids = qs.get("v")
    return ids[0] if ids else None

def _fetch_caption_tracks(video_id: str) -> list[dict]:
    """
    Fetch the list of caption tracks by hitting YouTube's internal
    /get_video_info or by parsing the ytInitialPlayerResponse embedded
    in the watch page HTML.
    Returns a list of track dicts with keys: languageCode, name, baseUrl, kind
    """
    # Fetch the watch page as a plain HTTP request (no browser needed)
    url = f"https://www.youtube.com/watch?v={video_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"      [WARN] HTTP fetch failed for caption list: {e}")
        return []

    # ytInitialPlayerResponse is a large JSON blob embedded in the page
    match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.+?\});\s*(?:var|const|let|</script>)", resp.text, re.DOTALL)
    if not match:
        return []

    try:
        player_data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    captions_data = (
        player_data
        .get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
        .get("captionTracks", [])
    )
    tracks = []
    for track in captions_data:
        tracks.append({
            "languageCode": track.get("languageCode", ""),
            "name":         track.get("name", {}).get("simpleText", ""),
            "baseUrl":      track.get("baseUrl", ""),
            "kind":         track.get("kind", ""),   # "asr" = auto-generated
        })
    return tracks


def _pick_english_track(tracks: list[dict]) -> dict | None:
    """
    Priority:
      1. Manual English track (en / en-US / en-GB …)
      2. Auto-generated English track (kind == "asr")
    Returns None if no English track found.
    """
    manual_en = None
    auto_en   = None

    for t in tracks:
        code = t["languageCode"].lower()
        if code.startswith("en"):
            if t["kind"] == "asr":
                if auto_en is None:
                    auto_en = t
            else:
                if manual_en is None:
                    manual_en = t

    return manual_en or auto_en


def _download_caption_text(base_url: str) -> str:
    """
    Download the XML caption file and return clean plain text
    (timestamps stripped, text only, lines joined).
    """
    # Request as plain text transcript (fmt=srv3 or fmt=json3 also work,
    # but the default XML is simplest to parse).
    try:
        resp = requests.get(base_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"      [WARN] Caption download failed: {e}")
        return ""

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        # Some tracks come as JSON — fall back to regex
        texts = re.findall(r'"utf8"\s*:\s*"([^"]*)"', resp.text)
        return " ".join(texts)

    lines = []
    for text_el in root.iter("text"):
        raw = text_el.text or ""
        # Decode HTML entities YouTube embeds in captions
        raw = raw.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        raw = raw.replace("&#39;", "'").replace("&quot;", '"')
        raw = raw.strip()
        if raw:
            lines.append(raw)

    return " ".join(lines)


def _get_english_caption(video_url: str) -> str:
    """Top-level: extract English captions for a video URL. Returns "" if unavailable."""
    vid_id = _extract_video_id(video_url)
    if not vid_id:
        return ""

    tracks = _fetch_caption_tracks(vid_id)
    if not tracks:
        return ""

    track = _pick_english_track(tracks)
    if not track:
        return ""

    kind_label = "auto-generated" if track["kind"] == "asr" else "manual"
    print(f"      [CAPTION] Found English {kind_label} captions ({track['languageCode']})")
    return _download_caption_text(track["baseUrl"])


# ──────────────────────────────────────────────
# WATCH PAGE SCRAPER
# ──────────────────────────────────────────────

async def _expand_description(page: Page) -> None:
    """Click '...more' to expand the description if it's collapsed."""
    for selector in [
        "tp-yt-paper-button#expand",
        "ytd-text-inline-expander tp-yt-paper-button#expand",
    ]:
        try:
            btn = await page.query_selector(selector)
            if btn:
                is_hidden = await btn.get_attribute("hidden")
                if is_hidden is None:   # not hidden → clickable
                    await btn.click()
                    await page.wait_for_timeout(800)
                    return
        except Exception:
            pass


async def _scrape_description(page: Page) -> str:
    await _expand_description(page)
    for sel in [
        "ytd-text-inline-expander#description-inline-expander yt-attributed-string span.yt-core-attributed-string",
        "#description-inline-expander span.yt-core-attributed-string",
        "ytd-watch-metadata #description span.yt-core-attributed-string",
    ]:
        try:
            el = await page.query_selector(sel)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    return text
        except Exception:
            pass
    return ""


async def _scrape_upload_date(page: Page) -> str:
    """
    Upload date lives inside  <yt-formatted-string id="info">
    as one of several <span> children, alongside the view count.
    We grab all spans and pick the one that looks like a date.
    """
    date_pattern = re.compile(
        r"\b(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})\b"
    )
    try:
        spans = await page.query_selector_all("yt-formatted-string#info span")
        for span in spans:
            text = (await span.inner_text()).strip()
            if date_pattern.search(text):
                return text
    except Exception:
        pass

    # Fallback: aria-label on the date-text container
    try:
        el = await page.query_selector("div#date-text")
        if el:
            label = await el.get_attribute("aria-label")
            if label:
                return label.strip()
    except Exception:
        pass

    return ""


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

async def main():
    # ── Load input ──
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_file}")
        return

    df = pd.read_csv(input_path)
    if "video_url" not in df.columns:
        print("[ERROR] Input CSV must contain a 'video_url' column.")
        return

    # Drop rows with no URL or with empty URLs
    df = df[df["video_url"].notna() & (df["video_url"].str.strip() != "")].reset_index(drop=True)
    total = len(df)
    print(f"[INFO] {total} video(s) to process from input file.")

    # ── Resume logic ──
    last_processed = _load_last_processed()
    resume_idx = 0
    if last_processed:
        matches = df.index[df["video_url"].str.strip() == last_processed.strip()].tolist()
        if matches:
            resume_idx = matches[0] + 1
            print(f"[RESUME] Resuming from index {resume_idx} (skipping {resume_idx} already done).")
        else:
            print(f"[RESUME] Progress URL not found in input; starting from beginning.")

    # ── Prepare output file ──
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "video_url", "video_title",
        "video_description", "video_upload_date", "video_caption",
    ]
    # Append mode if resuming, write mode otherwise
    write_mode = "a" if resume_idx > 0 else "w"
    out_f = open(output_path, write_mode, newline="", encoding="utf-8")
    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
    if write_mode == "w":
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

        for idx in range(resume_idx, total):
            row = df.iloc[idx]
            video_url   = str(row["video_url"]).strip()
            video_title = str(row.get("video_title", "")).strip() if "video_title" in df.columns else ""

            print(f"\n[{idx+1}/{total}] {video_title or video_url}")

            # ── Navigate to watch page ──
            try:
                await page.goto(video_url, wait_until="load", timeout=30_000)
                await page.wait_for_timeout(PAGE_SETTLE_SECONDS * 1000)
            except Exception as e:
                print(f"    [WARN] Could not load page: {e}")
                writer.writerow({
                    "video_url":         video_url,
                    "video_title":       video_title,
                    "video_description": "",
                    "video_upload_date": "",
                    "video_caption":     "",
                })
                out_f.flush()
                _save_progress(video_url)
                continue

            # ── Scrape description ──
            description = await _scrape_description(page)
            print(f"    Description : {description[:80] + '…' if len(description) > 80 else description or '(none)'}")

            # ── Scrape upload date ──
            upload_date = await _scrape_upload_date(page)
            print(f"    Upload date : {upload_date or '(not found)'}")

            # ── Fetch captions (plain HTTP — no browser needed) ──
            caption_text = _get_english_caption(video_url)
            if caption_text:
                print(f"    Caption len : {len(caption_text)} chars")
            else:
                print(f"    Caption     : (not available in English)")

            # ── Write row ──
            writer.writerow({
                "video_url":         video_url,
                "video_title":       video_title,
                "video_description": description,
                "video_upload_date": upload_date,
                "video_caption":     caption_text,
            })
            out_f.flush()

            # ── Save progress checkpoint ──
            _save_progress(video_url)

        await browser.close()

    out_f.close()

    # All done — clear the progress file so a fresh re-run starts from scratch
    _clear_progress()
    print(f"\n[DONE] Output saved → {output_file}")


if __name__ == "__main__":
    asyncio.run(main())