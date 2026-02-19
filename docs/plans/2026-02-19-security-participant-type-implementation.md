# Add SECURITY Participant Type — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `SECURITY` as a 5th participant type across all services, update seed data to include both `SECURITY` and `CITIZEN`, and clean up a dead interface in the web-app.

**Architecture:** This is a cross-cutting enum addition touching 6 repos. Each repo gets its own GitHub issue, feature branch, and PR. The video-service needs a Flyway migration to update the DB CHECK constraint. The search-service has no DB constraint to update. All other changes are code/config/docs.

**Tech Stack:** Java 21 / Spring Boot (video-service, search-service, moderation-service), Next.js / TypeScript (web-app), Playwright / TypeScript (integration-tests), Markdown (top-level docs)

---

## Task 1: video-service — Enum, API Spec, Migration, Seed Data, Docs

**Issue:** Create in `kelleyglenn/AcctAtlas-video-service` referencing top-level issue #46

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/videoservice/domain/Participant.java:3-8`
- Modify: `docs/api-specification.yaml:499` (Participant schema enum)
- Create: `src/main/resources/db/migration/V5__add_security_participant.sql`
- Modify: `src/main/resources/db/devdata/R__dev_seed_videos.sql:90-115`
- Modify: `docs/technical.md:13,98`

**Step 1: Add SECURITY to Java enum**

In `src/main/java/com/accountabilityatlas/videoservice/domain/Participant.java`, change:
```java
public enum Participant {
  POLICE,
  GOVERNMENT,
  BUSINESS,
  CITIZEN
}
```
To:
```java
public enum Participant {
  POLICE,
  GOVERNMENT,
  BUSINESS,
  CITIZEN,
  SECURITY
}
```

**Step 2: Update API specification**

In `docs/api-specification.yaml`, find the `Participant` schema (line 498-500) and change:
```yaml
    Participant:
      type: string
      enum: [POLICE, GOVERNMENT, BUSINESS, CITIZEN]
```
To:
```yaml
    Participant:
      type: string
      enum: [POLICE, GOVERNMENT, BUSINESS, CITIZEN, SECURITY]
```

**Step 3: Create Flyway migration**

Create `src/main/resources/db/migration/V5__add_security_participant.sql`:
```sql
-- Add SECURITY to the valid_participant CHECK constraint
ALTER TABLE videos.video_participants
    DROP CONSTRAINT valid_participant,
    ADD CONSTRAINT valid_participant CHECK (
        participant IN ('POLICE', 'GOVERNMENT', 'BUSINESS', 'CITIZEN', 'SECURITY')
    );
```

Note: The migration is V5 (not V3) because V3 and V4 already exist.

**Step 4: Update dev seed data**

In `src/main/resources/db/devdata/R__dev_seed_videos.sql`, add SECURITY to Video 4 (Utica MI) and CITIZEN to Video 5 (Pocahontas). Change lines 99-102 from:
```sql
    -- Video 4: Utica MI - POLICE
    ('10000000-0000-0000-0000-000000000004', 'POLICE'),
    -- Video 5: Pocahontas - GOVERNMENT
    ('10000000-0000-0000-0000-000000000005', 'GOVERNMENT'),
```
To:
```sql
    -- Video 4: Utica MI - POLICE, SECURITY
    ('10000000-0000-0000-0000-000000000004', 'POLICE'),
    ('10000000-0000-0000-0000-000000000004', 'SECURITY'),
    -- Video 5: Pocahontas - GOVERNMENT, CITIZEN
    ('10000000-0000-0000-0000-000000000005', 'GOVERNMENT'),
    ('10000000-0000-0000-0000-000000000005', 'CITIZEN'),
```

**Step 5: Update technical.md**

In `docs/technical.md`:

Line 13 — change:
```
- Participant tagging (police, government, business, citizen)
```
To:
```
- Participant tagging (police, government, business, citizen, security)
```

Line 98 — change:
```
enum Participant { POLICE, GOVERNMENT, BUSINESS, CITIZEN }
```
To:
```
enum Participant { POLICE, GOVERNMENT, BUSINESS, CITIZEN, SECURITY }
```

**Step 6: Run quality checks**

Run: `./gradlew check`
Expected: BUILD SUCCESSFUL (all existing tests pass, new enum value doesn't break anything)

**Step 7: Commit**

```bash
git add src/main/java/com/accountabilityatlas/videoservice/domain/Participant.java \
  docs/api-specification.yaml \
  src/main/resources/db/migration/V5__add_security_participant.sql \
  src/main/resources/db/devdata/R__dev_seed_videos.sql \
  docs/technical.md
git commit -m "feat: add SECURITY participant type (#46)"
```

---

## Task 2: search-service — Enum, API Spec, Seed Data, Docs

**Issue:** Create in `kelleyglenn/AcctAtlas-search-service` referencing top-level issue #46

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/searchservice/domain/Participant.java:3-8`
- Modify: `docs/api-specification.yaml:70,206,271` (3 inline enum occurrences)
- Modify: `docs/api-specification.yaml:349-352` (facet example)
- Modify: `src/main/resources/db/devdata/R__dev_seed_search_videos.sql:40,48`
- Modify: `docs/technical.md:137,158`

**Step 1: Add SECURITY to Java enum**

In `src/main/java/com/accountabilityatlas/searchservice/domain/Participant.java`, change:
```java
public enum Participant {
  POLICE,
  GOVERNMENT,
  BUSINESS,
  CITIZEN
}
```
To:
```java
public enum Participant {
  POLICE,
  GOVERNMENT,
  BUSINESS,
  CITIZEN,
  SECURITY
}
```

**Step 2: Update API specification (3 inline enums + facet example)**

In `docs/api-specification.yaml`, find and update ALL 3 occurrences of the inline enum. Each looks like:
```yaml
          enum: [POLICE, GOVERNMENT, BUSINESS, CITIZEN]
```
Change to:
```yaml
          enum: [POLICE, GOVERNMENT, BUSINESS, CITIZEN, SECURITY]
```

Locations (approximate lines):
- Line 70: `GET /search` `participants` param items
- Line 206: `GET /search/facets` `participants` param items
- Line 271: `VideoSearchResult.participants` array items

Also update the `SearchFacets` example (around lines 349-352). Change:
```yaml
              POLICE: 2000
              GOVERNMENT: 800
              CITIZEN: 1500
              BUSINESS: 200
```
To:
```yaml
              POLICE: 2000
              GOVERNMENT: 800
              CITIZEN: 1500
              BUSINESS: 200
              SECURITY: 150
```

**Step 3: Update dev seed data**

In `src/main/resources/db/devdata/R__dev_seed_search_videos.sql`:

Video 4 (line 40) — change:
```sql
     ARRAY['FIRST', 'FOURTH']::VARCHAR[], ARRAY['POLICE']::VARCHAR[],
```
To:
```sql
     ARRAY['FIRST', 'FOURTH']::VARCHAR[], ARRAY['POLICE', 'SECURITY']::VARCHAR[],
```

Video 5 (line 48) — change:
```sql
     ARRAY['FIRST']::VARCHAR[], ARRAY['GOVERNMENT']::VARCHAR[],
```
To:
```sql
     ARRAY['FIRST']::VARCHAR[], ARRAY['GOVERNMENT', 'CITIZEN']::VARCHAR[],
```

**Step 4: Update technical.md**

In `docs/technical.md`:

Line 137 — change:
```
| participants | String[] | Filter by participants (e.g., POLICE, CITIZEN) |
```
To:
```
| participants | String[] | Filter by participants (e.g., POLICE, SECURITY) |
```

Line 158 — change:
```
    "participants": ["POLICE", "CITIZEN"],
```
To:
```
    "participants": ["POLICE", "SECURITY"],
```

**Step 5: Run quality checks**

Run: `./gradlew check`
Expected: BUILD SUCCESSFUL

**Step 6: Commit**

```bash
git add src/main/java/com/accountabilityatlas/searchservice/domain/Participant.java \
  docs/api-specification.yaml \
  src/main/resources/db/devdata/R__dev_seed_search_videos.sql \
  docs/technical.md
git commit -m "feat: add SECURITY participant type (#46)"
```

---

## Task 3: moderation-service — API Spec Only

**Issue:** Create in `kelleyglenn/AcctAtlas-moderation-service` referencing top-level issue #46

**Files:**
- Modify: `docs/api-specification.yaml:860` (inline enum)
- Modify: `docs/api-specification.yaml:869` (example)

**Step 1: Update API specification**

In `docs/api-specification.yaml`, find the `UpdateVideoRequest.participants` inline enum (around line 860):
```yaml
           enum: [POLICE, GOVERNMENT, BUSINESS, CITIZEN]
```
Change to:
```yaml
           enum: [POLICE, GOVERNMENT, BUSINESS, CITIZEN, SECURITY]
```

Also update the example (around line 869):
```yaml
         participants: ["POLICE", "CITIZEN"]
```
To:
```yaml
         participants: ["POLICE", "SECURITY"]
```

**Step 2: Run quality checks**

Run: `./gradlew check`
Expected: BUILD SUCCESSFUL (generated code rebuilds with new enum value)

**Step 3: Commit**

```bash
git add docs/api-specification.yaml
git commit -m "feat: add SECURITY participant type (#46)"
```

---

## Task 4: web-app — Type Options, Dead Interface Removal, Docs

**Issue:** Create in `kelleyglenn/AcctAtlas-web-app` referencing top-level issue #46

**Files:**
- Modify: `src/types/map.ts:100,104-110,157-162`
- Modify: `docs/map-integration.md:256`

**Step 1: Add SECURITY to PARTICIPANT_TYPE_OPTIONS**

In `src/types/map.ts`, find `PARTICIPANT_TYPE_OPTIONS` (lines 157-162) and add SECURITY:
```typescript
export const PARTICIPANT_TYPE_OPTIONS = [
  { id: "POLICE", label: "Police" },
  { id: "GOVERNMENT", label: "Government" },
  { id: "BUSINESS", label: "Business" },
  { id: "CITIZEN", label: "Citizen" },
  { id: "SECURITY", label: "Security" },
];
```

**Step 2: Remove dead Participant interface and fix VideoDetails**

In `src/types/map.ts`:

Remove the `Participant` interface (lines 104-110):
```typescript
// Participant in a video
export interface Participant {
  id: string;
  name: string;
  role?: string;
  organizationType?: string;
}
```

Change `VideoDetails.participants` (line 100) from:
```typescript
  participants: Participant[];
```
To:
```typescript
  participants: string[];
```

This aligns `VideoDetails` with the actual API response shape (`string[]`, not `Participant[]`).

**Step 3: Update map-integration.md**

In `docs/map-integration.md`, find the filter values table (around line 256) and change:
```markdown
| Participants | `POLICE`, `GOVERNMENT`, `BUSINESS`, `CITIZEN`      |
```
To:
```markdown
| Participants | `POLICE`, `GOVERNMENT`, `BUSINESS`, `CITIZEN`, `SECURITY` |
```

**Step 4: Run build/lint**

Run: `npm run build`
Expected: Build succeeds with no type errors

Run: `npx prettier --write .`
Expected: Formatting applied

**Step 5: Commit**

```bash
git add src/types/map.ts docs/map-integration.md
git commit -m "feat: add SECURITY participant type, remove dead Participant interface (#46)"
```

---

## Task 5: Top-level Docs

**Files:**
- Modify: `docs/04-ServiceCatalog.md:171`
- Modify: `docs/05-DataArchitecture.md:207-209,349`

**Step 1: Update 04-ServiceCatalog.md**

Find the Video domain model (around line 171) and change:
```
├── participants: Set<Participant> (POLICE, GOVERNMENT, BUSINESS, CITIZEN)
```
To:
```
├── participants: Set<Participant> (POLICE, GOVERNMENT, BUSINESS, CITIZEN, SECURITY)
```

Find the search document example (around line 349) and change:
```json
"participants": ["POLICE", "CITIZEN"],
```
To:
```json
"participants": ["POLICE", "SECURITY"],
```

**Step 2: Update 05-DataArchitecture.md**

Find the CHECK constraint example (around lines 207-209) and change:
```sql
CONSTRAINT valid_participants CHECK (
    participants <@ ARRAY['POLICE', 'GOVERNMENT', 'BUSINESS', 'CITIZEN']::VARCHAR[]
)
```
To:
```sql
CONSTRAINT valid_participants CHECK (
    participants <@ ARRAY['POLICE', 'GOVERNMENT', 'BUSINESS', 'CITIZEN', 'SECURITY']::VARCHAR[]
)
```

Find the search document example (around line 349) and change:
```json
"participants": ["POLICE", "CITIZEN"],
```
To:
```json
"participants": ["POLICE", "SECURITY"],
```

**Step 3: Commit**

```bash
git add docs/04-ServiceCatalog.md docs/05-DataArchitecture.md
git commit -m "docs: add SECURITY participant type to architecture docs (#46)"
```

---

## Task 6: Deploy and Verify

This task deploys all affected services and runs the full integration test suite.

**Step 1: Deploy affected services**

```bash
./scripts/deploy.sh video-service search-service moderation-service web-app
```

Expected: All services rebuild, redeploy, and pass health checks.

**Step 2: Run full integration test suite**

```bash
cd AcctAtlas-integration-tests
npm run test:all
```

Expected: All API and E2E tests pass. The new SECURITY participant in seed data should be filterable.

---

## Task 7: integration-tests — Seed Data and SECURITY Filter Test

**Issue:** Create in `kelleyglenn/AcctAtlas-integration-tests` referencing top-level issue #46

**Important:** Do NOT create a PR for this repo until service PRs (Tasks 1-4) are merged.

**Files:**
- Modify: `e2e/fixtures/seed-data.ts:25,40,43`
- Modify: `api/tests/search-service.spec.ts` (add test near line 63)

**Step 1: Update seed data fixtures**

In `e2e/fixtures/seed-data.ts`:

Update `OAKLAND_MULTI_AMENDMENT` (Video 2, around line 25) — this is a California video that doesn't conflict with the video-service seed data changes to Video 4/5:

No, actually the e2e seed data must match the actual dev seed data. Update these to match:

Video 4 (Utica MI) is not in the e2e seed data, so no changes needed there. Video 5 (Pocahontas/Silverthorne) — `SILVERTHORNE_GOVERNMENT` (lines 38-46) already has `participants: ['GOVERNMENT']`. We need to add CITIZEN to match the updated dev seed for Video 8...

Wait — let me reconsider. The e2e `seed-data.ts` references specific video IDs from the dev seed SQL. Video 4 (`...0004`) is NOT in `seed-data.ts`, and Video 5 (`...0005`) is NOT in `seed-data.ts` either. The seed data file only has Videos 1, 2, 6, and 8. So the e2e fixtures don't need to change for the seed data updates to Videos 4 and 5.

However, we should ADD a seed data entry for Video 4 (which now has SECURITY) so we can test the SECURITY filter:

Add to `SEED_VIDEOS` object:
```typescript
  UTICA_SECURITY: {
    id: '10000000-0000-0000-0000-000000000004',
    youtubeId: 'AJi0LgnoIJA',
    title: 'Utica Michigan Police Confrontation',
    amendments: ['FIRST', 'FOURTH'],
    participants: ['POLICE', 'SECURITY'],
    city: 'Fremont',
    state: 'CA',
  },
```

**Step 2: Add SECURITY filter test to search-service tests**

In `api/tests/search-service.spec.ts`, add a new test after the existing participant filter test (around line 63):

```typescript
  test('supports SECURITY participant filter', async ({ request }) => {
    const response = await request.get(`${API_URL}/search`, {
      params: {
        participants: 'SECURITY',
      },
    });

    expect(response.ok()).toBeTruthy();
    const body = await response.json();

    expect(body.results).toBeInstanceOf(Array);
    // All results should have SECURITY participant if any exist
    for (const result of body.results) {
      expect(result.participants).toContain('SECURITY');
    }
  });
```

**Step 3: Run tests to verify**

```bash
npm run test:all
```

Expected: All tests pass, including the new SECURITY filter test.

**Step 4: Commit**

```bash
git add e2e/fixtures/seed-data.ts api/tests/search-service.spec.ts
git commit -m "test: add SECURITY participant filter test (#46)"
```

---

## Execution Order

Tasks 1-4 (service repos) can be worked on in parallel — they are independent repos.

Task 5 (top-level docs) can be done alongside Tasks 1-4.

Task 6 (deploy and verify) must come after Tasks 1-4 are committed and pushed.

Task 7 (integration-tests) must come after Task 6 passes. Its PR should not be created until the service PRs from Tasks 1-4 are merged.

```
Tasks 1-5 (parallel) → Task 6 (deploy & verify) → Task 7 (integration-tests)
```
