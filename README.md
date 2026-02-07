# AccountabilityAtlas

A multi-tier web application for geo-located video curation focused on constitutional rights audits. The platform enables users to discover, contribute, and explore videos of encounters involving 1st, 2nd, 4th, and 5th Amendment auditors interacting with police, government officials, business owners, and private citizens.

## Project Structure

```
AccountabilityAtlas/
├── docs/                              # Architecture and design documentation
├── scripts/
│   ├── dev-start.sh                   # Start all services (local dev mode)
│   ├── dev-stop.sh                    # Stop all services (local dev mode)
│   ├── docker-start.sh                # Start all services (docker mode)
│   ├── docker-stop.sh                 # Stop docker services
│   ├── lib/                           # Shared script utilities
│   └── integration/                   # Cross-service integration tests
├── docker-compose.yml                 # Local multi-service development
├── AcctAtlas-api-gateway/             # API Gateway service
├── AcctAtlas-user-service/            # User management and authentication
├── AcctAtlas-video-service/           # Video metadata and management
├── AcctAtlas-location-service/        # Geo-location handling
├── AcctAtlas-search-service/          # Search functionality
├── AcctAtlas-moderation-service/      # Content moderation
├── AcctAtlas-notification-service/    # User notifications
└── AcctAtlas-web-app/                 # Frontend web application
# External repository:
# AcctAtlas-integration-tests/        # E2E and API integration tests (separate repo)
```

Service subdirectories are independent git repositories (excluded via `.gitignore`).

## Core Features

- **Map-Based Video Discovery**: Interactive Google Maps integration with geo-located YouTube videos
- **User-Generated Content**: Submit and categorize videos by amendment type and location
- **Trust-Based User System**: Progressive trust tiers from new users to administrators
- **Comprehensive Search**: Spatial, full-text, and faceted filtering capabilities

## Documentation

See [docs/](docs/) for complete architecture and design documentation.

## Local Development

Two startup modes are available:

**Local Dev Mode** (fast iteration, no image rebuilds):
```bash
./scripts/dev-start.sh   # Starts postgres/redis via Docker, Java services via Gradle, web app via npm
./scripts/dev-stop.sh    # Stops everything
```

**Docker Mode** (production-like):
```bash
# First, build Docker images for Java services
cd AcctAtlas-user-service && ./gradlew jibDockerBuild && cd ..
cd AcctAtlas-api-gateway && ./gradlew jibDockerBuild && cd ..

./scripts/docker-start.sh   # Starts all backend services in containers
./scripts/docker-stop.sh    # Stops containers
```

Both modes start all services and open a browser to http://localhost:3000.

## Git and GitHub

This is a multi-repo project. The top-level AccountabilityAtlas repo contains project-wide configuration (README, CLAUDE.md for Claude Code context) and architecture documentation (in `docs/`). Each service subdirectory is its own independent git repository, excluded from the top-level repo via `.gitignore`. Service repos are hosted on GitHub and must be committed/pushed separately.

## The Claude Code Prompt That Started It All

> I am at the very beginning stages of creating a multi-tier web application. I'd like you to walk me through the process of outlining the high-level technical requirements, then creating a set of formal documentation to fully describe the high-level architecture, including all of the processes and services, their service interfaces, and the technology by which they are developed, built, tested, and deployed. I'd like the high-level documentation to live in a subproject called "HighLevelDocumentation", and each service to have its own subproject off the current top-level project. Each service will have a folder called "TechnicalDocumentation" to hold all design documents for that service. Are you able to manage subprojects like this while other subagents handle the work for those subprojects?
