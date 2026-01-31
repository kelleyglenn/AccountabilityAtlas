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
│  │   │PostgreSQL│   │  Redis   │   │OpenSearch│   │   SQS    │          │  │
│  │   │+ PostGIS │   │  Cache   │   │  Index   │   │  Queues  │          │  │
│  │   └──────────┘   └──────────┘   └──────────┘   └──────────┘          │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
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

### ADR-004: ECS Fargate over EKS
**Decision**: ECS Fargate for container orchestration
**Rationale**:
- Lower operational complexity than Kubernetes
- Sufficient for our scale and service count
- Serverless container management
- Native AWS integration

### ADR-005: YouTube Link-Only Model
**Decision**: Store YouTube links, not video content
**Rationale**:
- Avoids video hosting costs and complexity
- Respects YouTube's content policies
- Leverages YouTube's CDN and player
- Reduces legal/copyright liability
