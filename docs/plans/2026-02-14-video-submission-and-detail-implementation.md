# Video Submission & Detail Page Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add video submission form, enhanced video detail page, and persistent nav bar to make AccountabilityAtlas demo-ready.

**Architecture:** Three repos are touched: video-service (backend fix + new endpoint), web-app (nav bar, submission form, detail page rewrite), integration-tests (E2E coverage). All web-app work uses existing component patterns (Chip, Button, Input, Card, MapView, LocationSearch) and the established API client + React Query architecture.

**Tech Stack:** Next.js 14 / React 18 / TypeScript / Tailwind CSS / Mapbox GL JS / TanStack React Query / Axios / Spring Boot 3.4 / Java 21

---

## Task 1: Fix video-service GET /videos/{id} LazyInitializationException

**Repo:** AcctAtlas-video-service
**Issue:** The `toVideoDetail()` method in `VideoController.java` accesses `video.getLocations()` which triggers lazy loading outside the Hibernate session. The app has `spring.jpa.open-in-view: false` (correct for production), so this throws `LazyInitializationException`.

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/videoservice/service/VideoService.java`
- Modify: `src/main/java/com/accountabilityatlas/videoservice/repository/VideoRepository.java`
- Test: `src/test/java/com/accountabilityatlas/videoservice/service/VideoServiceTest.java`

**Step 1: Add eager-fetch query to VideoRepository**

Add a custom query that joins locations:

```java
@Query("SELECT v FROM Video v LEFT JOIN FETCH v.locations WHERE v.id = :id")
Optional<Video> findByIdWithLocations(@Param("id") UUID id);
```

**Step 2: Update VideoService.getVideo() to use the new query**

Change `findVideoOrThrow(id)` to use `findByIdWithLocations`:

```java
@Transactional(readOnly = true)
public Video getVideo(UUID id) {
    return videoRepository.findByIdWithLocations(id)
        .orElseThrow(() -> new VideoNotFoundException(id));
}
```

**Step 3: Run tests**

```bash
./gradlew test
```

Verify the existing `VideoServiceTest` and `VideoControllerTest` pass. If there's no integration test for `GET /videos/{id}`, the manual check is:

```bash
curl http://localhost:8082/videos/{seed-video-id}
```

Should return 200 with locations array instead of 500.

**Step 4: Commit**

```bash
git add -A && git commit -m "fix: eager-fetch locations in getVideo to prevent LazyInitializationException"
```

---

## Task 2: Add YouTube preview endpoint to video-service

**Repo:** AcctAtlas-video-service
**Issue:** The submission form needs to preview YouTube metadata before creating a video record. Add `GET /videos/preview?youtubeUrl=...`.

**Files:**
- Modify: `docs/api-specification.yaml` (add endpoint spec)
- Modify: `src/main/java/com/accountabilityatlas/videoservice/web/VideoController.java`
- Test: `src/test/java/com/accountabilityatlas/videoservice/web/VideoControllerTest.java`

**Step 1: Add endpoint to OpenAPI spec**

Add to `docs/api-specification.yaml` under `paths`:

```yaml
  /videos/preview:
    get:
      operationId: previewVideo
      summary: Preview YouTube video metadata
      description: >
        Fetches YouTube metadata for the given URL without creating a video record.
        Returns title, description, thumbnail, duration, channel info, and published date.
        Also checks if the video has already been submitted.
      tags: [Videos]
      parameters:
        - name: youtubeUrl
          in: query
          required: true
          schema:
            type: string
            format: uri
          description: YouTube video URL
      responses:
        '200':
          description: Video metadata preview
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/VideoPreview'
        '400':
          description: Invalid YouTube URL
        '409':
          description: Video already submitted
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
        '422':
          description: YouTube video unavailable or private
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
```

Add `VideoPreview` schema under `components/schemas`:

```yaml
    VideoPreview:
      type: object
      required: [youtubeId, title, thumbnailUrl, channelId, channelName, publishedAt]
      properties:
        youtubeId:
          type: string
        title:
          type: string
        description:
          type: string
          nullable: true
        thumbnailUrl:
          type: string
          format: uri
        durationSeconds:
          type: integer
          nullable: true
        channelId:
          type: string
        channelName:
          type: string
        publishedAt:
          type: string
          format: date-time
        alreadyExists:
          type: boolean
          description: True if this video has already been submitted
        existingVideoId:
          type: string
          format: uuid
          nullable: true
          description: ID of existing video if alreadyExists is true
```

**Step 2: Regenerate API models**

```bash
./gradlew openApiGenerate
```

This generates the `VideoPreview` model class and adds `previewVideo` to the `VideosApi` interface.

**Step 3: Implement the endpoint in VideoController**

Add method to `VideoController.java`:

```java
@Override
public ResponseEntity<VideoPreview> previewVideo(String youtubeUrl) {
    String videoId = youTubeService.extractVideoId(youtubeUrl);

    VideoPreview preview = new VideoPreview();
    preview.setYoutubeId(videoId);

    // Check if already submitted
    Optional<Video> existing = videoRepository.findByYoutubeId(videoId);
    if (existing.isPresent()) {
        preview.setAlreadyExists(true);
        preview.setExistingVideoId(existing.get().getId());
    } else {
        preview.setAlreadyExists(false);
    }

    // Fetch YouTube metadata
    YouTubeService.YouTubeMetadata metadata = youTubeService.fetchMetadata(videoId);
    preview.setTitle(metadata.title());
    preview.setDescription(metadata.description());
    preview.setThumbnailUrl(URI.create(metadata.thumbnailUrl()));
    preview.setDurationSeconds(metadata.durationSeconds());
    preview.setChannelId(metadata.channelId());
    preview.setChannelName(metadata.channelName());
    preview.setPublishedAt(metadata.publishedAt().atOffset(ZoneOffset.UTC));

    return ResponseEntity.ok(preview);
}
```

Note: `findByYoutubeId` may need to be added to `VideoRepository` if it doesn't exist. Check and add:

```java
Optional<Video> findByYoutubeId(String youtubeId);
```

**Step 4: Write tests**

Add to `VideoControllerTest.java`:

```java
@Test
void previewVideo_validUrl_returnsMetadata() {
    // Mock YouTubeService to return metadata
    // Mock VideoRepository.findByYoutubeId to return empty
    // Call GET /videos/preview?youtubeUrl=https://www.youtube.com/watch?v=test123
    // Assert 200 with expected fields
}

@Test
void previewVideo_alreadyExists_returnsWithExistingId() {
    // Mock VideoRepository.findByYoutubeId to return a video
    // Assert alreadyExists=true, existingVideoId set
}

@Test
void previewVideo_invalidUrl_returns400() {
    // Pass invalid URL
    // Assert 400
}
```

**Step 5: Run tests**

```bash
./gradlew test
```

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: add GET /videos/preview endpoint for YouTube metadata preview"
```

---

## Task 3: Add persistent nav bar to web-app

**Repo:** AcctAtlas-web-app
**Issue:** No global navigation exists. Add a nav bar to all pages.

**Files:**
- Create: `src/components/NavBar.tsx`
- Modify: `src/app/layout.tsx`
- Modify: `src/app/map/page.tsx` (adjust height for nav bar)
- Create: `src/__tests__/components/NavBar.test.tsx`

**Step 1: Create NavBar component**

Create `src/components/NavBar.tsx`:

```tsx
"use client";

import Link from "next/link";
import { useAuth } from "@/providers/AuthProvider";
import { Button } from "@/components/ui/Button";

export function NavBar() {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <nav className="h-14 bg-white border-b border-gray-200 px-4 flex items-center justify-between flex-shrink-0">
      <Link href="/" className="text-lg font-semibold text-gray-900 hover:text-blue-600 transition-colors">
        AccountabilityAtlas
      </Link>
      <div className="flex items-center gap-3">
        <Link href="/map">
          <Button variant="outline" className="text-sm">
            Explore Map
          </Button>
        </Link>
        {isAuthenticated ? (
          <>
            <Link href="/videos/new">
              <Button variant="primary" className="text-sm">
                Submit Video
              </Button>
            </Link>
            <span className="text-sm text-gray-600">{user?.displayName}</span>
            <button
              onClick={logout}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Sign Out
            </button>
          </>
        ) : (
          <Link href="/login">
            <Button variant="outline" className="text-sm">
              Sign In
            </Button>
          </Link>
        )}
      </div>
    </nav>
  );
}
```

**Step 2: Add NavBar to root layout**

Modify `src/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import { QueryProvider } from "@/providers/QueryProvider";
import { AuthProvider } from "@/providers/AuthProvider";
import { NavBar } from "@/components/NavBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "AccountabilityAtlas",
  description: "Geo-located video curation for constitutional rights audits",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-100 flex flex-col">
        <QueryProvider>
          <AuthProvider>
            <NavBar />
            <main className="flex-1">{children}</main>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
```

**Note:** NavBar uses `useAuth()` which requires `"use client"`, but the layout is a server component. The NavBar component itself has `"use client"` so this works — Next.js renders it as a client component island within the server layout.

**Step 3: Adjust map page height**

The map currently uses `h-screen`. With the 56px nav bar, it needs `h-[calc(100vh-3.5rem)]`. Modify `src/app/map/page.tsx` — find the outermost container div wrapping MapContainer and change its height class.

Also check `src/components/map/MapContainer.tsx` for any `h-screen` usage and change to `h-full` so it fills its parent.

**Step 4: Write NavBar tests**

Create `src/__tests__/components/NavBar.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { NavBar } from "@/components/NavBar";

// Mock AuthProvider
const mockLogout = jest.fn();
let mockAuth = { user: null, isAuthenticated: false, isLoading: false, logout: mockLogout };
jest.mock("@/providers/AuthProvider", () => ({
  useAuth: () => mockAuth,
}));

describe("NavBar", () => {
  it("shows site name linking to home", () => {
    render(<NavBar />);
    const link = screen.getByText("AccountabilityAtlas");
    expect(link.closest("a")).toHaveAttribute("href", "/");
  });

  it("shows Explore Map link", () => {
    render(<NavBar />);
    expect(screen.getByText("Explore Map").closest("a")).toHaveAttribute("href", "/map");
  });

  it("shows Sign In when not authenticated", () => {
    render(<NavBar />);
    expect(screen.getByText("Sign In")).toBeInTheDocument();
    expect(screen.queryByText("Submit Video")).not.toBeInTheDocument();
  });

  it("shows Submit Video and user name when authenticated", () => {
    mockAuth = {
      user: { id: "1", displayName: "Test User", email: "t@t.com", emailVerified: true, trustTier: "NEW" },
      isAuthenticated: true,
      isLoading: false,
      logout: mockLogout,
    };
    render(<NavBar />);
    expect(screen.getByText("Submit Video")).toBeInTheDocument();
    expect(screen.getByText("Test User")).toBeInTheDocument();
    expect(screen.getByText("Sign Out")).toBeInTheDocument();
  });
});
```

**Step 5: Run tests and verify**

```bash
npm run check
```

Verify the nav bar renders on all pages visually. Check that the map page still fills the viewport below the nav bar.

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: add persistent nav bar with auth-aware navigation"
```

---

## Task 4: Add redirect-after-login support

**Repo:** AcctAtlas-web-app
**Issue:** Login page always redirects to `/`. Need to support `?redirect=/videos/new`.

**Files:**
- Modify: `src/app/login/page.tsx`
- Test: `src/__tests__/app/login/page.test.tsx` (if exists, or create)

**Step 1: Update login page to read redirect param**

In `src/app/login/page.tsx`, add `useSearchParams`:

```tsx
import { useRouter, useSearchParams } from "next/navigation";
```

In the component, read the param:

```tsx
const searchParams = useSearchParams();
const redirectTo = searchParams.get("redirect") || "/";
```

Change the existing redirect-if-authenticated check:

```tsx
if (isAuthenticated) {
  router.push(redirectTo);
  return null;
}
```

Change the post-login redirect (inside the form submit handler) from `router.push("/")` to:

```tsx
router.push(redirectTo);
```

**Step 2: Run tests**

```bash
npm run check
```

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: support redirect query param on login page"
```

---

## Task 5: Add new API types and functions to web-app

**Repo:** AcctAtlas-web-app
**Issue:** The submission form and detail page need new types and API functions.

**Files:**
- Modify: `src/types/api.ts` (add VideoDetail, VideoPreview, ModerationItem types)
- Modify: `src/lib/api/videos.ts` (add previewVideo, createVideo)
- Modify: `src/lib/api/locations.ts` (add createLocation, reverseGeocode)
- Create: `src/lib/api/moderation.ts` (getModerationQueue, approveItem, rejectItem)
- Test: `src/__tests__/lib/api/videos.test.ts` (add tests for new functions)
- Test: `src/__tests__/lib/api/locations.test.ts` (add tests for new functions)
- Test: `src/__tests__/lib/api/moderation.test.ts`

**Step 1: Add types to `src/types/api.ts`**

```typescript
export interface VideoPreview {
  youtubeId: string;
  title: string;
  description?: string;
  thumbnailUrl: string;
  durationSeconds?: number;
  channelId: string;
  channelName: string;
  publishedAt: string;
  alreadyExists: boolean;
  existingVideoId?: string;
}

export interface VideoDetailResponse {
  id: string;
  youtubeId: string;
  title: string;
  description?: string;
  thumbnailUrl?: string;
  durationSeconds?: number;
  channelId: string;
  channelName: string;
  publishedAt: string;
  videoDate?: string;
  amendments: string[];
  participants: string[];
  status: "PENDING" | "APPROVED" | "REJECTED" | "DELETED";
  submittedBy: string;
  createdAt: string;
  locations: VideoLocationDetail[];
  submitter?: {
    id: string;
    displayName: string;
    avatarUrl?: string;
  };
}

export interface VideoLocationDetail {
  id: string;
  videoId: string;
  locationId: string;
  isPrimary: boolean;
  location?: {
    id: string;
    displayName: string;
    city?: string;
    state?: string;
    coordinates?: { latitude: number; longitude: number };
  };
}

export interface CreateVideoRequest {
  youtubeUrl: string;
  amendments: string[];
  participants: string[];
  videoDate?: string;
  locationId?: string;
}

export interface CreateLocationRequest {
  latitude: number;
  longitude: number;
  displayName: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
}

export interface CreateLocationResponse {
  id: string;
  displayName: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  latitude: number;
  longitude: number;
}

export interface ReverseGeocodeResponse {
  displayName: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
}

export interface ModerationItem {
  id: string;
  contentType: "VIDEO" | "LOCATION";
  contentId: string;
  submitterId: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  reviewerId?: string;
  reviewedAt?: string;
  rejectionReason?: string;
  createdAt: string;
}

export interface ModerationQueueResponse {
  content: ModerationItem[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
}
```

**Step 2: Update `src/lib/api/videos.ts`**

Add new functions alongside existing `getVideo`:

```typescript
import apiClient from "./client";
import type {
  VideoPreview,
  VideoDetailResponse,
  CreateVideoRequest,
} from "@/types/api";

export async function getVideo(id: string): Promise<VideoDetailResponse> {
  const response = await apiClient.get<VideoDetailResponse>(`/videos/${id}`);
  return response.data;
}

export async function previewVideo(youtubeUrl: string): Promise<VideoPreview> {
  const response = await apiClient.get<VideoPreview>("/videos/preview", {
    params: { youtubeUrl },
  });
  return response.data;
}

export async function createVideo(
  data: CreateVideoRequest
): Promise<VideoDetailResponse> {
  const response = await apiClient.post<VideoDetailResponse>("/videos", data);
  return response.data;
}
```

**Step 3: Update `src/lib/api/locations.ts`**

Add `createLocation` and `reverseGeocode` alongside existing functions:

```typescript
import type {
  CreateLocationRequest,
  CreateLocationResponse,
  ReverseGeocodeResponse,
} from "@/types/api";

export async function createLocation(
  data: CreateLocationRequest
): Promise<CreateLocationResponse> {
  const response = await apiClient.post<CreateLocationResponse>(
    "/locations",
    data
  );
  return response.data;
}

export async function reverseGeocode(
  lat: number,
  lng: number
): Promise<ReverseGeocodeResponse> {
  const response = await apiClient.get<ReverseGeocodeResponse>(
    "/locations/reverse",
    { params: { lat, lng } }
  );
  return response.data;
}
```

**Step 4: Create `src/lib/api/moderation.ts`**

```typescript
import apiClient from "./client";
import type { ModerationQueueResponse, ModerationItem } from "@/types/api";

export async function getModerationQueue(params: {
  status?: string;
  contentType?: string;
  page?: number;
  size?: number;
}): Promise<ModerationQueueResponse> {
  const response = await apiClient.get<ModerationQueueResponse>(
    "/moderation/queue",
    { params }
  );
  return response.data;
}

export async function approveItem(id: string): Promise<ModerationItem> {
  const response = await apiClient.post<ModerationItem>(
    `/moderation/queue/${id}/approve`
  );
  return response.data;
}

export async function rejectItem(
  id: string,
  reason: string
): Promise<ModerationItem> {
  const response = await apiClient.post<ModerationItem>(
    `/moderation/queue/${id}/reject`,
    { reason }
  );
  return response.data;
}
```

**Step 5: Write tests for new API functions**

Add tests to existing test files or create new ones. Mock `apiClient` and verify correct URLs, params, and return values. Follow the existing test pattern in `src/__tests__/lib/api/`.

**Step 6: Run tests**

```bash
npm run check
```

**Step 7: Commit**

```bash
git add -A && git commit -m "feat: add API types and functions for submission, detail, and moderation"
```

---

## Task 6: Build video submission form

**Repo:** AcctAtlas-web-app
**Issue:** web-app #22

**Files:**
- Create: `src/app/videos/new/page.tsx` (route page, auth guard)
- Create: `src/components/video/VideoSubmitForm.tsx` (main form)
- Create: `src/components/video/YouTubePreview.tsx` (preview card)
- Create: `src/components/video/LocationPicker.tsx` (map + reverse geocode)
- Test: `src/__tests__/components/video/YouTubePreview.test.tsx`
- Test: `src/__tests__/components/video/LocationPicker.test.tsx`

**Step 1: Create the route page with auth guard**

Create `src/app/videos/new/page.tsx`:

```tsx
"use client";

import { useAuth } from "@/providers/AuthProvider";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import dynamic from "next/dynamic";

const VideoSubmitForm = dynamic(
  () =>
    import("@/components/video/VideoSubmitForm").then(
      (mod) => mod.VideoSubmitForm
    ),
  { ssr: false }
);

export default function NewVideoPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login?redirect=/videos/new");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Submit a Video</h1>
      <VideoSubmitForm />
    </div>
  );
}
```

**Step 2: Create YouTubePreview component**

Create `src/components/video/YouTubePreview.tsx`:

```tsx
import type { VideoPreview } from "@/types/api";

interface YouTubePreviewProps {
  preview: VideoPreview;
}

export function YouTubePreview({ preview }: YouTubePreviewProps) {
  const minutes = preview.durationSeconds
    ? Math.floor(preview.durationSeconds / 60)
    : null;
  const seconds = preview.durationSeconds
    ? preview.durationSeconds % 60
    : null;

  return (
    <div className="flex gap-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
      <img
        src={preview.thumbnailUrl}
        alt={preview.title}
        className="w-40 h-24 object-cover rounded flex-shrink-0"
      />
      <div className="min-w-0">
        <h3 className="font-semibold text-gray-900 truncate">{preview.title}</h3>
        <p className="text-sm text-gray-600">{preview.channelName}</p>
        <div className="flex gap-3 mt-1 text-xs text-gray-500">
          {minutes !== null && seconds !== null && (
            <span>
              {minutes}:{seconds.toString().padStart(2, "0")}
            </span>
          )}
          <span>
            Published{" "}
            {new Date(preview.publishedAt).toLocaleDateString()}
          </span>
        </div>
      </div>
    </div>
  );
}
```

**Step 3: Create LocationPicker component**

Create `src/components/video/LocationPicker.tsx`:

This is the most complex component. It renders a Mapbox map where the user can click to place a marker, plus uses the existing LocationSearch for address search. After placing a marker, it calls reverseGeocode to display the resolved address.

```tsx
"use client";

import { useState, useCallback, useRef } from "react";
import Map, { Marker, type MapRef } from "react-map-gl";
import { MAPBOX_ACCESS_TOKEN, MAPBOX_STYLE } from "@/config/mapbox";
import { reverseGeocode } from "@/lib/api/locations";
import type { ReverseGeocodeResponse } from "@/types/api";
import "mapbox-gl/dist/mapbox-gl.css";

interface LocationPickerProps {
  onLocationChange: (location: {
    latitude: number;
    longitude: number;
    geocode: ReverseGeocodeResponse;
  } | null) => void;
  error?: string;
}

export function LocationPicker({ onLocationChange, error }: LocationPickerProps) {
  const mapRef = useRef<MapRef>(null);
  const [marker, setMarker] = useState<{ lat: number; lng: number } | null>(null);
  const [geocodeResult, setGeocodeResult] = useState<ReverseGeocodeResponse | null>(null);
  const [isGeocoding, setIsGeocoding] = useState(false);

  const handleMapClick = useCallback(
    async (e: { lngLat: { lng: number; lat: number } }) => {
      const { lng, lat } = e.lngLat;
      setMarker({ lat, lng });
      setIsGeocoding(true);
      setGeocodeResult(null);

      try {
        const result = await reverseGeocode(lat, lng);
        setGeocodeResult(result);
        onLocationChange({ latitude: lat, longitude: lng, geocode: result });
      } catch {
        setGeocodeResult(null);
        onLocationChange({ latitude: lat, longitude: lng, geocode: { displayName: `${lat.toFixed(4)}, ${lng.toFixed(4)}` } });
      } finally {
        setIsGeocoding(false);
      }
    },
    [onLocationChange]
  );

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        Location <span className="text-red-500">*</span>
      </label>
      <p className="text-xs text-gray-500 mb-2">
        Click the map to place a marker, or use the search box.
      </p>
      <div className="rounded-lg overflow-hidden border border-gray-300" style={{ height: 350 }}>
        <Map
          ref={mapRef}
          mapboxAccessToken={MAPBOX_ACCESS_TOKEN}
          mapStyle={MAPBOX_STYLE}
          initialViewState={{
            longitude: -98.5795,
            latitude: 39.8283,
            zoom: 4,
          }}
          onClick={handleMapClick}
          cursor="crosshair"
        >
          {marker && (
            <Marker latitude={marker.lat} longitude={marker.lng} color="#EF4444" />
          )}
        </Map>
      </div>
      {isGeocoding && (
        <p className="text-sm text-gray-500 mt-2">Resolving address...</p>
      )}
      {geocodeResult && (
        <p className="text-sm text-gray-700 mt-2">
          {[geocodeResult.address, geocodeResult.city, geocodeResult.state]
            .filter(Boolean)
            .join(", ") || geocodeResult.displayName}
        </p>
      )}
      {error && <p className="text-sm text-red-600 mt-1">{error}</p>}
    </div>
  );
}
```

**Step 4: Create VideoSubmitForm component**

Create `src/components/video/VideoSubmitForm.tsx`:

```tsx
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { YouTubePreview } from "@/components/video/YouTubePreview";
import { LocationPicker } from "@/components/video/LocationPicker";
import { previewVideo, createVideo } from "@/lib/api/videos";
import { createLocation } from "@/lib/api/locations";
import { useToasts } from "@/components/ui/Toast";
import { ToastContainer } from "@/components/ui/Toast";
import { AMENDMENT_OPTIONS, PARTICIPANT_TYPE_OPTIONS } from "@/types/map";
import type { VideoPreview, ReverseGeocodeResponse } from "@/types/api";
import axios from "axios";

export function VideoSubmitForm() {
  const router = useRouter();
  const { toasts, dismissToast, success, error: showError } = useToasts();

  // YouTube URL state
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [preview, setPreview] = useState<VideoPreview | null>(null);
  const [urlError, setUrlError] = useState("");
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);

  // Form fields
  const [videoDate, setVideoDate] = useState("");
  const [amendments, setAmendments] = useState<string[]>([]);
  const [participants, setParticipants] = useState<string[]>([]);
  const [location, setLocation] = useState<{
    latitude: number;
    longitude: number;
    geocode: ReverseGeocodeResponse;
  } | null>(null);

  // Validation
  const [amendmentError, setAmendmentError] = useState("");
  const [participantError, setParticipantError] = useState("");
  const [locationError, setLocationError] = useState("");

  // Submission
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handlePreview = async () => {
    if (!youtubeUrl.trim()) return;
    setUrlError("");
    setIsLoadingPreview(true);
    setPreview(null);

    try {
      const result = await previewVideo(youtubeUrl);
      if (result.alreadyExists) {
        setUrlError("This video has already been submitted.");
        setPreview(result);
      } else {
        setPreview(result);
      }
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 400) setUrlError("Please enter a valid YouTube URL.");
        else if (status === 422) setUrlError("This video is unavailable or private.");
        else setUrlError("Failed to fetch video info. Please try again.");
      } else {
        setUrlError("An unexpected error occurred.");
      }
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const toggleAmendment = (amendment: string) => {
    setAmendmentError("");
    setAmendments((prev) =>
      prev.includes(amendment)
        ? prev.filter((a) => a !== amendment)
        : [...prev, amendment]
    );
  };

  const toggleParticipant = (participant: string) => {
    setParticipantError("");
    setParticipants((prev) =>
      prev.includes(participant)
        ? prev.filter((p) => p !== participant)
        : [...prev, participant]
    );
  };

  const validate = (): boolean => {
    let valid = true;
    if (amendments.length === 0) {
      setAmendmentError("Select at least one amendment.");
      valid = false;
    }
    if (participants.length === 0) {
      setParticipantError("Select at least one participant type.");
      valid = false;
    }
    if (!location) {
      setLocationError("Click the map to place a location.");
      valid = false;
    }
    return valid;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!preview || preview.alreadyExists || !validate()) return;

    setIsSubmitting(true);
    try {
      // Create location first
      const loc = await createLocation({
        latitude: location!.latitude,
        longitude: location!.longitude,
        displayName: location!.geocode.displayName,
        address: location!.geocode.address,
        city: location!.geocode.city,
        state: location!.geocode.state,
        country: location!.geocode.country,
      });

      // Create video with location
      const video = await createVideo({
        youtubeUrl,
        amendments,
        participants,
        videoDate: videoDate || undefined,
        locationId: loc.id,
      });

      success("Video submitted successfully!");
      router.push(`/videos/${video.id}`);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        showError("This video has already been submitted.");
      } else {
        showError("Failed to submit video. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {/* YouTube URL */}
      <div className="mb-6">
        <div className="flex gap-2">
          <div className="flex-1">
            <Input
              label="YouTube URL"
              type="url"
              value={youtubeUrl}
              onChange={(e) => {
                setYoutubeUrl(e.target.value);
                setUrlError("");
              }}
              placeholder="https://www.youtube.com/watch?v=..."
              error={urlError}
              required
            />
          </div>
          <div className="pt-6">
            <Button
              type="button"
              variant="outline"
              onClick={handlePreview}
              isLoading={isLoadingPreview}
            >
              Preview
            </Button>
          </div>
        </div>
      </div>

      {/* Preview card */}
      {preview && !preview.alreadyExists && (
        <>
          <div className="mb-6">
            <YouTubePreview preview={preview} />
          </div>

          {/* Form fields in two columns on desktop */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Left column: metadata */}
            <div className="space-y-6">
              <Input
                label="Incident Date (optional)"
                type="date"
                value={videoDate}
                onChange={(e) => setVideoDate(e.target.value)}
              />

              {/* Amendments */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Amendments <span className="text-red-500">*</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {AMENDMENT_OPTIONS.map((opt) => (
                    <Chip
                      key={opt.id}
                      selected={amendments.includes(opt.amendment)}
                      onClick={() => toggleAmendment(opt.amendment)}
                    >
                      {opt.label}
                    </Chip>
                  ))}
                </div>
                {amendmentError && (
                  <p className="text-sm text-red-600 mt-1">{amendmentError}</p>
                )}
              </div>

              {/* Participants */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Participants <span className="text-red-500">*</span>
                </label>
                <div className="flex flex-wrap gap-2">
                  {PARTICIPANT_TYPE_OPTIONS.map((opt) => (
                    <Chip
                      key={opt.id}
                      selected={participants.includes(opt.id)}
                      onClick={() => toggleParticipant(opt.id)}
                    >
                      {opt.label}
                    </Chip>
                  ))}
                </div>
                {participantError && (
                  <p className="text-sm text-red-600 mt-1">{participantError}</p>
                )}
              </div>
            </div>

            {/* Right column: location picker */}
            <div>
              <LocationPicker
                onLocationChange={(loc) => {
                  setLocationError("");
                  setLocation(loc);
                }}
                error={locationError}
              />
            </div>
          </div>

          {/* Submit */}
          <div className="flex justify-end">
            <Button type="submit" variant="primary" isLoading={isSubmitting}>
              Submit Video
            </Button>
          </div>
        </>
      )}

      {/* Already exists message */}
      {preview && preview.alreadyExists && (
        <div className="mb-6">
          <YouTubePreview preview={preview} />
          <p className="mt-3 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-3">
            This video has already been submitted.{" "}
            {preview.existingVideoId && (
              <a
                href={`/videos/${preview.existingVideoId}`}
                className="underline font-medium"
              >
                View it here.
              </a>
            )}
          </p>
        </div>
      )}

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </form>
  );
}
```

**Step 5: Write tests for YouTubePreview and LocationPicker**

Test `YouTubePreview` renders title, channel, duration, thumbnail. Test `LocationPicker` renders map container and error message. Mock Mapbox components since they require WebGL.

**Step 6: Run tests**

```bash
npm run check
```

**Step 7: Commit**

```bash
git add -A && git commit -m "feat: add video submission form with YouTube preview and location picker

Closes #22"
```

---

## Task 7: Rewrite video detail page

**Repo:** AcctAtlas-web-app
**Issue:** web-app #24

**Files:**
- Rewrite: `src/app/videos/[id]/page.tsx`
- Create: `src/components/video/VideoDetail.tsx` (main detail component)
- Create: `src/components/video/ModerationControls.tsx` (approve/reject)
- Create: `src/components/video/MiniMap.tsx` (sidebar map)

**Step 1: Create MiniMap component**

Create `src/components/video/MiniMap.tsx`:

```tsx
"use client";

import Map, { Marker } from "react-map-gl";
import { MAPBOX_ACCESS_TOKEN, MAPBOX_STYLE } from "@/config/mapbox";
import "mapbox-gl/dist/mapbox-gl.css";

interface MiniMapProps {
  latitude: number;
  longitude: number;
}

export function MiniMap({ latitude, longitude }: MiniMapProps) {
  return (
    <div className="rounded-lg overflow-hidden border border-gray-200" style={{ height: 250 }}>
      <Map
        mapboxAccessToken={MAPBOX_ACCESS_TOKEN}
        mapStyle={MAPBOX_STYLE}
        initialViewState={{ latitude, longitude, zoom: 13 }}
        interactive={true}
      >
        <Marker latitude={latitude} longitude={longitude} color="#EF4444" />
      </Map>
    </div>
  );
}
```

**Step 2: Create ModerationControls component**

Create `src/components/video/ModerationControls.tsx`:

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { approveItem, rejectItem, getModerationQueue } from "@/lib/api/moderation";

interface ModerationControlsProps {
  videoId: string;
  onStatusChange: (newStatus: string) => void;
}

export function ModerationControls({ videoId, onStatusChange }: ModerationControlsProps) {
  const [isApproving, setIsApproving] = useState(false);
  const [isRejecting, setIsRejecting] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [error, setError] = useState("");

  const findModerationItemId = async (): Promise<string | null> => {
    const queue = await getModerationQueue({
      contentType: "VIDEO",
      status: "PENDING",
      size: 100,
    });
    const item = queue.content.find((i) => i.contentId === videoId);
    return item?.id ?? null;
  };

  const handleApprove = async () => {
    setIsApproving(true);
    setError("");
    try {
      const itemId = await findModerationItemId();
      if (!itemId) {
        setError("Moderation item not found.");
        return;
      }
      await approveItem(itemId);
      onStatusChange("APPROVED");
    } catch {
      setError("Failed to approve. Please try again.");
    } finally {
      setIsApproving(false);
    }
  };

  const handleReject = async () => {
    if (rejectReason.length < 10) {
      setError("Rejection reason must be at least 10 characters.");
      return;
    }
    setIsRejecting(true);
    setError("");
    try {
      const itemId = await findModerationItemId();
      if (!itemId) {
        setError("Moderation item not found.");
        return;
      }
      await rejectItem(itemId, rejectReason);
      onStatusChange("REJECTED");
      setShowRejectModal(false);
    } catch {
      setError("Failed to reject. Please try again.");
    } finally {
      setIsRejecting(false);
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-700">Moderation</h3>
      <div className="flex gap-2">
        <Button variant="primary" onClick={handleApprove} isLoading={isApproving}>
          Approve
        </Button>
        <Button variant="outline" onClick={() => setShowRejectModal(true)}>
          Reject
        </Button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {showRejectModal && (
        <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Rejection reason (min 10 characters)
          </label>
          <textarea
            className="w-full border border-gray-300 rounded-md p-2 text-sm"
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
          />
          <div className="flex gap-2 mt-2">
            <Button variant="outline" onClick={handleReject} isLoading={isRejecting}>
              Confirm Reject
            </Button>
            <button
              onClick={() => setShowRejectModal(false)}
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 3: Create VideoDetail component**

Create `src/components/video/VideoDetail.tsx`:

This is the main component that fetches video data, renders the layout with YouTube embed, metadata, description, mini-map, and moderation controls.

```tsx
"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/providers/AuthProvider";
import { getVideo } from "@/lib/api/videos";
import { Chip } from "@/components/ui/Chip";
import { MiniMap } from "@/components/video/MiniMap";
import { ModerationControls } from "@/components/video/ModerationControls";
import { AMENDMENT_OPTIONS, PARTICIPANT_TYPE_OPTIONS } from "@/types/map";
import Link from "next/link";

interface VideoDetailProps {
  videoId: string;
}

export function VideoDetail({ videoId }: VideoDetailProps) {
  const { user, isAuthenticated } = useAuth();
  const [descExpanded, setDescExpanded] = useState(false);

  const { data: video, isLoading, error, refetch } = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => getVideo(videoId),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading video...</div>
      </div>
    );
  }

  if (error || !video) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <p className="text-gray-500">Video not found.</p>
        <Link href="/map" className="text-blue-600 hover:underline">
          Back to Map
        </Link>
      </div>
    );
  }

  const primaryLocation = video.locations?.find((l) => l.isPrimary) ?? video.locations?.[0];
  const coords = primaryLocation?.location?.coordinates;
  const locationName = primaryLocation?.location?.displayName;
  const locationCity = primaryLocation?.location?.city;
  const locationState = primaryLocation?.location?.state;

  const isModerator = user?.trustTier === "MODERATOR" || user?.trustTier === "ADMIN"
    || user?.trustTier === "VERIFIED"; // ADMIN mapped from docs
  const isOwner = user?.id === video.submittedBy;
  const showStatus = isModerator || isOwner;
  const showModControls = isModerator && video.status === "PENDING";

  const durationMin = video.durationSeconds ? Math.floor(video.durationSeconds / 60) : null;
  const durationSec = video.durationSeconds ? video.durationSeconds % 60 : null;

  const formatAmendmentLabel = (amendment: string) => {
    const opt = AMENDMENT_OPTIONS.find((o) => o.amendment === amendment);
    return opt?.label ?? amendment;
  };

  const formatParticipantLabel = (participant: string) => {
    const opt = PARTICIPANT_TYPE_OPTIONS.find((o) => o.id === participant);
    return opt?.label ?? participant;
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main column */}
        <div className="lg:col-span-2 space-y-4">
          {/* YouTube embed */}
          <div className="aspect-video bg-black rounded-lg overflow-hidden">
            <iframe
              src={`https://www.youtube.com/embed/${video.youtubeId}`}
              title={video.title}
              className="w-full h-full"
              allowFullScreen
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            />
          </div>

          {/* Title */}
          <h1 className="text-xl font-bold text-gray-900">{video.title}</h1>

          {/* Metadata row */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
            {video.channelName && <span>{video.channelName}</span>}
            {durationMin !== null && durationSec !== null && (
              <span>{durationMin}:{durationSec.toString().padStart(2, "0")}</span>
            )}
            {video.publishedAt && (
              <span>Published {new Date(video.publishedAt).toLocaleDateString()}</span>
            )}
            {video.videoDate && (
              <span>Incident date: {new Date(video.videoDate).toLocaleDateString()}</span>
            )}
          </div>

          {/* Amendments and participants */}
          <div className="flex flex-wrap gap-2">
            {video.amendments.map((a) => (
              <Chip key={a} size="sm">{formatAmendmentLabel(a)}</Chip>
            ))}
            {video.participants.map((p) => (
              <Chip key={p} size="sm">{formatParticipantLabel(p)}</Chip>
            ))}
          </div>

          {/* Description */}
          {video.description && (
            <div>
              <p className={`text-sm text-gray-700 whitespace-pre-wrap ${descExpanded ? "" : "line-clamp-3"}`}>
                {video.description}
              </p>
              <button
                onClick={() => setDescExpanded(!descExpanded)}
                className="text-sm text-blue-600 hover:underline mt-1"
              >
                {descExpanded ? "Show less" : "Show more"}
              </button>
            </div>
          )}

          {/* Submitter */}
          {isAuthenticated && video.submitter && (
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <span>Submitted by</span>
              <span className="font-medium text-gray-700">{video.submitter.displayName}</span>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Status badge */}
          {showStatus && (
            <div>
              <span
                className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                  video.status === "APPROVED"
                    ? "bg-green-100 text-green-800"
                    : video.status === "PENDING"
                      ? "bg-yellow-100 text-yellow-800"
                      : "bg-red-100 text-red-800"
                }`}
              >
                {video.status}
              </span>
            </div>
          )}

          {/* Mini-map */}
          {coords && (
            <div>
              <MiniMap latitude={coords.latitude} longitude={coords.longitude} />
              {locationName && (
                <Link
                  href={`/map?lat=${coords.latitude}&lng=${coords.longitude}&zoom=14`}
                  className="block text-sm text-blue-600 hover:underline mt-2"
                >
                  {[locationName, locationCity, locationState].filter(Boolean).join(", ")}
                </Link>
              )}
            </div>
          )}

          {/* Moderation controls */}
          {showModControls && (
            <ModerationControls
              videoId={video.id}
              onStatusChange={() => refetch()}
            />
          )}

          {/* Back to map */}
          <Link
            href="/map"
            className="block text-sm text-gray-500 hover:text-gray-700"
          >
            &larr; Back to Map
          </Link>
        </div>
      </div>
    </div>
  );
}
```

**Step 4: Rewrite the route page**

Rewrite `src/app/videos/[id]/page.tsx`:

```tsx
"use client";

import { useParams } from "next/navigation";
import dynamic from "next/dynamic";

const VideoDetail = dynamic(
  () => import("@/components/video/VideoDetail").then((mod) => mod.VideoDetail),
  { ssr: false }
);

export default function VideoPage() {
  const params = useParams();
  const videoId = params.id as string;

  return <VideoDetail videoId={videoId} />;
}
```

**Step 5: Run tests**

```bash
npm run check
```

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: rewrite video detail page with mini-map, metadata, and moderation controls

Closes #24"
```

---

## Task 8: Handle map page query params for location linking

**Repo:** AcctAtlas-web-app
**Issue:** The video detail page links to `/map?lat=...&lng=...&zoom=14`. The map page needs to read these params and fly to that location on load.

**Files:**
- Modify: `src/app/map/page.tsx`
- Modify: `src/providers/MapProvider.tsx` (or handle in MapContainer)

**Step 1: Read query params in map page and pass initial viewport**

In `src/app/map/page.tsx`, read `searchParams` and pass initial viewport to MapProvider:

```tsx
"use client";

import { useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { MapProvider } from "@/providers/MapProvider";

const MapContainer = dynamic(
  () => import("@/components/map/MapContainer").then((mod) => mod.MapContainer),
  { ssr: false, loading: () => <div className="flex-1 bg-gray-200 animate-pulse" /> }
);

export default function MapPage() {
  const searchParams = useSearchParams();
  const lat = searchParams.get("lat");
  const lng = searchParams.get("lng");
  const zoom = searchParams.get("zoom");

  const initialViewport = lat && lng ? {
    latitude: parseFloat(lat),
    longitude: parseFloat(lng),
    zoom: zoom ? parseInt(zoom) : 14,
  } : undefined;

  return (
    <MapProvider initialViewport={initialViewport}>
      <MapContainer />
    </MapProvider>
  );
}
```

Update `MapProvider` to accept an optional `initialViewport` prop that overrides the default viewport.

**Step 2: Run tests**

```bash
npm run check
```

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: support lat/lng/zoom query params on map page for location linking"
```

---

## Task 9: Integration tests

**Repo:** AcctAtlas-integration-tests
**Issue:** Verify the full submission and detail page workflows end-to-end.

**Files:**
- Create: `api/videos/submit-video.spec.ts` (API test for submit flow)
- Create: `e2e/video-submission.spec.ts` (Playwright E2E test)

**Step 1: Write API integration test**

Test the full flow:
1. Login as test user
2. Call `GET /videos/preview?youtubeUrl=...` — verify metadata returned
3. Call `POST /locations` — create a location
4. Call `POST /videos` — create a video with the location
5. Call `GET /videos/{id}` — verify video detail returns with locations
6. Call `GET /search?q={title}` — verify video appears in search (if auto-approved)

**Step 2: Write E2E test**

Test the UI flow:
1. Navigate to `/videos/new` (should redirect to login)
2. Login
3. Should be redirected back to `/videos/new`
4. Paste YouTube URL, click Preview
5. Verify preview card appears
6. Select amendments and participants
7. Click map to place location
8. Submit form
9. Verify redirect to video detail page

**Step 3: Run tests**

```bash
npx playwright test api/videos/submit-video.spec.ts
npx playwright test e2e/video-submission.spec.ts
```

**Step 4: Commit**

```bash
git add -A && git commit -m "test: add integration tests for video submission and detail page workflows"
```

---

## Task Dependencies

```
Task 1 (fix lazy loading) ──┐
                             ├── Task 7 (detail page rewrite) ── Task 8 (map query params)
Task 2 (preview endpoint) ──┤
                             ├── Task 6 (submission form)
Task 5 (API types) ─────────┤
                             └── Task 9 (integration tests)
Task 3 (nav bar) ── standalone
Task 4 (login redirect) ── standalone (but needed by Task 6)
```

**Parallelizable groups:**
- **Group A (video-service):** Tasks 1, 2 — can be done together, same repo
- **Group B (web-app foundation):** Tasks 3, 4, 5 — independent of each other
- **Group C (web-app features):** Tasks 6, 7 — depend on Group A + B
- **Group D (polish + test):** Tasks 8, 9 — depend on Group C
