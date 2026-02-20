# Video Thumbnails Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire up thumbnailUrl, durationSeconds, and videoDate from the search API response to the frontend components so video thumbnails, durations, and dates display on the map page.

**Architecture:** The search API already returns these fields. The web-app's `transformSearchResponse()` function in `search.ts` drops them during mapping. We fix the interface and mapping, then update tests.

**Tech Stack:** TypeScript, Next.js, Jest

**Issue:** AccountabilityAtlas#31
**Design:** [2026-02-19-video-thumbnails-design.md](2026-02-19-video-thumbnails-design.md)
**Repo:** `AcctAtlas-web-app` (inside `AccountabilityAtlas/AcctAtlas-web-app`)

---

### Task 1: Write failing tests for thumbnail/duration/date mapping

**Files:**
- Modify: `src/__tests__/lib/api/search.test.ts:46-84` (the `transformSearchResponse` describe block)

**Step 1: Add test for thumbnailUrl, durationSeconds, videoDate mapping**

Add two new tests inside the existing `describe("transformSearchResponse", ...)` block (after the `participantCount` test at line 83):

```typescript
    it("maps thumbnailUrl, durationSeconds, and videoDate from API response", async () => {
      const apiResponse = makeApiResponse([
        makeResult({
          thumbnailUrl: "https://img.youtube.com/vi/abc123/mqdefault.jpg",
          durationSeconds: 185,
          videoDate: "2025-06-15",
        }),
      ]);

      (apiClient.get as jest.Mock).mockResolvedValue({ data: apiResponse });

      const result = await searchVideos({ page: 0, pageSize: 20 });

      expect(result.videos[0].thumbnailUrl).toBe(
        "https://img.youtube.com/vi/abc123/mqdefault.jpg"
      );
      expect(result.videos[0].duration).toBe(185);
      expect(result.videos[0].recordedAt).toBe("2025-06-15");
    });

    it("handles missing thumbnailUrl, durationSeconds, and videoDate gracefully", async () => {
      const apiResponse = makeApiResponse([makeResult()]);

      (apiClient.get as jest.Mock).mockResolvedValue({ data: apiResponse });

      const result = await searchVideos({ page: 0, pageSize: 20 });

      expect(result.videos[0].thumbnailUrl).toBeUndefined();
      expect(result.videos[0].duration).toBeUndefined();
      expect(result.videos[0].recordedAt).toBeUndefined();
    });
```

**Step 2: Run tests to verify they fail**

Run: `cd AcctAtlas-web-app && npx jest src/__tests__/lib/api/search.test.ts --verbose`

Expected: Both new tests FAIL — `thumbnailUrl`, `duration`, and `recordedAt` are all `undefined` even when provided in the API response (because `transformSearchResponse` doesn't map them yet).

---

### Task 2: Fix ApiSearchResult interface and transformSearchResponse mapping

**Files:**
- Modify: `src/lib/api/search.ts:22-40` (ApiSearchResult interface) and `src/lib/api/search.ts:60-71` (transform mapping)

**Step 1: Add missing fields to ApiSearchResult interface**

In `src/lib/api/search.ts`, add three fields to the `ApiSearchResult` interface (after `channelName` on line 27):

```typescript
interface ApiSearchResult {
  id: string;
  youtubeId: string;
  title: string;
  description?: string;
  channelName?: string;
  thumbnailUrl?: string;
  durationSeconds?: number;
  videoDate?: string;
  amendments: string[];
  participants: string[];
  locations: Array<{
    id: string;
    displayName: string;
    city?: string;
    state?: string;
    coordinates: {
      latitude: number;
      longitude: number;
    };
  }>;
}
```

**Step 2: Add the three fields to the transform mapping**

In `transformSearchResponse()`, add the three mapped fields to the return object (after `participantCount` on line 69):

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
      };
```

**Step 3: Run tests to verify they pass**

Run: `cd AcctAtlas-web-app && npx jest src/__tests__/lib/api/search.test.ts --verbose`

Expected: All tests PASS including the two new ones.

**Step 4: Run full test suite**

Run: `cd AcctAtlas-web-app && npx jest --verbose`

Expected: All tests PASS. No other tests should be affected since the `VideoLocation` type already declared these optional fields.

**Step 5: Run prettier**

Run: `cd AcctAtlas-web-app && npx prettier --write src/lib/api/search.ts src/__tests__/lib/api/search.test.ts`

Expected: Files formatted (may be no changes if already conformant).

**Step 6: Commit**

```bash
cd AcctAtlas-web-app
git checkout -b feature/31-video-thumbnails
git add src/lib/api/search.ts src/__tests__/lib/api/search.test.ts
git commit -m "feat(search): map thumbnailUrl, duration, videoDate from search API (#31)"
```

---

### Task 3: Deploy and verify end-to-end

**Step 1: Deploy web-app**

Run: `cd AccountabilityAtlas && ./scripts/deploy.sh web-app`

Expected: Quality checks pass, Docker image builds, container starts, health check passes.

**Step 2: Verify thumbnails in browser**

Open the map page. Video list items should show YouTube thumbnails instead of gray placeholders. Clicking a map marker should show the VideoInfoCard popup with a thumbnail.

**Step 3: Run integration tests**

Run: `cd AcctAtlas-integration-tests && npm run test:all`

Expected: All tests pass.

---

### Task 4: Create PR

**Step 1: Push branch and create PR**

```bash
cd AcctAtlas-web-app
git push -u origin feature/31-video-thumbnails
gh pr create --title "feat: map thumbnailUrl, duration, videoDate from search API" --body "$(cat <<'EOF'
## Summary
- Maps `thumbnailUrl`, `durationSeconds`, and `videoDate` from search API response to `VideoLocation` objects
- Video list items and info cards now display YouTube thumbnails instead of gray placeholders
- Duration badges and video dates also now display (were already supported in UI but never populated)

Closes AccountabilityAtlas/AccountabilityAtlas#31

## Changes
- `src/lib/api/search.ts`: Added 3 fields to `ApiSearchResult` interface and `transformSearchResponse()` mapping
- `src/__tests__/lib/api/search.test.ts`: Added tests for field mapping and graceful handling of missing values

## Test plan
- [x] Unit tests pass (`npx jest`)
- [x] Deploy via `deploy.sh web-app`
- [x] Integration tests pass (`npm run test:all`)
- [x] Visual verification: thumbnails visible in video list and info cards on map page
EOF
)"
```

**Step 2: Check CI status**

Run: `cd AcctAtlas-web-app && gh pr checks`

Expected: All CI checks pass.
