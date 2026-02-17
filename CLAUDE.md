# Claude Code Context for AccountabilityAtlas

See [README.md](README.md) for project overview and structure.

This is a **multi-repo project**: the top-level repo contains project-wide configuration and docs, while each service subdirectory is its own independent git repository (excluded via `.gitignore`).

## Key Documentation

### Project Architecture

Start here to understand the system:

| Document | Purpose |
|----------|---------|
| [03-ArchitectureOverview.md](docs/03-ArchitectureOverview.md) | System architecture and design decisions |
| [04-ServiceCatalog.md](docs/04-ServiceCatalog.md) | All microservices with responsibilities |
| [05-DataArchitecture.md](docs/05-DataArchitecture.md) | PostgreSQL schemas, temporal tables, Redis, OpenSearch |
| [06-SecurityArchitecture.md](docs/06-SecurityArchitecture.md) | Auth, authorization, security controls |

### Coding Standards

See [08-DevelopmentStandards.md](docs/08-DevelopmentStandards.md) for:

- **Technology stack**: Java 21, Spring Boot 3.4.x, Gradle 9.x
- **Code style**: Google Java Style Guide, enforced by Spotless
- **Static analysis**: Error Prone, SonarLint
- **Testing**: JUnit 5, Mockito, TestContainers (80% coverage target)
- **API design**: REST conventions, OpenAPI 3.1 specs

### Common Workflows

**Git workflow** (GitHub Flow):
- `master` - always deployable, **protected in all repos** (requires PR with approval)
- `feature/{ticket}-{description}` or `fix/{ticket}-{description}` - all work branches from master

**Branch protection** (applies to all repos):
- Direct pushes to `master` are blocked
- All changes **require** a pull request with at least 1 approving review
- Code owner reviews required. You are not the code owner. Although you may be logged in as the code owner, you must behave as if you are not.
- Always create a feature branch, open a PR, and merge via GitHub
- **NEVER** commit directly to master, unless given explicit instructions to disable the protections first

**Commit messages**: Follow [Conventional Commits](https://www.conventionalcommits.org/). Include the GitHub issue number when applicable:
```
feat(video): add amendment filtering (#42)
fix(auth): correct JWT expiry calculation (#15)
```

**Pull requests**: Use [GitHub keywords](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue) to link PRs to issues:
```
Closes #42
Fixes #15
Resolves #23
```

**Local development** (single service):
```bash
docker-compose up -d postgres redis    # Start dependencies
./gradlew flywayMigrate                # Run migrations
./gradlew bootRun                      # Run service
./gradlew spotlessApply                # Fix code formatting
./gradlew test                         # Run tests
```

**Deploying changes** (rebuild and redeploy to Docker):
```bash
./scripts/deploy.sh web-app                   # Single service
./scripts/deploy.sh user-service web-app      # Multiple services
./scripts/deploy.sh --skip-checks web-app     # Skip quality checks (faster iteration)
```
The deploy script runs quality checks, builds Docker images, recreates containers, and waits for health checks. Use `--skip-checks` only when you've already verified quality separately.

**Squash merging**: **NEVER** merge a PR, unless given explicit instructions to do so. Remember, you are **not** the code owner, and only they control access to master. If you are explicity asked to merge a PR, you squash merge (`gh pr merge --squash`) to keep commit history clean on master.

### Service Repo Standards

Each service repo should follow the user-service template:

**Required files:**
- `README.md` - follows user-service format with Prerequisites, Clone/Build, Local Development, Docker Image, Project Structure, Key Gradle Tasks, Documentation sections
- `docker-compose.yml` - standalone local dev stack (postgres/redis as needed, service with `profiles: [app]`)
- `docs/technical.md` - domain model, API endpoints, events, local dev setup
- `docs/database-schema.md` - JPA entity mappings, temporal vs non-temporal decisions, query patterns
- `docs/api-specification.yaml` - OpenAPI 3.1 spec

**Required Gradle tasks** (in Key Gradle Tasks table):
- `bootRun` - run locally
- `test` / `unitTest` / `integrationTest` - test tasks
- `check` - full quality gate
- `spotlessApply` - fix formatting
- `jibDockerBuild` - build Docker image
- `composeUp` - build image + docker-compose up
- `composeDown` - stop docker-compose services

## Database Notes

- **Temporal tables**: Most tables use `sys_period tstzrange` for automatic history tracking
- **Stats tables**: Counters are in separate non-temporal tables (`user_stats`, `location_stats`)
- See [05-DataArchitecture.md](docs/05-DataArchitecture.md) for full schema

## When Making Changes

1. Changes to high-level architecture go in `docs/`
2. Service-specific changes go in that service's repo
3. **Service repos must be committed/pushed separately from the top-level repo** - each service is its own git repository with its own commit history and PRs
4. Keep domain models in sync between high-level docs and service docs

## Verification Before Merging

Before considering PRs ready for merge, verify the full stack works end-to-end:

1. **Deploy affected services** via `./scripts/deploy.sh <services...>` (runs quality checks, builds, deploys, health checks)
2. **Run the full integration test suite** in `AcctAtlas-integration-tests`:
   ```bash
   cd AcctAtlas-integration-tests
   npm run test:all    # Runs both API integration tests and E2E browser tests
   ```
   - `test:api` — cross-service API contract tests (auth, CRUD, access control)
   - `test:e2e` — browser tests across Chromium, Firefox, and WebKit (map, video, auth flows)
3. Only after all checks pass should PRs be created or marked ready for review

## Environment Notes

**Windows with Git Bash**: Use `/c/code/...` paths in bash commands, not `C:\code\...`. The Windows-style paths don't work in Git Bash/MSYS2.

## Delegating Work to Subagents

When using subagents to write code in a repo:

1. **Create a GitHub issue first** in the target repo using `gh issue create`
2. **Issue description should include**:
   - References to relevant documentation (e.g., `docs/technical.md`, high-level architecture docs)
   - Specific requirements not already documented
   - Acceptance criteria if applicable
3. **Assign the subagent** to work on that issue by telling it the issue number and repo
4. The subagent should follow the issue instructions and reference the linked documentation
