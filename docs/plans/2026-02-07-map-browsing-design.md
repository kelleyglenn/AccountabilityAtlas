# Map Browsing Experience - Design Document

**Date:** 2026-02-07
**Status:** Draft
**Goal:** Enable users to discover constitutional audit videos via an interactive map, view video details, and allow users to submit content — all end-to-end from database to UI with full test coverage.

## Overview

This feature set creates the core map-based discovery experience for AccountabilityAtlas. Users can browse videos on an interactive map, filter by amendments and participants, view video details, and submit new videos. Moderators can review submissions from new users via a dedicated dashboard.

### Services to Build

| Service | Purpose |
|---------|---------|
| **video-service** | Video metadata CRUD, YouTube API integration, owns video-location relationships |
| **location-service** | Location entities, geocoding, bounding box queries, server-side clustering |
| **moderation-service** | Approval queue, approve/reject workflow, consumes VideoSubmitted events |
| **search-service** | Denormalized read layer, filters (amendments, participants, date), spatial search |

### Services to Update

| Service | Changes |
|---------|---------|
| **api-gateway** | Add routes for new services |
| **web-app** | Map page, side panel, video detail page, submission form, moderation dashboard |

### Infrastructure Additions

| Component | Purpose |
|-----------|---------|
| LocalStack | SQS emulation for event-driven messaging (local dev) |
| Mapbox | Maps, geocoding, places autocomplete |
| YouTube Data API | Fetch video metadata on submission |

---

## Map Page

**Route:** `/` or `/map`

### Layout (Desktop)

- Left side panel (fixed width, ~350px) with scrollable video list
- Main area: Mapbox map filling remaining space
- Top bar: Location search input + filter controls

### Layout (Mobile)

- Full-screen map
- Draggable bottom sheet (collapsed → half → full) showing video list
- Top bar: Location search + hamburger for filters

### Map Behavior

| Feature | Behavior |
|---------|----------|
| Initial view | Auto-zoom to fit all markers in dataset |
| Markers | Custom DOM elements with `data-video-id` attributes (for Playwright testability) |
| Clustering | Server-side via location-service; cluster markers show count, click to zoom in |
| Marker click | Centers map, scrolls side panel to video, opens info card popup |

### Side Panel

- Shows videos visible in current map viewport
- Each item: thumbnail, title, metadata chips (amendments, location name)
- **Hover:** Highlights corresponding marker(s) on map
- **Click:** Same as marker click (centers, opens info card)
- Updates dynamically as user pans/zooms

### Info Card (popup on map)

- Anchored to marker
- Shows: thumbnail, title, amendments, location name
- Right arrow button → navigates to `/videos/{id}`

### Location Search

- Mapbox Places Autocomplete (addresses, ZIP codes, city names)
- On selection: centers map, zooms to appropriate level, shows toast "X videos near [location name]"

### Filters

| Filter | Type |
|--------|------|
| Amendments | Multi-select chips: 1st, 2nd, 4th, 5th |
| Participants | Multi-select chips: Police, Government, Business, Citizen |
| Date range | From/To date pickers |

Filters apply immediately, updating side panel and markers.

---

## Video Detail Page

**Route:** `/videos/{id}`

### Access Control

| Video Status | Who Can View |
|--------------|--------------|
| Approved | Anyone |
| Pending | Admin, Moderator, or Submitter |
| Rejected | Admin, Moderator, or Submitter |
| Deleted | Admin only |

Unauthorized access returns 404 (not 403) to avoid revealing video existence.

### Layout

- Embedded YouTube player (responsive, 16:9 aspect ratio)
- Title (prominent, below player)
- Description (collapsed by default, "Show more" to expand)
- Metadata grid below

### Metadata Displayed

| Field | Notes |
|-------|-------|
| Location name | Clickable → navigates to map centered on location |
| Mini-map | Interactive Mapbox map showing pin, pan/zoom enabled |
| Amendments | 1st, 2nd, 4th, 5th as chips/badges |
| Participants | Police, Government, Business, Citizen as chips |
| Duration | From stored YouTube metadata |
| Published date | YouTube publish date (stored in DB) |
| Video date | User-provided incident date |
| Channel name | From stored YouTube metadata |
| Submitter | Name + avatar (only shown if user is logged in) |
| Status | Pending/Approved/Rejected (only shown to Admin, Moderator, or Submitter) |

### Moderation Controls (inline)

- Shown only to Admins and Moderators when video is Pending
- "Approve" button → marks approved, publishes VideoApproved event
- "Reject" button → opens modal for rejection reason, publishes VideoRejected event

---

## Video Submission

**Route:** `/videos/new`

**Access:** Any logged-in user

### Workflow

1. **Paste YouTube URL** → System extracts video ID, calls YouTube Data API once
2. **Auto-populated fields** (editable):
   - Title
   - Description
   - Thumbnail URL
   - Duration
   - Channel name
   - Channel ID
   - Published date
3. **User-provided fields:**
   - Video date (incident date, date picker)
   - Amendments (multi-select: 1st, 2nd, 4th, 5th)
   - Participants (multi-select: Police, Government, Business, Citizen)
   - Location (interactive map picker or address search)
4. **Submit** → Creates video record, publishes VideoSubmitted event

### Location Selection

- Mapbox map with "click to place marker" or search box
- Reverse geocoding fills in address/city/state
- User can adjust marker position after placement

### Auto-Approval Logic

| Submitter Trust Tier | Result |
|----------------------|--------|
| Admin | Direct to Approved |
| Moderator | Direct to Approved |
| Trusted | Direct to Approved |
| New | Status = Pending, added to moderation queue |

### Validation

- YouTube URL must be valid and video must exist
- At least one amendment required
- At least one location required

---

## Moderation Dashboard

**Route:** `/moderation`

**Access:** Admin and Moderator only

### Default View

- Filter: Pending only
- Sort: Oldest first (FIFO queue)

### Visibility by Role

| Status | Admin | Moderator |
|--------|-------|-----------|
| Pending | Yes | Yes |
| Approved | Yes | Yes |
| Rejected | Yes | No |

### Queue Item Display

| Field | Notes |
|-------|-------|
| Thumbnail | Video thumbnail |
| Title | Video title |
| Submitter | Name + avatar |
| Submitted at | Timestamp |
| Location | Location name |
| Amendments | Chips showing selected amendments |

### Actions

- **Click item** → Navigate to video detail page (inline approve/reject available)
- **Quick approve** → Approve directly from queue
- **Quick reject** → Opens rejection reason modal, then rejects

### Rejection Flow

1. Moderator clicks "Reject"
2. Modal opens with reason dropdown: Duplicate, Off-topic, Incorrect location, Low quality, Other
3. Optional free-text comment field
4. Confirm → Video status set to Rejected, VideoRejected event published

---

## Data Models

### video-service

```sql
videos
├── id: UUID (PK)
├── youtube_id: String (unique)
├── title: String
├── description: Text
├── thumbnail_url: String
├── duration_seconds: Integer
├── channel_id: String
├── channel_name: String
├── published_at: Timestamp (YouTube publish date)
├── video_date: Date (incident date)
├── amendments: Integer[] or join table (1, 2, 4, 5)
├── participants: String[] or join table
├── status: Enum (PENDING, APPROVED, REJECTED, DELETED)
├── submitted_by: UUID (FK to user)
├── created_at: Timestamp
└── updated_at: Timestamp

video_locations
├── id: UUID (PK)
├── video_id: UUID (FK)
├── location_id: UUID (FK to location-service)
├── is_primary: Boolean
└── added_at: Timestamp
```

### location-service

```sql
locations
├── id: UUID (PK)
├── coordinates: Point (PostGIS)
├── display_name: String
├── address: String
├── city: String
├── state: String
├── country: String
├── created_at: Timestamp
└── updated_at: Timestamp

location_stats
├── location_id: UUID (PK, FK)
└── video_count: Integer
```

### moderation-service

```sql
moderation_items
├── id: UUID (PK)
├── content_type: Enum (VIDEO)
├── content_id: UUID
├── submitter_id: UUID
├── status: Enum (PENDING, APPROVED, REJECTED)
├── reviewer_id: UUID (nullable)
├── reviewed_at: Timestamp (nullable)
├── rejection_reason: Enum (nullable)
├── rejection_comment: Text (nullable)
├── created_at: Timestamp
└── updated_at: Timestamp
```

### search-service

Denormalized view in PostgreSQL FTS (Phase 1), combining video + location data. Contains only APPROVED videos.

---

## API Endpoints

### video-service

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /videos/{id} | Public* | Get video details (*access control by status) |
| POST | /videos | User | Submit new video |
| PUT | /videos/{id} | Owner/Admin | Update video |
| DELETE | /videos/{id} | Owner/Admin | Soft delete video |
| GET | /videos/{id}/locations | Public | Get video's locations |
| POST | /videos/{id}/locations | Owner/Admin | Add location to video |
| POST | /videos/youtube-metadata | User | Fetch metadata from YouTube URL |

### location-service

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /locations/{id} | Public | Get location details |
| POST | /locations | User | Create new location |
| GET | /locations/geocode | User | Address → coordinates |
| GET | /locations/reverse | User | Coordinates → address |
| GET | /locations/cluster | Public | Get clustered markers for bounding box |

### search-service

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /search/videos | Public | Search videos with filters |
| GET | /search/videos/count | Public | Count videos near location |

### moderation-service

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /moderation/queue | Mod/Admin | Get pending items |
| GET | /moderation/queue/{id} | Mod/Admin | Get queue item details |
| POST | /moderation/queue/{id}/approve | Mod/Admin | Approve content |
| POST | /moderation/queue/{id}/reject | Mod/Admin | Reject with reason |

All endpoints prefixed with `/api/v1` at the gateway.

---

## Events & Messaging

### Infrastructure

- LocalStack SQS (local development)
- AWS SQS (production)

### Queues

| Queue | Publisher | Consumers |
|-------|-----------|-----------|
| video-events | video-service | moderation-service, search-service |
| moderation-events | moderation-service | video-service, search-service |

### Event Definitions

**VideoSubmitted** (video-service)
```json
{
  "eventType": "VideoSubmitted",
  "videoId": "uuid",
  "submitterId": "uuid",
  "submitterTrustTier": "NEW|TRUSTED|MODERATOR|ADMIN",
  "title": "string",
  "amendments": [1, 4],
  "locationIds": ["uuid"],
  "timestamp": "ISO8601"
}
```

**VideoApproved** (moderation-service)
```json
{
  "eventType": "VideoApproved",
  "videoId": "uuid",
  "reviewerId": "uuid",
  "timestamp": "ISO8601"
}
```

**VideoRejected** (moderation-service)
```json
{
  "eventType": "VideoRejected",
  "videoId": "uuid",
  "reviewerId": "uuid",
  "reason": "DUPLICATE|OFF_TOPIC|INCORRECT_LOCATION|LOW_QUALITY|OTHER",
  "comment": "string (optional)",
  "timestamp": "ISO8601"
}
```

### Event Flows

**New User Submission:**
1. video-service creates video (status=PENDING), publishes VideoSubmitted
2. moderation-service consumes event, creates queue item
3. Moderator approves via dashboard
4. moderation-service publishes VideoApproved
5. video-service updates status to APPROVED
6. search-service indexes the video

**Trusted+ Submission:**
1. video-service creates video (status=APPROVED), publishes VideoSubmitted
2. search-service indexes immediately
3. moderation-service ignores (submitterTrustTier != NEW)

**Video Rejection:**
1. moderation-service publishes VideoRejected
2. video-service updates status to REJECTED
3. search-service removes from index (if present)

---

## Testing Strategy

### Unit Tests (per service)

- JUnit 5 + Mockito
- 80% coverage target
- Focus on business logic, event handlers, access control

### Integration Tests (per service)

- TestContainers for PostgreSQL, Redis, LocalStack
- Test repository queries, SQS message handling
- Tagged with `@IntegrationTest`

### Web-App Tests

- Jest + React Testing Library for component tests
- Focus on form validation, state management, filter logic

### E2E Tests (AcctAtlas-integration-tests repo)

| Test Suite | Coverage |
|------------|----------|
| Map browsing | Load map, verify markers appear, click marker → info card shows |
| Side panel | Pan map → panel updates, hover panel item → marker highlights |
| Location search | Search "Phoenix, AZ" → map centers, toast shows count |
| Filters | Select amendments → markers filter, panel updates |
| Video detail | Navigate to video page, verify metadata displayed |
| Access control | Pending video returns 404 for anonymous user |
| Submission | Submit video via form, verify appears in queue or map |
| Moderation | Approve video → appears in search, reject → removed |

### Playwright + Mapbox

- Custom DOM markers with `data-video-id` attributes
- Test marker clicks, panel interactions, info card content
- Mock Mapbox geocoding API responses for deterministic tests

---

## Documentation Updates

### Files to Update

| File | Changes |
|------|---------|
| `docs/01-SystemOverview.md` | Change "Google Maps integration" to "Mapbox integration" |
| `docs/04-ServiceCatalog.md` | Update location-service dependencies, change status to "In Progress" for new services |
| `docs/09-CostEstimate.md` | Update cost estimates for Mapbox pricing |

### New Documentation

- Each new service gets `docs/technical.md` per project standards

---

## Implementation Order

### Phase 1: Backend Foundation

1. **location-service** — No dependencies, needed by others
2. **video-service** — Depends on location-service for location validation
3. **moderation-service** — Depends on video-service events
4. **search-service** — Depends on video-service and moderation-service events

### Phase 2: Infrastructure

5. **LocalStack SQS** — Add to docker-compose, queue initialization scripts
6. **api-gateway routes** — Add routing for new services

### Phase 3: Web-App

7. **Map page** — Mapbox integration, markers, clustering, side panel
8. **Video detail page** — Embedded player, metadata, mini-map, access control
9. **Video submission form** — YouTube fetch, location picker, amendments/participants
10. **Moderation dashboard** — Queue list, approve/reject actions

### Phase 4: Integration & Polish

11. **E2E tests** — Full flow coverage in integration-tests repo
12. **Documentation updates** — Mapbox migration, service catalog status
13. **Seed demo data** — Manually add 10-20 real videos via submission form

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Mapbox over Google Maps | Lower cost at scale, better customization, equivalent testability with DOM markers |
| video-service owns video-location relationship | Simpler writes; search-service has denormalized read view for read-heavy workload |
| LocalStack SQS | Matches production (AWS SQS) with zero code changes |
| Server-side clustering | Scales better than client-side for large datasets |
| Search-service for all filtered queries | Unified query interface, denormalized for performance |
| YouTube metadata fetched once at submission | Avoids rate limits, ensures consistency, reduces latency on reads |
