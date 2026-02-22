# AccountabilityAtlas

A multi-tier web application for geo-located video curation focused on constitutional rights audits. The platform enables users to discover, contribute, and explore videos of encounters involving 1st, 2nd, 4th, and 5th Amendment auditors interacting with police, government officials, business owners, and private citizens.

## Project Structure

```
AccountabilityAtlas/
├── docs/                              # Architecture and design documentation
├── infra/                             # OpenTofu (IaC) for AWS provisioning
├── scripts/
│   ├── dev-start.sh                   # Start all services (local dev mode)
│   ├── dev-stop.sh                    # Stop all services (local dev mode)
│   ├── docker-start.sh                # Start all services (docker mode)
│   ├── docker-stop.sh                 # Stop docker services
│   ├── deploy.sh                      # Build, check, and redeploy individual services
│   ├── seed-videos.sh                 # Seed videos from JSON into the running stack
│   ├── aws/                           # AWS start, stop, and deploy scripts
│   ├── extract-metadata/              # Python CLI for AI-powered video metadata extraction
│   ├── list-channel/                  # Python CLI to list video URLs from a YouTube channel
│   ├── lib/                           # Shared script utilities
│   └── integration/                   # Cross-service integration tests
├── seed-data/                         # Generated seed data (JSON, not committed)
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

## Prerequisites

- **Docker Desktop** (for PostgreSQL, Redis, LocalStack)
- **Git**

JDK 21 is managed automatically by the Gradle wrapper via [Foojay Toolchain](https://github.com/gradle/foojay-toolchain) -- no manual JDK installation required.

## Local Development

Two startup modes are available:

**Local Dev Mode** (fast iteration, no image rebuilds):
```bash
./scripts/dev-start.sh   # Starts postgres/redis via Docker, Java services via Gradle, web app via npm
./scripts/dev-stop.sh    # Stops everything
```

**Docker Mode** (production-like):
```bash
# Build Docker images for all services
./gradlew jibDockerBuildAll

./scripts/docker-start.sh   # Starts all backend services in containers
./scripts/docker-stop.sh    # Stops containers
```

Both modes start all services and open a browser to http://localhost:3000.

**Deploy Script** (rebuild and restart individual services):
```bash
./scripts/deploy.sh web-app                      # Rebuild and redeploy one service
./scripts/deploy.sh user-service video-service    # Multiple services
./scripts/deploy.sh --all                         # All services
./scripts/deploy.sh --skip-checks web-app         # Skip quality checks (faster iteration)
```

Runs quality checks, builds Docker images, recreates the targeted containers, and waits for health checks to pass.

## AWS Deployment

Infrastructure is provisioned with OpenTofu and deployed via SSH to a single EC2 instance running Docker Compose. See [infra/README.md](infra/README.md) for bootstrap and setup instructions.

```bash
./scripts/aws/aws-deploy.sh   # Build images, push to ECR, deploy to EC2
./scripts/aws/aws-start.sh    # Start EC2 + RDS instances
./scripts/aws/aws-stop.sh     # Stop EC2 + RDS instances (saves cost)
```

See [docs/07-InfrastructureArchitecture.md](docs/07-InfrastructureArchitecture.md) for the full infrastructure architecture across deployment phases.

## AI Metadata Extraction

The project includes tools for AI-powered extraction of video metadata (amendments, participants, location, date) using Claude:

- **`scripts/list-channel/`** — Python CLI that lists video URLs from a YouTube channel using yt-dlp, with date and duration filtering (excludes Shorts). Output is compatible with `extract.py --file`. See [scripts/list-channel/README.md](scripts/list-channel/README.md).
- **`scripts/extract-metadata/`** — Python CLI that uses yt-dlp and the Anthropic SDK to extract metadata from YouTube videos, including optional transcript analysis. See [scripts/extract-metadata/README.md](scripts/extract-metadata/README.md).
- **`scripts/seed-videos.sh`** — Seeds videos from a JSON file into the running stack via the API. Reads output from the extract CLI.
- **`/api/v1/videos/extract`** — Video-service REST endpoint for real-time extraction (title + description only, no transcript).

The shared prompt and output schema are documented in [docs/llm-extraction-prompt.md](docs/llm-extraction-prompt.md).

## Key Gradle Tasks

Top-level orchestration tasks that run across all service repositories:

| Task | Description |
|------|-------------|
| `jibDockerBuildAll` | Build Docker images for all services |
| `cleanAll` | Run clean in all services |
| `checkAll` | Run check (tests + quality gates) in all services |
| `testAll` | Run tests in all services |
| `spotlessApplyAll` | Apply code formatting in all services |
| `spotlessCheckAll` | Check code formatting in all services |

You can also target individual services (e.g., `./gradlew jibDockerBuild_AcctAtlas-user-service`).

Each service has its own Gradle build with service-specific tasks. See individual service READMEs for details.

## Git and GitHub

This is a multi-repo project. The top-level AccountabilityAtlas repo contains project-wide configuration (README, CLAUDE.md for Claude Code context) and architecture documentation (in `docs/`). Each service subdirectory is its own independent git repository, excluded from the top-level repo via `.gitignore`. Service repos are hosted on GitHub and must be committed/pushed separately.

## The Claude Code Prompt That Started It All

> I am at the very beginning stages of creating a multi-tier web application. I'd like you to walk me through the process of outlining the high-level technical requirements, then creating a set of formal documentation to fully describe the high-level architecture, including all of the processes and services, their service interfaces, and the technology by which they are developed, built, tested, and deployed. I'd like the high-level documentation to live in a subproject called "HighLevelDocumentation", and each service to have its own subproject off the current top-level project. Each service will have a folder called "TechnicalDocumentation" to hold all design documents for that service. Are you able to manage subprojects like this while other subagents handle the work for those subprojects?
