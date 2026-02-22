#!/usr/bin/env python3
"""
YouTube metadata + transcript fetcher for AccountabilityAtlas.

Uses yt-dlp to fetch video metadata and auto-generated transcripts,
writing intermediate JSON for downstream processing by claude_extract.py.

Usage:
    python fetch_youtube.py <url>
    python fetch_youtube.py --file urls.txt --output youtube-data.json
    python fetch_youtube.py --file urls.txt --output youtube-data.json --no-transcript
    python fetch_youtube.py --file urls.txt --output youtube-data.json --append
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print(
        "Error: 'yt-dlp' package is not installed. "
        "Run: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


# --- YouTube fetching ---


def fetch_youtube_metadata(url: str, include_transcript: bool = True) -> dict:
    """Fetch video metadata and optionally transcript from YouTube using yt-dlp.

    Args:
        url: YouTube video URL.
        include_transcript: Whether to attempt fetching auto-generated subtitles.

    Returns:
        Dictionary with keys: url, title, description, channel, thumbnail,
        duration, published (str or None), transcript (str or None).
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "best",
        "sleep_requests": 0.75,
        "sleep_interval": 2,
    }

    if include_transcript:
        ydl_opts.update(
            {
                "writeautomaticsub": True,
                "writesubtitles": True,
                "subtitleslangs": ["en"],
                "subtitlesformat": "json3",
                "sleep_subtitles": 5,
            }
        )

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    transcript = None
    if include_transcript:
        transcript = _extract_transcript(info)

    thumbnail = _pick_best_thumbnail(info)

    return {
        "url": info.get("webpage_url") or url,
        "title": info.get("title", ""),
        "description": info.get("description", ""),
        "channel": info.get("channel") or info.get("uploader", ""),
        "thumbnail": thumbnail,
        "duration": info.get("duration"),
        "published": info.get("upload_date"),
        "transcript": transcript,
    }


def _extract_transcript(info: dict) -> str | None:
    """Extract transcript text from yt-dlp subtitle data.

    yt-dlp stores fetched subtitles under 'requested_subtitles' when available.
    The json3 format contains an 'events' list with 'segs' (segments) containing 'utf8' text.
    Falls back to vtt/srv format text parsing if json3 is unavailable.
    """
    subs = info.get("requested_subtitles") or {}
    en_sub = subs.get("en")
    if not en_sub:
        return None

    # If yt-dlp returned the subtitle data directly (json3 format)
    sub_data = en_sub.get("data")
    if sub_data:
        return _parse_subtitle_data(sub_data, en_sub.get("ext", ""))

    # If yt-dlp provided a URL but no inline data, we need to fetch it
    sub_url = en_sub.get("url")
    if sub_url:
        import urllib.request

        for attempt in range(3):
            try:
                with urllib.request.urlopen(sub_url, timeout=15) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                return _parse_subtitle_data(raw, en_sub.get("ext", ""))
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 2:
                    wait = 5 * (attempt + 1)
                    print(
                        f"  Subtitle fetch rate-limited, retrying in {wait}s...",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                else:
                    print(f"  Subtitle fetch failed: {e}", file=sys.stderr)
                    return None
            except Exception as e:
                print(f"  Subtitle fetch failed: {e}", file=sys.stderr)
                return None

    return None


def _parse_subtitle_data(data: str, ext: str) -> str | None:
    """Parse subtitle data from various formats into plain text."""
    if ext == "json3":
        try:
            parsed = json.loads(data)
            segments = []
            for event in parsed.get("events", []):
                for seg in event.get("segs", []):
                    text = seg.get("utf8", "").strip()
                    if text and text != "\n":
                        segments.append(text)
            if segments:
                return " ".join(segments)
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: strip timing lines from vtt/srv formats
    lines = []
    for line in data.splitlines():
        line = line.strip()
        # Skip empty lines, timing lines, WEBVTT headers, and numeric cue IDs
        if not line:
            continue
        if "-->" in line:
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if line.isdigit():
            continue
        # Remove HTML-style tags (e.g. <c>, </c>, <00:01:02.345>)
        clean = re.sub(r"<[^>]+>", "", line)
        if clean.strip():
            lines.append(clean.strip())

    if lines:
        # Deduplicate consecutive identical lines (common in vtt)
        deduped = [lines[0]]
        for ln in lines[1:]:
            if ln != deduped[-1]:
                deduped.append(ln)
        return " ".join(deduped)

    return None


def _pick_best_thumbnail(info: dict) -> str | None:
    """Select the best thumbnail URL from yt-dlp info.

    Prefers maxresdefault, then high-quality thumbnails, then whatever is available.
    """
    thumbnails = info.get("thumbnails") or []
    thumbnail = info.get("thumbnail")

    if not thumbnails:
        return thumbnail

    # Prefer known high-quality YouTube thumbnail names
    for t in thumbnails:
        url = t.get("url", "")
        if "maxresdefault" in url:
            return url

    for t in thumbnails:
        url = t.get("url", "")
        if "hqdefault" in url or "sddefault" in url:
            return url

    # Fall back to highest resolution available
    best = max(
        (t for t in thumbnails if t.get("width")),
        key=lambda t: (t.get("width", 0) * t.get("height", 0)),
        default=None,
    )
    if best:
        return best.get("url")

    return thumbnail


def main():
    parser = argparse.ArgumentParser(
        description="Fetch YouTube video metadata and transcripts for AccountabilityAtlas.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Single YouTube URL to process.",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        help="Path to a text file with one YouTube URL per line.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output file path for JSON results. If not specified, prints to stdout.",
    )
    parser.add_argument(
        "--no-transcript",
        action="store_true",
        help="Skip transcript fetch (faster, but less data for extraction).",
    )
    parser.add_argument(
        "--append",
        "-a",
        action="store_true",
        help="Append to existing output file, skipping URLs already present.",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.url and not args.file:
        parser.error("Provide either a URL argument or --file with a file of URLs.")
    if args.url and args.file:
        parser.error("Provide either a URL argument or --file, not both.")
    if args.append and not args.output:
        parser.error("--append requires --output.")

    # Collect URLs
    urls = []
    if args.url:
        urls.append(args.url.strip())
    else:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.append(line)

    if not urls:
        print("Error: No URLs to process.", file=sys.stderr)
        sys.exit(1)

    include_transcript = not args.no_transcript

    # Load existing entries if appending
    existing_entries = []
    existing_urls = set()
    if args.append and args.output:
        output_path = Path(args.output)
        if output_path.exists():
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    existing_entries = json.load(f)
                if not isinstance(existing_entries, list):
                    print(
                        f"Error: Existing file {args.output} does not contain a JSON array.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                existing_urls = {entry.get("url") for entry in existing_entries}
                print(
                    f"Loaded {len(existing_entries)} existing entries from {args.output}.",
                    file=sys.stderr,
                )
            except json.JSONDecodeError as e:
                print(
                    f"Error: Failed to parse existing file {args.output}: {e}",
                    file=sys.stderr,
                )
                sys.exit(1)

    # Filter out already-fetched URLs when appending
    if existing_urls:
        original_count = len(urls)
        urls = [u for u in urls if u not in existing_urls]
        skipped = original_count - len(urls)
        if skipped:
            print(f"Skipping {skipped} already-fetched URL(s).", file=sys.stderr)

    if not urls and existing_entries:
        print("All URLs already fetched. Nothing to do.", file=sys.stderr)
        sys.exit(0)

    # Fetch metadata for each URL
    results = list(existing_entries)
    errors = []

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Fetching metadata for: {url}", file=sys.stderr)
        try:
            data = fetch_youtube_metadata(url, include_transcript=include_transcript)
            results.append(data)

            has_transcript = data.get("transcript") is not None
            if include_transcript and not has_transcript:
                print(
                    "  Warning: No transcript available for this video.",
                    file=sys.stderr,
                )
            print(f"  Done: {data.get('title', 'Unknown')}", file=sys.stderr)
        except Exception as e:
            error_msg = f"Failed to fetch {url}: {e}"
            print(f"  Error: {error_msg}", file=sys.stderr)
            errors.append(error_msg)

    # Output results
    output_json = json.dumps(results, indent=2, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json)
            f.write("\n")
        print(f"\nWrote {len(results)} entries to {args.output}.", file=sys.stderr)
    else:
        print(output_json)

    # Summary
    new_count = len(results) - len(existing_entries)
    if errors:
        print(f"\nCompleted with {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1 if new_count == 0 else 0)
    else:
        print(f"\nSuccessfully fetched {new_count} URL(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
