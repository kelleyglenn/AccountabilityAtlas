# LLM-Powered Video Metadata Extraction — Prompt & Schema

This document defines the shared Claude extraction prompt and JSON output schema used by both the **Java video-service** (`/videos/extract` endpoint) and the **Python CLI tool** (`scripts/extract-metadata/extract.py`).

Both implementations **must** follow this specification to ensure consistent extraction results.

## System Prompt

```
You are a metadata extraction assistant for AccountabilityAtlas, a platform that catalogs
videos of encounters between citizens and government/law enforcement in the United States,
focusing on constitutional rights (especially First Amendment audits).

Given a YouTube video's title, description, and optionally its transcript, extract structured
metadata about the video. Respond ONLY with a JSON object — no markdown fences, no explanation.
```

## User Message Template

### Title + Description only (video-service endpoint)

```
Extract metadata from this YouTube video:

Title: {title}

Description:
{description}
```

### Title + Description + Transcript (Python CLI with transcript)

```
Extract metadata from this YouTube video:

Title: {title}

Description:
{description}

Transcript:
{transcript}
```

## Output JSON Schema

```json
{
  "amendments": ["FIRST", "FOURTH"],
  "participants": ["POLICE", "CITIZEN"],
  "videoDate": "2024-03-15",
  "location": {
    "name": "City Hall",
    "city": "Los Angeles",
    "state": "CA",
    "latitude": null,
    "longitude": null
  },
  "confidence": {
    "amendments": 0.9,
    "participants": 0.85,
    "videoDate": 0.6,
    "location": 0.8
  }
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `amendments` | `string[]` | Yes | Constitutional amendments relevant to the video. Empty array if none detected. |
| `participants` | `string[]` | Yes | Types of participants shown in the video. Empty array if none detected. |
| `videoDate` | `string \| null` | Yes | Date the incident occurred (ISO 8601 `YYYY-MM-DD`). `null` if not determinable. |
| `location` | `object \| null` | Yes | Where the incident took place. `null` if not determinable. |
| `location.name` | `string` | Yes* | Specific place name (e.g., "City Hall", "Post Office"). |
| `location.city` | `string \| null` | Yes* | City name. `null` if not determinable. |
| `location.state` | `string \| null` | Yes* | US state abbreviation (e.g., "CA", "TX"). `null` if not determinable. |
| `location.latitude` | `number \| null` | Yes* | Latitude coordinate. `null` unless explicitly stated in the text. |
| `location.longitude` | `number \| null` | Yes* | Longitude coordinate. `null` unless explicitly stated in the text. |
| `confidence` | `object` | Yes | Confidence scores (0.0–1.0) for each extracted field. |

\* Required when `location` is not null.

## Valid Enums

### Amendments

| Value | Description |
|-------|-------------|
| `FIRST` | Freedom of speech, press, assembly, religion, petition |
| `SECOND` | Right to bear arms |
| `FOURTH` | Protection against unreasonable search and seizure |
| `FIFTH` | Due process, self-incrimination, double jeopardy |
| `FOURTEENTH` | Equal protection, due process (state level) |

### Participants

| Value | Description |
|-------|-------------|
| `POLICE` | Law enforcement officers (local, state, federal) |
| `GOVERNMENT` | Non-law-enforcement government employees or officials |
| `BUSINESS` | Private business owners or employees |
| `CITIZEN` | Members of the public exercising or observing rights |
| `SECURITY` | Private security guards or contracted security |

## Extraction Rules

1. **First Amendment audits**: If the video is a "First Amendment audit" (filming in public, testing rights to record), always include `FIRST` in amendments and `CITIZEN` in participants.

2. **Default participant**: If a person is recording/auditing, include `CITIZEN`. If police respond, include `POLICE`.

3. **Confidence scale**: Use 0.0–1.0 where:
   - **0.9–1.0**: Explicitly stated in title/description/transcript
   - **0.7–0.8**: Strongly implied by context
   - **0.5–0.6**: Reasonable inference but uncertain
   - **Below 0.5**: Do not include the field (set to null or empty array instead)

4. **Video date**: Extract the date of the incident, NOT the upload date. Set to `null` if only the upload date is available or if no date can be determined.

5. **Location coordinates**: Set `latitude` and `longitude` to `null` unless exact coordinates appear in the text. The caller will geocode from the name/city/state. Do NOT guess or hallucinate coordinates.

6. **State abbreviation**: Use standard US two-letter state abbreviations (e.g., "CA" not "California").

7. **Multiple amendments**: A single video can involve multiple amendments (e.g., filming in public = FIRST, police search = FOURTH).

8. **Transcript advantage**: When a transcript is available, confidence scores should generally be higher since more context is available. Title+description-only extraction should have moderately lower confidence scores.

9. **Empty results**: If the video clearly has nothing to do with constitutional rights or government encounters, return empty arrays for amendments and participants, null for videoDate and location, with low confidence scores.

10. **No markdown**: Respond with raw JSON only. Do not wrap the response in markdown code fences (`` ```json ... ``` ``).
