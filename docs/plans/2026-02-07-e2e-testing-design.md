# E2E Testing Design

## Overview

Add automated End-to-End (E2E) and functional testing to AccountabilityAtlas using Playwright. Tests run headless in CI and can also be run from a developer's terminal or IDE.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Test scope | Full stack E2E | Browser through API Gateway to services and database |
| Browsers | Chromium + Firefox + WebKit | Full cross-browser coverage including Safari-like behavior |
| Framework | Playwright | Native multi-browser support, semantic locators, auto-waiting, built-in API testing |
| Language | TypeScript | Matches web-app codebase, Playwright's primary language |
| Repository | `AcctAtlas-integration-tests` | Dedicated repo, independent of service repos |
| Structure | `e2e/` folder | Leaves room for `api/` folder for future API-level tests |
| CI/CD | GitHub Actions | Native to GitHub repos, excellent Playwright support |
| Stack orchestration | Hybrid | CI spins up via docker-compose; local assumes services running |
| Test data | Combination | Fresh DB per CI run + API seeding + SQL scripts for edge cases |

## Repository Structure

```
AcctAtlas-integration-tests/
├── e2e/
│   ├── tests/
│   │   ├── auth/
│   │   │   ├── login.spec.ts
│   │   │   ├── registration.spec.ts
│   │   │   └── oauth.spec.ts
│   │   ├── videos/
│   │   │   ├── submit-video.spec.ts
│   │   │   └── video-search.spec.ts
│   │   └── moderation/
│   │       └── approval-workflow.spec.ts
│   ├── fixtures/
│   │   └── test-data.ts
│   ├── seeds/
│   │   └── moderator-user.sql
│   └── playwright.config.ts
├── api/                        # Future: API-level integration tests
│   └── (placeholder)
├── package.json
├── tsconfig.json
└── README.md
```

## Playwright Configuration

**`e2e/playwright.config.ts`**:

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html'],
    ['github']
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
});
```

## GitHub Actions CI

**`.github/workflows/e2e.yml`**:

```yaml
name: E2E Tests

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]
  workflow_dispatch:

jobs:
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout integration tests
        uses: actions/checkout@v4

      - name: Checkout AccountabilityAtlas (docker-compose)
        uses: actions/checkout@v4
        with:
          repository: your-org/AccountabilityAtlas
          path: infra

      - name: Start services
        working-directory: infra
        run: docker-compose up -d --wait

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright browsers
        run: npx playwright install --with-deps

      - name: Run E2E tests
        run: npm run test:e2e
        env:
          BASE_URL: http://localhost:3000

      - name: Upload test report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: e2e/playwright-report/

      - name: Stop services
        if: always()
        working-directory: infra
        run: docker-compose down
```

## Test Data Management

### API-Based Seeding

**`e2e/fixtures/test-data.ts`**:

```typescript
import { APIRequestContext } from '@playwright/test';

const API_URL = process.env.API_URL || 'http://localhost:8080/api/v1';

export async function createTestUser(request: APIRequestContext, overrides = {}) {
  const userData = {
    email: `test-${Date.now()}@example.com`,
    password: 'TestPass123!',
    displayName: 'Test User',
    ...overrides,
  };

  const response = await request.post(`${API_URL}/auth/register`, {
    data: userData,
  });

  return { ...userData, response };
}

export async function loginAs(request: APIRequestContext, email: string, password: string) {
  const response = await request.post(`${API_URL}/auth/login`, {
    data: { email, password },
  });

  const { accessToken } = await response.json();
  return accessToken;
}
```

### SQL Seeds for Edge Cases

**`e2e/seeds/moderator-user.sql`**:

```sql
-- Creates a moderator user for testing moderation workflows
-- Password: ModeratorPass123! (bcrypt hash below)
INSERT INTO users (id, email, password_hash, display_name, trust_tier, created_at)
VALUES (
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  'moderator@test.local',
  '$2a$10$...',  -- bcrypt hash of ModeratorPass123!
  'Test Moderator',
  'MODERATOR',
  NOW()
) ON CONFLICT (email) DO NOTHING;
```

## Sample Test

**`e2e/tests/auth/login.spec.ts`**:

```typescript
import { test, expect } from '@playwright/test';
import { createTestUser } from '../../fixtures/test-data';

test.describe('Login', () => {
  test('user can log in with valid credentials', async ({ page, request }) => {
    // Arrange: create a user via API
    const user = await createTestUser(request);

    // Act: log in through the UI
    await page.goto('/login');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill(user.password);
    await page.getByRole('button', { name: 'Log in' }).click();

    // Assert: redirected to profile/home
    await expect(page).toHaveURL('/profile');
    await expect(page.getByText(user.displayName)).toBeVisible();
  });

  test('shows error for invalid credentials', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill('nobody@example.com');
    await page.getByLabel('Password').fill('WrongPassword');
    await page.getByRole('button', { name: 'Log in' }).click();

    await expect(page.getByRole('alert')).toContainText('Invalid email or password');
  });
});
```

## Documentation Updates

### New Document

Create `docs/11-IntegrationTesting.md` with:
- Overview of integration test repository
- Test types (E2E now, API planned)
- Technology stack
- How to run tests locally
- CI behavior

### Updates to Existing Docs

**`README.md`** (top-level):
- Add `AcctAtlas-integration-tests` to repository table

**`docs/README.md`**:
- Add link to `10-FutureFeatures.md` (existing, missing from TOC)
- Add link to `11-IntegrationTesting.md` (new)

## Deliverables

1. New repo `AcctAtlas-integration-tests` with Playwright E2E setup
2. GitHub Actions workflow for CI
3. Test fixtures and seed scripts
4. Sample login tests demonstrating patterns
5. New `docs/11-IntegrationTesting.md`
6. Updates to `README.md` and `docs/README.md`
