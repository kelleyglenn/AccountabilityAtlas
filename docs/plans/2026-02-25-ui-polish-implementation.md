# UI Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement five independent web-app UI polish items (#21, #35, #41, #65, #66) on a single `feature/ui-polish` branch.

**Architecture:** All changes are contained in `AcctAtlas-web-app`. Static page titles use Next.js `metadata` exports in per-route `layout.tsx` files. Dynamic titles use `generateMetadata` with server-side `fetch()`. NavBar gets avatar display and login redirect. Map gets translucent search bar + home button. Profile page gets a "View public profile" link.

**Tech Stack:** Next.js 14, React 18, Tailwind CSS 3, TypeScript, Jest + Testing Library

---

### Task 0: Create feature branch

**Step 1: Create branch from latest master**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app
git checkout master
git pull origin master
git checkout -b feature/ui-polish
```

**Step 2: Verify clean state**

```bash
git status
```

Expected: `On branch feature/ui-polish`, clean working tree.

---

### Task 1: Root layout title template (#35)

**Files:**
- Modify: `src/app/layout.tsx:7-10`

**Step 1: Update root layout metadata**

In `src/app/layout.tsx`, change the metadata from:

```ts
export const metadata: Metadata = {
  title: "AccountabilityAtlas",
  description: "Geo-located video curation for constitutional rights audits",
};
```

to:

```ts
export const metadata: Metadata = {
  title: {
    template: "%s | AccountabilityAtlas",
    default: "AccountabilityAtlas",
  },
  description: "Geo-located video curation for constitutional rights audits",
};
```

**Step 2: Run tests to verify nothing breaks**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest --passWithNoTests 2>&1 | tail -5
```

Expected: All existing tests pass.

**Step 3: Commit**

```bash
git add src/app/layout.tsx
git commit -m "feat: add title template to root layout (#35)"
```

---

### Task 2: Static route metadata layouts (#35)

**Files:**
- Create: `src/app/login/layout.tsx`
- Create: `src/app/register/layout.tsx`
- Create: `src/app/map/layout.tsx`
- Create: `src/app/videos/new/layout.tsx`
- Create: `src/app/profile/layout.tsx`

Each file follows the same pattern — a server component that exports `metadata` and passes children through. These are server components so they must NOT have `"use client"`.

**Step 1: Create all five layout files**

`src/app/login/layout.tsx`:
```tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign In",
};

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
```

`src/app/register/layout.tsx`:
```tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Register",
};

export default function RegisterLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
```

`src/app/map/layout.tsx`:
```tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Map",
};

export default function MapLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
```

`src/app/videos/new/layout.tsx`:
```tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Submit Video",
};

export default function SubmitVideoLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
```

`src/app/profile/layout.tsx`:
```tsx
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "My Profile",
};

export default function ProfileLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
```

**Step 2: Run tests**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest --passWithNoTests 2>&1 | tail -5
```

Expected: All existing tests pass (layouts are passthrough, no logic to break).

**Step 3: Commit**

```bash
git add src/app/login/layout.tsx src/app/register/layout.tsx src/app/map/layout.tsx src/app/videos/new/layout.tsx src/app/profile/layout.tsx
git commit -m "feat: add page title metadata to static routes (#35)"
```

---

### Task 3: Dynamic title for video detail page (#35)

**Files:**
- Modify: `src/app/videos/[id]/page.tsx` (rewrite as server component)
- Create: `src/app/videos/[id]/VideoDetailClient.tsx` (extracted client component)
- Modify: `src/__tests__/components/video/VideoDetail.test.tsx` (no change needed — tests the `VideoDetail` component directly, not the page)

The current `src/app/videos/[id]/page.tsx` is a `"use client"` component that dynamically imports `VideoDetail`. We'll convert it to a server component that exports `generateMetadata` and renders a new `VideoDetailClient` wrapper.

**Step 1: Create `src/app/videos/[id]/VideoDetailClient.tsx`**

Move the existing page content to a client component:

```tsx
"use client";

import { useParams } from "next/navigation";
import dynamic from "next/dynamic";

const VideoDetail = dynamic(
  () => import("@/components/video/VideoDetail").then((mod) => mod.VideoDetail),
  { ssr: false }
);

export default function VideoDetailClient() {
  const params = useParams();
  const videoId = Array.isArray(params.id)
    ? params.id[0]
    : (params.id as string);

  return <VideoDetail videoId={videoId} />;
}
```

**Step 2: Rewrite `src/app/videos/[id]/page.tsx` as server component**

```tsx
import type { Metadata } from "next";
import VideoDetailClient from "./VideoDetailClient";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api/v1";

interface VideoPageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({
  params,
}: VideoPageProps): Promise<Metadata> {
  const { id } = await params;
  try {
    const res = await fetch(`${API_BASE_URL}/videos/${id}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return { title: "Video" };
    const video = await res.json();
    return { title: video.title || "Video" };
  } catch {
    return { title: "Video" };
  }
}

export default function VideoPage() {
  return <VideoDetailClient />;
}
```

Note: In Next.js 14, `params` is a Promise in server components for `generateMetadata`. The `next: { revalidate: 60 }` caches the metadata fetch for 60 seconds.

**Step 3: Run tests**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest --passWithNoTests 2>&1 | tail -5
```

Expected: All tests pass. The `VideoDetail.test.tsx` tests the component directly (not the page wrapper), so it's unaffected.

**Step 4: Commit**

```bash
git add src/app/videos/[id]/page.tsx src/app/videos/[id]/VideoDetailClient.tsx
git commit -m "feat: add dynamic page title to video detail page (#35)"
```

---

### Task 4: Dynamic title for public profile page (#35)

**Files:**
- Modify: `src/app/users/[id]/page.tsx` (rewrite as server component)
- Create: `src/app/users/[id]/PublicProfileClient.tsx` (extracted client component)
- Modify: `src/__tests__/app/users/PublicProfilePage.test.tsx` (update import path)

**Step 1: Create `src/app/users/[id]/PublicProfileClient.tsx`**

Move the entire existing page content (the full client component with `useParams`, `useQuery`, social links, etc.) to this file. Copy the exact content of the current `src/app/users/[id]/page.tsx` but rename the default export:

```tsx
"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { getPublicProfile } from "@/lib/api/users";

export default function PublicProfileClient() {
  const params = useParams();
  const id = Array.isArray(params.id) ? params.id[0] : String(params.id);

  const {
    data: profile,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["public-profile", id],
    queryFn: () => getPublicProfile(id),
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg text-gray-600">Loading...</div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-4">
        <p className="text-gray-500">User not found.</p>
        <Link href="/map" className="text-blue-600 hover:underline">
          Back to Map
        </Link>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-lg mx-auto">
        <div className="bg-white rounded-lg shadow-md p-6 space-y-6">
          <div className="flex items-center gap-4">
            {profile.avatarUrl && (
              <img
                src={profile.avatarUrl}
                alt={`${profile.displayName}'s avatar`}
                className="w-16 h-16 rounded-full object-cover"
              />
            )}
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {profile.displayName}
              </h1>
              {profile.trustTier && (
                <span
                  className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                  data-testid="trust-tier-badge"
                >
                  {profile.trustTier}
                </span>
              )}
            </div>
          </div>

          <div className="space-y-2 text-sm text-gray-600">
            <p>
              Member since {new Date(profile.memberSince).toLocaleDateString()}
            </p>
            <p>
              {profile.approvedVideoCount} approved video
              {profile.approvedVideoCount === 1 ? "" : "s"}
            </p>
          </div>

          {profile.socialLinks &&
            Object.values(profile.socialLinks).some(Boolean) && (
              <div className="space-y-2">
                <h2 className="text-sm font-semibold text-gray-700">
                  Social Links
                </h2>
                <div className="flex flex-wrap gap-3">
                  {profile.socialLinks.youtube && (
                    <SocialLink
                      label="YouTube"
                      href={`https://youtube.com/channel/${profile.socialLinks.youtube}`}
                    />
                  )}
                  {profile.socialLinks.facebook && (
                    <SocialLink
                      label="Facebook"
                      href={`https://facebook.com/${profile.socialLinks.facebook}`}
                    />
                  )}
                  {profile.socialLinks.instagram && (
                    <SocialLink
                      label="Instagram"
                      href={`https://instagram.com/${profile.socialLinks.instagram}`}
                    />
                  )}
                  {profile.socialLinks.tiktok && (
                    <SocialLink
                      label="TikTok"
                      href={`https://tiktok.com/@${profile.socialLinks.tiktok}`}
                    />
                  )}
                  {profile.socialLinks.xTwitter && (
                    <SocialLink
                      label="X"
                      href={`https://x.com/${profile.socialLinks.xTwitter}`}
                    />
                  )}
                  {profile.socialLinks.bluesky && (
                    <SocialLink
                      label="Bluesky"
                      href={`https://bsky.app/profile/${profile.socialLinks.bluesky}`}
                    />
                  )}
                </div>
              </div>
            )}

          <div className="pt-4">
            <Link
              href="/map"
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              &larr; Back to Map
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}

function SocialLink({
  label,
  href,
}: Readonly<{ label: string; href: string }>) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-sm text-blue-600 hover:underline"
    >
      {label}
    </a>
  );
}
```

**Step 2: Rewrite `src/app/users/[id]/page.tsx` as server component**

```tsx
import type { Metadata } from "next";
import PublicProfileClient from "./PublicProfileClient";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api/v1";

interface UserPageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({
  params,
}: UserPageProps): Promise<Metadata> {
  const { id } = await params;
  try {
    const res = await fetch(`${API_BASE_URL}/users/${id}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return { title: "User Profile" };
    const user = await res.json();
    return { title: user.displayName || "User Profile" };
  } catch {
    return { title: "User Profile" };
  }
}

export default function UserPage() {
  return <PublicProfileClient />;
}
```

**Step 3: Update test import**

In `src/__tests__/app/users/PublicProfilePage.test.tsx`, change line 2:

From:
```ts
import PublicProfilePage from "@/app/users/[id]/page";
```

To:
```ts
import PublicProfilePage from "@/app/users/[id]/PublicProfileClient";
```

The test mocks `useParams` and `useQuery` — it tests the client component, not the server page wrapper. The rest of the test remains identical.

**Step 4: Run tests**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest --passWithNoTests 2>&1 | tail -5
```

Expected: All tests pass.

**Step 5: Commit**

```bash
git add src/app/users/[id]/page.tsx src/app/users/[id]/PublicProfileClient.tsx src/__tests__/app/users/PublicProfilePage.test.tsx
git commit -m "feat: add dynamic page title to public profile page (#35)"
```

---

### Task 5: NavBar login redirect (#41)

**Files:**
- Modify: `src/components/NavBar.tsx:70-71`
- Modify: `src/__tests__/components/NavBar.test.tsx`

**Step 1: Write the failing test**

Add to `src/__tests__/components/NavBar.test.tsx`, inside the main `describe("NavBar", ...)` block, after the existing tests:

```tsx
  describe("login redirect", () => {
    it("Sign In link includes redirect param with current path", () => {
      mockPathname = "/map";
      render(<NavBar />);
      const signInLink = screen.getByText("Sign In").closest("a");
      expect(signInLink).toHaveAttribute(
        "href",
        "/login?redirect=%2Fmap"
      );
    });

    it("Sign In link omits redirect param on home page", () => {
      mockPathname = "/";
      render(<NavBar />);
      const signInLink = screen.getByText("Sign In").closest("a");
      expect(signInLink).toHaveAttribute("href", "/login");
    });
  });
```

**Step 2: Run tests to verify they fail**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest NavBar.test --verbose 2>&1 | tail -20
```

Expected: The "includes redirect param" test fails (currently links to `/login` without params).

**Step 3: Implement the change**

In `src/components/NavBar.tsx`, change the Sign In link (around line 70):

From:
```tsx
          <Link href="/login">
```

To:
```tsx
          <Link
            href={
              isHome
                ? "/login"
                : `/login?redirect=${encodeURIComponent(pathname)}`
            }
          >
```

**Step 4: Run tests to verify they pass**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest NavBar.test --verbose 2>&1 | tail -20
```

Expected: All NavBar tests pass.

**Step 5: Commit**

```bash
git add src/components/NavBar.tsx src/__tests__/components/NavBar.test.tsx
git commit -m "feat: pass redirect param in Sign In link (#41)"
```

---

### Task 6: NavBar avatar display (#65)

**Files:**
- Modify: `src/components/NavBar.tsx:48-57`
- Modify: `src/__tests__/components/NavBar.test.tsx`

**Step 1: Write the failing tests**

Add to `src/__tests__/components/NavBar.test.tsx`, inside the main `describe` block:

```tsx
  describe("avatar display", () => {
    it("shows avatar image when user has avatarUrl", () => {
      mockAuth = {
        user: {
          id: "1",
          displayName: "Test User",
          email: "t@t.com",
          emailVerified: true,
          trustTier: "NEW",
          avatarUrl: "https://example.com/avatar.jpg",
        },
        isAuthenticated: true,
        isLoading: false,
        logout: mockLogout,
      };
      render(<NavBar />);
      const avatar = screen.getByAltText("Test User's avatar");
      expect(avatar).toBeInTheDocument();
      expect(avatar).toHaveAttribute("src", "https://example.com/avatar.jpg");
      expect(avatar.closest("a")).toHaveAttribute("href", "/profile");
    });

    it("shows display name text when user has no avatarUrl", () => {
      mockAuth = {
        user: {
          id: "1",
          displayName: "Test User",
          email: "t@t.com",
          emailVerified: true,
          trustTier: "NEW",
        },
        isAuthenticated: true,
        isLoading: false,
        logout: mockLogout,
      };
      render(<NavBar />);
      expect(screen.getByText("Test User")).toBeInTheDocument();
      expect(screen.queryByRole("img")).not.toBeInTheDocument();
    });
  });
```

**Step 2: Run tests to verify they fail**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest NavBar.test --verbose 2>&1 | tail -20
```

Expected: "shows avatar image" test fails (no img element rendered).

**Step 3: Implement the change**

In `src/components/NavBar.tsx`, replace the profile link section (around lines 48-57):

From:
```tsx
            <Link
              href="/profile"
              className={`text-sm transition-colors ${
                isHome
                  ? "text-white hover:text-gray-200"
                  : "text-gray-600 hover:text-blue-600"
              }`}
            >
              {user?.displayName}
            </Link>
```

To:
```tsx
            <Link href="/profile">
              {user?.avatarUrl ? (
                <img
                  src={user.avatarUrl}
                  alt={`${user.displayName}'s avatar`}
                  className={`w-7 h-7 rounded-full object-cover ${
                    isHome ? "ring-2 ring-white/50" : ""
                  }`}
                />
              ) : (
                <span
                  className={`text-sm transition-colors ${
                    isHome
                      ? "text-white hover:text-gray-200"
                      : "text-gray-600 hover:text-blue-600"
                  }`}
                >
                  {user?.displayName}
                </span>
              )}
            </Link>
```

**Step 4: Update the existing test that checks for display name link**

The existing test "shows Submit Video and user info when authenticated" (line 57-77) checks for `screen.getByText("Test User")`. The mock user in that test has no `avatarUrl`, so the display name text still renders. This test should still pass without changes. But the test at line 126 ("uses white text for authenticated links on home page") also checks for `screen.getByText("Test User")` — verify it still works (the mock user has no `avatarUrl`).

**Step 5: Run tests to verify they pass**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest NavBar.test --verbose 2>&1 | tail -25
```

Expected: All NavBar tests pass.

**Step 6: Commit**

```bash
git add src/components/NavBar.tsx src/__tests__/components/NavBar.test.tsx
git commit -m "feat: display user avatar in header when available (#65)"
```

---

### Task 7: View public profile link (#66)

**Files:**
- Modify: `src/app/profile/page.tsx:65-92`
- Modify: `src/__tests__/app/profile/ProfilePage.test.tsx`

**Step 1: Write the failing test**

Add to `src/__tests__/app/profile/ProfilePage.test.tsx`, inside the main `describe` block:

```tsx
  it("renders View public profile link", () => {
    render(<ProfilePage />);
    const link = screen.getByText("View public profile");
    expect(link.closest("a")).toHaveAttribute("href", "/users/1");
  });
```

**Step 2: Run test to verify it fails**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest ProfilePage.test --verbose 2>&1 | tail -15
```

Expected: FAIL — "View public profile" text not found.

**Step 3: Implement the change**

In `src/app/profile/page.tsx`, add the link after the email line (after line 89):

After:
```tsx
              <p className="text-sm text-gray-500">{user.email}</p>
```

Add:
```tsx
              <Link
                href={`/users/${user.id}`}
                className="text-sm text-blue-600 hover:underline"
              >
                View public profile
              </Link>
```

Note: `Link` is already imported at the top of this file (line 4).

**Step 4: Run tests to verify they pass**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest ProfilePage.test --verbose 2>&1 | tail -15
```

Expected: All ProfilePage tests pass.

**Step 5: Commit**

```bash
git add src/app/profile/page.tsx src/__tests__/app/profile/ProfilePage.test.tsx
git commit -m "feat: add View public profile link to profile page (#66)"
```

---

### Task 8: Map search bar translucency + home button (#21)

**Files:**
- Modify: `src/components/map/MapContainer.tsx:120-122,204-206`

This is the most visual change. The search bar overlay areas in both mobile and desktop layouts need to be wrapped in a group container with translucency, and a home button added.

**Step 1: Implement translucency wrapper and home button in MapContainer**

In `src/components/map/MapContainer.tsx`, add the import at the top:

```tsx
import { DEFAULT_VIEWPORT } from "@/config/mapbox";
```

(`DEFAULT_VIEWPORT` is not currently imported — `MAP_CONFIG` is imported but from the same file.)

Add `setViewport` and `setSelectedVideoId` to the destructured `useMap()` call (line 22). Currently it destructures `bounds`, `viewport`, `filters`, `selectedVideoId`. Change to:

```tsx
  const { bounds, viewport, filters, selectedVideoId, setViewport, setSelectedVideoId } = useMap();
```

**Mobile layout** (around line 120-122): Replace:

```tsx
        {/* Search bar overlay */}
        <div className="absolute top-4 left-4 right-4 z-30">
          <LocationSearch onLocationSelect={handleLocationSelect} />
        </div>
```

With:

```tsx
        {/* Search bar overlay */}
        <div className="absolute top-4 left-4 right-4 z-30 flex items-start gap-2 opacity-60 hover:opacity-100 focus-within:opacity-100 transition-opacity duration-300">
          <div className="flex-1">
            <LocationSearch onLocationSelect={handleLocationSelect} />
          </div>
          <button
            onClick={() => {
              setViewport(DEFAULT_VIEWPORT);
              setSelectedVideoId(null);
            }}
            className="flex-shrink-0 w-9 h-9 bg-white rounded-md shadow flex items-center justify-center text-gray-600 hover:text-gray-900 hover:bg-gray-50"
            aria-label="Reset map view"
            title="Reset map view"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
              <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
            </svg>
          </button>
        </div>
```

**Desktop layout** (around line 204-206): Replace:

```tsx
        {/* Search bar overlay */}
        <div className="absolute top-4 left-4 right-4 max-w-md z-10">
          <LocationSearch onLocationSelect={handleLocationSelect} />
        </div>
```

With:

```tsx
        {/* Search bar overlay */}
        <div className="absolute top-4 left-4 right-4 max-w-md z-10 flex items-start gap-2 opacity-60 hover:opacity-100 focus-within:opacity-100 transition-opacity duration-300">
          <div className="flex-1">
            <LocationSearch onLocationSelect={handleLocationSelect} />
          </div>
          <button
            onClick={() => {
              setViewport(DEFAULT_VIEWPORT);
              setSelectedVideoId(null);
            }}
            className="flex-shrink-0 w-9 h-9 bg-white rounded-md shadow flex items-center justify-center text-gray-600 hover:text-gray-900 hover:bg-gray-50"
            aria-label="Reset map view"
            title="Reset map view"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
              <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z" />
            </svg>
          </button>
        </div>
```

**Step 2: Run all tests**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest --passWithNoTests 2>&1 | tail -5
```

Expected: All tests pass (MapContainer doesn't have direct unit tests — it's tested via E2E).

**Step 3: Commit**

```bash
git add src/components/map/MapContainer.tsx
git commit -m "feat: add translucent search bar and home button to map (#21)"
```

---

### Task 9: Run full test suite and format

**Step 1: Run all tests**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx jest --passWithNoTests 2>&1 | tail -10
```

Expected: All tests pass.

**Step 2: Run Prettier**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx prettier --write .
```

**Step 3: Run lint**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && npx next lint
```

**Step 4: Commit any formatting changes**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app && git add -A && git diff --cached --stat
```

If there are changes:

```bash
git commit -m "style: apply Prettier formatting"
```

---

### Task 10: Deploy and verify

**Step 1: Deploy web-app**

```bash
cd /c/code/AccountabilityAtlas && ./scripts/deploy.sh --skip-checks web-app
```

(Skip checks since we already ran them in Task 9.)

**Step 2: Run integration tests**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-integration-tests && npm run test:all
```

**Step 3: Manual verification checklist**

- [ ] Home page tab: "AccountabilityAtlas"
- [ ] Map page tab: "Map | AccountabilityAtlas"
- [ ] Login page tab: "Sign In | AccountabilityAtlas"
- [ ] Video detail tab: shows video title
- [ ] User profile tab: shows user display name
- [ ] Map search bar is translucent, full opacity on hover/focus
- [ ] Home button resets map to continental US view
- [ ] Sign In from /map → login → redirects back to /map
- [ ] Avatar shows in header (if user has one)
- [ ] "View public profile" link works on /profile
