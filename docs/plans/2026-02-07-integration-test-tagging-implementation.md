# Integration Test Tagging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically tag all participating repos when integration tests pass, enabling deployment confidence and traceability.

**Architecture:** Add job outputs to capture commit SHAs during checkout, then a separate `tag-on-success` job that creates matching annotated tags across all repos using the GitHub API.

**Tech Stack:** GitHub Actions, GitHub API (via `gh` CLI), fine-grained PAT for cross-repo access.

---

## Prerequisites (Manual - User Must Complete)

Before starting automated tasks, the user must:

### 1. Create Fine-Grained PAT

1. Go to https://github.com/settings/personal-access-tokens/new
2. Configure:
   - **Name:** `integration-test-tagging`
   - **Expiration:** 1 year
   - **Repository access:** Select repositories:
     - `AcctAtlas-integration-tests`
     - `AcctAtlas-user-service`
     - `AcctAtlas-api-gateway`
     - `AcctAtlas-web-app`
   - **Permissions:** Contents → Read and write
3. Copy the generated token

### 2. Add Repository Secret

1. Go to https://github.com/kelleyglenn/AcctAtlas-integration-tests/settings/secrets/actions
2. Click "New repository secret"
3. **Name:** `INTEGRATION_TEST_PAT`
4. **Value:** Paste the PAT from step 1
5. Click "Add secret"

---

## Task 1: Add IDs to Checkout Steps

**Repo:** `AcctAtlas-integration-tests`

**Files:**
- Modify: `.github/workflows/e2e.yml:25-41`

**Step 1: Create feature branch**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-integration-tests
git checkout master
git pull origin master
git checkout -b feature/integration-test-tagging
```

**Step 2: Add id to user-service checkout**

Change line 25-29 from:
```yaml
      - name: Checkout user-service
        uses: actions/checkout@v4
        with:
          repository: kelleyglenn/AcctAtlas-user-service
          path: infra/AcctAtlas-user-service
```

To:
```yaml
      - name: Checkout user-service
        id: checkout-user
        uses: actions/checkout@v4
        with:
          repository: kelleyglenn/AcctAtlas-user-service
          path: infra/AcctAtlas-user-service
```

**Step 3: Add id to api-gateway checkout**

Change lines 31-35 from:
```yaml
      - name: Checkout api-gateway
        uses: actions/checkout@v4
        with:
          repository: kelleyglenn/AcctAtlas-api-gateway
          path: infra/AcctAtlas-api-gateway
```

To:
```yaml
      - name: Checkout api-gateway
        id: checkout-gateway
        uses: actions/checkout@v4
        with:
          repository: kelleyglenn/AcctAtlas-api-gateway
          path: infra/AcctAtlas-api-gateway
```

**Step 4: Add id to web-app checkout**

Change lines 37-41 from:
```yaml
      - name: Checkout web-app
        uses: actions/checkout@v4
        with:
          repository: kelleyglenn/AcctAtlas-web-app
          path: infra/AcctAtlas-web-app
```

To:
```yaml
      - name: Checkout web-app
        id: checkout-webapp
        uses: actions/checkout@v4
        with:
          repository: kelleyglenn/AcctAtlas-web-app
          path: infra/AcctAtlas-web-app
```

**Step 5: Verify YAML syntax**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-integration-tests
python -c "import yaml; yaml.safe_load(open('.github/workflows/e2e.yml'))" && echo "YAML valid"
```

Expected: `YAML valid`

**Step 6: Commit**

```bash
git add .github/workflows/e2e.yml
git commit -m "ci: add ids to checkout steps for commit tracking"
```

---

## Task 2: Add Job Outputs

**Repo:** `AcctAtlas-integration-tests`

**Files:**
- Modify: `.github/workflows/e2e.yml:10-14`

**Step 1: Add outputs block after e2e job declaration**

After line 13 (`timeout-minutes: 30`), add the outputs block so lines 10-18 become:

```yaml
jobs:
  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    outputs:
      integration-tests-sha: ${{ github.sha }}
      user-service-sha: ${{ steps.checkout-user.outputs.commit }}
      api-gateway-sha: ${{ steps.checkout-gateway.outputs.commit }}
      web-app-sha: ${{ steps.checkout-webapp.outputs.commit }}

    steps:
```

**Step 2: Verify YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/e2e.yml'))" && echo "YAML valid"
```

Expected: `YAML valid`

**Step 3: Commit**

```bash
git add .github/workflows/e2e.yml
git commit -m "ci: expose commit SHAs as job outputs"
```

---

## Task 3: Add tag-on-success Job

**Repo:** `AcctAtlas-integration-tests`

**Files:**
- Modify: `.github/workflows/e2e.yml` (append to end)

**Step 1: Add tag-on-success job at end of file**

Append after the final line (currently line 102):

```yaml

  tag-on-success:
    runs-on: ubuntu-latest
    needs: [e2e]
    if: success() && github.event_name == 'push'

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
              TAG_SHA=$(gh api "repos/kelleyglenn/${repo}/git/tags" \
                -f tag="$TAG_NAME" \
                -f message="Integration tests passed. Run: $RUN_URL" \
                -f object="$sha" \
                -f type="commit" \
                --jq '.sha' 2>/dev/null) || true

              if [ -n "$TAG_SHA" ]; then
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
            return 0
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

**Step 2: Verify YAML syntax**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/e2e.yml'))" && echo "YAML valid"
```

Expected: `YAML valid`

**Step 3: Commit**

```bash
git add .github/workflows/e2e.yml
git commit -m "ci: add tag-on-success job to tag repos after tests pass"
```

---

## Task 4: Push and Create PR for Integration Tests

**Repo:** `AcctAtlas-integration-tests`

**Step 1: Push branch**

```bash
git push -u origin feature/integration-test-tagging
```

**Step 2: Create PR**

```bash
gh pr create --title "feat: tag repos when integration tests pass" --body "$(cat <<'EOF'
## Summary

- Add commit SHA outputs to e2e job
- Add tag-on-success job that creates matching tags across repos
- Tags format: `integration-tested-YYYYMMDD-<run_id>`

## Tagged Repos

- AcctAtlas-integration-tests
- AcctAtlas-user-service
- AcctAtlas-api-gateway
- AcctAtlas-web-app

## Prerequisites

Requires `INTEGRATION_TEST_PAT` secret to be configured with write access to all repos.

Closes #<issue-number-if-applicable>

---

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Step 3: Return to master**

```bash
git checkout master
```

---

## Task 5: Update Documentation

**Repo:** `AccountabilityAtlas` (top-level)

**Files:**
- Modify: `docs/11-IntegrationTesting.md:59` (after "CI Behavior" section)

**Step 1: Create feature branch**

```bash
cd /c/code/AccountabilityAtlas
git checkout master
git pull origin master
git checkout -b docs/integration-test-tagging
```

**Step 2: Add Integration Test Tagging section**

After line 64 (`- Uploads HTML report as artifact`), add:

```markdown

## Integration Test Tagging

When all integration tests pass on a push to `master`, the workflow automatically tags all participating repos with matching tags for traceability.

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

**Step 3: Commit**

```bash
git add docs/11-IntegrationTesting.md
git commit -m "docs: add integration test tagging documentation"
```

**Step 4: Push and create PR**

```bash
git push -u origin docs/integration-test-tagging
gh pr create --title "docs: add integration test tagging documentation" --body "$(cat <<'EOF'
## Summary

Documents the new integration test tagging feature that marks known-good commit combinations across repos.

Related: kelleyglenn/AcctAtlas-integration-tests#<pr-number>

---

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

**Step 5: Return to master**

```bash
git checkout master
```

---

## Verification

After both PRs are merged and the PAT secret is configured:

1. Push any change to `AcctAtlas-integration-tests` master branch
2. Wait for E2E tests to pass
3. Check GitHub Actions run - should show "Tested Commits" table and "Tag Created" in summary
4. Verify tags exist in each repo:

```bash
gh api repos/kelleyglenn/AcctAtlas-integration-tests/tags --jq '.[0].name'
gh api repos/kelleyglenn/AcctAtlas-user-service/tags --jq '.[0].name'
gh api repos/kelleyglenn/AcctAtlas-api-gateway/tags --jq '.[0].name'
gh api repos/kelleyglenn/AcctAtlas-web-app/tags --jq '.[0].name'
```

All should show the same `integration-tested-YYYYMMDD-<run_id>` tag name.
