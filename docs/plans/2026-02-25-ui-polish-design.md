# UI Polish Design

Batch of five independent web-app-only UI improvements, shipped on a single `feature/ui-polish` branch.

Closes: AcctAtlas-web-app#21, #35, #41, #65, #66

## 1. Page Titles (#35)

Every route gets a unique browser tab title.

**Root layout** (`src/app/layout.tsx`): Change `title` to a template:

```ts
title: {
  template: "%s | AccountabilityAtlas",
  default: "AccountabilityAtlas",
}
```

**Static routes** — add a server-component `layout.tsx` in each route directory exporting `metadata`:

| Route directory | Title |
|-----------------|-------|
| `app/login/` | `Sign In` |
| `app/register/` | `Register` |
| `app/map/` | `Map` |
| `app/videos/new/` | `Submit Video` |
| `app/profile/` | `My Profile` |

**Dynamic routes** — restructure to support `generateMetadata`:

- `app/videos/[id]/page.tsx`: Convert to server component exporting `generateMetadata`. Fetch `/videos/{id}` via plain `fetch()` (not the axios client). Extract video `title`. Move existing client component to `VideoDetailClient.tsx`.
- `app/users/[id]/page.tsx`: Same pattern. Fetch `/users/{id}`, use `displayName`. Move client component to `PublicProfileClient.tsx`.

Fallback title if fetch fails: `"Video"` / `"User Profile"`.

## 2. Map Search Bar Translucency + Home Button (#21)

**Translucency**: In `MapContainer.tsx`, wrap `LocationSearch` and the new home button in a Tailwind `group` container with:

```
opacity-60 hover:opacity-100 focus-within:opacity-100 transition-opacity duration-300
```

Any interaction (hover, focus on search input, focus on home button) brings the whole group to full opacity.

**Home button**: Placed to the right of the search bar in a flex row. Inline SVG home icon. On click:

1. `setViewport(DEFAULT_VIEWPORT)` — reset to continental US view
2. `setSelectedVideoId(null)` — clear video selection

Applied identically to both mobile and desktop layouts in `MapContainer.tsx`.

Keyboard accessible: native `<button>` element.

## 3. Login Redirect (#41)

The login page already supports `?redirect=` and navigates there after login. The only missing piece: the NavBar "Sign In" link doesn't pass the current path.

**Change in `NavBar.tsx`**: Update Sign In link to:

```tsx
<Link href={pathname === "/" ? "/login" : `/login?redirect=${encodeURIComponent(pathname)}`}>
```

Skip passing `redirect=/` since that's the default behavior.

## 4. Avatar in Header (#65)

**Change in `NavBar.tsx`**: When `user?.avatarUrl` exists, display a small circular avatar image instead of the display name text.

- Use plain `<img>` (not Next.js `<Image>`) since avatars come from various external domains (Gravatar, YouTube)
- Size: `w-7 h-7 rounded-full object-cover`
- On home page (transparent nav): add `ring-2 ring-white/50` for visibility
- Wrapped in `<Link href="/profile">`
- Fallback: display name text (current behavior)

## 5. View Public Profile Link (#66)

**Change in `src/app/profile/page.tsx`**: Add a link near the top of the profile page:

```tsx
<Link href={`/users/${user.id}`} className="text-sm text-blue-600 hover:underline">
  View public profile
</Link>
```

Placed below the avatar/name section, before the edit forms.

## Files Changed

| File | Changes |
|------|---------|
| `src/app/layout.tsx` | Title template |
| `src/app/login/layout.tsx` | **New** — metadata export |
| `src/app/register/layout.tsx` | **New** — metadata export |
| `src/app/map/layout.tsx` | **New** — metadata export |
| `src/app/videos/new/layout.tsx` | **New** — metadata export |
| `src/app/profile/layout.tsx` | **New** — metadata export |
| `src/app/videos/[id]/page.tsx` | Convert to server component with `generateMetadata` |
| `src/app/videos/[id]/VideoDetailClient.tsx` | **New** — extracted client component |
| `src/app/users/[id]/page.tsx` | Convert to server component with `generateMetadata` |
| `src/app/users/[id]/PublicProfileClient.tsx` | **New** — extracted client component |
| `src/components/NavBar.tsx` | Avatar display (#65), login redirect (#41) |
| `src/components/map/MapContainer.tsx` | Translucency wrapper + home button (#21) |
| `src/app/profile/page.tsx` | View public profile link (#66) |

## Testing

- Existing unit tests updated for refactored pages
- Manual verification of all page titles in browser tabs
- Manual verification of map translucency/home button behavior
- Manual verification of login redirect flow
- Integration tests via `npm run test:all`
