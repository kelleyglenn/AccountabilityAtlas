# YouTube Channel Video Lister

A Python CLI tool that lists video URLs from a YouTube channel, with optional date and duration filtering. Output is compatible with `extract.py --file` for the metadata extraction pipeline.

## Prerequisites

- Python 3.10+

## Installation

```bash
cd scripts/list-channel
pip install -r requirements.txt
```

Or with a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
```

## Usage

### Basic Usage

List all non-Shorts videos from a channel (prints to stdout):

```bash
python list_channel.py "@ChannelName"
```

### Limit Results

```bash
python list_channel.py "@ChannelName" -n 10
```

### Filter by Date

```bash
python list_channel.py "@ChannelName" --after 2024-01-01
python list_channel.py "@ChannelName" --after 2024-01-01 --before 2025-01-01
```

### Save to File

```bash
python list_channel.py "@ChannelName" -o urls.txt
```

### Channel Identifier Formats

The tool accepts multiple formats for specifying a channel:

```bash
python list_channel.py "@AuditTheAudit"
python list_channel.py "UCwobzUc3z-0PrFpoRxNszXQ"
python list_channel.py "https://www.youtube.com/@AuditTheAudit"
```

### Pipeline with extract.py

List channel URLs, then extract metadata:

```bash
python list_channel.py "@ChannelName" -n 20 -o urls.txt
cd ../extract-metadata
python extract.py --file ../list-channel/urls.txt --output ../../seed-data/videos.json
```

## Output Format

```
# Channel: @ChannelName
# Fetched: 2026-02-22
# Count: 47
https://www.youtube.com/watch?v=abc123
https://www.youtube.com/watch?v=def456
```

Lines starting with `#` are comments. `extract.py --file` ignores comment lines and blank lines.

## Shorts Filtering

By default, videos shorter than 61 seconds are excluded to filter out YouTube Shorts. Adjust with `--min-duration`:

```bash
# Include all videos (no duration filter)
python list_channel.py "@ChannelName" --min-duration 0

# Only videos longer than 5 minutes
python list_channel.py "@ChannelName" --min-duration 300
```

## CLI Reference

```
usage: list_channel.py [-h] [-n MAX_RESULTS] [--after AFTER] [--before BEFORE]
                       [--min-duration MIN_DURATION] [-o OUTPUT]
                       channel

positional arguments:
  channel               Channel URL, @handle, or UCxxxx channel ID.

options:
  -h, --help            show this help message and exit
  -n, --max-results MAX_RESULTS
                        Maximum number of videos to return (default: no limit).
  --after AFTER         Only include videos published on/after this date (YYYY-MM-DD).
  --before BEFORE       Only include videos published on/before this date (YYYY-MM-DD).
  --min-duration MIN_DURATION
                        Minimum video duration in seconds (default: 61, filters Shorts).
  -o, --output OUTPUT   Output file path (default: stdout).
```
