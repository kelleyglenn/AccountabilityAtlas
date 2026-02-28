# Project Metrics Scripts

Scripts for collecting size, complexity, quality, and developer performance metrics across all AccountabilityAtlas repos. Results feed into [docs/project-metrics-report.md](../../docs/project-metrics-report.md).

## Prerequisites

- **Python 3.x** (available as `python`)
- **Git** (for commit/log analysis)
- **GitHub CLI** (`gh`) authenticated with access to all `kelleyglenn/AcctAtlas-*` repos
- **Gradle wrapper** (`./gradlew`) in each Java service (for coverage reports)
- **Node.js / npm** (for web-app Jest coverage)

## Scripts

### 1. `collect_loc_metrics.py` - Size & Complexity

Walks every repo's file tree and counts lines of code, categorized by type (source, test, config, migrations, build, docs). Also counts branching constructs, Java annotations, React components, and dependency counts.

```bash
python scripts/metrics/collect_loc_metrics.py
```

**Output:** `scripts/metrics/loc_metrics.json`

No build or network access required -- purely file-system analysis.

### 2. `collect_metrics.py` - Git & GitHub Metrics

Collects commit counts, lines added/removed, Claude co-authorship stats, merged PR counts, and issue counts across all repos.

```bash
python scripts/metrics/collect_metrics.py
```

**Output:** `scripts/metrics/git_metrics.json`

Requires `git` and `gh` CLI. GitHub API calls may be slow (~2 min for all repos).

### 3. `collect_coverage.py` - Test Coverage (Java)

Parses JaCoCo CSV reports from each Java service's `build/reports/jacoco/test/` directory. Reports must already exist from a prior `./gradlew check jacocoTestReport` run.

```bash
python scripts/metrics/collect_coverage.py
```

**Output:** `scripts/metrics/coverage_data.json`

**Prerequisite:** Run tests with coverage in each Java service first:

```bash
# All services in parallel (from project root)
for svc in api-gateway user-service video-service location-service search-service moderation-service; do
  (cd "AcctAtlas-$svc" && ./gradlew check jacocoTestReport) &
done
wait
```

### 4. Web-App Coverage (manual)

Jest coverage for the web-app is collected separately:

```bash
cd AcctAtlas-web-app
npx jest --coverage --silent
```

Results are written to `AcctAtlas-web-app/coverage/coverage-summary.json`.

### 5. `collect_endpoint_counts.py` - API Endpoints

Parses each service's `docs/api-specification.yaml` (OpenAPI 3.1) and counts HTTP methods (GET, POST, PUT, DELETE, PATCH) under the `paths:` section. Uses simple line-based YAML parsing -- no external YAML library required.

```bash
python scripts/metrics/collect_endpoint_counts.py
```

**Output:** `scripts/metrics/endpoint_counts.json`

## Running Everything

To regenerate all metrics from scratch:

```bash
# 1. LOC & structural metrics (fast, ~10s)
python scripts/metrics/collect_loc_metrics.py

# 2. Endpoint counts (fast, ~1s)
python scripts/metrics/collect_endpoint_counts.py

# 3. Git & GitHub metrics (~2 min)
python scripts/metrics/collect_metrics.py

# 4. Build all Java services with coverage (~2-5 min)
for svc in api-gateway user-service video-service location-service search-service moderation-service; do
  (cd "AcctAtlas-$svc" && ./gradlew check jacocoTestReport) &
done
wait

# 5. Extract Java coverage data (fast, ~1s)
python scripts/metrics/collect_coverage.py

# 6. Web-app Jest coverage (~30s)
cd AcctAtlas-web-app && npx jest --coverage --silent && cd ..
```

After running all scripts, update `docs/project-metrics-report.md` with the new data from the JSON output files.

## Output Files

| File | Contents |
|---|---|
| `loc_metrics.json` | LOC by repo/category/language, complexity, annotations, dependencies |
| `git_metrics.json` | Commits, lines added/removed, PRs, issues per repo |
| `coverage_data.json` | JaCoCo line/branch/instruction/method coverage per Java service |
| `endpoint_counts.json` | API endpoint counts by HTTP method per service |
