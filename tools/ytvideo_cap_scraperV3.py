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
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import pandas as pd
from playwright.async_api import async_playwright, Page

# ──────────────────────────────────────────────
# USER-CONFIGURABLE VARIABLES
# ──────────────────────────────────────────────

# Output CSV from yt_channel_scraper.py — must contain "video_url" column.
# "video_title" column is optional but carried over if present.
input_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\tools\Book2.csv"

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
# CAPTION FETCHER  (runs inside the authenticated Playwright browser)
# ──────────────────────────────────────────────
# The timedtext API URLs are session-locked — they require the browser's
# YouTube auth cookies to return content. Plain requests() calls get an
# empty 200 response. We use page.evaluate() to run fetch() inside the
# browser context so all cookies are sent automatically.

def _extract_video_id(url: str) -> str | None:
    """Pull the v= param out of any youtube watch URL."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    ids = qs.get("v")
    return ids[0] if ids else None




def _parse_caption_json3(raw: str) -> str:
    """
    Parse YouTube's fmt=json3 caption response into clean plain text.

    json3 structure:
      { "events": [ { "segs": [ { "utf8": "caption text" }, ... ] }, ... ] }

    Each event is one cue. Each cue has a "segs" list of text segments.
    We join all segment text, normalise whitespace, and join cues with spaces.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return ""

    lines = []
    for event in data.get("events", []):
        segs = event.get("segs")
        if not segs:
            continue
        cue = "".join(s.get("utf8", "") for s in segs)
        cue = html.unescape(cue).strip()
        # json3 uses "\n" within cues — normalise to spaces
        cue = cue.replace("\n", " ").strip()
        if cue:
            lines.append(cue)

    return " ".join(lines)


async def _get_english_caption(page: Page, video_url: str) -> str:
    """
    Extract English captions from the already-loaded watch page.

    Key insight: when multiple English tracks share the same base signature
    (common on YouTube), the URL is only valid for the track whose lang= param
    matches the signature. We therefore try EVERY English track in priority
    order and return the first one that yields a non-empty body.

    Priority order: asr (auto-generated) first because its URL is always the
    one the signature was issued for, then any manual English tracks.
    """
    # Step 1: read caption track list directly from the page's JS context
    try:
        tracks = await page.evaluate("""() => {
            try {
                const pr = ytInitialPlayerResponse;
                const tl = pr?.captions?.playerCaptionsTracklistRenderer?.captionTracks;
                if (!tl) return [];
                return tl.map(t => ({
                    languageCode: t.languageCode || '',
                    kind:         t.kind || '',
                    name:         t.name?.simpleText || '',
                    baseUrl:      t.baseUrl || '',
                }));
            } catch(e) { return []; }
        }""")
    except Exception as e:
        print(f"      [WARN] Could not read caption tracks: {e}")
        return ""

    if not tracks:
        return ""

    # Collect all English tracks: asr first, then manual, preserving order
    en_tracks = [t for t in tracks if t.get("kind") == "asr" and t.get("languageCode","").lower().startswith("en")]
    en_tracks += [t for t in tracks if t.get("kind") != "asr" and t.get("languageCode","").lower().startswith("en")]

    if not en_tracks:
        return ""

    # Step 2: try each track until we get a non-empty response
    for track in en_tracks:
        base_url = track.get("baseUrl", "")
        if not base_url:
            continue

        caption_url = base_url + ("&" if "?" in base_url else "?") + "fmt=json3"

        try:
            result = await page.evaluate("""async (url) => {
                const resp = await fetch(url);
                const text = await resp.text();
                return { ok: resp.ok, body: text };
            }""", caption_url)
        except Exception as e:
            print(f"      [WARN] fetch failed for {track['languageCode']}: {e}")
            continue

        if not result.get("ok") or not result.get("body"):
            continue

        text = _parse_caption_json3(result["body"])
        if text:
            kind_label = "auto-generated" if track.get("kind") == "asr" else "manual"
            print(f"      [CAPTION] {kind_label} English captions ({track['languageCode']}): {len(text)} chars")
            return text

    return ""


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

            # ── Fetch captions via browser (carries auth cookies) ──
            caption_text = await _get_english_caption(page, video_url)
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