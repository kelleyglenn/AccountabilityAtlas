# Seed Data Quality Filters Design

**Goal:** Add confidence-based filtering to `seed-videos.sh` so entries with unreliable metadata are automatically skipped during loading.

**Context:** The AI extraction pipeline (`claude_extract.py`) produces confidence scores for each field. Currently `seed-videos.sh` ignores these scores, leading to videos with vague locations, wrong participants, or non-accountability content being loaded into the system. The API already rejects entries with missing coordinates or empty participants, but lower-quality data slips through.

## Filtering Rules

### 1. Location confidence (primary filter)

**Rule:** Skip entries where location confidence is below 0.6, unless the location has a name, street address, and coordinates — in which case allow down to 0.55.

**Rationale:** The AI assigns low location confidence when the location was inferred from context (video title mentions a city). However, if the enrichment step independently found and geocoded a real street address, that corroborates the location. The 0.55 threshold with street-address verification catches genuinely vague locations ("bar parking lot", "Pocatello") while keeping well-geocoded ones (Apple Store with exact street address).

**Impact:** Excludes 9 entries from the current dataset (4 below 0.55, 5 at 0.55-0.59 without street addresses). Keeps 1 entry at 0.55 that has a verified street address.

### 2. Non-accountability content (combined confidence filter)

**Rule:** Skip entries where both amendments confidence is below 0.5 AND participants confidence is below 0.8.

**Rationale:** Videos that are genuinely about accountability encounters have high confidence in at least one of these fields. When both are low, the video is typically non-accountability content (product reviews, compilations, commentary). Using a combined check avoids false positives: a yard sale police raid has low amendment confidence (0.2) but high participant confidence (0.95), so it passes.

**Impact:** Excludes 2 entries (a Rolex product video and a hospital incident commentary).

### 3. Video date confidence (nullify, don't exclude)

**Rule:** If video date confidence is below 0.5, send the video without a date (don't include `videoDate` in the API request). Do not exclude the video.

**Rationale:** An uncertain date is worse than no date. The video itself is still valid content. In the current dataset this has no practical impact (all entries with dates set already have confidence >= 0.5), but it's a safety net for future data files.

**Impact:** 0 dates nullified in current dataset. No entries excluded.

### 4. No additional participants cutoff

Participants confidence is overwhelmingly high (354 of 431 loadable entries are >= 0.9). The 7 entries below 0.8 still have plausible participant tags and are legitimate accountability videos. The non-accountability filter (rule 2) already catches the truly irrelevant ones.

## Implementation

All filtering happens in `seed-videos.sh` using jq, before any API calls. A new `FILTERED` counter tracks skipped entries separately from API failures.

The filter check runs immediately after extracting the entry, before location creation or video creation. The output shows the skip reason:

```
[88/452] Olight Seeker 2 PRO in Limited Edition Blue REVIEW... filtered (amendments < 0.5 and participants < 0.8)
```

### Filter logic (pseudocode)

```
confidence = entry.confidence
location = entry.location

# Rule 1: Location confidence
if location exists and location has coordinates:
    loc_conf = confidence.location
    if loc_conf < 0.55:
        skip("location confidence too low")
    elif loc_conf < 0.6:
        if location missing name OR location missing streetAddress:
            skip("location confidence 0.55-0.59 without street address")

# Rule 2: Non-accountability content
amend_conf = confidence.amendments
part_conf = confidence.participants
if amend_conf < 0.5 AND part_conf < 0.8:
    skip("likely not accountability content")

# Rule 3: Video date confidence
if confidence.videoDate < 0.5:
    nullify videoDate (send without date)
```

## Summary

| Filter | Entries excluded | Entries loaded |
|--------|-----------------|----------------|
| No coordinates (existing) | 19 | - |
| No participants (existing) | 2 | - |
| Location confidence | 9 | - |
| Non-accountability content | 2 | - |
| **Total** | **32** | **420 / 452 (93%)** |
