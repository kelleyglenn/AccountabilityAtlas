# E2E Testing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create the AcctAtlas-integration-tests repository with Playwright E2E testing infrastructure.

**Architecture:** New dedicated GitHub repo with Playwright (TypeScript) for E2E tests. Tests organized under `e2e/` folder with room for future `api/` tests. GitHub Actions runs tests against full stack via docker-compose.

**Tech Stack:** Playwright, TypeScript, Node.js 20, GitHub Actions

**Closes:** #3

---

## Task 1: Create GitHub Repository

**Purpose:** Create the AcctAtlas-integration-tests repo on GitHub and clone it locally.

**Step 1: Create the repository on GitHub**

Run:
```bash
gh repo create kelleyglenn/AcctAtlas-integration-tests --public --description "E2E and API integration tests for AccountabilityAtlas" --clone
```

Expected: Repository created and cloned to current directory.

**Step 2: Move into the repo directory**

Run:
```bash
cd AcctAtlas-integration-tests
```

**Step 3: Verify repo is ready**

Run:
```bash
git status
```

Expected: Clean working directory on main/master branch.

---

## Task 2: Initialize Node.js Project

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `.gitignore`

**Step 1: Initialize package.json**

Run:
```bash
npm init -y
```

**Step 2: Update package.json with proper configuration**

Replace `package.json` contents with:

```json
{
  "name": "acctatlas-integration-tests",
  "version": "1.0.0",
  "description": "E2E and API integration tests for AccountabilityAtlas",
  "scripts": {
    "test:e2e": "playwright test --config=e2e/playwright.config.ts",
    "test:e2e:headed": "playwright test --config=e2e/playwright.config.ts --headed",
    "test:e2e:ui": "playwright test --config=e2e/playwright.config.ts --ui",
    "test:e2e:debug": "playwright test --config=e2e/playwright.config.ts --debug",
    "report": "playwright show-report e2e/playwright-report"
  },
  "keywords": ["e2e", "playwright", "integration-tests"],
  "author": "",
  "license": "MIT",
  "devDependencies": {}
}
```

**Step 3: Install Playwright and TypeScript**

Run:
```bash
npm install -D @playwright/test typescript
```

**Step 4: Install Playwright browsers**

Run:
```bash
npx playwright install
```

**Step 5: Create tsconfig.json**

Create `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist",
    "rootDir": "."
  },
  "include": ["e2e/**/*", "api/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

**Step 6: Create .gitignore**

Create `.gitignore`:

```
node_modules/
dist/
e2e/playwright-report/
e2e/test-results/
api/playwright-report/
api/test-results/
.env
.env.local
```

**Step 7: Commit**

Run:
```bash
git add package.json package-lock.json tsconfig.json .gitignore
git commit -m "chore: initialize Node.js project with Playwright

- Add package.json with test scripts
- Add TypeScript configuration
- Add .gitignore for node_modules and test artifacts"
```

---

## Task 3: Create Playwright Configuration

**Files:**
- Create: `e2e/playwright.config.ts`

**Step 1: Create e2e directory structure**

Run:
```bash
mkdir -p e2e/tests/auth e2e/tests/videos e2e/tests/moderation e2e/fixtures e2e/seeds
```

**Step 2: Create Playwright config**

Create `e2e/playwright.config.ts`:

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['github'],
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

  outputDir: 'test-results',
});
```

**Step 3: Commit**

Run:
```bash
git add e2e/playwright.config.ts
git commit -m "feat: add Playwright configuration

- Configure Chromium, Firefox, and WebKit browsers
- Enable parallel test execution
- Set up HTML and GitHub reporters
- Configure retry behavior for CI"
```

---

## Task 4: Create Test Fixtures

**Files:**
- Create: `e2e/fixtures/test-data.ts`

**Step 1: Create test data fixtures**

Create `e2e/fixtures/test-data.ts`:

```typescript
import { APIRequestContext } from '@playwright/test';

const API_URL = process.env.API_URL || 'http://localhost:8080/api/v1';

export interface TestUser {
  email: string;
  password: string;
  displayName: string;
  response: Response;
}

export async function createTestUser(
  request: APIRequestContext,
  overrides: Partial<Omit<TestUser, 'response'>> = {}
): Promise<TestUser> {
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

export async function loginAs(
  request: APIRequestContext,
  email: string,
  password: string
): Promise<string> {
  const response = await request.post(`${API_URL}/auth/login`, {
    data: { email, password },
  });

  const body = await response.json();
  return body.accessToken;
}
```

**Step 2: Commit**

Run:
```bash
git add e2e/fixtures/test-data.ts
git commit -m "feat: add test data fixtures

- Add createTestUser helper for API-based user creation
- Add loginAs helper for authentication
- Use environment variable for API URL"
```

---

## Task 5: Create Sample Login Tests

**Files:**
- Create: `e2e/tests/auth/login.spec.ts`

**Step 1: Create login test file**

Create `e2e/tests/auth/login.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';
import { createTestUser } from '../../fixtures/test-data';

test.describe('Login', () => {
  test('user can log in with valid credentials', async ({ page, request }) => {
    // Arrange: create a user via API
    const user = await createTestUser(request);
    expect(user.response.ok()).toBeTruthy();

    // Act: log in through the UI
    await page.goto('/login');
    await page.getByLabel('Email').fill(user.email);
    await page.getByLabel('Password').fill(user.password);
    await page.getByRole('button', { name: /log in/i }).click();

    // Assert: redirected to profile/home
    await expect(page).toHaveURL('/profile');
    await expect(page.getByText(user.displayName)).toBeVisible();
  });

  test('shows error for invalid credentials', async ({ page }) => {
    // Act: attempt login with invalid credentials
    await page.goto('/login');
    await page.getByLabel('Email').fill('nobody@example.com');
    await page.getByLabel('Password').fill('WrongPassword');
    await page.getByRole('button', { name: /log in/i }).click();

    // Assert: error message displayed
    await expect(page.getByRole('alert')).toContainText(/invalid email or password/i);
  });

  test('login page is accessible', async ({ page }) => {
    await page.goto('/login');

    // Verify key elements are present
    await expect(page.getByLabel('Email')).toBeVisible();
    await expect(page.getByLabel('Password')).toBeVisible();
    await expect(page.getByRole('button', { name: /log in/i })).toBeVisible();
  });
});
```

**Step 2: Verify tests are recognized**

Run:
```bash
npx playwright test --list --config=e2e/playwright.config.ts
```

Expected: Lists 3 tests (3 tests × 3 browsers = 9 total).

**Step 3: Commit**

Run:
```bash
git add e2e/tests/auth/login.spec.ts
git commit -m "feat: add sample login E2E tests

- Test successful login with valid credentials
- Test error message for invalid credentials
- Test login page accessibility
- Use semantic locators (getByLabel, getByRole)"
```

---

## Task 6: Create SQL Seed Script

**Files:**
- Create: `e2e/seeds/moderator-user.sql`
- Create: `e2e/seeds/README.md`

**Step 1: Create moderator user seed**

Create `e2e/seeds/moderator-user.sql`:

```sql
-- Creates a moderator user for testing moderation workflows
-- Password: ModeratorPass123!
--
-- To generate a new bcrypt hash:
--   node -e "console.log(require('bcryptjs').hashSync('ModeratorPass123!', 10))"
--
-- Usage:
--   docker exec acctatlas-postgres psql -U postgres -d acctatlas -f /seeds/moderator-user.sql

INSERT INTO users (id, email, password_hash, display_name, trust_tier, created_at, updated_at)
VALUES (
  'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  'moderator@test.local',
  '$2a$10$N9qo8uLOickgx2ZMRZoMy.Mrq4H5VbMxTqVZPzq1BpKvhFqvD4u5G',
  'Test Moderator',
  'MODERATOR',
  NOW(),
  NOW()
) ON CONFLICT (email) DO NOTHING;
```

**Step 2: Create seeds README**

Create `e2e/seeds/README.md`:

```markdown
# Test Data Seeds

SQL scripts for creating test data that cannot be created via the public API.

## Available Seeds

| File | Purpose | Credentials |
|------|---------|-------------|
| `moderator-user.sql` | Creates a MODERATOR tier user | `moderator@test.local` / `ModeratorPass123!` |

## Usage

### Local Development

```bash
docker exec acctatlas-postgres psql -U postgres -d acctatlas -f /path/to/seed.sql
```

### CI

Seeds are mounted into the postgres container and run during test setup.

## Generating Password Hashes

To generate a bcrypt hash for a new password:

```bash
node -e "console.log(require('bcryptjs').hashSync('YourPassword123!', 10))"
```
```

**Step 3: Commit**

Run:
```bash
git add e2e/seeds/
git commit -m "feat: add SQL seed scripts for test data

- Add moderator user seed for moderation workflow tests
- Add README documenting seed usage and password generation"
```

---

## Task 7: Create GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/e2e.yml`

**Step 1: Create workflows directory**

Run:
```bash
mkdir -p .github/workflows
```

**Step 2: Create E2E workflow**

Create `.github/workflows/e2e.yml`:

```yaml
name: E2E Tests

on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]
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
          repository: kelleyglenn/AccountabilityAtlas
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
          API_URL: http://localhost:8080/api/v1

      - name: Upload test report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: e2e/playwright-report/
          retention-days: 14

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: e2e/test-results/
          retention-days: 14

      - name: Stop services
        if: always()
        working-directory: infra
        run: docker-compose down
```

**Step 3: Commit**

Run:
```bash
git add .github/workflows/e2e.yml
git commit -m "ci: add GitHub Actions workflow for E2E tests

- Run on push/PR to master/main
- Spin up full stack via docker-compose
- Test on all three browsers
- Upload test reports as artifacts"
```

---

## Task 8: Create Repository README

**Files:**
- Create: `README.md`

**Step 1: Create README**

Create `README.md`:

```markdown
# AcctAtlas Integration Tests

End-to-end and API integration tests for [AccountabilityAtlas](https://github.com/kelleyglenn/AccountabilityAtlas).

## Test Types

| Type | Location | Purpose | Status |
|------|----------|---------|--------|
| E2E | `e2e/` | Full browser-to-database user journeys | Active |
| API | `api/` | Service contract validation | Planned |

## Technology Stack

- **Framework:** [Playwright](https://playwright.dev/)
- **Language:** TypeScript
- **Browsers:** Chromium, Firefox, WebKit
- **CI:** GitHub Actions

## Prerequisites

- Node.js 20+
- Docker and Docker Compose (for local full-stack testing)
- Full stack running (see [AccountabilityAtlas](https://github.com/kelleyglenn/AccountabilityAtlas))

## Running Tests Locally

### 1. Start the full stack

From the AccountabilityAtlas root:

```bash
./scripts/dev-start.sh
# or
docker-compose up -d
```

### 2. Run E2E tests

```bash
npm run test:e2e              # Run all tests headless
npm run test:e2e:headed       # Run with browser visible
npm run test:e2e:ui           # Run with Playwright UI
npm run test:e2e:debug        # Run with debugger
```

### 3. View test report

```bash
npm run report
```

## Running Specific Tests

```bash
# Run tests in a specific file
npm run test:e2e -- e2e/tests/auth/login.spec.ts

# Run tests matching a pattern
npm run test:e2e -- --grep "valid credentials"

# Run on a specific browser
npm run test:e2e -- --project=chromium
```

## CI Behavior

Tests run automatically on:
- Push to `master`/`main`
- Pull requests to `master`/`main`
- Manual trigger via `workflow_dispatch`

The CI workflow:
1. Spins up the full stack via `docker-compose`
2. Runs tests on Chromium, Firefox, and WebKit
3. Uploads HTML report as artifact (retained 14 days)

## Project Structure

```
AcctAtlas-integration-tests/
├── e2e/
│   ├── tests/           # Test files organized by feature
│   │   ├── auth/        # Authentication tests
│   │   ├── videos/      # Video submission tests
│   │   └── moderation/  # Moderation workflow tests
│   ├── fixtures/        # Reusable test helpers
│   ├── seeds/           # SQL scripts for test data
│   └── playwright.config.ts
├── api/                 # Future: API-level tests
├── package.json
└── tsconfig.json
```

## Writing Tests

See the [Playwright documentation](https://playwright.dev/docs/writing-tests) for general guidance.

### Key patterns used in this project

**Semantic locators** (layout-resilient):
```typescript
await page.getByLabel('Email').fill('test@example.com');
await page.getByRole('button', { name: /log in/i }).click();
```

**API-based test setup**:
```typescript
import { createTestUser } from '../../fixtures/test-data';

test('example', async ({ page, request }) => {
  const user = await createTestUser(request);
  // ... test with the created user
});
```

**SQL seeds for edge cases**:
```typescript
// For states not creatable via API (e.g., moderator users)
// Run SQL seed before tests, then use known credentials
```
```

**Step 2: Commit**

Run:
```bash
git add README.md
git commit -m "docs: add repository README

- Document test types and technology stack
- Add local development instructions
- Document CI behavior
- Include project structure and patterns"
```

---

## Task 9: Create API Placeholder

**Files:**
- Create: `api/.gitkeep`
- Create: `api/README.md`

**Step 1: Create api directory with placeholder**

Create `api/.gitkeep` (empty file):

```
```

Create `api/README.md`:

```markdown
# API Integration Tests

API-level integration tests for validating service contracts.

**Status:** Planned

## Purpose

Test backend service interactions without a browser:
- Service-to-service contracts
- API response validation
- Error handling behavior

## Technology

Will use Playwright's [API testing](https://playwright.dev/docs/api-testing) capabilities.
```

**Step 2: Commit**

Run:
```bash
git add api/
git commit -m "chore: add api directory placeholder for future API tests"
```

---

## Task 10: Push to GitHub

**Step 1: Push all commits**

Run:
```bash
git push -u origin main
```

Or if the default branch is `master`:
```bash
git push -u origin master
```

**Step 2: Verify on GitHub**

Open: `https://github.com/kelleyglenn/AcctAtlas-integration-tests`

Verify:
- All files are present
- README renders correctly
- GitHub Actions workflow is visible under Actions tab

---

## Task 11: Update AccountabilityAtlas Documentation

**Working directory:** `C:\code\AccountabilityAtlas` (top-level repo)

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Create: `docs/11-IntegrationTesting.md`

**Step 1: Create integration testing documentation**

Create `docs/11-IntegrationTesting.md`:

```markdown
# Integration Testing

## Overview

End-to-end and API integration tests live in a dedicated repository:
[AcctAtlas-integration-tests](https://github.com/kelleyglenn/AcctAtlas-integration-tests)

## Test Types

| Type | Location | Purpose | Status |
|------|----------|---------|--------|
| E2E | `e2e/` | Full browser-to-database user journeys | Active |
| API | `api/` | Service contract validation | Planned |

## Technology Stack

- **Framework:** Playwright
- **Language:** TypeScript
- **Browsers:** Chromium, Firefox, WebKit
- **CI:** GitHub Actions

## Running Tests Locally

### Prerequisites

- Node.js 20+
- Full stack running (see main README)

### Steps

1. Start the full stack (from AccountabilityAtlas root):
   ```bash
   ./scripts/dev-start.sh
   ```

2. Clone and set up the test repo:
   ```bash
   git clone https://github.com/kelleyglenn/AcctAtlas-integration-tests.git
   cd AcctAtlas-integration-tests
   npm install
   npx playwright install
   ```

3. Run E2E tests:
   ```bash
   npm run test:e2e
   ```

4. Run in headed mode for debugging:
   ```bash
   npm run test:e2e:headed
   ```

5. View the test report:
   ```bash
   npm run report
   ```

## CI Behavior

- Runs on every PR to `master`
- Spins up full stack via docker-compose
- Tests all three browsers (Chromium, Firefox, WebKit)
- Uploads HTML report as artifact

## Test Data Management

### API-Based Seeding

Most test data is created via the public API:

```typescript
import { createTestUser } from '../../fixtures/test-data';

test('example', async ({ page, request }) => {
  const user = await createTestUser(request);
  // Test with the created user
});
```

### SQL Seeds

For states not creatable via API (e.g., moderator users):

```bash
docker exec acctatlas-postgres psql -U postgres -d acctatlas -f /path/to/seed.sql
```

See `e2e/seeds/` in the integration tests repo for available seeds.

## Writing Tests

### Semantic Locators

Use layout-resilient locators that won't break if UI shifts:

```typescript
// Good - semantic
await page.getByLabel('Email').fill('test@example.com');
await page.getByRole('button', { name: /log in/i }).click();
await expect(page.getByRole('alert')).toContainText('Error');

// Avoid - brittle
await page.locator('#email-input').fill('test@example.com');
await page.locator('button.submit-btn').click();
```

### Test Structure

Follow Arrange-Act-Assert pattern:

```typescript
test('user can log in', async ({ page, request }) => {
  // Arrange
  const user = await createTestUser(request);

  // Act
  await page.goto('/login');
  await page.getByLabel('Email').fill(user.email);
  await page.getByLabel('Password').fill(user.password);
  await page.getByRole('button', { name: /log in/i }).click();

  // Assert
  await expect(page).toHaveURL('/profile');
});
```
```

**Step 2: Update docs/README.md**

Add to the Documentation Index table (after row 09):

```markdown
| [10-FutureFeatures.md](10-FutureFeatures.md) | Future features roadmap and enhancements |
| [11-IntegrationTesting.md](11-IntegrationTesting.md) | E2E and API integration testing guide |
```

Also add to Related Repositories section:

```markdown
- [AcctAtlas-integration-tests](https://github.com/kelleyglenn/AcctAtlas-integration-tests) - E2E and API integration tests
```

**Step 3: Update README.md (top-level)**

In the Project Structure section, after `AcctAtlas-web-app/`, add a comment:

```markdown
# External repository:
# AcctAtlas-integration-tests/        # E2E and API integration tests (separate repo)
```

**Step 4: Commit documentation updates**

Run:
```bash
git add docs/11-IntegrationTesting.md docs/README.md README.md
git commit -m "docs: add integration testing documentation

- Create docs/11-IntegrationTesting.md with full testing guide
- Update docs/README.md with missing 10-FutureFeatures.md link
- Add AcctAtlas-integration-tests to related repositories

Closes #3"
```

**Step 5: Push to GitHub**

Run:
```bash
git push origin master
```

---

## Summary

After completing all tasks, you will have:

1. **New repository:** `AcctAtlas-integration-tests` with:
   - Playwright configured for Chromium, Firefox, WebKit
   - TypeScript project structure
   - Sample login tests demonstrating patterns
   - Test fixtures for API-based data setup
   - SQL seeds for edge cases
   - GitHub Actions CI workflow
   - Comprehensive README

2. **Updated documentation** in AccountabilityAtlas:
   - New `docs/11-IntegrationTesting.md`
   - Updated `docs/README.md` with missing links
   - Updated `README.md` with reference to test repo

3. **GitHub issue #3** closed automatically via commit message.
