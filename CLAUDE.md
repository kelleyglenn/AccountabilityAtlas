# Claude Code Context for AccountabilityAtlas

## Project Overview

AccountabilityAtlas is a multi-tier web application for geo-located video curation focused on constitutional rights audits. It consists of 7 microservices plus a frontend web application.

## Project Structure

This is a multi-repo project. Each subdirectory is its own git repository:

```
AccountabilityAtlas/           # NOT a git repo (local super-project only)
├── AcctAtlas-HighLevelDocumentation/  # Architecture docs
├── AcctAtlas-api-gateway/
├── AcctAtlas-user-service/
├── AcctAtlas-video-service/
├── AcctAtlas-location-service/
├── AcctAtlas-search-service/
├── AcctAtlas-moderation-service/
├── AcctAtlas-notification-service/
└── AcctAtlas-web-app/
```

## Key Documentation

### Project Architecture

Start here to understand the system:

| Document | Purpose |
|----------|---------|
| [03-ArchitectureOverview.md](AcctAtlas-HighLevelDocumentation/03-ArchitectureOverview.md) | System architecture and design decisions |
| [04-ServiceCatalog.md](AcctAtlas-HighLevelDocumentation/04-ServiceCatalog.md) | All microservices with responsibilities |
| [05-DataArchitecture.md](AcctAtlas-HighLevelDocumentation/05-DataArchitecture.md) | PostgreSQL schemas, temporal tables, Redis, OpenSearch |
| [06-SecurityArchitecture.md](AcctAtlas-HighLevelDocumentation/06-SecurityArchitecture.md) | Auth, authorization, security controls |

### Coding Standards

See [08-DevelopmentStandards.md](AcctAtlas-HighLevelDocumentation/08-DevelopmentStandards.md) for:

- **Technology stack**: Java 21, Spring Boot 3.2.x, Gradle 9.x
- **Code style**: Google Java Style Guide, enforced by Spotless
- **Static analysis**: Error Prone, SonarLint
- **Testing**: JUnit 5, Mockito, TestContainers (80% coverage target)
- **API design**: REST conventions, OpenAPI 3.0 specs

### Common Workflows

**Git workflow** (GitHub Flow):
- `main` - always deployable (protected, requires PR approval)
- `feature/{ticket}-{description}` or `fix/{ticket}-{description}` - all work branches from main

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
- See [05-DataArchitecture.md](AcctAtlas-HighLevelDocumentation/05-DataArchitecture.md) for full schema

## When Making Changes

1. Changes to high-level architecture go in `AcctAtlas-HighLevelDocumentation/`
2. Service-specific changes go in that service's repo
3. Each repo must be committed/pushed separately
4. Keep domain models in sync between high-level docs and service docs

## Delegating Work to Subagents

When using subagents to write code in a repo:

1. **Create a GitHub issue first** in the target repo using `gh issue create`
2. **Issue description should include**:
   - References to relevant documentation (e.g., `docs/technical.md`, high-level architecture docs)
   - Specific requirements not already documented
   - Acceptance criteria if applicable
3. **Assign the subagent** to work on that issue by telling it the issue number and repo
4. The subagent should follow the issue instructions and reference the linked documentation
