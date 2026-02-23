#!/usr/bin/env python3
"""
Claude LLM metadata extraction for AccountabilityAtlas.

Reads intermediate JSON from fetch_youtube.py and uses Claude to extract
structured metadata (amendments, participants, dates, locations) in
the seed-data format.

Usage:
    python claude_extract.py --input youtube-data.json --output seed-data/videos.json
    python claude_extract.py --input youtube-data.json --output videos.json --batch
    python claude_extract.py --input youtube-data.json --output videos.json --append
    python claude_extract.py --input youtube-data.json --output videos.json --model claude-sonnet-4-20250514
"""

import argparse
import json
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


# --- Message building ---


def build_user_message(title: str, description: str, published: str | None, transcript: str | None) -> str:
    """Build the user message for Claude following the shared prompt spec."""
    return _fill_template(USER_PROMPT_TEMPLATE, title, description, published, transcript)


def build_batch_user_message(
    title: str, description: str, published: str | None, transcript: str | None
) -> str:
    """Build the per-video user message for batch mode."""
    return _fill_template(BATCH_USER_TEMPLATE, title, description, published, transcript)


# --- JSON extraction ---


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences (```...```) from text."""
    if not text.startswith("```"):
        return text
    first_newline = text.find("\n")
    if first_newline < 0:
        return text
    last_fence = text.rfind("```")
    if last_fence <= first_newline:
        return text
    return text[first_newline + 1 : last_fence].strip()


def _extract_json(text: str) -> str:
    """Extract the last top-level JSON object from the response text.

    The response may contain XML thinking tags (evidence_extraction,
    amendment_analysis, etc.) followed by the final JSON object.
    This finds the last balanced {...} block in the response, matching
    the Java service's extractJson logic.
    """
    trimmed = _strip_code_fences(text.strip())

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

    Args:
        client: Anthropic client instance.
        youtube_data: Dictionary from fetch_youtube.py intermediate JSON.
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
    """Combine YouTube metadata and Claude extraction into the seed-data format."""
    location = claude_metadata.get("location")
    if location is not None:
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


def process_single(
    youtube_data: dict,
    client: anthropic.Anthropic,
    model: str,
) -> dict:
    """Process a single video entry through Claude extraction.

    Args:
        youtube_data: Dictionary from fetch_youtube.py intermediate JSON.
        client: Anthropic client instance.
        model: Claude model ID.

    Returns:
        Output entry dictionary in seed-data format.
    """
    url = youtube_data.get("url", "")
    print(f"  Calling Claude ({model})...", file=sys.stderr)
    claude_metadata = extract_metadata_with_claude(client, youtube_data, model=model)

    entry = build_output_entry(url, youtube_data, claude_metadata)
    print(f"  Done: {entry.get('title', 'Unknown')}", file=sys.stderr)
    return entry


def _process_batch_entry(
    entry,
    yt_data: dict,
    url: str,
    results: list[dict],
    errors: list[str],
) -> None:
    """Process a single result from the Message Batches API response."""
    result_type = entry.result.type

    if result_type != "succeeded":
        _ERROR_MESSAGES = {
            "errored": lambda: f"API error for {url}: "
            + getattr(entry.result.error, "message", str(entry.result.error)),
            "expired": lambda: f"Request expired for {url}",
            "canceled": lambda: f"Request canceled for {url}",
        }
        msg_fn = _ERROR_MESSAGES.get(result_type)
        if msg_fn:
            errors.append(msg_fn())
        return

    try:
        raw_text = entry.result.message.content[0].text.strip()
        json_str = _extract_json(raw_text)
        claude_metadata = json.loads(json_str)
        results.append(build_output_entry(url, yt_data, claude_metadata))
        print(f"  Processed: {yt_data.get('title', url)}", file=sys.stderr)
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        errors.append(f"Failed to parse response for {url}: {e}")


def process_batch(
    youtube_data_list: list[dict],
    client: anthropic.Anthropic,
    model: str,
) -> tuple[list[dict], list[str]]:
    """Process multiple videos using the Message Batches API for 50% cost savings.

    Submits all requests as a single batch and polls for completion.
    The prompt is split into a shared system message (with cache_control)
    and per-video user messages to maximize prompt caching hits.

    Args:
        youtube_data_list: List of dictionaries from fetch_youtube.py intermediate JSON.
        client: Anthropic client instance.
        model: Claude model ID.

    Returns:
        Tuple of (results list, errors list).
    """
    print(f"\nSubmitting batch of {len(youtube_data_list)} requests...", file=sys.stderr)

    requests = []
    # custom_id must be [a-zA-Z0-9_-]{1,64} — use video ID, map back to index
    id_to_index = {}
    for idx, yt_data in enumerate(youtube_data_list):
        url = yt_data.get("url", "")
        video_id = url.split("watch?v=")[-1].split("&")[0] if "watch?v=" in url else f"idx-{idx}"
        id_to_index[video_id] = idx

        user_message = build_batch_user_message(
            title=yt_data["title"],
            description=yt_data["description"],
            published=yt_data.get("published"),
            transcript=yt_data.get("transcript"),
        )

        user_message = _truncate_message(user_message)

        requests.append(
            {
                "custom_id": video_id,
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

    # Poll for completion
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

    # Retrieve and process results
    results = []
    errors = []

    for entry in client.messages.batches.results(batch.id):
        video_id = entry.custom_id
        idx = id_to_index.get(video_id)
        if idx is None:
            errors.append(f"Unknown custom_id in batch response: {video_id}")
            continue
        yt_data = youtube_data_list[idx]
        url = yt_data.get("url", video_id)
        _process_batch_entry(entry, yt_data, url, results, errors)

    return results, errors


def _load_json_array(path: Path, label: str) -> list:
    """Load and validate a JSON array from a file, exiting on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse {label} {path}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print(f"Error: {label} {path} does not contain a JSON array.", file=sys.stderr)
        sys.exit(1)

    return data


def _load_existing_output(output_path: Path) -> tuple[list, set]:
    """Load existing entries from output file for append mode."""
    if not output_path.exists():
        return [], set()

    entries = _load_json_array(output_path, "Existing file")
    urls = {entry.get("youtubeUrl") for entry in entries}
    print(f"Loaded {len(entries)} existing entries from {output_path}.", file=sys.stderr)
    return entries, urls


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured metadata from YouTube data using Claude for AccountabilityAtlas.",
        epilog="Requires ANTHROPIC_API_KEY environment variable to be set.",
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Input JSON file from fetch_youtube.py.",
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
        "--batch",
        "-b",
        action="store_true",
        help="Use the Message Batches API for 50%% cost savings.",
    )
    parser.add_argument(
        "--append",
        "-a",
        action="store_true",
        help="Append to existing output file, skipping URLs already present.",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.append and not args.output:
        parser.error("--append requires --output.")

    # Load input data
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    youtube_data_list = _load_json_array(input_path, "Input file")

    if not youtube_data_list:
        print("Error: Input file contains no entries.", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(youtube_data_list)} entries from {args.input}.", file=sys.stderr)

    # Initialize Anthropic client
    try:
        client = anthropic.Anthropic()
    except anthropic.AuthenticationError:
        print(
            "Error: ANTHROPIC_API_KEY environment variable is not set or invalid.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load existing entries if appending
    existing_entries = []
    existing_urls = set()
    if args.append and args.output:
        existing_entries, existing_urls = _load_existing_output(Path(args.output))

    # Filter out already-processed entries when appending
    if existing_urls:
        original_count = len(youtube_data_list)
        youtube_data_list = [
            d for d in youtube_data_list if d.get("url") not in existing_urls
        ]
        skipped = original_count - len(youtube_data_list)
        if skipped:
            print(f"Skipping {skipped} already-extracted URL(s).", file=sys.stderr)

    if not youtube_data_list and existing_entries:
        print("All entries already extracted. Nothing to do.", file=sys.stderr)
        sys.exit(0)

    # Process entries
    results = list(existing_entries)
    errors = []

    if args.batch:
        batch_results, batch_errors = process_batch(
            youtube_data_list, client, args.model
        )
        results.extend(batch_results)
        errors.extend(batch_errors)
    else:
        for i, yt_data in enumerate(youtube_data_list, 1):
            url = yt_data.get("url", "unknown")
            print(f"\n[{i}/{len(youtube_data_list)}] Processing: {url}", file=sys.stderr)
            try:
                entry = process_single(yt_data, client, args.model)
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
        print(f"\nSuccessfully processed {new_count} entry(ies).", file=sys.stderr)


if __name__ == "__main__":
    main()
