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
- **API design**: REST conventions, OpenAPI 3.0 specs

### Common Workflows

**Git workflow** (GitHub Flow):
- `master` - always deployable, **protected in all repos** (requires PR with approval)
- `feature/{ticket}-{description}` or `fix/{ticket}-{description}` - all work branches from master

**Branch protection** (applies to all service repos and AcctAtlas-integration-tests):
- Direct pushes to `master` are blocked
- All changes require a pull request with at least 1 approving review
- Code owner reviews required
- Always create a feature branch, open a PR, and merge via GitHub

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

**Local development**:
```bash
docker-compose up -d postgres redis    # Start dependencies
./gradlew flywayMigrate                # Run migrations
./gradlew bootRun                      # Run service
./gradlew spotlessApply                # Fix code formatting
./gradlew test                         # Run tests
```

### Service-Specific Documentation

Each service has a `docs/technical.md` with:
- Domain model
- API endpoints
- Events published/consumed
- Local development setup

## Database Notes

- **Temporal tables**: Most tables use `sys_period tstzrange` for automatic history tracking
- **Stats tables**: Counters are in separate non-temporal tables (`user_stats`, `location_stats`)
- See [05-DataArchitecture.md](docs/05-DataArchitecture.md) for full schema

## When Making Changes

1. Changes to high-level architecture go in `docs/`
2. Service-specific changes go in that service's repo
3. **Service repos must be committed/pushed separately from the top-level repo** - each service is its own git repository with its own commit history and PRs
4. Keep domain models in sync between high-level docs and service docs

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
