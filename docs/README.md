# AccountabilityAtlas - High-Level Documentation

This repository contains the high-level architecture and design documentation for AccountabilityAtlas, a geo-located video curation platform focused on constitutional rights audits.

## Overview

AccountabilityAtlas enables users to discover, contribute, and explore videos of encounters involving 1st, 2nd, 4th, and 5th Amendment auditors interacting with police, government officials, business owners, and private citizens.

## Documentation Index

| Document | Description |
|----------|-------------|
| [01-SystemOverview.md](01-SystemOverview.md) | Executive summary, business objectives, and core features |
| [02-TechnicalRequirements.md](02-TechnicalRequirements.md) | Non-functional requirements, constraints, and SLAs |
| [03-ArchitectureOverview.md](03-ArchitectureOverview.md) | High-level system architecture and design decisions |
| [04-ServiceCatalog.md](04-ServiceCatalog.md) | Complete list of microservices with responsibilities |
| [05-DataArchitecture.md](05-DataArchitecture.md) | Data storage strategy and schema overview |
| [06-SecurityArchitecture.md](06-SecurityArchitecture.md) | Authentication, authorization, and security controls |
| [07-InfrastructureArchitecture.md](07-InfrastructureArchitecture.md) | AWS infrastructure and deployment architecture |
| [08-DevelopmentStandards.md](08-DevelopmentStandards.md) | Coding standards, testing, and CI/CD practices |
| [09-CostEstimate.md](09-CostEstimate.md) | Detailed cost breakdown by environment and service |

## Related Repositories

- [AcctAtlas-api-gateway](https://github.com/kelleyglenn/AcctAtlas-api-gateway) - API Gateway service
- [AcctAtlas-user-service](https://github.com/kelleyglenn/AcctAtlas-user-service) - User management service
- [AcctAtlas-video-service](https://github.com/kelleyglenn/AcctAtlas-video-service) - Video metadata service
- [AcctAtlas-location-service](https://github.com/kelleyglenn/AcctAtlas-location-service) - Geolocation service
- [AcctAtlas-search-service](https://github.com/kelleyglenn/AcctAtlas-search-service) - Search service
- [AcctAtlas-moderation-service](https://github.com/kelleyglenn/AcctAtlas-moderation-service) - Content moderation service
- [AcctAtlas-notification-service](https://github.com/kelleyglenn/AcctAtlas-notification-service) - Notification service
