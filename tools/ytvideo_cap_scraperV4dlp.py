"""
YouTube Video Detail Scraper
------------------------------
Extracts for each video URL from the input CSV:

  1. video_url          – from input file
  2. video_title        – from input file
  3. video_description  – via yt-dlp (no browser needed)
  4. video_upload_date  – via yt-dlp (no browser needed)
  5. video_caption      – English captions via yt-dlp (auto-generated OK)

yt-dlp handles everything: auth via browser cookies, age gates, format
changes, caption track selection. No Playwright needed at all.

RESUME SUPPORT:
  A .progress file next to the output CSV stores the last successfully
  processed URL. On restart the script skips already-done rows.

Requirements:
    pip install yt-dlp pandas

HOW AUTH WORKS:
  yt-dlp reads cookies directly from your Chrome/Firefox browser profile
  via --cookies-from-browser. Set COOKIE_BROWSER below to match the browser
  you use for YouTube (chrome, firefox, edge, brave, opera).
"""

import csv
import glob
import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd

# ──────────────────────────────────────────────
# USER-CONFIGURABLE VARIABLES
# ──────────────────────────────────────────────

# Input CSV — must contain "video_url" column. "video_title" is optional.
input_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\tools\Book2.csv"

# Where to save results.
output_file = r"C:\Users\shubh\Desktop\desktop\PROJECT SV\Project SV No Other Option\Project Kla\Project SV Web\tools\video_details.csv"

# Browser whose cookies yt-dlp should use for YouTube auth.
# Options: chrome, firefox, edge, brave, opera, chromium, safari
COOKIE_BROWSER = "brave"

# ──────────────────────────────────────────────
# RESUME / PROGRESS FILE
# ──────────────────────────────────────────────

progress_file = output_file + ".progress"

def _load_last_processed() -> str | None:
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
# yt-dlp HELPERS
# ──────────────────────────────────────────────

def _run_ytdlp(args: list[str]) -> tuple[str, str, int]:
    """Run yt-dlp and return (stdout, stderr, returncode)."""
    cmd = [sys.executable, "-m", "yt_dlp"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout, result.stderr, result.returncode


def _fetch_video_metadata(video_url: str) -> dict:
    """
    Fetch video metadata (title, description, upload_date) via yt-dlp.
    Returns a dict or {} on failure.
    """
    stdout, stderr, code = _run_ytdlp([
        "--cookies-from-browser", COOKIE_BROWSER,
        "--skip-download",
        "--no-playlist",
        "--print", "%()j",
        "--quiet",
        video_url,
    ])

    if code != 0 or not stdout.strip():
        print(f"      [WARN] yt-dlp metadata failed (code {code}): {stderr.strip()[:200]}")
        return {}

    try:
        first_line = stdout.strip().splitlines()[0]
        return json.loads(first_line)
    except (json.JSONDecodeError, IndexError) as e:
        print(f"      [WARN] JSON parse failed: {e}")
        return {}


def _fetch_captions(video_url: str) -> str:
    """
    Download English captions via yt-dlp into a temp dir.
    Tries manual captions first, falls back to auto-generated.
    Returns plain text or "" if unavailable.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        out_template = str(Path(tmpdir) / "cap")

        for sub_opts, kind_label in [
            (["--write-subs", "--no-write-auto-subs"], "manual"),
            (["--write-auto-subs", "--no-write-subs"], "auto-generated"),
        ]:
            _run_ytdlp([
                "--cookies-from-browser", COOKIE_BROWSER,
                "--skip-download",
                "--no-playlist",
                "--quiet",
                "--sub-langs", "en.*",
                "--sub-format", "json3/srv3/vtt/ttml/best",
                "-o", out_template,
            ] + sub_opts + [video_url])

            sub_files = (
                glob.glob(str(Path(tmpdir) / "*.json3")) +
                glob.glob(str(Path(tmpdir) / "*.json")) +
                glob.glob(str(Path(tmpdir) / "*.srv3")) +
                glob.glob(str(Path(tmpdir) / "*.vtt")) +
                glob.glob(str(Path(tmpdir) / "*.ttml"))
            )

            if sub_files:
                text = _parse_subtitle_file(sub_files[0])
                if text:
                    print(f"      [CAPTION] {kind_label} English captions: {len(text)} chars")
                    return text

    return ""


def _parse_subtitle_file(path: str) -> str:
    """Route to the appropriate parser based on file extension."""
    content = Path(path).read_text(encoding="utf-8", errors="replace")
    ext = Path(path).suffix.lower()

    if ext in (".json3", ".json", ".srv3"):
        return _parse_json3(content)
    elif ext == ".vtt":
        return _parse_vtt(content)
    else:
        # TTML — strip XML tags
        text = re.sub(r"<[^>]+>", " ", content)
        return re.sub(r"\s+", " ", text).strip()


def _parse_json3(raw: str) -> str:
    """Parse yt-dlp json3/srv3 subtitle format into plain text."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return ""

    lines = []
    for event in data.get("events", []):
        segs = event.get("segs")
        if not segs:
            continue
        cue = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
        if cue:
            lines.append(cue)
    return " ".join(lines)


def _parse_vtt(content: str) -> str:
    """Parse WebVTT into clean plain text, deduplicating repeated cues."""
    lines = []
    for line in content.splitlines():
        line = line.strip()
        if (not line
                or line.startswith("WEBVTT")
                or line.startswith("NOTE")
                or "-->" in line
                or re.match(r"^\d+$", line)):
            continue
        line = re.sub(r"<[^>]+>", "", line).strip()
        if line:
            lines.append(line)

    # Deduplicate consecutive identical lines
    deduped = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return " ".join(deduped)


def _format_upload_date(raw: str) -> str:
    """Convert yt-dlp YYYYMMDD to readable DD Mon YYYY."""
    if not raw or len(raw) != 8:
        return raw
    try:
        return datetime.strptime(raw, "%Y%m%d").strftime("%d %b %Y")
    except ValueError:
        return raw


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    # Verify yt-dlp is available
    _, _, code = _run_ytdlp(["--version"])
    if code != 0:
        print("[ERROR] yt-dlp not found. Run: pip install yt-dlp")
        return

    # Load input
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"[ERROR] Input file not found: {input_file}")
        return

    df = pd.read_csv(input_path)
    if "video_url" not in df.columns:
        print("[ERROR] Input CSV must contain a 'video_url' column.")
        return

    df = df[df["video_url"].notna() & (df["video_url"].str.strip() != "")].reset_index(drop=True)
    total = len(df)
    print(f"[INFO] {total} video(s) to process.")

    # Resume logic
    last_processed = _load_last_processed()
    resume_idx = 0
    if last_processed:
        matches = df.index[df["video_url"].str.strip() == last_processed.strip()].tolist()
        if matches:
            resume_idx = matches[0] + 1
            print(f"[RESUME] Resuming from index {resume_idx} (skipping {resume_idx} already done).")
        else:
            print("[RESUME] Progress URL not found in input; starting from beginning.")

    # Prepare output file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["video_url", "video_title", "video_description", "video_upload_date", "video_caption"]
    write_mode = "a" if resume_idx > 0 else "w"
    out_f = open(output_path, write_mode, newline="", encoding="utf-8")
    writer = csv.DictWriter(out_f, fieldnames=fieldnames)
    if write_mode == "w":
        writer.writeheader()

    # Process each video
    for idx in range(resume_idx, total):
        row = df.iloc[idx]
        video_url   = str(row["video_url"]).strip()
        video_title = str(row.get("video_title", "")).strip() if "video_title" in df.columns else ""

        print(f"\n[{idx+1}/{total}] {video_title or video_url}")

        # Metadata
        meta = _fetch_video_metadata(video_url)
        description = meta.get("description", "") or ""
        upload_date = _format_upload_date(meta.get("upload_date", "") or "")
        if not video_title:
            video_title = meta.get("title", "") or ""

        print(f"    Description : {description[:80] + '…' if len(description) > 80 else description or '(none)'}")
        print(f"    Upload date : {upload_date or '(not found)'}")

        # Captions
        caption_text = _fetch_captions(video_url)
        if not caption_text:
            print("    Caption     : (not available in English)")

        # Write
        writer.writerow({
            "video_url":         video_url,
            "video_title":       video_title,
            "video_description": description,
            "video_upload_date": upload_date,
            "video_caption":     caption_text,
        })
        out_f.flush()
        _save_progress(video_url)

    out_f.close()
    _clear_progress()
    print(f"\n[DONE] Output saved → {output_file}")


if __name__ == "__main__":
    main()