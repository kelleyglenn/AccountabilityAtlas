# Video Submission Form + Video Detail Page Design

## Overview

Two features to make AccountabilityAtlas demo-ready:
1. **Video submission form** (`/videos/new`) — allows logged-in users to submit constitutional audit videos
2. **Video detail page enhancements** (`/videos/[id]`) — full metadata display, mini-map, moderation controls

Both features also require a **persistent nav bar** and two **backend prerequisite fixes**.

## Related Issues

- web-app #22 — Video submission form
- web-app #24 — Video detail page enhancements
- top-level #33 — Dedicated video detail endpoint

---

## Prerequisites (Backend Fixes)

### Fix GET /videos/{id} LazyInitializationException

The video-service `GET /videos/{id}` endpoint returns 500 due to a Hibernate `LazyInitializationException` on `Video.locations`. The DTO conversion in the controller accesses the lazy collection after the Hibernate session closes.

**Fix:** Either eager-fetch locations in the repository query, or move DTO conversion inside the `@Transactional` service method.

### Add YouTube metadata preview endpoint

New endpoint: `GET /videos/preview?youtubeUrl=...`

Returns YouTube metadata (title, description, thumbnail, duration, channel name, channel ID, published date) without creating a video record. Used by the submission form to show a preview before the user submits.

**Response shape:** Same fields as `VideoDetail` but only the YouTube-fetched fields, plus a `youtubeId` field. Returns 422 if video is unavailable/private, 409 if already submitted.

---

## Navigation (Persistent Nav Bar)

**Component:** `NavBar` in root layout, visible on every page.

**Layout:** Horizontal bar, ~56px height. Map page content starts below it.

| Position | Element | Visibility | Action |
|----------|---------|-----------|--------|
| Left | "AccountabilityAtlas" text | Always | Links to `/` |
| Right | "Submit Video" button | Logged in | Links to `/videos/new` |
| Right | "Explore Map" button | Always | Links to `/map` |
| Right | "Sign In" link | Not logged in | Links to `/login` |
| Right | User name + Sign Out | Logged in | Sign Out calls `logout()` |

**Mobile:** Right-side items stack or wrap (full hamburger menu deferred to web-app #25).

**Map page impact:** Map fills `calc(100vh - 56px)` instead of `100vh`. Search bar and filter controls remain as map overlays.

---

## Video Submission Form (`/videos/new`)

### Access

Requires authentication. Unauthenticated users redirect to `/login?redirect=/videos/new`. Login page reads `redirect` query param and navigates there on success.

### Layout

Single-page form (no wizard). Desktop: two columns (form fields left, map picker right). Mobile: stacked (form top, map below).

### Workflow

**Step 1 — YouTube URL input:**
- User pastes URL, presses Enter or blurs the field
- Calls `GET /api/v1/videos/preview?youtubeUrl=...`
- Loading: spinner in the input area
- Success: preview card appears (thumbnail, title, channel, duration, published date)
- Error: inline message (invalid URL, private video, already submitted with link to existing)

**Step 2 — Metadata fields** (appear after successful preview):
- **Video date** (optional) — date picker for incident date
- **Amendments** (required, min 1) — multi-select chips (1st, 2nd, 4th, 5th), reusing existing chip pattern
- **Participants** (required, min 1) — multi-select chips (Police, Government, Business, Citizen)

**Step 3 — Location picker** (required):
- Interactive Mapbox map with click-to-place marker
- Mapbox SearchBox for address search (reuses `LocationSearch` component)
- After placing marker: reverse geocode via `GET /api/v1/locations/reverse` to show address/city/state below map
- User can click again to reposition marker
- Single location only (multiple locations deferred to web-app #26)

**Submit:**
- Creates location via `POST /api/v1/locations` (with geocoded data)
- Creates video via `POST /api/v1/videos` (with locationId from previous step)
- On success: redirect to `/videos/{id}`
- On error: toast notification

### Auto-Approval

Handled server-side by moderation-service. No client-side logic needed — the form always submits, and the backend determines status based on the user's trust tier (NEW = Pending, TRUSTED/MODERATOR/ADMIN = auto-Approved).

### New Components

- `VideoSubmitForm` — main form page component
- `YouTubePreview` — preview card showing fetched metadata
- `LocationPicker` — map with click-to-place + reverse geocode display

### New API Functions

- `previewVideo(youtubeUrl)` — `GET /api/v1/videos/preview?youtubeUrl=...`
- `createVideo(data)` — `POST /api/v1/videos`
- `createLocation(data)` — `POST /api/v1/locations`
- `reverseGeocode(lat, lng)` — `GET /api/v1/locations/reverse?lat=...&lng=...`

### Validation

| Field | Rule | Error Display |
|-------|------|---------------|
| YouTube URL | Valid URL, video exists, not already submitted | Inline below input |
| Amendments | At least 1 selected | Inline below chips |
| Participants | At least 1 selected | Inline below chips |
| Location | Marker placed on map | Inline below map |

### Error States

| Error | Source | Display |
|-------|--------|---------|
| Invalid YouTube URL | Client-side regex | Inline: "Please enter a valid YouTube URL" |
| Video unavailable/private | Preview endpoint 422 | Inline: "Video is unavailable or private" |
| Video already exists | POST returns 409 | Toast with link to existing video |
| No amendments selected | Client-side | Inline below amendment chips |
| No location placed | Client-side | Inline below map |
| Network error | Any API call | Toast notification |

---

## Video Detail Page (`/videos/[id]`)

### Data Source

Switch from search API workaround (`/search?pageSize=100`) to `GET /api/v1/videos/{id}` (after fixing the lazy loading bug). This provides full data: status, submitter info, locations, all metadata.

### Layout

Two-column on desktop (main content left, sidebar right). Single column stacked on mobile.

### Main Column (Left)

- **YouTube embed** — responsive iframe, 16:9 aspect ratio (already exists)
- **Title** — prominent heading below player
- **Metadata row** — channel name, duration, published date, video date — inline with subtle separators
- **Amendment + participant badges** — chips below metadata row, reusing `Chip` component
- **Description** — collapsed by default (3 lines), "Show more" toggle expands
- **Submitter info** — avatar + display name, only shown to logged-in users

### Sidebar (Right)

- **Mini-map** — small Mapbox map (~250px tall) with location pin, pan/zoom enabled, reuses `MapView`
- **Location name** — clickable, navigates to `/map?lat=...&lng=...&zoom=14`
- **Status badge** — Pending/Approved/Rejected, visible only to Admin, Moderator, or Submitter

### Moderation Controls

Shown to Admin/Moderator when video status is Pending:
- **"Approve" button** — fetches moderation item by contentId from queue, calls approve endpoint
- **"Reject" button** — opens modal for rejection reason, calls reject endpoint

**Implementation note:** The moderation API uses moderation item IDs, not video IDs. The detail page fetches `GET /api/v1/moderation/queue?contentType=VIDEO&status=PENDING` and matches on `contentId` to find the moderation item ID. This extra call is only made for moderators viewing pending content.

### Access Control

| Video Status | Who Can View |
|-------------|-------------|
| Approved | Anyone |
| Pending | Admin, Moderator, Submitter |
| Rejected | Admin, Moderator, Submitter |
| Deleted | Admin only |
| Unauthorized | Show 404 (not 403) |

### New API Functions

- `approveVideo(moderationItemId)` — `POST /api/v1/moderation/queue/{id}/approve`
- `rejectVideo(moderationItemId, reason)` — `POST /api/v1/moderation/queue/{id}/reject`
- `getModerationQueue(params)` — `GET /api/v1/moderation/queue` (to find item by contentId)

### Error States

| Error | Display |
|-------|---------|
| Video not found (404) | Full-page "Video not found" with link to map |
| Server error (500) | Full-page "Something went wrong" with retry |
| Unauthorized (pending, wrong user) | Same as 404 |

---

## Auth Guard Enhancement

The login page needs to support redirect-after-login:
- `/videos/new` redirects unauthenticated users to `/login?redirect=/videos/new`
- Login page reads `redirect` query param
- On successful login, navigates to `redirect` value instead of `/`

---

## Testing Strategy

- **Unit tests:** New components (VideoSubmitForm, YouTubePreview, LocationPicker, NavBar), new API functions
- **Video-service:** Unit test for preview endpoint, fix for lazy loading bug
- **Integration tests (AcctAtlas-integration-tests):** API test for full submit flow (login, preview, create location, create video, verify in search), E2E Playwright test for form workflow

---

## Out of Scope

| Feature | Issue |
|---------|-------|
| Mobile hamburger menu | web-app #25 |
| Multiple locations per video | web-app #26 |
| Related videos section | web-app #27 |
| Abuse report button | web-app #28 |
| OAuth login (Google, Apple) | web-app #29 |
| Edit/delete video controls | web-app #30 |
| Full moderation dashboard | web-app #23 |
| Refresh token handling | web-app #3 |
| Editing YouTube-fetched fields | Not planned |
