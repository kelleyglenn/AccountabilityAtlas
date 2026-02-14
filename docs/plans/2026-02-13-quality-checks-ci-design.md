# Quality Checks via GitHub Actions (Issue #38)

## Problem

No repo runs code quality checks (formatting, tests, coverage) in CI. The 6 Java service repos have OpenAPI lint and workflow lint workflows, but these trigger on push to `main` instead of `master` (the actual default branch), so push triggers never fire. The web-app has no CI workflows at all.

## Design

### Java Service Repos (6 repos)

Add `check.yaml` to each of: user-service, video-service, location-service, moderation-service, search-service, api-gateway.

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

This runs: spotlessCheck (formatting), unit tests, integration tests (TestContainers, Docker available on ubuntu-latest), and JaCoCo coverage verification.

### Web-App (1 repo)

Add `check.yaml`:

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

This runs: `prettier --check .` (formatting), `next lint` (ESLint), and `jest` (unit tests).

### Top-Level AccountabilityAtlas Repo

Skip. It contains only docs and docker-compose config. No code to check.

### Fix Existing Branch Triggers

Change `main` to `master` in all existing `lint.yaml` and `lint-workflows.yaml` files across all 6 Java repos. This fixes push triggers that currently never fire.

## Scope

| Repo | New `check.yaml` | Fix `lint.yaml` | Fix `lint-workflows.yaml` |
|------|:-:|:-:|:-:|
| user-service | Y | Y | Y |
| video-service | Y | Y | Y |
| location-service | Y | Y | Y |
| moderation-service | Y | Y | Y |
| search-service | Y | Y | Y |
| api-gateway | Y | Y | Y |
| web-app | Y | - | - |

Total: 7 new files + 12 file edits across 7 repos.

## Deployment

All changes are independent per repo. PRs can be created and merged in any order.
