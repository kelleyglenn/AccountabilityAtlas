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
