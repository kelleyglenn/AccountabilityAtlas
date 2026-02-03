# Technical Requirements

## Performance Requirements

### Response Time Targets

| Operation Type | P50 Target | P95 Target | P99 Target |
|----------------|------------|------------|------------|
| Map tile loading | < 100ms | < 200ms | < 500ms |
| Video marker clustering | < 150ms | < 300ms | < 600ms |
| Video detail fetch | < 100ms | < 200ms | < 400ms |
| Search queries | < 200ms | < 400ms | < 800ms |
| User authentication | < 300ms | < 500ms | < 1000ms |
| Video submission | < 500ms | < 1000ms | < 2000ms |

### Throughput Requirements

| Metric | Phase 1 (Launch) | Phase 2 (Growth) | Phase 3 (Scale) | Phase 4 (Full Prod) |
|--------|-------------------|-------------------|-----------------|---------------------|
| Concurrent users | 200 | 500 | 2,000 | 5,000 |
| Requests per second | 50 | 200 | 1,000 | 2,000 |
| Video submissions/day | 25 | 100 | 500 | 1,000 |
| Search queries/day | 5,000 | 10,000 | 50,000 | 100,000 |

## Availability Requirements

Availability targets vary by deployment phase. Phase 1 accepts higher downtime risk in exchange for lower cost.

| Component | Phase 1 (Launch) | Phase 2 (Growth) | Phase 3-4 (Scale/Prod) |
|-----------|-------------------|-------------------|------------------------|
| Public API | 99.5% (~3.6 hr/mo) | 99.9% (~43 min/mo) | 99.9% (~43 min/mo) |
| Map display | 99.5% (~3.6 hr/mo) | 99.9% (~43 min/mo) | 99.9% (~43 min/mo) |
| Authentication | 99.5% (~3.6 hr/mo) | 99.9% (~43 min/mo) | 99.95% (~22 min/mo) |
| Admin functions | 99.0% (~7.3 hr/mo) | 99.5% (~3.6 hr/mo) | 99.5% (~3.6 hr/mo) |

## Scalability Requirements

### Horizontal Scaling
- All services must support horizontal scaling behind load balancers
- Stateless service design (session state in Redis)
- Database read replicas for read-heavy workloads

### Data Volume Projections

| Data Type | Year 1 | Year 3 | Year 5 |
|-----------|--------|--------|--------|
| Video records | 50,000 | 250,000 | 1,000,000 |
| User accounts | 10,000 | 100,000 | 500,000 |
| Location points | 75,000 | 400,000 | 1,500,000 |
| Search index size | 5 GB | 25 GB | 100 GB |

## Security Requirements

### Authentication
- Password complexity: minimum 8 characters, mixed case, numbers
- OAuth 2.0/OIDC for social login providers
- JWT tokens with 1-hour expiry, refresh token rotation
- Multi-factor authentication (future enhancement)

### Authorization
- Role-based access control (RBAC)
- Resource-level permissions for content ownership
- API rate limiting by user tier

### Data Protection
- TLS 1.3 for all data in transit
- AES-256 encryption for sensitive data at rest
- PII handling compliant with CCPA/GDPR principles
- No storage of external video content (YouTube links only)

### Infrastructure Security

Security controls scale with deployment phase:

| Control | Phase 1 (Launch) | Phase 2 (Growth) | Phase 3-4 (Scale/Prod) |
|---------|-------------------|-------------------|------------------------|
| Network isolation | Public subnet (EC2) + data subnet (RDS) | VPC with private subnets for ECS | Full VPC with public/private/data subnets |
| Endpoint protection | Nginx rate limiting | ALB + security groups | WAF + ALB + CloudFront |
| Secrets management | AWS Secrets Manager | AWS Secrets Manager | AWS Secrets Manager |
| TLS | Let's Encrypt (certbot) | ACM (ALB-terminated) | ACM (ALB + CloudFront) |
| Access control | Security groups (least-privilege) | Security groups | Security groups + WAF rules |

## Compliance Requirements

### Content Moderation
- User-submitted content moderation workflow
- Abuse reporting mechanism
- DMCA takedown process for copyright claims
- Community guidelines enforcement

### Legal Considerations
- Terms of Service acceptance
- Privacy Policy disclosure
- Cookie consent (for EU visitors)
- YouTube Terms of Service compliance (embedding/linking)

## Technology Constraints

### Required Technologies
| Layer | Technology | Rationale |
|-------|------------|-----------|
| Backend Language | Java 21 LTS (Amazon Corretto) | Team expertise, JVM ecosystem |
| Backend Framework | Spring Boot 3.2.x | Production-ready, extensive ecosystem |
| API Protocol | REST + OpenAPI 3.0 | Industry standard, tooling support |
| Primary Database | PostgreSQL 15 with PostGIS | Relational + spatial queries |
| Search Engine | PostgreSQL FTS (Phase 1-2), OpenSearch 2.x (Phase 3+) | Full-text + faceted search |
| Cache | Redis 7.x | Session, caching, rate limiting |
| Message Queue | Amazon SQS | Async processing, decoupling |
| Container Runtime | Docker 24.x | Consistent environments |
| Build Tool | Gradle 9.x | Build automation |
| Container Orchestration | Docker Compose (Phase 1), Amazon ECS Fargate (Phase 2+) | Container management |
| Cloud Provider | AWS | Team familiarity, service breadth |

### Frontend Technologies (Client Teams)
| Platform | Technology |
|----------|------------|
| Web | React/Next.js (recommendation) |
| iOS | Swift/SwiftUI |
| Android | Kotlin/Jetpack Compose |

## Integration Requirements

### External Services
| Service | Purpose | Integration Type |
|---------|---------|------------------|
| Google Maps Platform | Map display, geocoding | JavaScript SDK, REST API |
| YouTube Data API | Video metadata, thumbnails, validation | REST API |
| SendGrid/SES | Transactional email | REST API |
| OAuth Providers | Google, Apple login | OAuth 2.0/OIDC |

### External API Integration Patterns

All backend services calling external APIs must implement these patterns:

**Resilience**
- Circuit breakers to prevent cascade failures when external APIs are unavailable
- Retry with exponential backoff (max 3 retries, 1s/2s/4s delays)
- Timeouts: 5 seconds for metadata fetches, 10 seconds for bulk operations

**Caching**
- Cache external API responses to reduce quota usage and latency
- YouTube metadata: cache for 24 hours (title, description, channel rarely change)
- Geocoding results: cache for 30 days (addresses rarely change, allows eventual refresh)

**Rate Limiting**
- Implement client-side rate limiting to respect API quotas
- YouTube Data API: 10,000 units/day default quota
  - videos.list: 1 unit per call
  - Batch requests where possible to reduce quota consumption

**Fallback Behavior**
- Graceful degradation when external APIs are unavailable
- Return cached data if available, even if stale
- Queue failed requests for retry when service recovers

**Error Handling**
- Map external API errors to internal error responses
- Log external API failures with correlation IDs for debugging
- Alert on elevated external API error rates

### API Requirements
- RESTful API design following OpenAPI 3.0 specification
- JSON request/response format
- Versioned endpoints (v1, v2)
- Consistent error response format
- Pagination for list endpoints
- Rate limiting headers

## Operational Requirements

### Monitoring & Observability
- Centralized logging (CloudWatch Logs)
- Distributed tracing (Phase 3+: AWS X-Ray)
- Metrics collection (Phase 1: CloudWatch Agent; Phase 2+: CloudWatch Metrics, Prometheus)
- Alerting for SLA violations (Phase 1: basic CloudWatch alarms; Phase 2+: full alarm suite)
- Dashboard for system health

### Disaster Recovery

DR capabilities scale with deployment phase:

| Metric | Phase 1 (Launch) | Phase 2 (Growth) | Phase 3 (Scale) | Phase 4 (Full Prod) |
|--------|-------------------|-------------------|-----------------|---------------------|
| RPO | 24 hours | 4 hours | 1 hour | 1 hour |
| RTO | ~30 min (same AZ) | ~15 min (ECS redeploy) | 4 hours (cross-AZ) | 4 hours (cross-region) |
| Backups | RDS daily snapshots (7-day) | RDS daily + PITR | RDS + OpenSearch snapshots | All + cross-region replication |
| Redundancy | None (single EC2) | ECS task restart | Multi-AZ (RDS, ECS) | Multi-AZ + DR region |

### Deployment

Deployment strategy evolves with deployment phase:

| Aspect | Phase 1 (Launch) | Phase 2 (Growth) | Phase 3-4 (Scale/Prod) |
|--------|-------------------|-------------------|------------------------|
| Strategy | Docker Compose via SSH | ECS rolling deploy | Blue-green with canary |
| Downtime | Brief (~30s during redeploy) | Zero-downtime (rolling) | Zero-downtime |
| Rollback | Manual (previous image tag) | ECS task rollback | Automated (CodeDeploy) |
| Environments | Production only | Production only | Staging + Production |
| CI/CD | GitHub Actions → ECR → SSH | GitHub Actions → ECR → ECS | CodePipeline → CodeBuild → ECS |

> **Note**: Staging environment is deferred until Phase 3. During Phases 1-2, pre-production testing relies on local Docker Compose and CI pipeline checks.
