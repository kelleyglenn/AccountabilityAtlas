# LLM-Powered Video Metadata Extraction — Prompt & Schema

This document defines the shared Claude extraction prompt and JSON output schema used by both the **Java video-service** (`/videos/extract` endpoint) and the **Python CLI tool** (`scripts/extract-metadata/extract.py`).

Both implementations **must** follow this specification to ensure consistent extraction results.

## Model

`claude-sonnet-4-6` — chosen for its stronger reasoning and analysis capabilities compared to Haiku, which produces more accurate classification of amendments, participants, and locations.

## Prompt Structure

The extraction uses a **user-only prompt** (no system prompt). The prompt includes XML-tagged video data, detailed classification instructions, and a multi-step analytical process that produces XML thinking tags followed by the final JSON output.

### Template Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `{{title}}` | YouTube API `snippet.title` | Video title |
| `{{description}}` | YouTube API `snippet.description` | Video description |
| `{{published}}` | YouTube API `snippet.publishedAt` | Publication date (used as reference for relative date calculations) |

### User Prompt Template

```
You are a metadata extraction assistant for AccountabilityAtlas, a platform that catalogs
videos documenting encounters between citizens and government/law enforcement in the
United States, with a focus on constitutional rights (especially First Amendment audits).

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

## Your Task

Extract structured metadata from this video and output it as a JSON object. You will identify:

1. **Constitutional amendments** involved in the encounter
2. **Types of participants** in the encounter (excluding the video publisher themselves)
3. **Date** when the encounter occurred (not the publication date)
4. **Location** where the encounter occurred
5. **Confidence scores** for each category of extracted information

## Classification Categories

### Amendments

Identify which constitutional amendments are relevant to this encounter. You may select
multiple amendments.

**Valid values:**
- **FIRST**: The encounter involves freedom of press, religion, assembly, speech, or the
  right to petition the government and/or protest
- **SECOND**: The encounter involves the right to bear firearms or other weapons
- **FOURTH**: The encounter involves the right to be free from searches or seizures,
  including issues about providing identification or requiring search warrants
- **FIFTH**: The encounter involves the right to remain silent and not incriminate oneself
- **FOURTEENTH**: The encounter involves citizenship rights for those born/naturalized in
  the U.S., or guarantees of due process and equal protection under the law

**CRITICAL CONSTRAINT for FOURTH, FIFTH, and FOURTEENTH:**
You may ONLY select these amendments if:
- POLICE or GOVERNMENT are among the participants, OR
- These specific amendments are explicitly mentioned by name in the video title or description

If you cannot identify any valid amendments after applying this constraint, default to FIRST
and assign an appropriately low confidence score.

### Participants

Identify all types of participants involved in the encounter. You may select multiple
participant types. Do NOT categorize the video publisher themselves.

**Valid values:**
- **POLICE**: Law enforcement at any level (local, city, county, state, or federal)
- **GOVERNMENT**: Government workers who are not law enforcement (e.g., mayor, city/county
  clerk, district attorneys, public works employees)
- **BUSINESS**: Owners or employees of private (non-government) businesses
- **SECURITY**: Private security personnel (not law enforcement)
- **CITIZEN**: Use this when an encounter participant is mentioned but their category cannot
  otherwise be determined

### Video Date

Extract the date when the encounter occurred (not the publication date).

- Use format: YYYY-MM-DD
- Set to null if you cannot determine the date from the title or description
- If the title and description don't specify an exact date AND don't provide a relative date
  (like "yesterday", "last Tuesday", or "five days ago"), set to null and assign a low
  confidence score

### Location

Extract location information where the encounter occurred.

**Fields to extract:**
- **name**: Location name such as a landmark (e.g., "Springfield City Hall") or street
  address. See special instructions below.
- **city**: City name
- **state**: State abbreviation (e.g., "CA", "TX")
- **latitude** and **longitude**: Set these to null UNLESS they are explicitly stated in
  the video description. Do not calculate, assume, or look up coordinates.

**Special instruction for location name:**
If you find multiple potential location names in the evidence, select ONE using this
priority order:
1. Street address (most specific)
2. Specific landmark (e.g., "City Hall", "County Courthouse")
3. General landmark (e.g., "Police Department", "Post Office")
4. If no other distinguishing factors exist, choose the first one mentioned

Set the entire location object to null if you cannot determine any location information.

### Confidence Scores

For each major field (amendments, participants, videoDate, location), provide a confidence
score between 0.0 (no confidence) and 1.0 (complete confidence) indicating how certain you
are about your extraction.

## Required Output Format

You must output ONLY a JSON object. Do NOT include markdown code fences (like ```json). Do
NOT include any explanatory text before or after the JSON.

The JSON structure:

{
  "amendments": ["AMENDMENT_NAME_1", "AMENDMENT_NAME_2"],
  "participants": ["PARTICIPANT_TYPE_1", "PARTICIPANT_TYPE_2"],
  "videoDate": "YYYY-MM-DD or null",
  "location": {
    "name": "location name or null",
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

## Processing Steps

Before constructing your final JSON output, work through the following analytical steps:

**Step 1: Extract Evidence**

Wrap your work in <evidence_extraction> tags. Extract and quote relevant information from
the video title and description. It's OK for this section to be quite long.

- Quote specific phrases that suggest constitutional concepts
- Quote specific phrases that identify participant types
- Quote any dates mentioned (absolute and relative)
- Quote any location information
- Explicitly check: Are latitude and longitude coordinates stated in the description?

**Step 2: Analyze Amendments**

Wrap your work in <amendment_analysis> tags. Map constitutional concepts to amendments.

**Step 3: Validate Amendments**

Wrap your work in <amendment_validation> tags. Validate amendment selections against the
critical constraint (FOURTH, FIFTH, FOURTEENTH require POLICE or GOVERNMENT participants
or explicit mention by name).

**Step 4: Process Date**

Wrap your work in <date_processing> tags. Determine the video date using absolute dates,
relative dates (calculated from publication date), or null.

**Step 5: Process Location**

Wrap your work in <location_processing> tags. Structure location information using the
name selection priority. Set latitude/longitude to null unless explicitly found.

**Step 6: Construct JSON**

Wrap your work in <json_construction> tags. Build the final JSON with explicit
justification for each confidence score.

**Step 7: Output Final JSON**

After completing all analytical steps, output only the final JSON object.
```

## Response Format

The model's response contains XML thinking tags followed by the final JSON:

```
<evidence_extraction>
...analysis of title and description...
</evidence_extraction>

<amendment_analysis>
...mapping concepts to amendments...
</amendment_analysis>

<amendment_validation>
...validating against constraints...
</amendment_validation>

<date_processing>
...determining video date...
</date_processing>

<location_processing>
...structuring location data...
</location_processing>

<json_construction>
...building final JSON with confidence justifications...
</json_construction>

{
  "amendments": ["FIRST"],
  "participants": ["POLICE", "GOVERNMENT"],
  "videoDate": null,
  "location": {
    "name": "City Hall",
    "city": "Springfield",
    "state": "IL",
    "latitude": null,
    "longitude": null
  },
  "confidence": {
    "amendments": 0.95,
    "participants": 0.9,
    "videoDate": null,
    "location": 0.85
  }
}
```

The service parses the last balanced `{...}` block from the response.

## Output JSON Schema

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `amendments` | `string[]` | Yes | Constitutional amendments relevant to the video. Defaults to `["FIRST"]` with low confidence if none detected. |
| `participants` | `string[]` | Yes | Types of participants shown in the video (excluding the publisher). Empty array if none detected. |
| `videoDate` | `string \| null` | Yes | Date the incident occurred (ISO 8601 `YYYY-MM-DD`). `null` if not determinable. |
| `location` | `object \| null` | Yes | Where the incident took place. `null` if not determinable. |
| `location.name` | `string` | Yes* | Specific place name, prioritized: street address > specific landmark > general landmark. |
| `location.city` | `string \| null` | Yes* | City name. `null` if not determinable. |
| `location.state` | `string \| null` | Yes* | US state abbreviation (e.g., "CA", "TX"). `null` if not determinable. |
| `location.latitude` | `number \| null` | Yes* | Latitude. Always `null` unless explicitly stated in description text. |
| `location.longitude` | `number \| null` | Yes* | Longitude. Always `null` unless explicitly stated in description text. |
| `confidence` | `object` | Yes | Confidence scores (0.0–1.0) for each extracted field. |

\* Required when `location` is not null.

## Confidence Score Interpretation

Confidence scores indicate extraction certainty. Consumers should use them to filter low-quality extractions:

| Range | Meaning | Recommended Action |
|-------|---------|-------------------|
| **0.8–1.0** | High confidence — explicitly stated or strongly supported | Apply to form automatically |
| **0.5–0.79** | Moderate confidence — reasonable inference | Apply but highlight for user review |
| **Below 0.5** | Low confidence — weak or speculative | Do not apply; ignore the value |

## Valid Enums

### Amendments

| Value | Description |
|-------|-------------|
| `FIRST` | Freedom of press, religion, assembly, speech, petition, protest |
| `SECOND` | Right to bear firearms or weapons |
| `FOURTH` | Protection against searches/seizures, ID requirements, warrant issues |
| `FIFTH` | Right to remain silent, self-incrimination protection |
| `FOURTEENTH` | Citizenship rights, due process, equal protection |

### Participants

| Value | Description |
|-------|-------------|
| `POLICE` | Law enforcement at any level (local, city, county, state, federal) |
| `GOVERNMENT` | Non-law-enforcement government employees or officials |
| `BUSINESS` | Private business owners or employees |
| `SECURITY` | Private security guards or contracted security |
| `CITIZEN` | Participants whose category cannot otherwise be determined |

## Key Extraction Rules

1. **Amendment constraint**: FOURTH, FIFTH, and FOURTEENTH require POLICE or GOVERNMENT participants, or explicit mention by name in the video text. This prevents over-classification.

2. **Default amendment**: If no amendments can be identified after applying constraints, default to FIRST with low confidence.

3. **Publisher exclusion**: Do not classify the video publisher/auditor as a participant type.

4. **Location coordinates**: Always `null` unless coordinates are explicitly written in the video description. The caller handles geocoding from name/city/state.

5. **Video date vs publication date**: Extract the date of the incident, not the upload date. Use the publication date only as a reference for calculating relative dates.

6. **Location name priority**: When multiple location names appear, select one using: street address > specific landmark > general landmark > first mentioned.

## Geocoding

Since the prompt instructs Claude to set latitude/longitude to `null` unless explicitly found in the description, consumers must geocode the location when coordinates are missing:

- **Web-app**: Calls the location-service geocode endpoint (`GET /locations/geocode?address=...`) using the extracted name/city/state
- **Python CLI**: Uses the location-service geocode endpoint or a local geocoding library
