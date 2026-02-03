# Architecture Overview

## Architecture Style

AccountabilityAtlas follows a **microservices architecture** with the following characteristics:

- **Service-Oriented**: Domain-driven service boundaries
- **API-First**: OpenAPI specifications define contracts before implementation
- **Event-Driven**: Asynchronous messaging for cross-service workflows
- **Cloud-Native**: Designed for containerized deployment on AWS

## System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SYSTEMS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   YouTube    │  │ Google Maps  │  │    OAuth     │  │    Email     │     │
│  │   Data API   │  │   Platform   │  │  Providers   │  │   Service    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ACCOUNTABILITYATLAS                                │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                           API GATEWAY                                  │  │
│  │              (Authentication, Routing, Rate Limiting)                  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│         ┌────────────────────────────┼────────────────────────────┐         │
│         ▼                            ▼                            ▼         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │    User     │  │   Video     │  │  Location   │  │   Search    │        │
│  │   Service   │  │   Service   │  │   Service   │  │   Service   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│         │                │                │                │                 │
│         │         ┌──────┴──────┐         │                │                 │
│         │         ▼             ▼         │                │                 │
│         │  ┌─────────────┐  ┌─────────────┐                │                 │
│         │  │ Moderation  │  │Notification │                │                 │
│         │  │   Service   │  │   Service   │                │                 │
│         │  └─────────────┘  └─────────────┘                │                 │
│         │         │                │                       │                 │
│         ▼         ▼                ▼                       ▼                 │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         DATA LAYER                                     │  │
│  │   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐          │  │
│  │   │PostgreSQL│   │  Redis   │   │ Search  │   │   SQS    │          │  │
│  │   │+ PostGIS │   │  Cache   │   │Backend* │   │  Queues  │          │  │
│  │   └──────────┘   └──────────┘   └──────────┘   └──────────┘          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  * Search Backend: PostgreSQL FTS (Phase 1-2), OpenSearch (Phase 3+)       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│                               CLIENTS                                        │
│     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐              │
│     │   Web App    │     │  iOS App     │     │ Android App  │              │
│     │  (React)     │     │  (Swift)     │     │  (Kotlin)    │              │
│     └──────────────┘     └──────────────┘     └──────────────┘              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Service Responsibilities

### API Gateway
- **Purpose**: Single entry point for all client requests
- **Responsibilities**:
  - Request routing to backend services
  - JWT token validation
  - Rate limiting by user tier
  - Request/response logging
  - CORS handling

### User Service
- **Purpose**: Identity and access management
- **Responsibilities**:
  - User registration and authentication
  - OAuth integration (Google, Apple)
  - Profile management
  - Trust tier management
  - Session management

### Video Service
- **Purpose**: Core content management
- **Responsibilities**:
  - Video record CRUD operations
  - YouTube API integration for metadata
  - Amendment categorization
  - Participant tagging
  - Video-location associations

### Location Service
- **Purpose**: Geospatial data management
- **Responsibilities**:
  - Location storage and retrieval
  - Spatial queries (bounding box, radius)
  - Marker clustering for map display
  - Geocoding integration
  - Location validation

### Search Service
- **Purpose**: Content discovery
- **Responsibilities**:
  - Full-text search indexing
  - Faceted search execution
  - Search result ranking
  - Autocomplete suggestions
  - Search analytics

### Moderation Service
- **Purpose**: Content quality control
- **Responsibilities**:
  - Moderation queue management
  - Content approval/rejection workflow
  - User trust tier promotion
  - Abuse report handling
  - Audit logging

### Notification Service
- **Purpose**: User communications
- **Responsibilities**:
  - Email notifications
  - Notification preferences
  - Email template management
  - Delivery tracking

## Communication Patterns

### Synchronous (REST)
Used for real-time user-facing operations:
- Client → API Gateway → Services
- Service-to-service queries (with circuit breakers)

### Asynchronous (SQS)
Used for decoupled, non-blocking operations:
- Video submission → Moderation queue
- Content approval → Search index update
- User actions → Notification triggers

## Key Architectural Decisions

### ADR-001: Microservices vs Monolith
**Decision**: Microservices architecture
**Rationale**:
- Independent scaling of map/search-heavy components
- Team scalability for future growth
- Technology flexibility per service
- Fault isolation

### ADR-002: PostgreSQL with PostGIS
**Decision**: Single primary database with spatial extension
**Rationale**:
- Proven spatial query performance
- ACID compliance for data integrity
- Simpler operations than separate geo database
- Strong Java/JDBC ecosystem support

### ADR-003: OpenSearch over Elasticsearch
**Decision**: Amazon OpenSearch Service
**Rationale**:
- Managed service reduces operational burden
- AWS-native integration
- Functionally equivalent to Elasticsearch
- Cost-effective for our scale

**Addendum**: OpenSearch is deferred to Phase 3. PostgreSQL full-text search is used for Phases 1-2. See [ADR-007](#adr-007-postgresql-fts-initially).

### ADR-004: ECS Fargate over EKS
**Decision**: ECS Fargate for container orchestration
**Rationale**:
- Lower operational complexity than Kubernetes
- Sufficient for our scale and service count
- Serverless container management
- Native AWS integration

**Addendum**: ECS Fargate is deferred to Phase 2. Phase 1 uses Docker Compose on a single EC2 instance. See [ADR-006](#adr-006-phased-deployment-strategy).

**EKS migration is not part of the current phase plan.** ECS Fargate comfortably handles the scale described through Phase 4. Reopen this decision if:
- Service count exceeds 15+
- Multiple independent teams need isolated deployment pipelines
- Requirements emerge for service mesh or advanced traffic routing (canary deploys, traffic splitting)
- Multi-cloud or hybrid deployment becomes a requirement

### ADR-005: YouTube Link-Only Model
**Decision**: Store YouTube links, not video content
**Rationale**:
- Avoids video hosting costs and complexity
- Respects YouTube's content policies
- Leverages YouTube's CDN and player
- Reduces legal/copyright liability

### ADR-006: Phased Deployment Strategy
**Decision**: Deploy incrementally across 4 phases, starting with a single EC2 instance running Docker Compose
**Rationale**:
- Phase 1 (~$150-200/month) validates product-market fit before committing to managed-service costs
- Microservices remain as separate Docker containers from day one, preserving the architecture
- Measurable triggers (CPU utilization, concurrent users, search latency) govern each phase transition
- Each phase adds infrastructure complexity only when user scale demands it

**Phases**:

| Phase | Name | ~Cost/mo | Compute | Search | Triggers to Next |
|-------|------|----------|---------|--------|------------------|
| 1 | Launch | $150-200 | EC2 t3.xlarge + Docker Compose | PostgreSQL FTS | CPU >70%, >200 concurrent users |
| 2 | Growth | $500-800 | ECS Fargate (1 task/svc) + ALB | PostgreSQL FTS | >1,000 users, search P95 >500ms |
| 3 | Scale | $2,300-2,900* | ECS Fargate (2 tasks/svc, HA) + Staging env | OpenSearch | >5,000 users, compliance needs |
| 4 | Full Prod | $2,400-2,900* | ECS auto-scaling + DR | OpenSearch cluster | Current doc target state |

*Phases 3-4 include a staging environment (~$570/mo). See [09-CostEstimate.md](../docs/09-CostEstimate.md) for detailed breakdowns.

**Trade-offs**:
- Phase 1 has a single point of failure (one EC2 instance) — acceptable for launch-stage traffic
- No staging environment until Phase 3 — testing relies on local Docker Compose and CI
- Manual SSH deployment in Phase 1 — replaced by ECS rolling deploys in Phase 2

### ADR-007: PostgreSQL FTS Initially
**Decision**: Use PostgreSQL full-text search with `tsvector`/GIN indexes for Phases 1-2 instead of OpenSearch
**Rationale**:
- Eliminates ~$29-400/month in OpenSearch costs during early phases
- PostgreSQL FTS supports weighted ranking, synonym dictionaries, and phrase search
- No additional infrastructure to operate — search queries run against the existing RDS instance
- Domain-specific synonym dictionary (1A→First Amendment, cop→police, etc.) provides equivalent UX for our vocabulary
- `SearchRepository` interface pattern allows transparent migration to OpenSearch in Phase 3

**Migration triggers to OpenSearch (Phase 3)**:
- Search query P95 latency exceeds 500ms
- Need for fuzzy matching, "did you mean" suggestions, or complex relevance tuning
- Search index size exceeds PostgreSQL comfortable range (~10 GB+)
- User base exceeds ~1,000 active users with heavy search usage
