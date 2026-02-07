# Integration Test Tagging Design

## Overview

When all integration tests pass in CI, automatically tag all participating repos with a matching tag to mark a known-good combination of commits. This enables:

1. **Deployment confidence** - Know which service versions are safe to deploy together
2. **Debugging regressions** - Compare against last known-good state when tests fail
3. **Release documentation** - Track what was tested for compliance/audit purposes
4. **Rollback reference** - Quickly identify a known-good combination to revert to

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tag format | `integration-tested-YYYYMMDD-<run_id>` | Human-readable date, unique run ID, sorts chronologically |
| Tagged repos | integration-tests, user-service, api-gateway, web-app | Deployable services + test repo; excludes infra-only top-level repo |
| Tag type | Annotated | Message contains run URL for traceability |
| Trigger | All test jobs pass | Future-proof for adding API tests |
| Authentication | Fine-grained PAT | Scoped to just these 4 repos, simple to manage |
| Error handling | Retry + best effort | 3 retries, log failures, don't fail workflow |
| Workflow structure | Separate `tag-on-success` job | Clean separation, easy to add test jobs to `needs` array |

## Tag Format

```
integration-tested-YYYYMMDD-<run_id>
```

Example: `integration-tested-20260207-12345678`

- **YYYYMMDD**: Date of the test run (compact, sorts well)
- **run_id**: GitHub Actions run ID (clickable in GitHub UI, guarantees uniqueness)

## Workflow Structure

```
┌─────────────┐     ┌─────────────┐
│   e2e job   │     │  api job    │  (future)
└──────┬──────┘     └──────┬──────┘
       │                   │
       └───────┬───────────┘
               ▼
      ┌─────────────────┐
      │ tag-on-success  │
      │  (needs: both)  │
      └─────────────────┘
```

## Implementation

### 1. E2E Job Outputs

Add `id` to checkout steps and expose commit SHAs as job outputs:

```yaml
jobs:
  e2e:
    runs-on: ubuntu-latest
    outputs:
      integration-tests-sha: ${{ github.sha }}
      user-service-sha: ${{ steps.checkout-user.outputs.commit }}
      api-gateway-sha: ${{ steps.checkout-gateway.outputs.commit }}
      web-app-sha: ${{ steps.checkout-webapp.outputs.commit }}

    steps:
      - name: Checkout integration tests
        uses: actions/checkout@v4

      - name: Checkout user-service
        id: checkout-user
        uses: actions/checkout@v4
        with:
          repository: kelleyglenn/AcctAtlas-user-service
          path: infra/AcctAtlas-user-service

      - name: Checkout api-gateway
        id: checkout-gateway
        uses: actions/checkout@v4
        with:
          repository: kelleyglenn/AcctAtlas-api-gateway
          path: infra/AcctAtlas-api-gateway

      - name: Checkout web-app
        id: checkout-webapp
        uses: actions/checkout@v4
        with:
          repository: kelleyglenn/AcctAtlas-web-app
          path: infra/AcctAtlas-web-app

      # ... rest of existing steps
```

### 2. Tag-on-Success Job

```yaml
  tag-on-success:
    runs-on: ubuntu-latest
    needs: [e2e]  # Will become [e2e, api] when API tests are added
    if: success()

    steps:
      - name: Log tested commits
        run: |
          echo "## Tested Commits" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Repo | Commit |" >> $GITHUB_STEP_SUMMARY
          echo "|------|--------|" >> $GITHUB_STEP_SUMMARY
          echo "| integration-tests | [${INTEGRATION_SHA:0:7}](https://github.com/kelleyglenn/AcctAtlas-integration-tests/commit/$INTEGRATION_SHA) |" >> $GITHUB_STEP_SUMMARY
          echo "| user-service | [${USER_SHA:0:7}](https://github.com/kelleyglenn/AcctAtlas-user-service/commit/$USER_SHA) |" >> $GITHUB_STEP_SUMMARY
          echo "| api-gateway | [${GATEWAY_SHA:0:7}](https://github.com/kelleyglenn/AcctAtlas-api-gateway/commit/$GATEWAY_SHA) |" >> $GITHUB_STEP_SUMMARY
          echo "| web-app | [${WEBAPP_SHA:0:7}](https://github.com/kelleyglenn/AcctAtlas-web-app/commit/$WEBAPP_SHA) |" >> $GITHUB_STEP_SUMMARY
        env:
          INTEGRATION_SHA: ${{ needs.e2e.outputs.integration-tests-sha }}
          USER_SHA: ${{ needs.e2e.outputs.user-service-sha }}
          GATEWAY_SHA: ${{ needs.e2e.outputs.api-gateway-sha }}
          WEBAPP_SHA: ${{ needs.e2e.outputs.web-app-sha }}

      - name: Create tags
        env:
          GH_TOKEN: ${{ secrets.INTEGRATION_TEST_PAT }}
          INTEGRATION_SHA: ${{ needs.e2e.outputs.integration-tests-sha }}
          USER_SHA: ${{ needs.e2e.outputs.user-service-sha }}
          GATEWAY_SHA: ${{ needs.e2e.outputs.api-gateway-sha }}
          WEBAPP_SHA: ${{ needs.e2e.outputs.web-app-sha }}
        run: |
          TAG_NAME="integration-tested-$(date +%Y%m%d)-${{ github.run_id }}"
          RUN_URL="${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"

          echo "Creating tag: $TAG_NAME"
          echo "Run URL: $RUN_URL"

          tag_repo() {
            local repo=$1
            local sha=$2
            local retries=3

            echo "Tagging $repo at $sha..."

            for ((i=1; i<=retries; i++)); do
              # Create annotated tag object
              TAG_SHA=$(gh api "repos/kelleyglenn/${repo}/git/tags" \
                -f tag="$TAG_NAME" \
                -f message="Integration tests passed. Run: $RUN_URL" \
                -f object="$sha" \
                -f type="commit" \
                --jq '.sha' 2>/dev/null) || true

              if [ -n "$TAG_SHA" ]; then
                # Create ref pointing to the tag object
                if gh api "repos/kelleyglenn/${repo}/git/refs" \
                  -f ref="refs/tags/$TAG_NAME" \
                  -f sha="$TAG_SHA" >/dev/null 2>&1; then
                  echo "Successfully tagged $repo"
                  return 0
                fi
              fi

              echo "Attempt $i/$retries failed for $repo, retrying in 2s..."
              sleep 2
            done

            echo "::warning::Failed to tag $repo after $retries attempts"
            return 0  # Don't fail the job
          }

          tag_repo "AcctAtlas-integration-tests" "$INTEGRATION_SHA"
          tag_repo "AcctAtlas-user-service" "$USER_SHA"
          tag_repo "AcctAtlas-api-gateway" "$GATEWAY_SHA"
          tag_repo "AcctAtlas-web-app" "$WEBAPP_SHA"

          echo "" >> $GITHUB_STEP_SUMMARY
          echo "## Tag Created" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "\`$TAG_NAME\`" >> $GITHUB_STEP_SUMMARY
```

## Setup Required

### 1. Create Fine-Grained PAT

1. Go to GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens
2. Create new token:
   - **Name:** `integration-test-tagging`
   - **Expiration:** 1 year (set calendar reminder to rotate)
   - **Repository access:** Select repositories:
     - `AcctAtlas-integration-tests`
     - `AcctAtlas-user-service`
     - `AcctAtlas-api-gateway`
     - `AcctAtlas-web-app`
   - **Permissions:** Contents: Read and write

### 2. Add Repository Secret

1. Go to `AcctAtlas-integration-tests` repo settings
2. Settings > Secrets and variables > Actions
3. New repository secret:
   - **Name:** `INTEGRATION_TEST_PAT`
   - **Value:** The PAT from step 1

## Documentation Update

Add section to `docs/11-IntegrationTesting.md` after "CI Behavior":

```markdown
## Integration Test Tagging

When all integration tests pass, the workflow automatically tags all participating
repos with matching tags for traceability.

### Tag Format

`integration-tested-YYYYMMDD-<run_id>`

Example: `integration-tested-20260207-12345678`

### Tagged Repos

- `AcctAtlas-integration-tests`
- `AcctAtlas-user-service`
- `AcctAtlas-api-gateway`
- `AcctAtlas-web-app`

### Usage

**Find last tested version of a service:**
```bash
git describe --tags --match "integration-tested-*"
# Output: integration-tested-20260207-12345678-3-gabcd123
# (3 commits ahead of last tested version)
```

**List all integration-tested tags:**
```bash
git tag -l "integration-tested-*"
```

**View tag details (includes link to CI run):**
```bash
git tag -n1 integration-tested-20260207-12345678
```
```

## Deliverables

1. **Update `.github/workflows/e2e.yml`** in `AcctAtlas-integration-tests`:
   - Add `id` to checkout steps
   - Add `outputs` block to `e2e` job
   - Add `tag-on-success` job

2. **Create PAT and add secret** (manual setup)

3. **Update `docs/11-IntegrationTesting.md`** in `AccountabilityAtlas` repo

## Future-Proofing

When API tests are added:
1. Add `api` job to workflow
2. Change `tag-on-success` to `needs: [e2e, api]`
3. If API tests check out additional repos, add their SHAs to outputs and tagging
