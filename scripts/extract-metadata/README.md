# Video Metadata Extraction CLI

A Python CLI tool that extracts structured metadata from YouTube videos for AccountabilityAtlas seed data. It uses `yt-dlp` to fetch video metadata and auto-generated transcripts, then calls Claude to extract amendments, participants, dates, and locations.

## Prerequisites

- Python 3.10+
- `ANTHROPIC_API_KEY` environment variable set with a valid Anthropic API key

## Installation

```bash
cd scripts/extract-metadata
pip install -r requirements.txt
```

Or with a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
```

## Usage

### Single URL

Prints JSON to stdout:

```bash
python extract.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Bulk Processing

Process a file of URLs (one per line) and write results to a JSON file:

```bash
python extract.py --file urls.txt --output seed-data/videos.json
```

### Append to Existing File

Add new entries to an existing JSON array file without overwriting:

```bash
python extract.py --file more-urls.txt --output seed-data/videos.json --append
```

### Skip Transcript

Faster extraction using only title and description (lower confidence scores):

```bash
python extract.py --no-transcript "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Batch Processing

Use the [Message Batches API](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing) for **50% cost savings** on bulk processing. Requests are submitted as a single batch and processed asynchronously:

```bash
python extract.py --file urls.txt --output seed-data/videos.json --batch
```

Batch processing may take minutes to hours depending on queue depth. The CLI polls for completion and prints progress updates. The output format is identical to sequential mode.

The `--batch` flag can be combined with other options:

```bash
python extract.py --file urls.txt --output videos.json --batch --append --no-transcript
```

### Custom Model

Override the default Claude model:

```bash
python extract.py --model claude-sonnet-4-20250514 "https://www.youtube.com/watch?v=VIDEO_ID"
```

## URL File Format

One URL per line. Blank lines and lines starting with `#` are ignored:

```
# First Amendment audit videos
https://www.youtube.com/watch?v=abc123
https://www.youtube.com/watch?v=def456

# Police encounter videos
https://www.youtube.com/watch?v=ghi789
```

## Output Format

Each entry in the output JSON array follows this schema:

```json
{
  "youtubeUrl": "https://www.youtube.com/watch?v=...",
  "title": "Video Title",
  "description": "Video description from YouTube",
  "channelName": "Channel Name",
  "thumbnailUrl": "https://i.ytimg.com/vi/.../maxresdefault.jpg",
  "durationSeconds": 1234,
  "amendments": ["FIRST"],
  "participants": ["POLICE", "CITIZEN"],
  "videoDate": "2024-03-15",
  "location": {
    "name": "City Hall",
    "streetAddress": "200 N Spring St",
    "city": "Los Angeles",
    "state": "CA",
    "latitude": null,
    "longitude": null
  },
  "confidence": {
    "amendments": 0.9,
    "participants": 0.85,
    "videoDate": 0.7,
    "location": 0.95
  }
}
```

### Fields from YouTube (via yt-dlp)

| Field | Description |
|-------|-------------|
| `youtubeUrl` | Canonical YouTube URL |
| `title` | Video title |
| `description` | Video description |
| `channelName` | YouTube channel name |
| `thumbnailUrl` | Highest quality thumbnail URL |
| `durationSeconds` | Video duration in seconds |

### Fields from Claude (via LLM extraction)

| Field | Description |
|-------|-------------|
| `amendments` | Constitutional amendments relevant to the video (e.g., `FIRST`, `FOURTH`) |
| `participants` | Types of participants (e.g., `POLICE`, `CITIZEN`, `GOVERNMENT`) |
| `videoDate` | Date of the incident (ISO 8601), or `null` if not determinable |
| `location` | Location object with name, streetAddress, city, state, latitude, longitude; or `null` |
| `confidence` | Confidence scores (0.0-1.0) for each extracted field |

See [docs/llm-extraction-prompt.md](../../docs/llm-extraction-prompt.md) for the full extraction prompt specification, valid enum values, and extraction rules.

## How It Works

1. **Fetch metadata**: Uses the `yt-dlp` Python library to extract video title, description, publication date, channel, thumbnail, and duration without downloading the video.
2. **Fetch transcript**: Optionally retrieves auto-generated English subtitles and parses them into plain text.
3. **Call Claude**: Sends the extraction prompt with XML-tagged video data, following the shared extraction prompt spec from [`docs/llm-extraction-prompt.md`](../../docs/llm-extraction-prompt.md). In sequential mode, this is a user-only prompt (no system prompt) identical to the Java video-service. In batch mode (`--batch`), the shared instructions are sent as a system message with `cache_control` for prompt caching, and only the per-video data is in the user message. Claude responds with XML thinking tags (multi-step analysis) followed by the final JSON object.
4. **Parse response**: Extracts the last balanced JSON object from the response (skipping the XML thinking tags), matching the Java service's parsing logic.
5. **Combine results**: Merges YouTube metadata with Claude's extracted fields into the seed-data format.

If a transcript is unavailable, the tool falls back to extracting from title and description only, which typically produces lower confidence scores.

## CLI Reference

```
usage: extract.py [-h] [--file FILE] [--output OUTPUT] [--model MODEL]
                  [--no-transcript] [--append] [--batch]
                  [url]

positional arguments:
  url                   Single YouTube URL to process.

options:
  -h, --help            show this help message and exit
  --file FILE, -f FILE  Path to a text file with one YouTube URL per line.
  --output OUTPUT, -o OUTPUT
                        Output file path for JSON results.
  --model MODEL, -m MODEL
                        Claude model to use (default: claude-haiku-4-5-20251001).
  --no-transcript       Skip transcript fetch (faster, less accurate).
  --append, -a          Append to existing output file instead of overwriting.
  --batch, -b           Use Message Batches API for 50% cost savings (requires --file).
```
