# Video Thumbnails on Map Page

**Issue**: AccountabilityAtlas#31
**Date**: 2026-02-19
**Scope**: Web-app only (AcctAtlas-web-app)

## Problem

The map page video list and info cards show placeholder icons instead of YouTube thumbnails. The backend pipeline works correctly — thumbnailUrl flows from YouTube through video-service to search-service and is returned in search API responses. The web-app's `transformSearchResponse()` function drops it during API response mapping.

The same mapping gap applies to `durationSeconds` and `videoDate`, which the UI components already support but never receive.

## Investigation Summary

| Layer | thumbnailUrl | Status |
|-------|-------------|--------|
| video-service DB | `thumbnail_url VARCHAR(500)` | Stored |
| video-service API | `VideoSummary.thumbnailUrl` | Returned |
| search-service index | `search_videos.thumbnail_url` | Indexed |
| search-service API | `VideoSearchResult.thumbnailUrl` | Returned |
| web-app `VideoLocation` type | `thumbnailUrl?: string` | Declared |
| web-app `transformSearchResponse()` | **Not mapped** | **Bug** |
| web-app components | Conditional render with fallback | Ready |
| next.config.js | `i.ytimg.com` in remotePatterns | Configured |

## Changes

### `src/lib/api/search.ts`

1. Add missing fields to `ApiSearchResult` interface:
   - `thumbnailUrl?: string`
   - `durationSeconds?: number`
   - `videoDate?: string`

2. Map them in `transformSearchResponse()`:
   - `thumbnailUrl` -> `thumbnailUrl`
   - `durationSeconds` -> `duration`
   - `videoDate` -> `recordedAt`

### `src/__tests__/lib/api/search.test.ts`

- Add the three fields to mock API responses
- Assert correct mapping to VideoLocation properties
- Test graceful handling of undefined values

## What Doesn't Change

- `types/map.ts` — `VideoLocation` already declares all fields
- `VideoListItem.tsx` — Already renders thumbnails with placeholder fallback
- `VideoInfoCard.tsx` — Already renders thumbnails with duration overlay
- `next.config.js` — `i.ytimg.com` already configured
- Backend services — Already return all needed data
