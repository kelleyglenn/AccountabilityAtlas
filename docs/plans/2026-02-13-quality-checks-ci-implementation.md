# Quality Checks CI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `./gradlew check` CI to all 6 Java service repos, `npm run check` CI to web-app, and fix broken branch triggers in existing lint workflows.

**Architecture:** Each repo gets a standalone `check.yaml` workflow. Existing `lint.yaml` and `lint-workflows.yaml` have two bugs fixed: push trigger targets `main` (should be `master`), and actionlint glob matches `*.yml` (files use `.yaml`). All 7 repos are independent — can be done in parallel.

**Tech Stack:** GitHub Actions, Java 21 (Temurin), Gradle, Node 20, npm

**Design doc:** `docs/plans/2026-02-13-quality-checks-ci-design.md`

---

## Overview

There are 7 independent tasks — one per repo. Each task follows the same pattern:

**Java repos (Tasks 1-6):** create issue, create branch, add `check.yaml`, fix `lint.yaml` branch trigger, fix `lint-workflows.yaml` branch trigger + glob, commit, push, create PR.

**Web-app (Task 7):** create issue, create branch, add `check.yaml`, commit, push, create PR.

Since all 7 tasks are independent with no shared state, they can be dispatched as parallel subagents.

---

## Task 1: AcctAtlas-user-service

**Repo:** `C:\code\AccountabilityAtlas\AcctAtlas-user-service` (git repo: `kelleyglenn/AcctAtlas-user-service`)

**Files:**
- Create: `.github/workflows/check.yaml`
- Modify: `.github/workflows/lint.yaml` (line 6: `main` → `master`)
- Modify: `.github/workflows/lint-workflows.yaml` (line 6: `main` → `master`, line 19: `*.yml` → `*.yaml`)

**Step 1: Create GitHub issue**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-user-service
gh issue create --title "Add quality checks workflow" --body "Add \`./gradlew check\` GitHub Actions workflow. Fix branch triggers in existing lint workflows (\`main\` → \`master\`). Fix actionlint glob (\`*.yml\` → \`*.yaml\`). Part of AccountabilityAtlas#38."
```

**Step 2: Create feature branch**

```bash
git checkout master && git pull
git checkout -b feature/<issue#>-quality-checks
```

**Step 3: Create `.github/workflows/check.yaml`**

```yaml
name: Check

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '21'
      - name: Run checks
        run: ./gradlew check
```

**Step 4: Fix `.github/workflows/lint.yaml`**

Change line 6 from `- main` to `- master`.

**Step 5: Fix `.github/workflows/lint-workflows.yaml`**

Change line 6 from `- main` to `- master`.
Change line 19 from `files: ".github/workflows/*.yml"` to `files: ".github/workflows/*.yaml"`.

**Step 6: Commit and push**

```bash
git add .github/workflows/check.yaml .github/workflows/lint.yaml .github/workflows/lint-workflows.yaml
git commit -m "ci: add quality checks workflow (#<issue#>)"
git push -u origin feature/<issue#>-quality-checks
```

**Step 7: Create PR**

```bash
gh pr create --title "ci: add quality checks workflow" --body "$(cat <<'EOF'
## Summary
- Add `check.yaml` workflow that runs `./gradlew check` (spotless, tests, coverage) on PRs and master pushes
- Fix `lint.yaml` push trigger: `main` → `master`
- Fix `lint-workflows.yaml` push trigger: `main` → `master`
- Fix `lint-workflows.yaml` actionlint glob: `*.yml` → `*.yaml` (all workflow files use `.yaml` extension)

Closes #<issue#>
Part of AccountabilityAtlas#38

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Tasks 2-6: Remaining Java Service Repos

**Identical to Task 1**, just in different repos:

| Task | Repo directory | GitHub repo |
|------|---------------|-------------|
| 2 | `AcctAtlas-video-service` | `kelleyglenn/AcctAtlas-video-service` |
| 3 | `AcctAtlas-location-service` | `kelleyglenn/AcctAtlas-location-service` |
| 4 | `AcctAtlas-moderation-service` | `kelleyglenn/AcctAtlas-moderation-service` |
| 5 | `AcctAtlas-search-service` | `kelleyglenn/AcctAtlas-search-service` |
| 6 | `AcctAtlas-api-gateway` | `kelleyglenn/AcctAtlas-api-gateway` |

Each task follows the exact same steps as Task 1. The only differences are the repo path and GitHub repo name.

---

## Task 7: AcctAtlas-web-app

**Repo:** `C:\code\AccountabilityAtlas\AcctAtlas-web-app` (git repo: `kelleyglenn/AcctAtlas-web-app`)

**Files:**
- Create: `.github/workflows/check.yaml`

(No existing lint workflows to fix.)

**Step 1: Create GitHub issue**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-web-app
gh issue create --title "Add quality checks workflow" --body "Add \`npm run check\` GitHub Actions workflow (prettier, eslint, jest). Part of AccountabilityAtlas#38."
```

**Step 2: Create feature branch**

```bash
git checkout master && git pull
git checkout -b feature/<issue#>-quality-checks
```

**Step 3: Create `.github/workflows/check.yaml`**

```yaml
name: Check

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'
      - run: npm ci
      - name: Run checks
        run: npm run check
```

**Step 4: Commit and push**

```bash
git add .github/workflows/check.yaml
git commit -m "ci: add quality checks workflow (#<issue#>)"
git push -u origin feature/<issue#>-quality-checks
```

**Step 5: Create PR**

```bash
gh pr create --title "ci: add quality checks workflow" --body "$(cat <<'EOF'
## Summary
- Add `check.yaml` workflow that runs `npm run check` (prettier, eslint, jest) on PRs and master pushes

Closes #<issue#>
Part of AccountabilityAtlas#38

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Execution Strategy

All 7 tasks are independent. Use `superpowers:dispatching-parallel-agents` to dispatch one subagent per repo. Each subagent creates the issue, branch, files, commit, and PR autonomously.

## Verification

After all PRs are created, each PR's Actions tab should show the new `Check` workflow running (triggered by the PR itself). The lint workflows should also run on the PR. This self-verifies the workflows work.
