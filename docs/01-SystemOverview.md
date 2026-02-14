# AccountabilityAtlas - System Overview

## Executive Summary

AccountabilityAtlas is a geo-located video curation platform focused on constitutional rights audits. The platform enables users to discover, contribute, and explore videos of encounters involving 1st, 2nd, 4th, and 5th Amendment auditors interacting with police, government officials, business owners, and private citizens.

## Business Objectives

1. **Content Discovery**: Provide an intuitive map-based interface for discovering constitutional audit videos by location
2. **Community Curation**: Enable users to contribute and curate video content with accurate geo-location data
3. **Education & Awareness**: Serve as an educational resource for understanding constitutional rights in practice
4. **Scalable Growth**: Support growth from initial launch to 100K+ active users

## Core Features

### Map-Based Video Discovery
- Interactive Mapbox integration displaying thousands of geo-located YouTube videos
- Clustering for high-density areas
- Pan, zoom, and location-based browsing
- Video preview on marker selection

### User-Generated Content
- Submit YouTube video links with metadata
- Assign videos to one or more map locations
- Categorize by amendment type (1st, 2nd, 4th, 5th)
- Tag encounter participants (police, government officials, business owners, citizens)

### User Accounts & Trust Tiers
- Email/password and social login (Google, Apple)
- Progressive trust system:
  - **New Users**: Submissions require moderation approval
  - **Trusted Users**: Direct publishing privileges
  - **Moderators**: Content review and user management
  - **Administrators**: Full system access

### Comprehensive Search
- Map-based spatial search
- Full-text search across titles, descriptions, and metadata
- Faceted filtering by amendment type, date range, location, outcome, participants

## Target Users

| User Type | Description | Key Needs |
|-----------|-------------|-----------|
| Viewers | Casual visitors exploring content | Easy discovery, intuitive navigation |
| Contributors | Active users submitting videos | Simple submission workflow, location tools |
| Researchers | Journalists, academics, advocates | Advanced search, data export |
| Moderators | Volunteer content reviewers | Efficient review queue, moderation tools |

## Success Metrics

- Monthly Active Users (MAU)
- Videos submitted per month
- Video view/play rate
- Search success rate
- Moderation queue turnaround time
- Mobile vs. web engagement ratio

## Document Index

| Document | Description |
|----------|-------------|
| [02-TechnicalRequirements.md](02-TechnicalRequirements.md) | Non-functional requirements, constraints, SLAs |
| [03-ArchitectureOverview.md](03-ArchitectureOverview.md) | High-level system architecture and design decisions |
| [04-ServiceCatalog.md](04-ServiceCatalog.md) | Complete list of services with responsibilities |
| [05-DataArchitecture.md](05-DataArchitecture.md) | Data storage strategy and schema overview |
| [06-SecurityArchitecture.md](06-SecurityArchitecture.md) | Authentication, authorization, and security controls |
| [07-InfrastructureArchitecture.md](07-InfrastructureArchitecture.md) | AWS infrastructure and deployment architecture |
| [08-DevelopmentStandards.md](08-DevelopmentStandards.md) | Coding standards, testing, and CI/CD practices |
| [09-CostEstimate.md](09-CostEstimate.md) | Detailed cost breakdown by environment and service |
