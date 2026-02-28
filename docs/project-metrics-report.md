# AccountabilityAtlas Project Metrics Report

> Generated: February 27, 2026
> Project span: January 31 - February 27, 2026 (27 days)

---

## Table of Contents

1. [Project Size](#1-project-size)
2. [Complexity](#2-complexity)
3. [Quality Metrics](#3-quality-metrics)
4. [Developer Performance](#4-developer-performance)
5. [Methodology](#5-methodology)

---

## 1. Project Size

### 1.1 Lines of Code by Repository

| Repository | Source | Tests | Config | Migrations | Build | Docs | Other | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **top-level** | - | - | 285 | - | 138 | 29,461 | 10,449 | 40,333 |
| **user-service** | 2,108 | 3,175 | 149 | 165 | 502 | 4,541 | 341 | 10,981 |
| **video-service** | 2,361 | 3,120 | 212 | 226 | 503 | 1,615 | 451 | 8,488 |
| **moderation-service** | 2,245 | 2,947 | 124 | 126 | 495 | 1,802 | 278 | 8,017 |
| **web-app** | 5,895 | 8,231 | 152 | - | 81 | 1,495 | 75 | 15,929 |
| **integration-tests** | - | 4,855 | 122 | - | 39 | 930 | 5,575 | 11,521 |
| **search-service** | 1,027 | 2,089 | 156 | 169 | 496 | 1,252 | 323 | 5,512 |
| **location-service** | 1,155 | 1,701 | 120 | 122 | 499 | 1,271 | 266 | 5,134 |
| **api-gateway** | 183 | 278 | 114 | - | 411 | 683 | 135 | 1,804 |
| **notification-service** | - | - | - | - | - | 412 | - | 412 |
| **Overall** | **14,974** | **26,396** | **1,434** | **808** | **3,164** | **43,462** | **17,893** | **108,131** |

"Other" includes infrastructure (1,323), scripts (6,879), seed data fixtures, and miscellaneous files.

### 1.2 Lines of Code by Category (Overall)

| Category | Total Lines | Code Lines | Files | % of Project |
|---|---:|---:|---:|---:|
| Documentation | 43,462 | 34,242 | 99 | 40.2% |
| Tests | 26,396 | 20,321 | 155 | 24.4% |
| Production source | 14,974 | 12,304 | 236 | 13.8% |
| Other | 9,691 | 9,257 | 93 | 9.0% |
| Scripts & infra | 8,202 | 6,620 | 51 | 7.6% |
| Build files | 3,164 | 2,692 | 30 | 2.9% |
| Config | 1,434 | 1,319 | 43 | 1.3% |
| Migrations (SQL) | 808 | 719 | 26 | 0.7% |
| **Total** | **108,131** | **87,474** | **733** | **100%** |

### 1.3 Language Breakdown

| Language | Total Lines | Code Lines | Files | % of Code |
|---|---:|---:|---:|---:|
| Markdown | 39,190 | 30,060 | 95 | 34.4% |
| Java | 22,341 | 17,177 | 254 | 19.6% |
| TypeScript (JSX) | 11,866 | 9,899 | 86 | 11.3% |
| TypeScript | 7,281 | 5,647 | 53 | 6.5% |
| YAML | 6,981 | 6,580 | 70 | 7.5% |
| JSON | 6,574 | 6,574 | 10 | 7.5% |
| Shell | 3,882 | 2,971 | 22 | 3.4% |
| Python | 2,515 | 1,986 | 7 | 2.3% |
| SQL | 1,733 | 1,539 | 55 | 1.8% |
| Gradle (Groovy) | 1,507 | 1,203 | 14 | 1.4% |
| XML | 874 | 874 | 2 | 1.0% |
| Terraform/OpenTofu | 651 | 529 | 12 | 0.6% |
| Other | 2,736 | 2,435 | 53 | 2.8% |
| **Total** | **108,131** | **87,474** | **733** | **100%** |

**Primary application languages**: Java (17,177 LOC) + TypeScript/TSX (15,546 LOC) = **32,723 LOC** of application code.

### 1.4 File Counts by Repository

| Repository | Source | Test | Config | Migration | Build | Docs | Other | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| top-level | - | - | 2 | - | 3 | 58 | 62 | 125 |
| user-service | 52 | 25 | 5 | 9 | 4 | 8 | 17 | 120 |
| video-service | 36 | 14 | 5 | 7 | 4 | 4 | 14 | 84 |
| moderation-service | 36 | 17 | 5 | 3 | 4 | 4 | 10 | 79 |
| web-app | 63 | 43 | 7 | - | 2 | 8 | 9 | 132 |
| integration-tests | - | 29 | 4 | - | 1 | 4 | 5 | 43 |
| search-service | 22 | 10 | 6 | 2 | 4 | 4 | 9 | 57 |
| location-service | 22 | 13 | 5 | 5 | 4 | 4 | 12 | 65 |
| api-gateway | 5 | 4 | 4 | - | 4 | 3 | 6 | 26 |
| notification-service | - | - | - | - | - | 2 | - | 2 |
| **Overall** | **236** | **155** | **43** | **26** | **30** | **99** | **144** | **733** |

---

## 2. Complexity

### 2.1 API Endpoints (from OpenAPI Specifications)

| Service | GET | POST | PUT | DELETE | Total | Paths |
|---|---:|---:|---:|---:|---:|---:|
| moderation-service | 6 | 6 | 1 | 1 | **14** | 13 |
| user-service | 2 | 7 | 2 | 0 | **11** | 10 |
| video-service | 6 | 2 | 1 | 2 | **11** | 7 |
| location-service | 5 | 1 | 0 | 0 | **6** | 5 |
| search-service | 4 | 0 | 0 | 0 | **4** | 4 |
| notification-service | 1 | 0 | 1 | 0 | **2** | 1 |
| **Backend total** | **24** | **16** | **5** | **3** | **48** | **40** |
| api-gateway (routing) | 9 | 4 | 3 | 1 | 17 | 9 |

The API gateway exposes a subset of backend endpoints through unified routing. The 48 backend endpoints represent the true API surface area. No service uses PATCH.

### 2.2 Domain Architecture

**Java Backend Services**

| Service | @Entity | @Repository | @Service | @RestController | @Configuration | @Bean |
|---|---:|---:|---:|---:|---:|---:|
| user-service | 7 | - | 6 | 3 | 4 | 6 |
| moderation-service | 3 | 3 | 5 | 2 | 3 | 6 |
| video-service | 2 | 2 | 4 | 2 | 2 | 4 |
| location-service | 2 | 2 | 4 | 3 | 2 | 2 |
| search-service | 1 | 1 | 3 | 2 | 2 | 2 |
| api-gateway | - | - | - | - | 2 | 2 |
| **Total** | **15** | **8** | **22** | **12** | **15** | **22** |

**Web Frontend (Next.js)**

| Metric | Count |
|---|---:|
| React components | 54 |
| Next.js pages | 8 |
| API routes | 0 |
| Runtime dependencies | 10 |
| Dev dependencies | 19 |

### 2.3 Branching Complexity

| Repository | if | else if | switch/case | catch | loops | && / \|\| | Est. CC |
|---|---:|---:|---:|---:|---:|---:|---:|
| web-app | 118 | 5 | 0 | 14 | 1 | 180 | **319** |
| integration-tests | 67 | 1 | 0 | 1 | 17 | 14 | **101** |
| video-service | 56 | 2 | 5 | 11 | 4 | 16 | **95** |
| moderation-service | 28 | 1 | 30 | 20 | 1 | 11 | **92** |
| user-service | 33 | 2 | 2 | 9 | 1 | 12 | **60** |
| search-service | 16 | 0 | 2 | 11 | 1 | 12 | **43** |
| location-service | 16 | 1 | 0 | 2 | 10 | 4 | **34** |
| api-gateway | 3 | 0 | 0 | 2 | 0 | 1 | **7** |
| **Overall** | **337** | **12** | **39** | **70** | **35** | **250** | **744** |

*Estimated Cyclomatic Complexity (CC) = 1 + if + else_if + switch_cases + catch + loops + logical_operators*

### 2.4 Dependencies

| Repository | Compile | Test | Total |
|---|---:|---:|---:|
| web-app | 10 | 19 | **29** |
| video-service | 19 | 6 | **25** |
| user-service | 16 | 6 | **22** |
| moderation-service | 14 | 7 | **21** |
| search-service | 14 | 7 | **21** |
| location-service | 15 | 6 | **21** |
| api-gateway | 5 | 5 | **10** |
| integration-tests | 0 | 8 | **8** |
| **Total unique deps** | **93** | **64** | **157** |

### 2.5 Estimated Function Points

Using a simplified IFPUG methodology based on the system's functional capabilities:

| Component Type | Count | Avg Weight | FP |
|---|---:|---:|---:|
| External Inputs (POST/PUT/DELETE endpoints) | 24 | 4 | 96 |
| External Outputs (GET endpoints) | 24 | 5 | 120 |
| Internal Logical Files (domain entities) | 15 | 10 | 150 |
| External Interface Files (YouTube, Mapbox, Nominatim, OAuth) | 4 | 7 | 28 |
| UI Pages (Next.js routes) | 8 | 5 | 40 |
| **Unadjusted Function Points** | | | **434** |

Applying a value adjustment factor of 1.05 (microservice architecture adds some complexity):

**Adjusted Function Points: ~456 FP**

For context, this represents a medium-sized application. The COCOMO II model would estimate ~12-18 person-months of effort for this size.

---

## 3. Quality Metrics

### 3.1 Structural Quality

| Metric | Value |
|---|---|
| **Test-to-source ratio** | 1.76:1 (26,396 test LOC / 14,974 source LOC) |
| **Avg source file size** | 63 lines (14,974 / 236 files) |
| **Avg test file size** | 170 lines (26,396 / 155 files) |
| **Documentation ratio** | 2.90:1 (43,462 doc LOC / 14,974 source LOC) |
| **Migration files** | 26 SQL migrations across 5 services |
| **Total test files** | 155 (unit + integration + E2E) |
| **CI/CD workflows** | Present in all active service repos |

### 3.2 Test Coverage - Java Backend (JaCoCo)

| Service | Line | Branch | Instruction | Method | Lines Covered |
|---|---:|---:|---:|---:|---:|
| user-service | **97.3%** | 87.4% | 97.6% | 95.0% | 639 / 657 |
| search-service | **96.9%** | 88.3% | 97.9% | 96.4% | 285 / 294 |
| video-service | **95.8%** | 72.1% | 95.4% | 93.8% | 711 / 742 |
| location-service | **93.5%** | 81.5% | 94.9% | 91.9% | 371 / 397 |
| api-gateway | **91.4%** | 75.0% | 94.2% | 78.6% | 53 / 58 |
| moderation-service | **84.4%** | 77.3% | 84.3% | 84.7% | 615 / 729 |
| **Weighted avg** | **92.9%** | **79.9%** | **93.3%** | **91.5%** | **2,674 / 2,877** |

All services exceed the **80% coverage target**. Weighted average line coverage is **92.9%**.

### 3.3 Test Coverage - Web Frontend (Jest)

| Metric | Coverage | Covered / Total |
|---|---:|---:|
| Lines | **79.7%** | 1,009 / 1,266 |
| Statements | 78.6% | 1,053 / 1,339 |
| Functions | 75.8% | 238 / 314 |
| Branches | 71.2% | 389 / 546 |

Web-app line coverage is just below the 80% target at 79.7%.

### 3.4 Integration & E2E Tests

| Test Suite | Test Files | Location |
|---|---:|---|
| API integration tests | 10 | `integration-tests/api/tests/` |
| E2E browser tests | 15 | `integration-tests/e2e/tests/` |
| Web-app unit tests | 43 suites (442 tests) | `web-app/src/__tests__/` |

E2E tests cover **3 browsers**: Chromium, Firefox (via xvfb), and WebKit.

### 3.5 Static Analysis

All 6 active Java services pass the full quality gate:

| Check | Tool | Status |
|---|---|---|
| Code formatting | Spotless (Google Java Style) | All pass |
| Static analysis | Error Prone | All pass |
| Coverage threshold | JaCoCo (80% minimum) | All pass |
| Web-app formatting | Prettier (via husky pre-commit) | Configured |

### 3.6 Overall Quality Summary

| Dimension | Rating | Notes |
|---|---|---|
| Test coverage (backend) | Excellent | 92.9% line coverage, all services > 80% |
| Test coverage (frontend) | Good | 79.7% line, 71.2% branch |
| Test-to-code ratio | Excellent | 1.76x more test code than source |
| Documentation ratio | Excellent | 2.90x more docs than source |
| Static analysis | Excellent | All checks pass, no violations |
| Architectural consistency | Excellent | All services follow same layered pattern |

---

## 4. Developer Performance

### 4.1 Project Timeline

| Metric | Value |
|---|---|
| **Project start** | January 31, 2026 |
| **Latest activity** | February 27, 2026 |
| **Active development days** | 27 days |
| **Repositories** | 10 (1 parent + 7 services + 1 web-app + 1 integration-tests) |

### 4.2 Commit Activity

| Metric | Value |
|---|---:|
| **Total commits** | 308 |
| **Commits per day** (avg) | 11.4 |
| **Claude co-authored commits** | 96 (31.2%) |
| **Human-only commits** | 212 (68.8%) |

**Commits by Repository:**

| Repository | Commits | First Commit | Latest Commit |
|---|---:|---|---|
| top-level (AccountabilityAtlas) | 80 | Jan 31 | Feb 27 |
| integration-tests | 42 | Feb 7 | Feb 25 |
| video-service | 37 | Jan 31 | Feb 26 |
| user-service | 33 | Jan 31 | Feb 26 |
| web-app | 31 | Jan 31 | Feb 25 |
| search-service | 24 | Jan 31 | Feb 26 |
| moderation-service | 22 | Jan 31 | Feb 25 |
| location-service | 17 | Jan 31 | Feb 24 |
| api-gateway | 15 | Jan 31 | Feb 20 |
| notification-service | 7 | Jan 31 | Feb 5 |

### 4.3 Code Volume

| Metric | Value |
|---|---:|
| **Total lines added** | 118,550 |
| **Total lines removed** | 5,804 |
| **Net lines** | 112,746 |
| **Lines added per day** (avg) | 4,391 |
| **Churn rate** | 4.9% (lines removed / lines added) |

**Lines by Repository:**

| Repository | Added | Removed | Net | % of Total |
|---|---:|---:|---:|---:|
| top-level | 38,637 | 1,827 | 36,810 | 32.6% |
| web-app | 28,777 | 1,059 | 27,718 | 24.6% |
| user-service | 11,111 | 189 | 10,922 | 9.7% |
| integration-tests | 9,425 | 1,482 | 7,943 | 7.0% |
| video-service | 8,760 | 439 | 8,321 | 7.4% |
| moderation-service | 8,372 | 349 | 8,023 | 7.1% |
| search-service | 5,802 | 332 | 5,470 | 4.9% |
| location-service | 5,259 | 109 | 5,150 | 4.6% |
| api-gateway | 1,951 | 13 | 1,938 | 1.7% |
| notification-service | 456 | 5 | 451 | 0.4% |

### 4.4 Pull Request Activity

| Metric | Value |
|---|---:|
| **Total merged PRs** | 193 |
| **PRs per day** (avg) | 7.1 |
| **PR-to-commit ratio** | 0.63 (193 PRs / 308 commits) |

**PRs by Repository:**

| Repository | Merged PRs |
|---|---:|
| top-level | 37 |
| video-service | 28 |
| web-app | 27 |
| integration-tests | 27 |
| user-service | 23 |
| search-service | 16 |
| moderation-service | 15 |
| api-gateway | 10 |
| location-service | 10 |
| notification-service | 0 |

### 4.5 Issue Tracking

| Metric | Value |
|---|---:|
| **Total issues** | 213 |
| **Closed issues** | 147 (69.0%) |
| **Open issues** | 66 (31.0%) |
| **Issue closure rate** | 5.4 issues/day |

**Issues by Repository:**

| Repository | Total | Open | Closed | Closure Rate |
|---|---:|---:|---:|---:|
| top-level | 65 | 39 | 26 | 40.0% |
| web-app | 43 | 16 | 27 | 62.8% |
| user-service | 24 | 3 | 21 | 87.5% |
| video-service | 22 | 1 | 21 | 95.5% |
| integration-tests | 18 | 2 | 16 | 88.9% |
| search-service | 14 | 2 | 12 | 85.7% |
| moderation-service | 12 | 1 | 11 | 91.7% |
| location-service | 11 | 2 | 9 | 81.8% |
| api-gateway | 4 | 0 | 4 | 100.0% |
| notification-service | 0 | 0 | 0 | - |

### 4.6 Velocity & Productivity Summary

| Metric | Per Day | Per Week | Total |
|---|---:|---:|---:|
| Commits | 11.4 | 79.8 | 308 |
| Lines of code added | 4,391 | 30,737 | 118,550 |
| PRs merged | 7.1 | 49.7 | 193 |
| Issues closed | 5.4 | 37.8 | 147 |

### 4.7 AI-Assisted Development

| Metric | Value |
|---|---|
| Claude co-authored commits | 96 / 308 (31.2%) |
| Human-AI collaboration model | Human-directed, AI-implemented |
| Quality gate compliance | 100% - all services pass all checks |

---

## 5. Methodology

### Data Sources

| Metric | Source | Tool |
|---|---|---|
| Lines of code | File system analysis | `collect_loc_metrics.py` |
| Endpoints | OpenAPI specification YAML files | `collect_endpoint_counts.py` |
| Domain annotations | Source code grep | `collect_loc_metrics.py` |
| Branching complexity | Source code regex matching | `collect_loc_metrics.py` |
| Function points | IFPUG simplified methodology | Manual estimation |
| Test coverage (Java) | JaCoCo XML/CSV reports | `collect_coverage.py` |
| Test coverage (JS) | Jest coverage reports | `npx jest --coverage` |
| Git metrics | Git log analysis | `collect_metrics.py` |
| GitHub metrics | GitHub API | `collect_metrics.py` |

### Definitions

- **Lines of code (LOC)**: All non-binary tracked files, including blank lines and comments
- **Code lines**: LOC minus blank lines and comments
- **Source**: Production application code (`src/main/java/**`, `src/**/*.{ts,tsx}`)
- **Tests**: Test code (`src/test/**`, `__tests__/**`, `*.spec.ts`)
- **Estimated CC**: Simplified cyclomatic complexity approximation, not equivalent to formal CC measurement
- **Function Points**: Estimated using simplified IFPUG methodology; actual FP analysis may differ
- **Coverage**: Measured on hand-written source code only; generated code (OpenAPI models/APIs) excluded
- **Comment detection**: Language-aware (C-style `//` `/* */` for Java/TS/CSS/Gradle; `#` for Python/Shell/YAML; no comments for Markdown/JSON/XML/SQL)

### Scripts

Collection scripts are located in `scripts/metrics/`:
- `collect_loc_metrics.py` - LOC, language, complexity, annotation analysis
- `collect_metrics.py` - Git and GitHub metrics
- `collect_coverage.py` - JaCoCo coverage extraction
- `collect_endpoint_counts.py` - API endpoint counts from OpenAPI specs

---

*Report generated by Claude Code metrics analysis pipeline.*
