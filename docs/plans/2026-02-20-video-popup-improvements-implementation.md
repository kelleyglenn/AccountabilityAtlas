# VideoInfoCard Popup Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the map marker popup (VideoInfoCard) with a custom close button, close-on-map-click, 16:9 clickable thumbnail, and participant type chips.

**Architecture:** Four independent UI improvements to VideoInfoCard, plus one data-flow change (wiring `participants[]` array through the search transform). All changes are in AcctAtlas-web-app except E2E tests in AcctAtlas-integration-tests.

**Tech Stack:** TypeScript, Next.js, Tailwind CSS, react-map-gl, Jest, Playwright

**Issues:** AcctAtlas-web-app#11, #56, #57, #58
**Design:** [2026-02-20-video-popup-improvements-design.md](2026-02-20-video-popup-improvements-design.md)
**Repo:** `AcctAtlas-web-app` (inside `AccountabilityAtlas/AcctAtlas-web-app`)

---

### Task 1: Write failing test for participants array mapping

**Files:**
- Modify: `src/__tests__/lib/api/search.test.ts:83` (add test after existing `participantCount` test)

**Step 1: Add test for participants array mapping**

Add a new test inside the existing `describe("transformSearchResponse", ...)` block, after the `maps participants.length to participantCount` test at line 83:

```typescript
    it("maps participants array from API response", async () => {
      const apiResponse = makeApiResponse([
        makeResult({ participants: ["POLICE", "GOVERNMENT"] }),
      ]);

      (apiClient.get as jest.Mock).mockResolvedValue({ data: apiResponse });

      const result = await searchVideos({ page: 0, pageSize: 20 });

      expect(result.videos[0].participants).toEqual(["POLICE", "GOVERNMENT"]);
      // participantCount should still be set for VideoListItem
      expect(result.videos[0].participantCount).toBe(2);
    });
```

**Step 2: Run test to verify it fails**

Run: `cd AcctAtlas-web-app && npx jest src/__tests__/lib/api/search.test.ts --verbose`

Expected: New test FAILS — `participants` is `undefined` because `transformSearchResponse` doesn't map it yet. The `participantCount` assertion should pass (already mapped).

---

### Task 2: Wire participants array through data layer

**Files:**
- Modify: `src/types/map.ts:20-31` (add `participants` to `VideoLocation` interface)
- Modify: `src/types/map.ts:155` (add `formatParticipant()` after `PARTICIPANT_TYPE_OPTIONS`)
- Modify: `src/lib/api/search.ts:74-76` (add `participants` to transform mapping)

**Step 1: Add `participants` field to `VideoLocation` interface**

In `src/types/map.ts`, add `participants?: string[];` after `participantCount` (line 30):

```typescript
export interface VideoLocation {
  id: string;
  videoId: string;
  latitude: number;
  longitude: number;
  title: string;
  thumbnailUrl?: string;
  duration?: number;
  recordedAt?: string;
  amendments: string[];
  participantCount?: number;
  participants?: string[];
}
```

**Step 2: Add `formatParticipant()` helper**

In `src/types/map.ts`, add after the closing `];` of `PARTICIPANT_TYPE_OPTIONS` (after line 155):

```typescript

/**
 * Format a participant type value for display (e.g., "POLICE" -> "Police")
 */
export function formatParticipant(participant: string): string {
  const option = PARTICIPANT_TYPE_OPTIONS.find((o) => o.id === participant);
  return option?.label || participant;
}
```

**Step 3: Map `participants` in `transformSearchResponse()`**

In `src/lib/api/search.ts`, add `participants: result.participants,` after the `participantCount` line (line 75):

```typescript
      return {
        id: primaryLocation.id,
        videoId: result.id,
        latitude: primaryLocation.coordinates.latitude,
        longitude: primaryLocation.coordinates.longitude,
        title: result.title,
        thumbnailUrl: result.thumbnailUrl,
        duration: result.durationSeconds,
        recordedAt: result.videoDate,
        amendments: result.amendments,
        participantCount: result.participants.length,
        participants: result.participants,
      };
```

**Step 4: Run tests to verify they pass**

Run: `cd AcctAtlas-web-app && npx jest src/__tests__/lib/api/search.test.ts --verbose`

Expected: All tests PASS including the new `participants` array test.

**Step 5: Run full test suite**

Run: `cd AcctAtlas-web-app && npx jest --verbose`

Expected: All tests PASS.

**Step 6: Run prettier**

Run: `cd AcctAtlas-web-app && npx prettier --write src/types/map.ts src/lib/api/search.ts src/__tests__/lib/api/search.test.ts`

**Step 7: Commit**

```bash
cd AcctAtlas-web-app
git add src/types/map.ts src/lib/api/search.ts src/__tests__/lib/api/search.test.ts
git commit -m "feat(search): wire participants array through transform (#57)"
```

---

### Task 3: UI improvements to VideoInfoCard

**Files:**
- Modify: `src/app/globals.css:15` (add CSS to hide default Mapbox close button)
- Modify: `src/components/map/VideoInfoCard.tsx` (all 4 UI changes)

**Step 1: Hide default Mapbox close button via CSS**

In `src/app/globals.css`, add after the closing `}` of the `body` block (after line 15):

```css

/* Hide default Mapbox popup close button in video info popups */
.video-info-popup .mapboxgl-popup-close-button {
  display: none;
}
```

**Step 2: Update VideoInfoCard with all 4 improvements**

Replace the entire content of `src/components/map/VideoInfoCard.tsx`. Key changes from the current file:

1. **Import `formatParticipant`** from `@/types/map`
2. **`closeOnClick={true}`** (was `false`) — popup closes on map click (issue #58)
3. **Thumbnail wrapped in `<a href={/videos/${video.videoId}}>`** — clickable thumbnail (issue #56)
4. **Custom close button** — 28x28px (`w-7 h-7`) circular button (`rounded-full bg-white/80 hover:bg-white`), positioned `absolute top-1 right-1 z-10`, with X SVG icon. On the thumbnail `<a>`, the button uses `e.preventDefault(); e.stopPropagation()` to prevent navigation (issue #11)
5. **`aspect-video`** replaces `h-32 object-cover` — 16:9 ratio, no cropping (issue #56)
6. **Fallback close button** when no thumbnail — same styling, positioned at top-right of card
7. **Participant chips** replace count text — uses `formatParticipant()` for labels, styled `bg-gray-100 text-gray-700` (issue #57)

Full replacement:

```tsx
"use client";

import { Popup } from "react-map-gl/mapbox";
import { useMap } from "@/providers/MapProvider";
import {
  formatAmendment,
  formatParticipant,
  type VideoLocation,
} from "@/types/map";

interface VideoInfoCardProps {
  video: VideoLocation;
  onClose?: () => void;
}

export function VideoInfoCard({ video, onClose }: VideoInfoCardProps) {
  const { setSelectedVideoId } = useMap();

  // Safety check for valid coordinates
  if (
    typeof video.longitude !== "number" ||
    typeof video.latitude !== "number" ||
    isNaN(video.longitude) ||
    isNaN(video.latitude)
  ) {
    return null;
  }

  const handleClose = () => {
    setSelectedVideoId(null);
    onClose?.();
  };

  // Format duration as mm:ss
  const formatDuration = (seconds?: number) => {
    if (!seconds) return null;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Format date
  const formatDate = (dateString?: string) => {
    if (!dateString) return null;
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  const closeButton = (
    <button
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        handleClose();
      }}
      className="absolute top-1 right-1 z-10 w-7 h-7 rounded-full bg-white/80 hover:bg-white flex items-center justify-center transition-colors"
      aria-label="Close popup"
    >
      <svg
        className="w-4 h-4 text-gray-700"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M6 18L18 6M6 6l12 12"
        />
      </svg>
    </button>
  );

  return (
    <Popup
      longitude={video.longitude}
      latitude={video.latitude}
      anchor="bottom"
      onClose={handleClose}
      closeOnClick={true}
      className="video-info-popup"
      maxWidth="300px"
    >
      <div className="p-1">
        {/* Thumbnail with custom close button overlay */}
        {video.thumbnailUrl ? (
          <a
            href={`/videos/${video.videoId}`}
            className="relative mb-2 rounded overflow-hidden block"
          >
            {closeButton}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={video.thumbnailUrl}
              alt={video.title}
              className="w-full aspect-video"
            />
            {video.duration && (
              <span className="absolute bottom-1 right-1 bg-black/75 text-white text-xs px-1 rounded">
                {formatDuration(video.duration)}
              </span>
            )}
          </a>
        ) : (
          <div className="relative">
            {closeButton}
          </div>
        )}

        {/* Title */}
        <h3 className="font-semibold text-gray-900 text-sm line-clamp-2 mb-1">
          {video.title}
        </h3>

        {/* Amendments */}
        <div className="flex flex-wrap gap-1 mb-2">
          {video.amendments.map((amendment) => (
            <span
              key={amendment}
              className="inline-block bg-blue-100 text-blue-800 text-xs px-1.5 py-0.5 rounded"
            >
              {formatAmendment(amendment)}
            </span>
          ))}
        </div>

        {/* Date and participant chips */}
        <div className="text-xs text-gray-500 space-y-1">
          {video.recordedAt && <p>Recorded: {formatDate(video.recordedAt)}</p>}
          {video.participants && video.participants.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {video.participants.map((participant) => (
                <span
                  key={participant}
                  className="inline-block bg-gray-100 text-gray-700 text-xs px-1.5 py-0.5 rounded"
                >
                  {formatParticipant(participant)}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* View button */}
        <a
          href={`/videos/${video.videoId}`}
          className="mt-2 block w-full text-center bg-blue-600 text-white text-sm py-1.5 rounded hover:bg-blue-700 transition-colors"
        >
          View Video
        </a>
      </div>
    </Popup>
  );
}
```

**Step 3: Run full test suite**

Run: `cd AcctAtlas-web-app && npx jest --verbose`

Expected: All tests PASS. No component tests exist for VideoInfoCard, so only verifying no regressions.

**Step 4: Run prettier**

Run: `cd AcctAtlas-web-app && npx prettier --write src/app/globals.css src/components/map/VideoInfoCard.tsx`

**Step 5: Commit**

```bash
cd AcctAtlas-web-app
git add src/app/globals.css src/components/map/VideoInfoCard.tsx
git commit -m "feat(map): improve popup with custom close button, clickable 16:9 thumbnail, participant chips (#11, #56, #57, #58)"
```

---

### Task 4: Deploy and verify end-to-end

**Step 1: Deploy web-app**

Run: `cd /c/code/AccountabilityAtlas && ./scripts/deploy.sh web-app`

Expected: Quality checks pass, Docker image builds, container starts, health check passes.

**Step 2: Run integration tests**

Run: `cd /c/code/AccountabilityAtlas/AcctAtlas-integration-tests && npm run test:all`

Expected: All tests pass. Existing E2E tests for popup should still work — "View Video" link is unchanged.

---

### Task 5: Add E2E tests for popup improvements

**Files:**
- Modify: `AcctAtlas-integration-tests/e2e/tests/map/map-browse.spec.ts:310` (add tests after "video info popup displays thumbnail" test)

**Step 1: Add E2E tests for new popup behavior**

Add three tests after the "video info popup displays thumbnail" test (after line 310). These test the three user-visible improvements (closeOnClick is tested implicitly by the close button test — clicking the close button verifies the custom button exists and works).

```typescript
  test("popup thumbnail links to video detail page", async ({
    page,
    browserName,
  }) => {
    // Arrange: go to map and click video in list to show popup
    await page.goto("/map");
    if (browserName !== "chromium") {
      await page.waitForTimeout(1000);
    }

    const videoList = page.locator('[data-testid="video-list-item"]');
    await expect(videoList.first()).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });
    await videoList.first().click();

    // Wait for popup to appear
    await expect(page.getByRole("link", { name: /View Video/i })).toBeVisible({
      timeout: UI_INTERACTION_TIMEOUT,
    });

    // Act: click the popup thumbnail image
    const popup = page.locator(".video-info-popup");
    const popupThumbnail = popup.locator("img");
    await expect(popupThumbnail).toBeVisible();
    await popupThumbnail.click();

    // Assert: navigated to video detail page
    await expect(page).toHaveURL(/\/videos\/[a-f0-9-]+/, {
      timeout: PAGE_LOAD_TIMEOUT,
    });
  });

  test("popup shows participant type chips", async ({
    page,
    browserName,
  }) => {
    // Arrange: go to map and click video in list to show popup
    await page.goto("/map");
    if (browserName !== "chromium") {
      await page.waitForTimeout(1000);
    }

    const videoList = page.locator('[data-testid="video-list-item"]');
    await expect(videoList.first()).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });
    await videoList.first().click();

    // Wait for popup to appear
    await expect(page.getByRole("link", { name: /View Video/i })).toBeVisible({
      timeout: UI_INTERACTION_TIMEOUT,
    });

    // Assert: popup shows participant type chips (not just a count)
    const popup = page.locator(".video-info-popup");
    // Seed data videos have participant types like Police, Government, etc.
    await expect(
      popup.getByText(/Police|Government|Business|Citizen|Security/),
    ).toBeVisible({ timeout: UI_INTERACTION_TIMEOUT });
  });

  test("popup has custom close button", async ({ page, browserName }) => {
    // Arrange: go to map and click video in list to show popup
    await page.goto("/map");
    if (browserName !== "chromium") {
      await page.waitForTimeout(1000);
    }

    const videoList = page.locator('[data-testid="video-list-item"]');
    await expect(videoList.first()).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });
    await videoList.first().click();

    // Wait for popup to appear
    await expect(page.getByRole("link", { name: /View Video/i })).toBeVisible({
      timeout: UI_INTERACTION_TIMEOUT,
    });

    // Act: click the custom close button
    const closeButton = page.getByRole("button", { name: /Close popup/i });
    await expect(closeButton).toBeVisible();
    await closeButton.click();

    // Assert: popup is closed
    await expect(
      page.getByRole("link", { name: /View Video/i }),
    ).not.toBeVisible({ timeout: UI_INTERACTION_TIMEOUT });
  });
```

**Step 2: Run E2E tests to verify they pass**

Run: `cd /c/code/AccountabilityAtlas/AcctAtlas-integration-tests && npm run test:e2e`

Expected: All tests PASS.

**Step 3: Run full test suite**

Run: `cd /c/code/AccountabilityAtlas/AcctAtlas-integration-tests && npm run test:all`

Expected: All tests PASS.

**Step 4: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-integration-tests
git add e2e/tests/map/map-browse.spec.ts
git commit -m "test(map): add E2E tests for popup close button, clickable thumbnail, participant chips"
```

---

### Task 6: Create PRs

**Step 1: Push web-app branch and create PR**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app
git push -u origin <branch-name>
gh pr create --title "feat: improve VideoInfoCard popup UI" --body "$(cat <<'EOF'
## Summary
- Custom circular close button overlaying thumbnail, hides default Mapbox button via CSS
- Popup closes when clicking on the map (`closeOnClick={true}`)
- 16:9 thumbnail aspect ratio (no cropping) + clickable thumbnail linking to video detail page
- Participant type chips in popup (Police, Government, etc.) instead of generic count

Closes #11
Closes #56
Closes #57
Closes #58

## Changes
- `src/app/globals.css`: Hide default Mapbox popup close button for `.video-info-popup`
- `src/components/map/VideoInfoCard.tsx`: All 4 UI improvements
- `src/types/map.ts`: Add `participants?: string[]` to `VideoLocation`, add `formatParticipant()` helper
- `src/lib/api/search.ts`: Map `participants` array in `transformSearchResponse()`
- `src/__tests__/lib/api/search.test.ts`: Test for participants array mapping

## Test plan
- [x] Unit tests pass (`npx jest`)
- [x] Deploy via `deploy.sh web-app`
- [x] Integration tests pass (`npm run test:all`)
- [x] Visual verification: custom close button, 16:9 thumbnail, clickable thumbnail, participant chips

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Step 2: Check CI status on web-app PR**

Run: `cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && gh pr checks`

Expected: All CI checks pass.

**Step 3: After web-app PR is merged, create integration-tests PR**

Per project rules, integration-tests PRs must wait until service PRs are merged. After the web-app PR is merged:

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-integration-tests
git push -u origin <branch-name>
gh pr create --title "test: add E2E tests for popup improvements" --body "$(cat <<'EOF'
## Summary
- E2E test: clicking popup thumbnail navigates to video detail page
- E2E test: popup shows participant type chips (Police, Government, etc.)
- E2E test: custom close button closes popup

Depends on AcctAtlas-web-app popup improvements PR.

## Test plan
- [x] E2E tests pass locally (`npm run test:e2e`)
- [x] Full suite passes (`npm run test:all`)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: CI checks pass.
