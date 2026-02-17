# User Profile Pages Design

## Summary

Add full profile management: self-view/edit page (`/profile`), public profile page (`/users/{id}`), social media links, per-section privacy controls, avatar picker (Gravatar + YouTube), and "My Submissions" list with moderation statuses.

## Related Issues

| Issue | Repo | Title |
|-------|------|-------|
| #18 | AccountabilityAtlas | Add "My Submissions" page for users to view their videos |
| #68 | AccountabilityAtlas | Allow users to add social media to their profiles |
| #24 | AcctAtlas-user-service | Implement profile update endpoint (PUT /users/me) |
| #30 | AcctAtlas-web-app | Add edit and delete controls for video owners on detail page |

## Architecture Decision

**Approach: Extend user-service** with social links and privacy settings tables. Frontend makes two calls for profile page (user-service for profile data, video-service for submissions). No gateway aggregation, no new services.

## Data Model

### New table: `users.user_social_links`

| Column | Type | Notes |
|--------|------|-------|
| user_id | UUID | FK → users.users, PK |
| youtube | VARCHAR(100) | Channel URL or username |
| facebook | VARCHAR(100) | Profile URL or username |
| instagram | VARCHAR(50) | Username (no @) |
| tiktok | VARCHAR(50) | Username (no @) |
| x_twitter | VARCHAR(50) | Username (no @) |
| bluesky | VARCHAR(100) | Handle (e.g., user.bsky.social) |
| sys_period | tstzrange | Temporal tracking |

One row per user (1:1). Temporal with history table. Created lazily on first update.

### New table: `users.user_privacy_settings`

| Column | Type | Notes |
|--------|------|-------|
| user_id | UUID | FK → users.users, PK |
| social_links_visibility | VARCHAR(20) | `PUBLIC` or `REGISTERED` (default: `REGISTERED`) |
| submissions_visibility | VARCHAR(20) | `PUBLIC` or `REGISTERED` (default: `PUBLIC`) |
| sys_period | tstzrange | Temporal tracking |

Privacy is per-section (social links as a group, submissions as a group). Display name and avatar are always public.

### video-service schema change

Add `rejection_reason VARCHAR(500)` to `videos.videos` table. Populated from `VideoRejectedEvent.reason` when moderation rejects a video. Returned in API responses for video owners.

### Avatar resolution

No new columns. Existing `avatar_url` on `users.users` stores the resolved URL. Backend resolves from:
- **Gravatar**: Computed from email hash (no API call needed)
- **YouTube**: Channel thumbnail via YouTube Data API (user-service gets its own API key)

Frontend presents available sources; user picks one; backend validates and stores the URL.

## API Changes

### user-service

#### `PUT /users/me` — Update own profile (extend existing stub)

Request body (all fields optional, PATCH semantics):
```json
{
  "displayName": "New Name",
  "avatarUrl": "https://gravatar.com/...",
  "socialLinks": {
    "youtube": "UCxyz...",
    "instagram": "myhandle",
    "bluesky": "me.bsky.social"
  },
  "privacySettings": {
    "socialLinksVisibility": "REGISTERED",
    "submissionsVisibility": "PUBLIC"
  }
}
```

#### `GET /users/me` — Extend existing

Add to response: `socialLinks`, `privacySettings`, `avatarSources`.

`avatarSources` returns available avatar options:
```json
{
  "avatarSources": {
    "gravatar": "https://gravatar.com/avatar/abc123?d=404",
    "youtube": "https://yt3.ggpht.com/..."
  }
}
```

Only populated sources included (YouTube only if user has a YouTube social link).

#### `GET /users/{id}` — Public profile (implement existing stub)

Returns profile data filtered by viewer auth status:
- **Always visible**: displayName, avatarUrl, memberSince, approvedVideoCount
- **If viewer is registered AND visibility = REGISTERED or PUBLIC**: socialLinks
- **If visibility = PUBLIC**: socialLinks visible to everyone
- Same logic for submissions visibility

Returns 404 if user doesn't exist. Never exposes email, trustTier, or privacy settings to other users.

### video-service

No new endpoints. Existing `GET /videos?submittedBy=me` returns all statuses for the owner. Add `rejectionReason` to response when status is REJECTED.

## Frontend Pages

### `/profile` — Self profile (authenticated)

**Profile header**: Avatar with "Change Avatar" button, display name (editable), member since, trust tier badge (read-only).

**Sections:**
1. **Profile Info** — Display name edit, avatar source picker
2. **Social Links** — Form with fields for each platform (YouTube, Facebook, Instagram, TikTok, X, Bluesky)
3. **Privacy Settings** — Two toggles: social links visibility, submissions visibility
4. **My Submissions** — Video list with thumbnail, title, date, status badge (Pending/Approved/Rejected), rejection reason inline when rejected. Click navigates to video detail.

### `/users/[id]` — Public profile (new page)

Minimal card: avatar, display name, member since, social links (if privacy allows, shown as icon links), approved video count (if privacy allows). No edit controls, no pending/rejected videos.

### Navigation

- Existing profile link in nav bar goes to `/profile`
- Video detail page: submitter's display name links to `/users/{id}`

## Privacy Model

Two visibility levels per section: **PUBLIC** (everyone) and **REGISTERED** (logged-in users only).

- Display name and avatar: always public
- Social links: default REGISTERED
- Submissions: default PUBLIC

## Cross-Service Data Flow

### Profile page (`/profile`)
1. `GET /users/me` → profile, social links, privacy, avatar sources
2. `GET /videos?submittedBy=me` → all user's videos with statuses

### Public profile (`/users/{id}`)
1. `GET /users/{id}` → filtered profile
2. If submissions visible: `GET /videos?submittedBy={id}` → approved videos only

### Rejection reason flow
`VideoRejectedEvent` arrives via SQS → `ModerationEventHandler` stores reason in `rejection_reason` column → returned in video list API for owners.

### YouTube API key
user-service gets its own `YOUTUBE_API_KEY` env var for avatar thumbnail resolution. No inter-service calls.

## Testing Strategy (Outside-In TDD)

Tests written outside-in: **E2E → API integration → service → unit**
Implementation inside-out: **unit → service → API → E2E**

Outer tests committed to feature branches early; PRs created only after all tests pass.

### E2E tests (integration-tests repo)
- Profile edit flow: change display name, verify persistence
- Social links: add YouTube link, verify on public profile for registered viewer
- Privacy: set social links to "registered only", verify anonymous viewer doesn't see them
- My Submissions: verify own videos with correct statuses
- Public profile: navigate to another user's profile, verify minimal card

### API integration tests (integration-tests repo)
- `PUT /users/me` contract: update fields, verify response
- `GET /users/{id}` contract: filtered fields based on auth
- `GET /videos?submittedBy=me` includes rejection reason

### Service-layer tests (user-service, video-service)
- UserService: updateProfile, getPublicProfile, privacy filtering
- Avatar resolution: Gravatar hash computation, YouTube API mock
- VideoService: rejection reason storage from event

### Unit tests (user-service, video-service)
- Mappers, validators, social link format validation
- Privacy settings defaults

### Component tests (web-app)
- Profile edit form, social links form, privacy toggles
- Avatar picker, submissions list with status badges

## Repos Affected

| Repo | Changes |
|------|---------|
| AcctAtlas-user-service | Social links table, privacy settings table, `PUT /users/me` impl, `GET /users/{id}` impl, avatar resolution, YouTube API integration |
| AcctAtlas-video-service | `rejection_reason` column, store from event, return in API |
| AcctAtlas-web-app | Profile edit page, public profile page, avatar picker, social links form, submissions list, API client functions |
| AcctAtlas-integration-tests | E2E + API integration tests for profile flows |
| AccountabilityAtlas | docker-compose env vars (YouTube API key for user-service), design doc |
