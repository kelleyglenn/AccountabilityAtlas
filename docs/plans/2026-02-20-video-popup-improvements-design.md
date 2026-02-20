# VideoInfoCard Popup Improvements

**Issues:**
- AcctAtlas-web-app#11 — Improve close button appearance
- AcctAtlas-web-app#56 — Fix thumbnail aspect ratio and make clickable
- AcctAtlas-web-app#57 — Show participant type chips
- AcctAtlas-web-app#58 — Close popup on map click

**Date:** 2026-02-20
**Scope:** Web-app only (AcctAtlas-web-app)

## Changes

### 1. Custom Close Button (issue #11)

Hide the default Mapbox close button via CSS in `globals.css`, scoped to `.video-info-popup`:

```css
.video-info-popup .mapboxgl-popup-close-button {
  display: none;
}
```

Render a custom 28x28px circular close button inside `VideoInfoCard.tsx`:
- Semi-transparent white background (`bg-white/80 hover:bg-white`)
- X SVG icon (Heroicons style, `stroke-current`)
- Positioned absolute top-right, overlaying the thumbnail
- `z-10` to stay above thumbnail and duration badge
- Falls back to top-right of card content when no thumbnail

### 2. Close on Map Click (issue #58)

Change `closeOnClick={false}` to `closeOnClick={true}` on the `Popup` component.

### 3. Thumbnail: 16:9 Aspect Ratio + Clickable (issue #56)

Replace `h-32 object-cover` with `aspect-video` (Tailwind 16:9 utility). The image fills the full popup width and height adjusts to maintain ratio — no cropping.

Wrap the thumbnail container in `<a href={/videos/${video.videoId}}>` so clicking the thumbnail navigates to the video detail page. Duration badge and close button overlays remain on top.

### 4. Participant Type Chips (issue #57)

**Data flow** (same wiring pattern as the thumbnail fix):
- Add `participants?: string[]` to `VideoLocation` in `types/map.ts`
- Map `participants: result.participants` in `transformSearchResponse()` (keep `participantCount` too)
- Update tests

**Display in VideoInfoCard:**
- Replace `"{count} participant(s)"` text with chips
- Chip styling: `bg-gray-100 text-gray-700` (distinct from amendment `bg-blue-100 text-blue-800`)
- Labels from `PARTICIPANT_TYPE_OPTIONS`: POLICE → Police, GOVERNMENT → Government, etc.
- Add a `formatParticipant()` helper (similar to `formatAmendment()`)

**VideoListItem unchanged** — continues showing participant count.

## Files Changed

| File | Changes |
|------|---------|
| `src/app/globals.css` | Hide default Mapbox close button for `.video-info-popup` |
| `src/components/map/VideoInfoCard.tsx` | Custom close button, `closeOnClick`, 16:9 thumbnail, clickable thumbnail, participant chips |
| `src/types/map.ts` | Add `participants?: string[]` to `VideoLocation`, add `formatParticipant()` |
| `src/lib/api/search.ts` | Map `participants` array in transform |
| `src/__tests__/lib/api/search.test.ts` | Test `participants` mapping |

## What Doesn't Change

- `VideoListItem.tsx` — Keeps participant count display
- Backend services — Already return participant arrays
- `next.config.js` — No changes needed
