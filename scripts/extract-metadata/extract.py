#!/usr/bin/env python3
"""
Video metadata extraction CLI for AccountabilityAtlas.

Uses yt-dlp to fetch YouTube metadata and auto-generated transcripts,
then calls Claude to extract structured metadata matching the seed-data format.

Usage:
    python extract.py <url>
    python extract.py --file urls.txt --output seed-data/videos.json
    python extract.py --file urls.txt --output videos.json --append
    python extract.py <url> --no-transcript
    python extract.py <url> --model claude-sonnet-4-20250514
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    print(
        "Error: 'anthropic' package is not installed. "
        "Run: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import yt_dlp
except ImportError:
    print(
        "Error: 'yt-dlp' package is not installed. "
        "Run: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


SYSTEM_PROMPT = (
    "You are a metadata extraction assistant for AccountabilityAtlas, a platform that catalogs\n"
    "videos of encounters between citizens and government/law enforcement in the United States,\n"
    "focusing on constitutional rights (especially First Amendment audits).\n"
    "\n"
    "Given a YouTube video's title, description, and optionally its transcript, extract structured\n"
    "metadata about the video. Respond ONLY with a JSON object — no markdown fences, no explanation."
)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def fetch_youtube_metadata(url: str, include_transcript: bool = True) -> dict:
    """Fetch video metadata and optionally transcript from YouTube using yt-dlp.

    Args:
        url: YouTube video URL.
        include_transcript: Whether to attempt fetching auto-generated subtitles.

    Returns:
        Dictionary with keys: url, title, description, channel, thumbnail,
        duration, transcript (str or None).
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "best",
    }

    if include_transcript:
        ydl_opts.update(
            {
                "writeautomaticsub": True,
                "writesubtitles": True,
                "subtitleslangs": ["en"],
                "subtitlesformat": "json3",
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
        try:
            import urllib.request

            with urllib.request.urlopen(sub_url, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return _parse_subtitle_data(raw, en_sub.get("ext", ""))
        except Exception:
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
        import re

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


def build_user_message(title: str, description: str, transcript: str | None) -> str:
    """Build the user message for Claude following the shared prompt spec."""
    msg = f"Extract metadata from this YouTube video:\n\nTitle: {title}\n\nDescription:\n{description}"
    if transcript:
        msg += f"\n\nTranscript:\n{transcript}"
    return msg


def extract_metadata_with_claude(
    client: anthropic.Anthropic,
    youtube_data: dict,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Call Claude to extract structured metadata from video information.

    Args:
        client: Anthropic client instance.
        youtube_data: Dictionary from fetch_youtube_metadata().
        model: Claude model ID to use.

    Returns:
        Parsed JSON metadata from Claude's response.
    """
    user_message = build_user_message(
        title=youtube_data["title"],
        description=youtube_data["description"],
        transcript=youtube_data.get("transcript"),
    )

    # Truncate very long transcripts to stay within context limits
    max_message_len = 180_000
    if len(user_message) > max_message_len:
        truncation_notice = "\n\n[Transcript truncated due to length]"
        user_message = user_message[: max_message_len - len(truncation_notice)] + truncation_notice

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown fences if Claude included them despite instructions
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        raw_text = "\n".join(lines).strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse Claude's response as JSON: {e}", file=sys.stderr)
        print(f"Raw response:\n{raw_text}", file=sys.stderr)
        raise


def build_output_entry(url: str, youtube_data: dict, claude_metadata: dict) -> dict:
    """Combine YouTube metadata and Claude extraction into the seed-data format.

    Returns a dictionary matching the expected output schema with youtubeUrl,
    title, description, channelName, thumbnailUrl, durationSeconds, and all
    Claude-extracted fields.
    """
    location = claude_metadata.get("location")
    if location is not None:
        # Ensure all expected location fields exist
        location = {
            "name": location.get("name"),
            "city": location.get("city"),
            "state": location.get("state"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
        }

    confidence = claude_metadata.get("confidence", {})
    confidence = {
        "amendments": confidence.get("amendments", 0.0),
        "participants": confidence.get("participants", 0.0),
        "videoDate": confidence.get("videoDate", 0.0),
        "location": confidence.get("location", 0.0),
    }

    return {
        "youtubeUrl": youtube_data.get("url") or url,
        "title": youtube_data.get("title", ""),
        "description": youtube_data.get("description", ""),
        "channelName": youtube_data.get("channel", ""),
        "thumbnailUrl": youtube_data.get("thumbnail"),
        "durationSeconds": youtube_data.get("duration"),
        "amendments": claude_metadata.get("amendments", []),
        "participants": claude_metadata.get("participants", []),
        "videoDate": claude_metadata.get("videoDate"),
        "location": location,
        "confidence": confidence,
    }


def process_single_url(
    url: str,
    client: anthropic.Anthropic,
    model: str,
    include_transcript: bool,
) -> dict:
    """Process a single YouTube URL end-to-end.

    Args:
        url: YouTube video URL.
        client: Anthropic client instance.
        model: Claude model ID.
        include_transcript: Whether to fetch transcript.

    Returns:
        Output entry dictionary in seed-data format.
    """
    print(f"Fetching metadata for: {url}", file=sys.stderr)
    youtube_data = fetch_youtube_metadata(url, include_transcript=include_transcript)

    has_transcript = youtube_data.get("transcript") is not None
    if include_transcript and not has_transcript:
        print(
            "  Warning: No transcript available. Extracting from title+description only.",
            file=sys.stderr,
        )

    print(f"  Calling Claude ({model})...", file=sys.stderr)
    claude_metadata = extract_metadata_with_claude(client, youtube_data, model=model)

    entry = build_output_entry(url, youtube_data, claude_metadata)
    print(f"  Done: {entry.get('title', 'Unknown')}", file=sys.stderr)
    return entry


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured metadata from YouTube videos for AccountabilityAtlas.",
        epilog="Requires ANTHROPIC_API_KEY environment variable to be set.",
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
        "--model",
        "-m",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--no-transcript",
        action="store_true",
        help="Skip transcript fetch (faster, but less accurate extraction).",
    )
    parser.add_argument(
        "--append",
        "-a",
        action="store_true",
        help="Append to existing output file instead of overwriting.",
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

    # Initialize Anthropic client
    try:
        client = anthropic.Anthropic()
    except anthropic.AuthenticationError:
        print(
            "Error: ANTHROPIC_API_KEY environment variable is not set or invalid.",
            file=sys.stderr,
        )
        sys.exit(1)

    include_transcript = not args.no_transcript

    # Load existing entries if appending
    existing_entries = []
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

    # Process URLs
    results = list(existing_entries)
    errors = []

    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}]", file=sys.stderr)
        try:
            entry = process_single_url(url, client, args.model, include_transcript)
            results.append(entry)
        except Exception as e:
            error_msg = f"Failed to process {url}: {e}"
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
        print(f"\nSuccessfully processed {new_count} URL(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
