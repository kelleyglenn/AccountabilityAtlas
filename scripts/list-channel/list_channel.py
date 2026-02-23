#!/usr/bin/env python3
"""
YouTube channel video URL lister for AccountabilityAtlas.

Uses yt-dlp to fetch video URLs from a YouTube channel, filtering by date
and duration (to exclude Shorts). Output is compatible with extract.py --file.

Usage:
    python list_channel.py "@ChannelName"
    python list_channel.py "@ChannelName" -n 10
    python list_channel.py "@ChannelName" --after 2024-01-01 --before 2025-01-01
    python list_channel.py "https://www.youtube.com/@ChannelName" -o urls.txt
"""

import argparse
import sys
from datetime import datetime

try:
    import yt_dlp
except ImportError:
    print(
        "Error: 'yt-dlp' package is not installed. "
        "Run: pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)


_CHANNEL_PATH_SUFFIXES = ("/videos", "/shorts", "/streams", "/playlists", "/community")


def _strip_channel_path_suffix(url: str) -> str:
    """Strip known YouTube channel path suffixes from a URL."""
    url = url.rstrip("/")
    for suffix in _CHANNEL_PATH_SUFFIXES:
        if url.endswith(suffix):
            return url[: -len(suffix)]
    return url


def normalize_channel_url(channel: str) -> str:
    """Normalize a channel identifier to a full YouTube URL with /videos suffix.

    Accepts:
        - @handle (e.g., "@AuditTheAudit")
        - UCxxxx channel ID (e.g., "UCwobzUc3z-0PrFpoRxNszXQ")
        - Full URL (e.g., "https://www.youtube.com/@AuditTheAudit")

    Returns:
        Full YouTube URL ending with /videos.
    """
    channel = channel.strip()

    # Already a full URL
    if channel.startswith(("http://", "https://")):
        return _strip_channel_path_suffix(channel) + "/videos"

    # @handle
    if channel.startswith("@"):
        return f"https://www.youtube.com/{channel}/videos"

    # UCxxxx channel ID
    if channel.startswith("UC") and len(channel) == 24:
        return f"https://www.youtube.com/channel/{channel}/videos"

    # Assume it's a handle without the @
    return f"https://www.youtube.com/@{channel}/videos"


def _build_ydl_opts(max_results: int | None) -> dict:
    """Build yt-dlp options for channel video extraction."""
    opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "ignoreerrors": True,
    }

    # Over-fetch to account for Shorts/date filtering that will remove entries
    if max_results is not None:
        opts["playlistend"] = max_results * 3

    return opts


def _is_outside_date_range(
    upload_date: str, after_date: str | None, before_date: str | None
) -> bool:
    """Check if an upload date falls outside the specified range."""
    if not upload_date:
        return False
    if after_date and upload_date < after_date:
        return True
    if before_date and upload_date > before_date:
        return True
    return False


def _parse_entry(
    entry: dict | None,
    min_duration: int,
    after_date: str | None,
    before_date: str | None,
) -> dict | None:
    """Parse a single yt-dlp entry into a video dict, or None if filtered out."""
    if entry is None:
        return None

    duration = entry.get("duration") or 0
    if duration < min_duration:
        return None

    upload_date = entry.get("upload_date", "")
    if _is_outside_date_range(upload_date, after_date, before_date):
        return None

    video_url = entry.get("webpage_url") or entry.get("url", "")
    if not video_url:
        return None

    # Ensure it's a proper watch URL, not a channel/playlist URL
    video_id = entry.get("id", "")
    if video_id and "watch?v=" not in video_url:
        video_url = f"https://www.youtube.com/watch?v={video_id}"

    return {
        "url": video_url,
        "title": entry.get("title", ""),
        "duration": duration,
        "upload_date": upload_date,
    }


def fetch_channel_videos(
    channel_url: str,
    max_results: int | None = None,
    after_date: str | None = None,
    before_date: str | None = None,
    min_duration: int = 61,
) -> list[dict]:
    """Fetch video metadata from a YouTube channel using yt-dlp.

    Args:
        channel_url: Normalized YouTube channel URL (ending in /videos).
        max_results: Maximum number of videos to return after filtering.
        after_date: Only include videos published on/after this date (YYYYMMDD).
        before_date: Only include videos published on/before this date (YYYYMMDD).
        min_duration: Minimum duration in seconds (default 61, filters Shorts).

    Returns:
        List of dicts with keys: url, title, duration, upload_date.
    """
    ydl_opts = _build_ydl_opts(max_results)

    print(f"Fetching videos from: {channel_url}", file=sys.stderr)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    if not info:
        print("Error: Could not extract channel information.", file=sys.stderr)
        return []

    videos = []
    for entry in info.get("entries") or []:
        video = _parse_entry(entry, min_duration, after_date, before_date)
        if video is not None:
            videos.append(video)
            if max_results is not None and len(videos) >= max_results:
                break

    return videos


def format_output(videos: list[dict], channel_name: str) -> str:
    """Format video URLs as one-per-line output with header comments.

    Args:
        videos: List of video dicts from fetch_channel_videos().
        channel_name: Channel name for the header comment.

    Returns:
        Formatted string with # comments and URLs.
    """
    lines = [
        f"# Channel: {channel_name}",
        f"# Fetched: {datetime.now().strftime('%Y-%m-%d')}",
        f"# Count: {len(videos)}",
    ]

    for video in videos:
        lines.append(video["url"])

    return "\n".join(lines) + "\n"


def _parse_date_arg(parser, value: str | None, name: str) -> str | None:
    """Validate a YYYY-MM-DD date argument and convert to YYYYMMDD."""
    if value is None:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        parser.error(f"{name} must be in YYYY-MM-DD format, got: {value}")
    return value.replace("-", "")


def main():
    parser = argparse.ArgumentParser(
        description="List YouTube video URLs from a channel for AccountabilityAtlas.",
        epilog="Output is compatible with extract.py --file (# comment lines are ignored).",
    )
    parser.add_argument(
        "channel",
        help="Channel URL, @handle, or UCxxxx channel ID.",
    )
    parser.add_argument(
        "-n",
        "--max-results",
        type=int,
        default=None,
        help="Maximum number of videos to return (default: no limit).",
    )
    parser.add_argument(
        "--after",
        type=str,
        default=None,
        help="Only include videos published on/after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--before",
        type=str,
        default=None,
        help="Only include videos published on/before this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--min-duration",
        type=int,
        default=61,
        help="Minimum video duration in seconds (default: 61, filters Shorts).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output file path (default: stdout).",
    )

    args = parser.parse_args()

    # Validate date formats and convert to YYYYMMDD for yt-dlp comparison
    after_yyyymmdd = _parse_date_arg(parser, args.after, "--after")
    before_yyyymmdd = _parse_date_arg(parser, args.before, "--before")

    channel_url = normalize_channel_url(args.channel)

    videos = fetch_channel_videos(
        channel_url=channel_url,
        max_results=args.max_results,
        after_date=after_yyyymmdd,
        before_date=before_yyyymmdd,
        min_duration=args.min_duration,
    )

    if not videos:
        print("No videos found matching the criteria.", file=sys.stderr)
        sys.exit(0)

    # Try to extract channel name from the first video or use the input
    channel_name = args.channel
    output = format_output(videos, channel_name)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(
            f"Wrote {len(videos)} URLs to {args.output}",
            file=sys.stderr,
        )
    else:
        print(output, end="")

    print(f"Found {len(videos)} videos.", file=sys.stderr)


if __name__ == "__main__":
    main()
