# Video Metadata Extraction Pipeline

A two-script Python pipeline that extracts structured metadata from YouTube videos for AccountabilityAtlas seed data.

1. **`fetch_youtube.py`** — fetches video metadata and transcripts via yt-dlp, outputs intermediate JSON
2. **`claude_extract.py`** — reads intermediate JSON, calls Claude to extract amendments/participants/dates/locations, outputs seed-data format JSON

Splitting the pipeline lets each phase run independently. If the Claude prompt changes or extraction fails, you don't need to re-fetch from YouTube.

## Prerequisites

- Python 3.10+
- `ANTHROPIC_API_KEY` environment variable set (only needed for `claude_extract.py`)

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

## Pipeline Usage

### Full pipeline: URL list → YouTube data → seed data

```bash
# 1. (Optional) Generate URL list from a YouTube channel
python ../list-channel/list_channel.py CHANNEL_ID > urls.txt

# 2. Fetch YouTube metadata + transcripts
python fetch_youtube.py --file urls.txt --output youtube-data.json

# 3. Extract structured metadata via Claude
python claude_extract.py --input youtube-data.json --output seed-data/videos.json
```

### Single URL (quick test)

```bash
# Fetch metadata to stdout
python fetch_youtube.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Or pipe directly to claude_extract.py
python fetch_youtube.py "https://www.youtube.com/watch?v=VIDEO_ID" --output single.json
python claude_extract.py --input single.json
```

## fetch_youtube.py

Fetches video metadata and auto-generated transcripts from YouTube using yt-dlp.

### Usage

```bash
# Single URL (prints JSON to stdout)
python fetch_youtube.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Bulk from file
python fetch_youtube.py --file urls.txt --output youtube-data.json

# Skip transcripts (faster)
python fetch_youtube.py --file urls.txt --output youtube-data.json --no-transcript

# Resume interrupted batch (skips already-fetched URLs)
python fetch_youtube.py --file urls.txt --output youtube-data.json --append
```

### CLI Reference

```
usage: fetch_youtube.py [-h] [--file FILE] [--output OUTPUT] [--no-transcript]
                        [--append]
                        [url]

positional arguments:
  url                   Single YouTube URL to process.

options:
  -h, --help            show this help message and exit
  --file FILE, -f FILE  Path to a text file with one YouTube URL per line.
  --output OUTPUT, -o OUTPUT
                        Output file path for JSON results.
  --no-transcript       Skip transcript fetch (faster, but less data for extraction).
  --append, -a          Append to existing output file, skipping URLs already present.
```

### Intermediate JSON Format

Output is a JSON array where each element has:

```json
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "title": "Video Title",
  "description": "Full YouTube description",
  "channel": "Channel Name",
  "thumbnail": "https://i.ytimg.com/.../maxresdefault.jpg",
  "duration": 1234,
  "published": "20240315",
  "transcript": "Full transcript text or null"
}
```

## claude_extract.py

Reads intermediate JSON from `fetch_youtube.py` and calls Claude to extract structured metadata in the seed-data format.

### Usage

```bash
# Sequential processing
python claude_extract.py --input youtube-data.json --output seed-data/videos.json

# Batch API (50% cost savings, async processing)
python claude_extract.py --input youtube-data.json --output videos.json --batch

# Resume interrupted extraction (skips already-processed URLs)
python claude_extract.py --input youtube-data.json --output videos.json --append

# Custom model
python claude_extract.py --input youtube-data.json --output videos.json --model claude-sonnet-4-20250514

# Combine flags
python claude_extract.py --input youtube-data.json --output videos.json --batch --append
```

Batch processing uses the [Message Batches API](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing) and may take minutes to hours depending on queue depth. The CLI polls for completion and prints progress updates.

### CLI Reference

```
usage: claude_extract.py [-h] --input INPUT [--output OUTPUT] [--model MODEL]
                         [--batch] [--append]

options:
  -h, --help            show this help message and exit
  --input INPUT, -i INPUT
                        Input JSON file from fetch_youtube.py.
  --output OUTPUT, -o OUTPUT
                        Output file path for JSON results.
  --model MODEL, -m MODEL
                        Claude model to use (default: claude-haiku-4-5-20251001).
  --batch, -b           Use the Message Batches API for 50% cost savings.
  --append, -a          Append to existing output file, skipping URLs already present.
```

### Seed-Data Output Format

Each entry in the output JSON array:

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

## URL File Format

One URL per line. Blank lines and lines starting with `#` are ignored:

```
# First Amendment audit videos
https://www.youtube.com/watch?v=abc123
https://www.youtube.com/watch?v=def456

# Police encounter videos
https://www.youtube.com/watch?v=ghi789
```

## How It Works

### fetch_youtube.py

1. **Fetch metadata**: Uses the `yt-dlp` Python library to extract video title, description, publication date, channel, thumbnail, and duration without downloading the video.
2. **Fetch transcript**: Optionally retrieves auto-generated English subtitles and parses them into plain text.
3. **Output**: Writes intermediate JSON with all YouTube data for downstream processing.

### claude_extract.py

1. **Read input**: Loads intermediate JSON from `fetch_youtube.py`.
2. **Call Claude**: Sends the extraction prompt with XML-tagged video data, following the shared extraction prompt spec from [`docs/llm-extraction-prompt.md`](../../docs/llm-extraction-prompt.md). In sequential mode, this is a user-only prompt (no system prompt) identical to the Java video-service. In batch mode (`--batch`), the shared instructions are sent as a system message with `cache_control` for prompt caching, and only the per-video data is in the user message. Claude responds with XML thinking tags (multi-step analysis) followed by the final JSON object.
3. **Parse response**: Extracts the last balanced JSON object from the response (skipping the XML thinking tags), matching the Java service's parsing logic.
4. **Combine results**: Merges YouTube metadata with Claude's extracted fields into the seed-data format.

If a transcript is unavailable, the tool falls back to extracting from title and description only, which typically produces lower confidence scores.
