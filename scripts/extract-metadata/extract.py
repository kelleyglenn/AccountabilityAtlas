#!/usr/bin/env python3
"""
Video metadata extraction CLI for AccountabilityAtlas.

Uses yt-dlp to fetch YouTube metadata and auto-generated transcripts,
then calls Claude to extract structured metadata matching the seed-data format.

Usage:
    python extract.py <url>
    python extract.py --file urls.txt --output seed-data/videos.json
    python extract.py --file urls.txt --output videos.json --append
    python extract.py --file urls.txt --output videos.json --batch
    python extract.py <url> --no-transcript
    python extract.py <url> --model claude-sonnet-4-20250514
"""

import argparse
import json
import re
import sys
import time
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


DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# --- Prompt building blocks ---
# The prompt is decomposed into reusable parts so that both sequential and batch
# modes share a single source of truth for classification instructions and
# processing steps.  See docs/llm-extraction-prompt.md for the shared spec.

_ROLE_PREAMBLE = """\
You are a metadata extraction assistant for AccountabilityAtlas, a platform that catalogs \
videos documenting encounters between citizens and government/law enforcement in the \
United States, with a focus on constitutional rights (especially First Amendment audits)."""

_VIDEO_DATA_TEMPLATE = """\
Here is the YouTube video information you need to analyze:

<video_description>
{{description}}
</video_description>

<video_title>
{{title}}
</video_title>

<publication_date>
{{published}}
</publication_date>
{{transcript_section}}"""

_TASK_LIST = """\
1. **Constitutional amendments** involved in the encounter
2. **Types of participants** in the encounter (excluding the video publisher themselves)
3. **Date** when the encounter occurred (not the publication date)
4. **Location** where the encounter occurred
5. **Confidence scores** for each category of extracted information"""

_CLASSIFICATION_AND_STEPS = """\
## Classification Categories

### Amendments

Identify which constitutional amendments are relevant to this encounter. You may select \
multiple amendments.

**Valid values:**
- **FIRST**: The encounter involves freedom of press, religion, assembly, speech, or the \
right to petition the government and/or protest
- **SECOND**: The encounter involves the right to bear firearms or other weapons
- **FOURTH**: The encounter involves the right to be free from searches or seizures, \
including issues about providing identification or requiring search warrants
- **FIFTH**: The encounter involves the right to remain silent and not incriminate oneself
- **FOURTEENTH**: The encounter involves citizenship rights for those born/naturalized in \
the U.S., or guarantees of due process and equal protection under the law

**CRITICAL CONSTRAINT for FOURTH, FIFTH, and FOURTEENTH:**
You may ONLY select these amendments if:
- POLICE or GOVERNMENT are among the participants, OR
- These specific amendments are explicitly mentioned by name in the video title or description

If you cannot identify any valid amendments after applying this constraint, default to FIRST \
and assign an appropriately low confidence score.

### Participants

Identify all types of participants involved in the encounter. You may select multiple \
participant types. Do NOT categorize the video publisher themselves.

**Valid values:**
- **POLICE**: Law enforcement at any level (local, city, county, state, or federal)
- **GOVERNMENT**: Government workers who are not law enforcement (e.g., mayor, city/county \
clerk, district attorneys, public works employees)
- **BUSINESS**: Owners or employees of private (non-government) businesses
- **SECURITY**: Private security personnel (not law enforcement)
- **CITIZEN**: Use this when an encounter participant is mentioned but their category cannot \
otherwise be determined

### Video Date

Extract the date when the encounter occurred (not the publication date).

- Use format: YYYY-MM-DD
- Set to null if you cannot determine the date from the title or description
- If the title and description don't specify an exact date AND don't provide a relative date \
(like "yesterday", "last Tuesday", or "five days ago"), set to null and assign a low \
confidence score

### Location

Extract location information where the encounter occurred.

**Fields to extract:**
- **name**: Location name such as a landmark (e.g., "Springfield City Hall") or street \
address. See special instructions below.
- **streetAddress**: The street address of the named location (e.g., "800 E Monroe St"). \
If you know the physical street address from your training data, provide it. If you \
are not confident, set to null. Do NOT fabricate addresses.
- **city**: City name
- **state**: State abbreviation (e.g., "CA", "TX")
- **latitude** and **longitude**: Set these to null UNLESS they are explicitly stated in \
the video description. Do not calculate, assume, or look up coordinates.

**Special instruction for location name:**
If you find multiple potential location names in the evidence, select ONE using this \
priority order:
1. Street address (most specific)
2. Specific landmark (e.g., "City Hall", "County Courthouse")
3. General landmark (e.g., "Police Department", "Post Office")
4. If no other distinguishing factors exist, choose the first one mentioned

Set the entire location object to null if you cannot determine any location information.

### Confidence Scores

For each major field (amendments, participants, videoDate, location), provide a confidence \
score between 0.0 (no confidence) and 1.0 (complete confidence) indicating how certain you \
are about your extraction.

## Required Output Format

You must output ONLY a JSON object. Do NOT include markdown code fences (like ```json). Do \
NOT include any explanatory text before or after the JSON.

The JSON structure:

```json
{
  "amendments": ["AMENDMENT_NAME_1", "AMENDMENT_NAME_2"],
  "participants": ["PARTICIPANT_TYPE_1", "PARTICIPANT_TYPE_2"],
  "videoDate": "YYYY-MM-DD or null",
  "location": {
    "name": "location name or null",
    "streetAddress": "street address or null",
    "city": "city name or null",
    "state": "XX or null",
    "latitude": 0.0 or null,
    "longitude": 0.0 or null
  },
  "confidence": {
    "amendments": 0.0,
    "participants": 0.0,
    "videoDate": 0.0,
    "location": 0.0
  }
}
```

## Processing Steps

Before constructing your final JSON output, work through the following analytical steps:

**Step 1: Extract Evidence**

Wrap your work in <evidence_extraction> tags. Extract and quote relevant information from \
the video title and description. It's OK for this section to be quite long.

- Quote specific phrases that suggest constitutional concepts (e.g., "filming in public", \
"refused to ID", "open carry", "detained")
- Quote specific phrases that identify participant types (e.g., "officer", "deputy", \
"city clerk", "security guard", "store manager")
- Quote any dates mentioned (both absolute dates like "January 15, 2024" and relative dates \
like "yesterday" or "last week")
- Quote any location information (city names, state names, building names, street addresses)
- Explicitly check: Are latitude and longitude coordinates stated in the description? If \
yes, quote them exactly.

**Step 2: Analyze Amendments**

Wrap your work in <amendment_analysis> tags. Map the constitutional concepts to amendments:

- For each constitutional concept you identified, determine which amendment(s) it relates to
- List all potentially relevant amendments with your reasoning
- Note which participant types you've identified so far

**Step 3: Validate Amendments**

Wrap your work in <amendment_validation> tags. Validate your amendment selections against \
the critical constraint:

- For each amendment you're considering (FIRST, SECOND, FOURTH, FIFTH, FOURTEENTH), \
explicitly write "VALID" or "INVALID" next to it
- For FOURTH, FIFTH, and FOURTEENTH specifically: Check if POLICE or GOVERNMENT are \
participants, OR if these amendments are explicitly mentioned by name in the \
title/description. Write out your reasoning for marking each as VALID or INVALID.
- For FIRST and SECOND: These don't have the critical constraint, so explain why they are \
VALID or INVALID based on the content alone
- If all amendments are marked INVALID, note that you will default to FIRST with low \
confidence

**Step 4: Process Date**

Wrap your work in <date_processing> tags to determine the video date:

- Is there an absolute date in the title/description? If yes, convert it to YYYY-MM-DD format
- Is there a relative date (e.g., "yesterday", "last Tuesday")? If yes, calculate the \
actual date using the publication date as reference
- If neither, note that videoDate should be null
- Assess what your confidence score should be based on the specificity of date information

**Step 5: Process Location**

Wrap your work in <location_processing> tags to structure the location information:

- List out ALL potential location names found in the evidence (landmarks, street addresses, \
building names)
- If multiple location names exist, apply the selection priority: street address > specific \
landmark > general landmark > first mentioned. Explain your selection by evaluating each \
candidate against these criteria.
- Extract the city (if any)
- Extract the state (if any)
- If the location is a well-known government building, courthouse, police station, or \
other prominent landmark, provide the street address if you know it confidently. \
If unsure, set streetAddress to null.
- For latitude/longitude: Set to null unless you explicitly found coordinates in Step 1
- If no location information was found, note that location should be null
- Assess what your confidence score should be based on the specificity of location information

**Step 6: Construct JSON**

Wrap your work in <json_construction> tags to build your JSON object step by step:

- Finalize the amendments array (only VALID amendments from Step 3)
- Finalize the participants array
- Set the videoDate value
- Structure the location object with the selected location name
- Assign confidence scores for each field. For each of the four confidence scores \
(amendments, participants, videoDate, location), write out explicit justification for \
the specific numeric value you're assigning (e.g., "amendments: 0.85 because X, Y, \
and Z").

**Step 7: Output Final JSON**

After completing all analytical steps, output only the final JSON object with no additional \
text, no markdown formatting, and no code fences."""

# --- Composed templates ---

# Sequential mode: single user-only prompt (matches Java video-service structure).
# The only addition is the optional {{transcript_section}}.
USER_PROMPT_TEMPLATE = (
    _ROLE_PREAMBLE + "\n\n"
    + _VIDEO_DATA_TEMPLATE + "\n"
    + "## Your Task\n\n"
    + "Extract structured metadata from this video and output it as a JSON object. "
    + "You will identify:\n\n"
    + _TASK_LIST + "\n\n"
    + _CLASSIFICATION_AND_STEPS
)

# Batch mode: shared instructions as system message (cacheable with cache_control).
BATCH_SYSTEM_PROMPT = (
    _ROLE_PREAMBLE + "\n\n"
    + "## Your Task\n\n"
    + "You will be given YouTube video information in XML tags. Extract structured metadata "
    + "from the video and output it as a JSON object. You will identify:\n\n"
    + _TASK_LIST + "\n\n"
    + _CLASSIFICATION_AND_STEPS
)

# Batch mode: per-video data only (varies per request, not cached).
BATCH_USER_TEMPLATE = (
    _VIDEO_DATA_TEMPLATE + "\n"
    + "Analyze this video following the instructions above."
)


# --- Helpers ---


def _build_transcript_section(transcript: str | None) -> str:
    """Build the XML-tagged transcript section for prompt insertion."""
    if not transcript:
        return ""
    return "\n<transcript>\n" + transcript + "\n</transcript>\n"


def _truncate_message(message: str, max_len: int = 180_000) -> str:
    """Truncate a message to stay within context limits."""
    if len(message) <= max_len:
        return message
    notice = "\n\n[Transcript truncated due to length]"
    return message[: max_len - len(notice)] + notice


def _fill_template(
    template: str,
    title: str,
    description: str,
    published: str | None,
    transcript: str | None,
) -> str:
    """Fill a prompt template with video data."""
    return (
        template
        .replace("{{title}}", title or "")
        .replace("{{description}}", description or "")
        .replace("{{published}}", published or "unknown")
        .replace("{{transcript_section}}", _build_transcript_section(transcript))
    )


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


# --- Message building ---


def build_user_message(title: str, description: str, published: str | None, transcript: str | None) -> str:
    """Build the user message for Claude following the shared prompt spec.

    Uses USER_PROMPT_TEMPLATE with the same structure as the Java video-service.
    When a transcript is available, it is inserted as an additional XML-tagged section.
    """
    return _fill_template(USER_PROMPT_TEMPLATE, title, description, published, transcript)


def build_batch_user_message(
    title: str, description: str, published: str | None, transcript: str | None
) -> str:
    """Build the per-video user message for batch mode.

    Uses BATCH_USER_TEMPLATE which contains only the video data XML tags
    and a brief instruction. The shared extraction instructions are in the
    system message (BATCH_SYSTEM_PROMPT) for prompt caching optimization.
    """
    return _fill_template(BATCH_USER_TEMPLATE, title, description, published, transcript)


# --- JSON extraction ---


def _extract_json(text: str) -> str:
    """Extract the last top-level JSON object from the response text.

    The response may contain XML thinking tags (evidence_extraction,
    amendment_analysis, etc.) followed by the final JSON object.
    This finds the last balanced {...} block in the response, matching
    the Java service's extractJson logic.
    """
    trimmed = text.strip()

    # Handle code fences if present
    if trimmed.startswith("```"):
        first_newline = trimmed.index("\n") if "\n" in trimmed else -1
        if first_newline >= 0:
            last_fence = trimmed.rfind("```")
            if last_fence > first_newline:
                trimmed = trimmed[first_newline + 1 : last_fence].strip()

    # Find the last '}' and walk back to find its matching '{'
    last_brace = trimmed.rfind("}")
    if last_brace < 0:
        return trimmed

    depth = 0
    for i in range(last_brace, -1, -1):
        c = trimmed[i]
        if c == "}":
            depth += 1
        elif c == "{":
            depth -= 1
            if depth == 0:
                return trimmed[i : last_brace + 1]

    return trimmed


# --- Claude extraction ---


def extract_metadata_with_claude(
    client: anthropic.Anthropic,
    youtube_data: dict,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Call Claude to extract structured metadata from video information.

    Uses the same user-only prompt as the Java video-service, with an
    additional transcript section when available. See docs/llm-extraction-prompt.md.

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
        published=youtube_data.get("published"),
        transcript=youtube_data.get("transcript"),
    )

    user_message = _truncate_message(user_message)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()
    json_str = _extract_json(raw_text)

    try:
        return json.loads(json_str)
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
            "streetAddress": location.get("streetAddress"),
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


def process_urls_batch(
    urls: list[str],
    client: anthropic.Anthropic,
    model: str,
    include_transcript: bool,
) -> tuple[list[dict], list[str]]:
    """Process multiple URLs using the Message Batches API for 50% cost savings.

    Submits all requests as a single batch and polls for completion.
    The prompt is split into a shared system message (with cache_control)
    and per-video user messages to maximize prompt caching hits.

    Args:
        urls: List of YouTube video URLs.
        client: Anthropic client instance.
        model: Claude model ID.
        include_transcript: Whether to fetch transcripts.

    Returns:
        Tuple of (results list, errors list).
    """
    # Phase 1: Fetch YouTube metadata for all URLs
    youtube_data = {}
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] Fetching metadata for: {url}", file=sys.stderr)
        try:
            youtube_data[url] = fetch_youtube_metadata(url, include_transcript=include_transcript)
            has_transcript = youtube_data[url].get("transcript") is not None
            if include_transcript and not has_transcript:
                print(
                    "  Warning: No transcript available. Will extract from title+description only.",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"  Error fetching metadata: {e}", file=sys.stderr)
            # Skip this URL entirely — can't submit to batch without metadata

    if not youtube_data:
        return [], [f"Failed to fetch metadata for all {len(urls)} URLs"]

    # Phase 2: Build and submit the batch
    print(f"\nSubmitting batch of {len(youtube_data)} requests...", file=sys.stderr)

    requests = []
    for url, yt_data in youtube_data.items():
        user_message = build_batch_user_message(
            title=yt_data["title"],
            description=yt_data["description"],
            published=yt_data.get("published"),
            transcript=yt_data.get("transcript"),
        )

        user_message = _truncate_message(user_message)

        requests.append(
            {
                "custom_id": url,
                "params": {
                    "model": model,
                    "max_tokens": 4096,
                    "system": [
                        {
                            "type": "text",
                            "text": BATCH_SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "messages": [{"role": "user", "content": user_message}],
                },
            }
        )

    batch = client.messages.batches.create(requests=requests)
    print(f"Batch created: {batch.id}", file=sys.stderr)

    # Phase 3: Poll for completion
    while batch.processing_status != "ended":
        counts = batch.request_counts
        print(
            f"  Batch {batch.id}: "
            f"{counts.succeeded} succeeded, "
            f"{counts.errored} errored, "
            f"{counts.processing} processing, "
            f"{counts.canceled} canceled",
            file=sys.stderr,
        )
        time.sleep(60)
        batch = client.messages.batches.retrieve(batch.id)

    counts = batch.request_counts
    print(
        f"\nBatch complete: {counts.succeeded} succeeded, "
        f"{counts.errored} errored, "
        f"{counts.expired} expired, "
        f"{counts.canceled} canceled",
        file=sys.stderr,
    )

    # Phase 4: Retrieve and process results
    results = []
    errors = []

    for entry in client.messages.batches.results(batch.id):
        url = entry.custom_id
        if entry.result.type == "succeeded":
            try:
                raw_text = entry.result.message.content[0].text.strip()
                json_str = _extract_json(raw_text)
                claude_metadata = json.loads(json_str)
                results.append(build_output_entry(url, youtube_data[url], claude_metadata))
                print(f"  Processed: {youtube_data[url].get('title', url)}", file=sys.stderr)
            except (json.JSONDecodeError, IndexError, KeyError) as e:
                errors.append(f"Failed to parse response for {url}: {e}")
        elif entry.result.type == "errored":
            error_msg = getattr(entry.result.error, "message", str(entry.result.error))
            errors.append(f"API error for {url}: {error_msg}")
        elif entry.result.type == "expired":
            errors.append(f"Request expired for {url}")
        elif entry.result.type == "canceled":
            errors.append(f"Request canceled for {url}")

    # Also count URLs that failed metadata fetch
    for url in urls:
        if url not in youtube_data:
            errors.append(f"Failed to fetch YouTube metadata for {url}")

    return results, errors


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
    parser.add_argument(
        "--batch",
        "-b",
        action="store_true",
        help=(
            "Use the Message Batches API for bulk processing (requires --file). "
            "Submits all requests as a single batch for 50%% cost savings."
        ),
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.url and not args.file:
        parser.error("Provide either a URL argument or --file with a file of URLs.")
    if args.url and args.file:
        parser.error("Provide either a URL argument or --file, not both.")
    if args.append and not args.output:
        parser.error("--append requires --output.")
    if args.batch and not args.file:
        parser.error("--batch requires --file.")

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

    if args.batch:
        batch_results, batch_errors = process_urls_batch(
            urls, client, args.model, include_transcript
        )
        results.extend(batch_results)
        errors.extend(batch_errors)
    else:
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
