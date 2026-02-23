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
import tempfile
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


def fetch_youtube_metadata(
    url: str,
    include_transcript: bool = True,
    cookies_from_browser: str | None = None,
) -> dict:
    """Fetch video metadata and optionally transcript from YouTube using yt-dlp.

    Subtitles are downloaded by yt-dlp to a temp directory (rather than fetched
    separately) so that cookies and rate-limit handling are applied consistently.

    Args:
        url: YouTube video URL.
        include_transcript: Whether to attempt fetching auto-generated subtitles.
        cookies_from_browser: Browser name to read cookies from (e.g., "firefox").

    Returns:
        Dictionary with keys: url, title, description, channel, thumbnail,
        duration, published (str or None), transcript (str or None).
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "ignore_no_formats_error": True,
        "sleep_requests": 0.75,
        "sleep_interval": 2,
    }

    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)

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

    with tempfile.TemporaryDirectory() as tmpdir:
        ydl_opts["outtmpl"] = str(Path(tmpdir) / "%(id)s.%(ext)s")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        transcript = None
        if include_transcript:
            transcript = _read_subtitle_file(tmpdir, info.get("id", ""))

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


def _read_subtitle_file(tmpdir: str, video_id: str) -> str | None:
    """Read a subtitle file written by yt-dlp from a temp directory.

    yt-dlp writes subtitle files as {id}.{lang}.{ext} (e.g., dQw4w9WgXcQ.en.json3).
    """
    for ext in ("json3", "vtt", "srv1", "srv2", "srv3", "ttml"):
        sub_path = Path(tmpdir) / f"{video_id}.en.{ext}"
        if sub_path.exists():
            data = sub_path.read_text(encoding="utf-8")
            return _parse_subtitle_data(data, ext)
    return None


def _parse_json3_subtitles(data: str) -> str | None:
    """Parse json3 format subtitle data into plain text."""
    try:
        parsed = json.loads(data)
    except (json.JSONDecodeError, KeyError):
        return None

    segments = []
    for event in parsed.get("events", []):
        for seg in event.get("segs", []):
            text = seg.get("utf8", "").strip()
            if text and text != "\n":
                segments.append(text)

    return " ".join(segments) if segments else None


def _is_vtt_metadata_line(line: str) -> bool:
    """Check if a line is a VTT/SRV metadata line that should be skipped."""
    if not line:
        return True
    if "-->" in line:
        return True
    if line.startswith(("WEBVTT", "Kind:", "Language:")):
        return True
    return line.isdigit()


def _parse_vtt_subtitles(data: str) -> str | None:
    """Parse VTT/SRV format subtitle data into plain text."""
    lines = []
    for raw_line in data.splitlines():
        line = raw_line.strip()
        if _is_vtt_metadata_line(line):
            continue
        # Remove HTML-style tags (e.g. <c>, </c>, <00:01:02.345>)
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if clean:
            lines.append(clean)

    if not lines:
        return None

    # Deduplicate consecutive identical lines (common in vtt)
    deduped = [lines[0]]
    for ln in lines[1:]:
        if ln != deduped[-1]:
            deduped.append(ln)
    return " ".join(deduped)


def _parse_subtitle_data(data: str, ext: str) -> str | None:
    """Parse subtitle data from various formats into plain text."""
    if ext == "json3":
        result = _parse_json3_subtitles(data)
        if result:
            return result

    return _parse_vtt_subtitles(data)


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


def _collect_urls(args) -> list[str]:
    """Collect URLs from command-line arguments or file."""
    if args.url:
        return [args.url.strip()]

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    urls = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def _write_json_output(path: Path, data: list) -> None:
    """Write a JSON array to a file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _load_existing_output(output_path: Path) -> tuple[list, set]:
    """Load existing entries from output file for append mode."""
    if not output_path.exists():
        return [], set()

    try:
        with open(output_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse existing file {output_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(entries, list):
        print(f"Error: Existing file {output_path} does not contain a JSON array.", file=sys.stderr)
        sys.exit(1)

    urls = {entry.get("url") for entry in entries}
    print(f"Loaded {len(entries)} existing entries from {output_path}.", file=sys.stderr)
    return entries, urls


def _validate_args(parser, args) -> None:
    """Validate CLI argument combinations."""
    if not args.url and not args.file:
        parser.error("Provide either a URL argument or --file with a file of URLs.")
    if args.url and args.file:
        parser.error("Provide either a URL argument or --file, not both.")
    if args.append and not args.output:
        parser.error("--append requires --output.")


def _filter_existing_urls(urls: list[str], existing_urls: set) -> list[str]:
    """Remove already-fetched URLs and report skipped count."""
    if not existing_urls:
        return urls

    filtered = [u for u in urls if u not in existing_urls]
    skipped = len(urls) - len(filtered)
    if skipped:
        print(f"Skipping {skipped} already-fetched URL(s).", file=sys.stderr)
    return filtered


def _is_rate_limited(error: Exception) -> bool:
    """Check if an error indicates YouTube rate limiting."""
    return "429" in str(error)


def _fetch_all(
    urls: list[str],
    include_transcript: bool,
    cookies_from_browser: str | None,
    output_path: Path | None,
    delay: float,
    results: list[dict],
) -> list[str]:
    """Fetch metadata for all URLs, writing incrementally. Returns errors list.

    Stops immediately on rate limiting (429) since subsequent requests
    will also fail. Progress is preserved via incremental writes.
    """
    errors = []

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Fetching metadata for: {url}", file=sys.stderr)
        try:
            data = fetch_youtube_metadata(
                url, include_transcript=include_transcript,
                cookies_from_browser=cookies_from_browser,
            )
            results.append(data)

            if include_transcript and data.get("transcript") is None:
                print("  Warning: No transcript available for this video.", file=sys.stderr)
            print(f"  Done: {data.get('title', 'Unknown')}", file=sys.stderr)

            if output_path:
                _write_json_output(output_path, results)
            if delay > 0 and i < len(urls):
                time.sleep(delay)
        except Exception as e:
            if _is_rate_limited(e):
                remaining = len(urls) - i
                print(
                    "\n  Rate limited by YouTube (HTTP 429). Stopping.",
                    file=sys.stderr,
                )
                print(
                    f"  {len(results)} video(s) saved. {remaining} remaining.",
                    file=sys.stderr,
                )
                print(
                    "  Wait for the rate limit to clear, then re-run with --append.",
                    file=sys.stderr,
                )
                errors.append(f"Rate limited at video {i}/{len(urls)}: {url}")
                break
            error_msg = f"Failed to fetch {url}: {e}"
            print(f"  Error: {error_msg}", file=sys.stderr)
            errors.append(error_msg)

    return errors


def _print_summary(
    output_path: Path | None,
    output_arg: str | None,
    results: list[dict],
    existing_count: int,
    errors: list[str],
) -> None:
    """Print final output and summary."""
    if output_path:
        print(f"\nWrote {len(results)} entries to {output_arg}.", file=sys.stderr)
    else:
        print(json.dumps(results, indent=2, ensure_ascii=False))

    new_count = len(results) - existing_count
    if errors:
        print(f"\nCompleted with {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1 if new_count == 0 else 0)
    else:
        print(f"\nSuccessfully fetched {new_count} URL(s).", file=sys.stderr)


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
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=0,
        help="Seconds to wait between videos (default: 0). Use 5-10 to avoid rate limiting.",
    )
    parser.add_argument(
        "--cookies-from-browser",
        type=str,
        default=None,
        metavar="BROWSER",
        help="Browser to read YouTube cookies from (e.g., firefox, chrome). Raises rate limits ~6x.",
    )

    args = parser.parse_args()
    _validate_args(parser, args)

    urls = _collect_urls(args)
    if not urls:
        print("Error: No URLs to process.", file=sys.stderr)
        sys.exit(1)

    # Load existing entries if appending
    existing_entries = []
    if args.append and args.output:
        existing_entries, existing_urls = _load_existing_output(Path(args.output))
        urls = _filter_existing_urls(urls, existing_urls)

    if not urls and existing_entries:
        print("All URLs already fetched. Nothing to do.", file=sys.stderr)
        sys.exit(0)

    results = list(existing_entries)
    output_path = Path(args.output) if args.output else None
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    errors = _fetch_all(
        urls,
        include_transcript=not args.no_transcript,
        cookies_from_browser=args.cookies_from_browser,
        output_path=output_path,
        delay=args.delay,
        results=results,
    )

    _print_summary(output_path, args.output, results, len(existing_entries), errors)


if __name__ == "__main__":
    main()
