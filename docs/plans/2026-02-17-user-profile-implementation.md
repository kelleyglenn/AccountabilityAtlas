# User Profile Pages Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement profile management with self-edit, public profile, social links, privacy controls, avatar picker, and "My Submissions" with moderation statuses.

**Architecture:** Extend user-service with social links and privacy settings tables. Frontend makes two calls (user-service for profile, video-service for submissions). Video-service stores rejection reasons from moderation events.

**Tech Stack:** Java 21, Spring Boot 3.4.x, PostgreSQL (temporal tables), Next.js 14, Playwright, Gravatar, YouTube Data API

**Design doc:** `docs/plans/2026-02-17-user-profile-design.md`

**TDD approach:** Outside-in. Write tests E2E → API → service → unit. Implement unit → service → API → E2E. Commit tests to feature branches early; PRs created only after all tests pass.

---

## Phase 1: Write Outer Tests (E2E + API Integration)

These tests define "done" and won't pass until implementation is complete.

### Task 1: E2E tests — profile edit flow (integration-tests)

**Branch:** `feature/user-profile-e2e-tests` in AcctAtlas-integration-tests

**Files:**
- Create: `e2e/tests/profile/profile-edit.spec.ts`
- Create: `e2e/fixtures/test-users.ts`
- Modify: `e2e/fixtures/seed-data.ts`

**Step 1: Create test user fixture**

```typescript
// e2e/fixtures/test-users.ts

/**
 * Helper to register and login a test user via API.
 * Returns access token for authenticated E2E actions.
 */
export async function createAndLoginTestUser(
  page: import('@playwright/test').Page,
  overrides?: { displayName?: string; email?: string }
): Promise<{ accessToken: string; email: string; displayName: string }> {
  const timestamp = Date.now();
  const email = overrides?.email ?? `e2e-user-${timestamp}@test.com`;
  const displayName = overrides?.displayName ?? `E2E User ${timestamp}`;
  const password = 'TestPassword123!';

  // Register via API
  const apiUrl = process.env.API_URL || 'http://localhost:8080/api/v1';
  const registerResponse = await fetch(`${apiUrl}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, displayName }),
  });
  const registerData = await registerResponse.json();

  return {
    accessToken: registerData.tokens.accessToken,
    email,
    displayName,
  };
}

/**
 * Login via browser UI. Sets session cookie/token.
 */
export async function loginViaUI(
  page: import('@playwright/test').Page,
  email: string,
  password: string
): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /sign in|log in/i }).click();
  await page.waitForURL(/\/(map|profile)/, { timeout: 10000 });
}
```

**Step 2: Write profile edit E2E tests**

```typescript
// e2e/tests/profile/profile-edit.spec.ts
import { test, expect } from '@playwright/test';
import { PAGE_LOAD_TIMEOUT, UI_INTERACTION_TIMEOUT } from '../../fixtures/test-constants';

test.describe('Profile Edit', () => {
  const timestamp = Date.now();
  const testEmail = `profile-test-${timestamp}@test.com`;
  const testPassword = 'TestPassword123!';
  const originalName = `Test User ${timestamp}`;

  test.beforeEach(async ({ page }) => {
    // Register user via API
    const apiUrl = process.env.API_URL || 'http://localhost:8080/api/v1';
    await fetch(`${apiUrl}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: testEmail,
        password: testPassword,
        displayName: originalName,
      }),
    });

    // Login via UI
    await page.goto('/login');
    await page.getByLabel('Email').fill(testEmail);
    await page.getByLabel('Password').fill(testPassword);
    await page.getByRole('button', { name: /sign in|log in/i }).click();
    await page.waitForURL(/\/(map|profile)/, { timeout: PAGE_LOAD_TIMEOUT });
  });

  test('profile page shows current user info', async ({ page }) => {
    await page.goto('/profile');
    await expect(page.getByText(originalName)).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });
    await expect(page.getByText(testEmail)).toBeVisible();
  });

  test('can edit display name and see update persist', async ({ page }) => {
    await page.goto('/profile');
    await expect(page.getByText(originalName)).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });

    // Click edit / fill new name
    const newName = `Updated Name ${timestamp}`;
    const displayNameInput = page.getByLabel(/display name/i);
    await displayNameInput.clear();
    await displayNameInput.fill(newName);
    await page.getByRole('button', { name: /save/i }).first().click();

    // Verify success feedback
    await expect(page.getByText(/saved|updated/i)).toBeVisible({ timeout: UI_INTERACTION_TIMEOUT });

    // Reload and verify persistence
    await page.reload();
    await expect(page.getByText(newName)).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });
  });

  test('can add social links', async ({ page }) => {
    await page.goto('/profile');
    await expect(page.getByText(originalName)).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });

    // Fill YouTube social link
    const youtubeInput = page.getByLabel(/youtube/i);
    await youtubeInput.fill('UCtest123');
    await page.getByRole('button', { name: /save/i }).last().click();

    // Verify persistence
    await page.reload();
    await expect(page.getByLabel(/youtube/i)).toHaveValue('UCtest123', { timeout: PAGE_LOAD_TIMEOUT });
  });

  test('can toggle privacy settings', async ({ page }) => {
    await page.goto('/profile');
    await expect(page.getByText(originalName)).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });

    // Find and toggle social links visibility
    const socialLinksToggle = page.getByLabel(/social links.*visible/i);
    await socialLinksToggle.click();

    // Verify it saves
    await page.getByRole('button', { name: /save/i }).click();
    await expect(page.getByText(/saved|updated/i)).toBeVisible({ timeout: UI_INTERACTION_TIMEOUT });
  });
});
```

**Step 3: Commit**

```bash
git add e2e/tests/profile/ e2e/fixtures/test-users.ts
git commit -m "test(e2e): add profile edit E2E tests (red)

These tests define acceptance criteria for the profile edit feature.
They will fail until backend and frontend are implemented."
```

---

### Task 2: E2E tests — public profile and my submissions (integration-tests)

**Files:**
- Create: `e2e/tests/profile/public-profile.spec.ts`
- Create: `e2e/tests/profile/my-submissions.spec.ts`

**Step 1: Write public profile E2E tests**

```typescript
// e2e/tests/profile/public-profile.spec.ts
import { test, expect } from '@playwright/test';
import { PAGE_LOAD_TIMEOUT } from '../../fixtures/test-constants';
import { SEED_VIDEOS } from '../../fixtures/seed-data';

test.describe('Public Profile', () => {
  // Seed user ID from dev seed data (submitter of all seed videos)
  const seedUserId = '00000000-0000-0000-0000-000000000003';

  test('public profile shows display name and avatar', async ({ page }) => {
    await page.goto(`/users/${seedUserId}`);
    // Should show display name (from seed data)
    await expect(page.getByRole('heading')).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });
    // Should show member since
    await expect(page.getByText(/member since/i)).toBeVisible();
  });

  test('public profile shows approved video count', async ({ page }) => {
    await page.goto(`/users/${seedUserId}`);
    await expect(page.getByText(/\d+ approved video/i)).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });
  });

  test('returns 404 for non-existent user', async ({ page }) => {
    await page.goto('/users/00000000-0000-0000-0000-000000000099');
    await expect(page.getByText(/not found/i)).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });
  });
});
```

**Step 2: Write my submissions E2E tests**

```typescript
// e2e/tests/profile/my-submissions.spec.ts
import { test, expect } from '@playwright/test';
import { PAGE_LOAD_TIMEOUT } from '../../fixtures/test-constants';

test.describe('My Submissions', () => {
  test('profile page shows my submissions section', async ({ page }) => {
    // This test requires a logged-in user who has submitted videos
    // Setup: register, login, submit a video, then check profile
    // For now, define the test shape — implementation details depend on seed data
    await page.goto('/profile');
    // Should see submissions section (empty or populated)
    await expect(page.getByText(/my submissions/i)).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });
  });

  test('submissions show status badges', async ({ page }) => {
    await page.goto('/profile');
    // Each submission should have a visible status badge
    const submissions = page.locator('[data-testid="submission-item"]');
    // At minimum the section should exist
    await expect(page.getByText(/my submissions/i)).toBeVisible({ timeout: PAGE_LOAD_TIMEOUT });
  });
});
```

**Step 3: Commit**

```bash
git add e2e/tests/profile/
git commit -m "test(e2e): add public profile and my submissions E2E tests (red)"
```

---

### Task 3: API integration tests — PUT /users/me and GET /users/{id} (integration-tests)

**Files:**
- Modify: `api/tests/user-service.spec.ts`

**Step 1: Add profile update API tests**

Add the following test suite to the existing `user-service.spec.ts` after the "Trust Tier Management" describe block:

```typescript
test.describe('Profile Update (PUT /users/me)', () => {
  test('requires authentication', async ({ request }) => {
    const response = await request.put(`${API_URL}/users/me`, {
      data: { displayName: 'Updated Name' },
    });
    expect([401, 403]).toContain(response.status());
  });

  test('updates display name', async ({ request }) => {
    const user = await createTestUser(request);
    const newName = `Updated ${Date.now()}`;

    const response = await request.put(`${API_URL}/users/me`, {
      data: { displayName: newName },
      headers: authHeaders(user.accessToken),
    });

    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.displayName).toBe(newName);
  });

  test('updates avatar URL', async ({ request }) => {
    const user = await createTestUser(request);

    const response = await request.put(`${API_URL}/users/me`, {
      data: { avatarUrl: 'https://gravatar.com/avatar/test123' },
      headers: authHeaders(user.accessToken),
    });

    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.avatarUrl).toBe('https://gravatar.com/avatar/test123');
  });

  test('supports partial updates (preserves other fields)', async ({ request }) => {
    const user = await createTestUser(request);

    const response = await request.put(`${API_URL}/users/me`, {
      data: { displayName: 'Partial Update' },
      headers: authHeaders(user.accessToken),
    });

    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.displayName).toBe('Partial Update');
    expect(body.email).toBe(user.email); // Unchanged
  });

  test('validates display name minimum length', async ({ request }) => {
    const user = await createTestUser(request);

    const response = await request.put(`${API_URL}/users/me`, {
      data: { displayName: 'X' }, // Too short (min 2)
      headers: authHeaders(user.accessToken),
    });

    expect(response.status()).toBe(400);
  });

  test('updates social links', async ({ request }) => {
    const user = await createTestUser(request);

    const response = await request.put(`${API_URL}/users/me`, {
      data: {
        socialLinks: {
          youtube: 'UCtest123',
          instagram: 'testhandle',
        },
      },
      headers: authHeaders(user.accessToken),
    });

    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.socialLinks.youtube).toBe('UCtest123');
    expect(body.socialLinks.instagram).toBe('testhandle');
  });

  test('updates privacy settings', async ({ request }) => {
    const user = await createTestUser(request);

    const response = await request.put(`${API_URL}/users/me`, {
      data: {
        privacySettings: {
          socialLinksVisibility: 'PUBLIC',
          submissionsVisibility: 'REGISTERED',
        },
      },
      headers: authHeaders(user.accessToken),
    });

    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.privacySettings.socialLinksVisibility).toBe('PUBLIC');
    expect(body.privacySettings.submissionsVisibility).toBe('REGISTERED');
  });

  test('GET /users/me returns social links and privacy settings', async ({ request }) => {
    const user = await createTestUser(request);

    // Update social links first
    await request.put(`${API_URL}/users/me`, {
      data: { socialLinks: { youtube: 'UCtest456' } },
      headers: authHeaders(user.accessToken),
    });

    // GET should return them
    const response = await request.get(`${API_URL}/users/me`, {
      headers: authHeaders(user.accessToken),
    });

    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.socialLinks.youtube).toBe('UCtest456');
    expect(body.privacySettings).toBeDefined();
  });
});

test.describe('Public Profile (GET /users/{id})', () => {
  test('returns public profile fields', async ({ request }) => {
    const user = await createTestUser(request);

    const response = await request.get(`${API_URL}/users/${user.userId}`);

    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.displayName).toBeDefined();
    expect(body.memberSince).toBeDefined();
    // Should NOT expose private fields
    expect(body.email).toBeUndefined();
    expect(body.trustTier).toBeUndefined();
    expect(body.privacySettings).toBeUndefined();
  });

  test('hides social links from anonymous when visibility is REGISTERED', async ({ request }) => {
    const user = await createTestUser(request);

    // Set social links with REGISTERED visibility (default)
    await request.put(`${API_URL}/users/me`, {
      data: { socialLinks: { youtube: 'UCprivate' } },
      headers: authHeaders(user.accessToken),
    });

    // Anonymous request should not see social links
    const response = await request.get(`${API_URL}/users/${user.userId}`);
    const body = await response.json();
    expect(body.socialLinks).toBeUndefined();
  });

  test('shows social links to registered user when visibility is REGISTERED', async ({ request }) => {
    const user1 = await createTestUser(request);
    const user2 = await createTestUser(request);

    // User1 sets social links (default REGISTERED visibility)
    await request.put(`${API_URL}/users/me`, {
      data: { socialLinks: { youtube: 'UCvisible' } },
      headers: authHeaders(user1.accessToken),
    });

    // User2 (registered) should see them
    const response = await request.get(`${API_URL}/users/${user1.userId}`, {
      headers: authHeaders(user2.accessToken),
    });
    const body = await response.json();
    expect(body.socialLinks.youtube).toBe('UCvisible');
  });

  test('returns 404 for non-existent user', async ({ request }) => {
    const response = await request.get(`${API_URL}/users/00000000-0000-0000-0000-000000000099`);
    expect(response.status()).toBe(404);
  });
});
```

**Step 2: Commit**

```bash
git add api/tests/user-service.spec.ts
git commit -m "test(api): add profile update and public profile API tests (red)"
```

---

### Task 4: API integration tests — video rejection reason (integration-tests)

**Files:**
- Modify: `api/tests/video-service.spec.ts`

**Step 1: Add rejection reason test**

Add to video-service API tests:

```typescript
test.describe('Video Rejection Reason', () => {
  test('owner can see rejection reason on their rejected videos', async ({ request }) => {
    // This test requires a video that has been rejected with a reason
    // The rejection flow goes through moderation-service → SQS → video-service
    // For API tests, we verify the field exists in the response shape
    const user = await createTestUser(request);

    // Submit a video
    const submitResponse = await request.post(`${API_URL}/videos`, {
      data: {
        youtubeUrl: 'https://youtube.com/watch?v=dQw4w9WgXcQ',
        amendments: ['FIRST'],
        locations: [{ lat: 37.7749, lng: -122.4194 }],
      },
      headers: authHeaders(user.accessToken),
    });

    expect(submitResponse.status()).toBe(201);
    const video = await submitResponse.json();

    // Fetch own videos — rejection reason field should exist in schema
    const listResponse = await request.get(`${API_URL}/videos?submittedBy=me`, {
      headers: authHeaders(user.accessToken),
    });

    expect(listResponse.ok()).toBeTruthy();
    const listBody = await listResponse.json();
    // Video should be PENDING (no rejection reason yet)
    const found = listBody.data.find((v: any) => v.id === video.id);
    expect(found).toBeDefined();
    expect(found.status).toBe('PENDING');
    // rejectionReason should be null for non-rejected videos
    expect(found.rejectionReason ?? null).toBeNull();
  });
});
```

**Step 2: Commit**

```bash
git add api/tests/video-service.spec.ts
git commit -m "test(api): add video rejection reason API test (red)"
```

---

## Phase 2: Write Service & Unit Tests, Then Implement (Inside-Out)

### Task 5: video-service — add rejection_reason column and store from event

**Branch:** `feature/video-rejection-reason` in AcctAtlas-video-service

**Files:**
- Create: `src/main/resources/db/migration/V6__add_rejection_reason.sql`
- Modify: `src/main/java/com/.../domain/Video.java`
- Modify: `src/main/java/com/.../event/ModerationEventHandler.java`
- Modify: `src/main/java/com/.../web/VideoController.java` (response mapping)
- Modify: `docs/api-specification.yaml`
- Modify: `docs/database-schema.md`
- Tests: `src/test/java/com/.../event/ModerationEventHandlerTest.java`
- Tests: `src/test/java/com/.../service/VideoServiceTest.java`

**Step 1: Write failing test for rejection reason storage**

Add to `ModerationEventHandlerTest.java`:

```java
@Test
void handleVideoRejected_storesRejectionReason() {
  // Arrange
  UUID videoId = UUID.randomUUID();
  String reason = "Duplicate submission";
  var event = new VideoRejectedEvent(videoId, UUID.randomUUID(), reason, Instant.now());
  var video = new Video();
  video.setId(videoId);
  video.setStatus(VideoStatus.REJECTED);
  video.setRejectionReason(reason);
  when(videoService.updateVideoStatus(videoId, VideoStatus.REJECTED, reason)).thenReturn(video);

  // Act
  handler.handleVideoRejected(event);

  // Assert
  verify(videoService).updateVideoStatus(videoId, VideoStatus.REJECTED, reason);
}
```

**Step 2: Run test — expect FAIL** (method signature doesn't exist yet)

```bash
./gradlew test --tests "*ModerationEventHandlerTest.handleVideoRejected_storesRejectionReason"
```

**Step 3: Create migration**

```sql
-- V6__add_rejection_reason.sql
ALTER TABLE videos.videos
ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(500);

COMMENT ON COLUMN videos.videos.rejection_reason IS
    'Reason provided by moderator when video is rejected';
```

**Step 4: Add field to Video entity**

In `Video.java`, add:

```java
@Column(name = "rejection_reason", length = 500)
private String rejectionReason;
```

**Step 5: Update VideoService.updateVideoStatus to accept reason**

Add overloaded method or modify existing:

```java
@Transactional
public Video updateVideoStatus(UUID videoId, VideoStatus newStatus, String rejectionReason) {
  Video video = getVideoByIdOrThrow(videoId);
  VideoStatus previousStatus = video.getStatus();
  video.setStatus(newStatus);
  if (rejectionReason != null) {
    video.setRejectionReason(rejectionReason);
  }
  Video saved = videoRepository.save(video);
  // ... existing event publishing logic
  return saved;
}
```

**Step 6: Update ModerationEventHandler to pass reason**

```java
public void handleVideoRejected(VideoRejectedEvent event) {
  videoService.updateVideoStatus(event.videoId(), VideoStatus.REJECTED, event.reason());
}
```

**Step 7: Update API spec and response mapping to include rejectionReason**

**Step 8: Run all tests — expect PASS**

```bash
./gradlew check
```

**Step 9: Commit**

```bash
git add -A
git commit -m "feat(video): store rejection reason from moderation events (#related-issue)"
```

---

### Task 6: user-service — database migrations for social links and privacy

**Branch:** `feature/user-profile-update` in AcctAtlas-user-service

**Files:**
- Create: `src/main/resources/db/migration/V8__add_social_links_and_privacy.sql`

**Step 1: Write migration**

```sql
-- V8__add_social_links_and_privacy.sql
-- Social links table (1:1 with users, temporal)

CREATE TABLE IF NOT EXISTS users.user_social_links (
    user_id UUID PRIMARY KEY REFERENCES users.users(id) ON DELETE CASCADE,
    youtube VARCHAR(100),
    facebook VARCHAR(100),
    instagram VARCHAR(50),
    tiktok VARCHAR(50),
    x_twitter VARCHAR(50),
    bluesky VARCHAR(100),
    sys_period tstzrange NOT NULL DEFAULT tstzrange(current_timestamp, null)
);

CREATE TABLE IF NOT EXISTS users.user_social_links_history (LIKE users.user_social_links);

CREATE TRIGGER user_social_links_versioning
    BEFORE INSERT OR UPDATE OR DELETE ON users.user_social_links
    FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'users.user_social_links_history', true);

-- Privacy settings table (1:1 with users, temporal)

CREATE TABLE IF NOT EXISTS users.user_privacy_settings (
    user_id UUID PRIMARY KEY REFERENCES users.users(id) ON DELETE CASCADE,
    social_links_visibility VARCHAR(20) NOT NULL DEFAULT 'REGISTERED',
    submissions_visibility VARCHAR(20) NOT NULL DEFAULT 'PUBLIC',
    sys_period tstzrange NOT NULL DEFAULT tstzrange(current_timestamp, null),
    CONSTRAINT valid_social_links_visibility CHECK (social_links_visibility IN ('PUBLIC', 'REGISTERED')),
    CONSTRAINT valid_submissions_visibility CHECK (submissions_visibility IN ('PUBLIC', 'REGISTERED'))
);

CREATE TABLE IF NOT EXISTS users.user_privacy_settings_history (LIKE users.user_privacy_settings);

CREATE TRIGGER user_privacy_settings_versioning
    BEFORE INSERT OR UPDATE OR DELETE ON users.user_privacy_settings
    FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'users.user_privacy_settings_history', true);

COMMENT ON TABLE users.user_social_links IS 'User social media profile links (1:1 with users)';
COMMENT ON TABLE users.user_privacy_settings IS 'Per-section privacy visibility settings (1:1 with users)';
```

**Step 2: Run migration locally**

```bash
./gradlew flywayMigrate
```

**Step 3: Commit**

```bash
git add src/main/resources/db/migration/V8__add_social_links_and_privacy.sql
git commit -m "feat(db): add social links and privacy settings tables"
```

---

### Task 7: user-service — domain entities for social links and privacy

**Files:**
- Create: `src/main/java/com/.../domain/UserSocialLinks.java`
- Create: `src/main/java/com/.../domain/UserPrivacySettings.java`
- Create: `src/main/java/com/.../domain/Visibility.java`
- Create: `src/main/java/com/.../repository/UserSocialLinksRepository.java`
- Create: `src/main/java/com/.../repository/UserPrivacySettingsRepository.java`
- Modify: `src/main/java/com/.../domain/User.java` — add relations

**Step 1: Write unit tests for entities**

```java
// UserSocialLinksTest.java
@Test
void defaults_allFieldsNull() {
  var links = new UserSocialLinks();
  assertThat(links.getYoutube()).isNull();
  assertThat(links.getFacebook()).isNull();
  assertThat(links.getInstagram()).isNull();
  assertThat(links.getTiktok()).isNull();
  assertThat(links.getXTwitter()).isNull();
  assertThat(links.getBluesky()).isNull();
}

// UserPrivacySettingsTest.java
@Test
void defaults_socialLinksRegistered_submissionsPublic() {
  var settings = new UserPrivacySettings();
  assertThat(settings.getSocialLinksVisibility()).isEqualTo(Visibility.REGISTERED);
  assertThat(settings.getSubmissionsVisibility()).isEqualTo(Visibility.PUBLIC);
}
```

**Step 2: Implement entities**

```java
// Visibility.java
public enum Visibility {
  PUBLIC,
  REGISTERED
}

// UserSocialLinks.java
@Entity
@Table(name = "user_social_links", schema = "users")
@Getter @Setter
public class UserSocialLinks {
  @Id
  @Column(name = "user_id")
  private UUID userId;

  @Column(length = 100)
  private String youtube;

  @Column(length = 100)
  private String facebook;

  @Column(length = 50)
  private String instagram;

  @Column(length = 50)
  private String tiktok;

  @Column(name = "x_twitter", length = 50)
  private String xTwitter;

  @Column(length = 100)
  private String bluesky;
}

// UserPrivacySettings.java
@Entity
@Table(name = "user_privacy_settings", schema = "users")
@Getter @Setter
public class UserPrivacySettings {
  @Id
  @Column(name = "user_id")
  private UUID userId;

  @Enumerated(EnumType.STRING)
  @Column(name = "social_links_visibility", nullable = false)
  private Visibility socialLinksVisibility = Visibility.REGISTERED;

  @Enumerated(EnumType.STRING)
  @Column(name = "submissions_visibility", nullable = false)
  private Visibility submissionsVisibility = Visibility.PUBLIC;
}
```

**Step 3: Run tests — expect PASS**

```bash
./gradlew test --tests "*UserSocialLinksTest*" --tests "*UserPrivacySettingsTest*"
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat(domain): add social links and privacy settings entities"
```

---

### Task 8: user-service — update OpenAPI spec and regenerate

**Files:**
- Modify: `docs/api-specification.yaml` — add socialLinks, privacySettings, avatarSources to response schemas; add UpdateUserRequest fields
- Modify: `docs/database-schema.md` — document new tables

**Step 1: Update OpenAPI spec**

Add to `UpdateUserRequest` schema:
- `socialLinks` object with youtube, facebook, instagram, tiktok, xTwitter, bluesky fields
- `privacySettings` object with socialLinksVisibility, submissionsVisibility enums

Add to `User` response schema:
- `socialLinks` (same shape)
- `privacySettings` (same shape)
- `avatarSources` object with gravatar, youtube optional URL fields

Add `PublicProfile` response schema for `GET /users/{id}`:
- displayName, avatarUrl, memberSince, approvedVideoCount, socialLinks (conditional)

**Step 2: Regenerate**

```bash
./gradlew openApiGenerate
```

**Step 3: Commit**

```bash
git add docs/api-specification.yaml docs/database-schema.md
git commit -m "feat(api): extend OpenAPI spec with social links, privacy, and public profile"
```

---

### Task 9: user-service — implement PUT /users/me with social links and privacy

**Files:**
- Modify: `src/main/java/com/.../service/UserService.java`
- Modify: `src/main/java/com/.../web/UsersController.java`
- Tests: `src/test/java/com/.../service/UserServiceTest.java`
- Tests: `src/test/java/com/.../web/UsersControllerTest.java`

**Step 1: Write failing service tests**

```java
// In UserServiceTest.java
@Test
void updateProfile_updatesDisplayName() {
  // Arrange
  var user = createTestUser();
  when(userRepository.findById(user.getId())).thenReturn(Optional.of(user));
  when(userRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
  var request = new UpdateUserRequest();
  request.setDisplayName("New Name");

  // Act
  User updated = userService.updateProfile(user.getId(), request);

  // Assert
  assertThat(updated.getDisplayName()).isEqualTo("New Name");
}

@Test
void updateProfile_updatesSocialLinks() {
  // Arrange
  var user = createTestUser();
  when(userRepository.findById(user.getId())).thenReturn(Optional.of(user));
  when(userRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
  when(socialLinksRepository.findById(user.getId())).thenReturn(Optional.empty());
  when(socialLinksRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

  var socialLinks = new SocialLinksRequest();
  socialLinks.setYoutube("UCtest");
  var request = new UpdateUserRequest();
  request.setSocialLinks(socialLinks);

  // Act
  userService.updateProfile(user.getId(), request);

  // Assert
  verify(socialLinksRepository).save(argThat(sl -> "UCtest".equals(sl.getYoutube())));
}

@Test
void updateProfile_updatesPrivacySettings() {
  // Arrange - similar pattern
  // Assert: privacy settings saved with correct visibility
}

@Test
void updateProfile_partialUpdate_preservesExistingFields() {
  // Arrange: user has displayName "Original"
  // Act: update only avatarUrl
  // Assert: displayName still "Original"
}
```

**Step 2: Write failing controller tests**

```java
// In UsersControllerTest.java
@Test
void updateCurrentUser_returns200_withUpdatedProfile() throws Exception {
  // Arrange
  var updated = createTestUser();
  updated.setDisplayName("Updated");
  when(userService.updateProfile(eq(userId), any())).thenReturn(updated);

  // Act & Assert
  mockMvc.perform(put("/users/me")
      .contentType(MediaType.APPLICATION_JSON)
      .content("{\"displayName\": \"Updated\"}")
      .with(jwt()))
    .andExpect(status().isOk())
    .andExpect(jsonPath("$.displayName").value("Updated"));
}

@Test
void updateCurrentUser_returns400_forShortDisplayName() throws Exception {
  mockMvc.perform(put("/users/me")
      .contentType(MediaType.APPLICATION_JSON)
      .content("{\"displayName\": \"X\"}")
      .with(jwt()))
    .andExpect(status().isBadRequest());
}
```

**Step 3: Implement service and controller**

Follow existing patterns in UserService.java and UsersController.java.

**Step 4: Run all tests**

```bash
./gradlew check
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(profile): implement PUT /users/me with social links and privacy (#24)"
```

---

### Task 10: user-service — implement GET /users/{id} public profile

**Files:**
- Modify: `src/main/java/com/.../service/UserService.java`
- Modify: `src/main/java/com/.../web/UsersController.java`
- Tests for service and controller

**Step 1: Write failing tests**

```java
// Service test
@Test
void getPublicProfile_returnsPublicFields_forAnonymousViewer() {
  // Assert: returns displayName, avatarUrl, memberSince
  // Assert: does NOT return email, trustTier
}

@Test
void getPublicProfile_hidesSocialLinks_whenVisibilityRegistered_andViewerAnonymous() {
  // Assert: socialLinks is null
}

@Test
void getPublicProfile_showsSocialLinks_whenVisibilityRegistered_andViewerRegistered() {
  // Assert: socialLinks populated
}

@Test
void getPublicProfile_showsSocialLinks_whenVisibilityPublic_andViewerAnonymous() {
  // Assert: socialLinks populated
}
```

**Step 2: Implement and verify**

**Step 3: Commit**

```bash
git add -A
git commit -m "feat(profile): implement GET /users/{id} public profile with privacy filtering"
```

---

### Task 11: user-service — avatar resolution (Gravatar + YouTube)

**Files:**
- Create: `src/main/java/com/.../service/AvatarService.java`
- Tests: `src/test/java/com/.../service/AvatarServiceTest.java`

**Step 1: Write failing tests**

```java
@Test
void resolveGravatar_returnsUrlFromEmailHash() {
  String url = avatarService.resolveGravatarUrl("test@example.com");
  // Gravatar URL uses MD5 hash of lowercase trimmed email
  assertThat(url).startsWith("https://gravatar.com/avatar/");
  assertThat(url).contains("d=404"); // 404 if no gravatar
}

@Test
void resolveYoutubeThumbnail_returnsChannelThumbnail() {
  when(youtubeClient.getChannelThumbnail("UCtest")).thenReturn("https://yt3.ggpht.com/...");
  String url = avatarService.resolveYoutubeThumbnail("UCtest");
  assertThat(url).isEqualTo("https://yt3.ggpht.com/...");
}

@Test
void getAvatarSources_returnsGravatarAlways() {
  var sources = avatarService.getAvatarSources("test@example.com", null);
  assertThat(sources.getGravatar()).isNotNull();
  assertThat(sources.getYoutube()).isNull(); // No YouTube link
}

@Test
void getAvatarSources_returnsYoutube_whenSocialLinkPresent() {
  var socialLinks = new UserSocialLinks();
  socialLinks.setYoutube("UCtest");
  when(youtubeClient.getChannelThumbnail("UCtest")).thenReturn("https://yt3.ggpht.com/...");

  var sources = avatarService.getAvatarSources("test@example.com", socialLinks);
  assertThat(sources.getGravatar()).isNotNull();
  assertThat(sources.getYoutube()).isEqualTo("https://yt3.ggpht.com/...");
}
```

**Step 2: Implement AvatarService**

**Step 3: Wire into GET /users/me response**

**Step 4: Run tests, commit**

```bash
git add -A
git commit -m "feat(avatar): add Gravatar and YouTube avatar resolution"
```

---

## Phase 3: Frontend Implementation

### Task 12: web-app — API client and types

**Branch:** `feature/user-profile-pages` in AcctAtlas-web-app

**Files:**
- Modify: `src/types/api.ts`
- Modify: `src/lib/api/users.ts`

**Step 1: Add types**

```typescript
// In api.ts
export interface SocialLinks {
  youtube?: string;
  facebook?: string;
  instagram?: string;
  tiktok?: string;
  xTwitter?: string;
  bluesky?: string;
}

export interface PrivacySettings {
  socialLinksVisibility: 'PUBLIC' | 'REGISTERED';
  submissionsVisibility: 'PUBLIC' | 'REGISTERED';
}

export interface AvatarSources {
  gravatar?: string;
  youtube?: string;
}

export interface UpdateProfileRequest {
  displayName?: string;
  avatarUrl?: string;
  socialLinks?: SocialLinks;
  privacySettings?: PrivacySettings;
}

export interface PublicProfile {
  displayName: string;
  avatarUrl?: string;
  memberSince: string;
  approvedVideoCount: number;
  socialLinks?: SocialLinks;
  submissionsVisible: boolean;
}
```

**Step 2: Add API functions**

```typescript
// In users.ts
export async function updateProfile(data: UpdateProfileRequest): Promise<User> {
  const response = await apiClient.put<User>('/users/me', data);
  return response.data;
}

export async function getPublicProfile(userId: string): Promise<PublicProfile> {
  const response = await apiClient.get<PublicProfile>(`/users/${userId}`);
  return response.data;
}
```

**Step 3: Commit**

---

### Task 13: web-app — profile edit page

**Files:**
- Rewrite: `src/app/profile/page.tsx`
- Create: `src/components/profile/ProfileInfoForm.tsx`
- Create: `src/components/profile/SocialLinksForm.tsx`
- Create: `src/components/profile/PrivacySettingsForm.tsx`
- Create: `src/components/profile/AvatarPicker.tsx`
- Create: `src/components/profile/MySubmissions.tsx`

Follow existing component patterns from VideoSubmitForm.tsx. Each form section handles its own save operation to `PUT /users/me`.

**Step 1: Write component tests for each form**

**Step 2: Implement components**

**Step 3: Wire into profile page**

**Step 4: Run `npm run check`, commit**

---

### Task 14: web-app — public profile page

**Files:**
- Create: `src/app/users/[id]/page.tsx`

Server component that fetches `GET /users/{id}` and renders the minimal card.

**Step 1: Write test**

**Step 2: Implement page**

**Step 3: Add link from video detail page (submitter name → `/users/{id}`)**

**Step 4: Run `npm run check`, commit**

---

### Task 15: web-app — My Submissions section

**Files:**
- Create: `src/components/profile/MySubmissions.tsx`
- Modify: `src/lib/api/videos.ts` — add `getMyVideos()` function

Fetches `GET /videos?submittedBy=me` and renders list with status badges and rejection reasons.

**Step 1: Write component test**

**Step 2: Implement component**

**Step 3: Run `npm run check`, commit**

---

## Phase 4: Infrastructure and Integration

### Task 16: docker-compose — add YOUTUBE_API_KEY for user-service

**Branch:** `feature/user-profile-config` in AccountabilityAtlas

**Files:**
- Modify: `docker-compose.yml` (top-level repo)

Add `YOUTUBE_API_KEY: ${YOUTUBE_API_KEY}` to user-service environment.

**Commit to feature branch, PR to master.**

---

### Task 17: Deploy and run full test suite

**Step 1: Deploy affected services**

```bash
./scripts/deploy.sh user-service video-service web-app
```

**Step 2: Run full integration test suite**

```bash
cd AcctAtlas-integration-tests
npm run test:all
```

**Step 3: Fix any failures, re-deploy, re-test**

---

### Task 18: Create PRs

Create PRs in each repo only after all tests pass:

| Repo | Branch | Issues |
|------|--------|--------|
| AcctAtlas-video-service | `feature/video-rejection-reason` | — |
| AcctAtlas-user-service | `feature/user-profile-update` | Closes #24 |
| AcctAtlas-web-app | `feature/user-profile-pages` | — |
| AcctAtlas-integration-tests | `feature/user-profile-e2e-tests` | — |
| AccountabilityAtlas | `feature/user-profile-config` | Refs #18, #68 |

---

## Task Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 1: Outer Tests | 1–4 | E2E + API integration tests (red) |
| 2: Backend | 5–11 | video-service + user-service (TDD per task) |
| 3: Frontend | 12–15 | web-app types, pages, components |
| 4: Integration | 16–18 | Infrastructure, deploy, verify, PRs |
