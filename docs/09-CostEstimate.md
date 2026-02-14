# Cost Estimate

This document provides monthly cost estimates for AccountabilityAtlas infrastructure across all deployment phases. Phase 1 is the current deployment.

**Pricing Region**: us-east-1 (N. Virginia)
**Pricing Date**: January 2025 (prices subject to change)
**Current Phase**: 1 (Launch)

---

## Summary by Phase

| Phase | Name | Monthly Cost | Notes |
|-------|------|-------------|-------|
| **1** | **Launch (Current)** | **~$162** | **EC2 + RDS free tier (~$179 after yr 1)** |
| 2 | Growth | ~$525 | ECS Fargate + ALB + ElastiCache |
| 3 | Scale | ~$2,335 (+ ~$570 staging) | OpenSearch + WAF + Multi-AZ |
| 4 | Full Prod | ~$2,370 (+ ~$570 staging) | Auto-scaling + DR (~$1,825 with RI) |
| — | External APIs | ~$0 | Mapbox free tier (all phases) |

*All phase estimates include 20% buffer except Phase 1 (exact pricing). See each phase section for detailed breakdowns.*

---

## Phase 1 Cost Breakdown (Current)

### Compute (EC2)

| Service | Instance | Pricing | Monthly Cost |
|---------|----------|---------|--------------|
| EC2 | t3.xlarge (4 vCPU, 16 GB) | On-Demand | $122.64 |

### Database (RDS PostgreSQL)

| Setting | Value | Year 1 Cost | After Year 1 |
|---------|-------|-------------|--------------|
| Instance | db.t4g.micro (2 vCPU, 1 GB) | **Free** (free tier) | $12.41 |
| Storage | 20 GB gp3 | **Free** (free tier) | $2.30 |
| Backup | 7-day retention | ~$1.40 | ~$1.40 |
| **Subtotal** | | **~$1.40** | **~$16.11** |

> **Note**: RDS db.t4g.micro includes 750 hours/month free for the first 12 months, plus 20 GB free storage. After year 1, costs increase by ~$15/month.

### Messaging (SQS)

| Usage | Monthly Cost |
|-------|--------------|
| ~500K requests/month | $0.20 |

### Other Services

| Service | Monthly Cost |
|---------|--------------|
| Route 53 (1 hosted zone + queries) | $0.50 |
| Secrets Manager (6 secrets) | $2.40 |
| ECR (5 GB images) | $0.50 |
| CloudWatch Logs (5 GB) | $2.50 |
| CloudWatch Alarms (6) | $0.60 |
| S3 (5 GB backups) | $0.12 |
| Elastic IP | $3.65 |
| **Subtotal** | **~$10.27** |

### Phase 1 Total

| Category | Year 1 Monthly | After Year 1 Monthly |
|----------|----------------|---------------------|
| Compute (EC2) | $122.64 | $122.64 |
| Database (RDS) | $1.40 | $16.11 |
| Messaging (SQS) | $0.20 | $0.20 |
| Other Services | $10.27 | $10.27 |
| **Total** | **~$135** | **~$149** |
| **Total + 20% buffer** | **~$162** | **~$179** |

**Not included in Phase 1** (deferred to later phases): ALB, NAT Gateway, ElastiCache, OpenSearch, CloudFront, WAF, X-Ray, CodePipeline, CodeBuild. Redis runs as a Docker container on the EC2 instance at no additional cost.

---

## External API Costs

### Mapbox

| API | Free Tier | Unit Price | Estimated Monthly Usage | Cost |
|-----|-----------|------------|-------------------------|------|
| Map Loads (Mapbox GL JS) | 50K/month free | $5.00/1K loads | 10K loads | $0 (within free tier) |
| Geocoding (forward + reverse) | 100K/month free | $0.75/1K requests | 5K requests | $0 (within free tier) |
| Search Box sessions | 1K/month free | $0.10/session | 500 sessions | $0 (within free tier) |

**Note**: Mapbox provides generous free tiers. At current usage levels, all map-related API costs are $0/month. Costs only begin when usage exceeds free tier thresholds.

**Estimated**: ~$0/month (Phase 1-2), review at Phase 3+ scale

#### Caching Strategy (Implemented)

Per [05-DataArchitecture.md](05-DataArchitecture.md), external API responses are cached in Redis to control costs as traffic grows:

| Cache | TTL | Benefit |
|-------|-----|---------|
| `extapi:geocode:{hash}` | 30 days | Same address lookups hit cache, not API |
| `extapi:reverse:{lat}:{lng}` | 30 days | Same coordinate lookups hit cache |

**Impact**: Caching ensures API costs remain within free tiers even as user traffic increases significantly.

### YouTube Data API

| Quota | Limit | Cost |
|-------|-------|------|
| Default | 10,000 units/day | Free |
| Overage | Request quota increase | Free (approval required) |

Per [05-DataArchitecture.md](05-DataArchitecture.md), YouTube metadata is cached at `extapi:youtube:{videoId}` with 24-hour TTL (95%+ cache hit rate expected).

**Estimated**: $0/month (caching keeps usage well within free tier)

---

## Phase 2 Cost Projection (Growth)

Triggered when Phase 1 capacity is exceeded. See [07-InfrastructureArchitecture.md](07-InfrastructureArchitecture.md#phase-1--phase-2-migration-triggers) for triggers.

| Category | Monthly Cost |
|----------|--------------|
| Compute (ECS Fargate, 1 task/svc) | $228 |
| Database (RDS db.t3.medium) | $60 |
| Cache (ElastiCache cache.t3.medium) | $49 |
| Networking (ALB + NAT Gateway) | $92 |
| Other Services | $15 |
| **Subtotal** | **$444** |
| **Buffer (20%)** | **$81** |
| **Total** | **~$525** |

**Key cost drivers vs Phase 1**: ECS Fargate compute (~$228 vs $123 EC2), ElastiCache (~$49 vs $0 containerized Redis), NAT Gateway (~$66).

---

## Phase 3 Cost Projection (Scale)

Triggered when PostgreSQL FTS or single-task ECS becomes a bottleneck. See [07-InfrastructureArchitecture.md](07-InfrastructureArchitecture.md#phase-2--phase-3-migration-triggers) for triggers.

### Production Environment

| Category | Monthly Cost |
|----------|--------------|
| Compute (ECS Fargate, 2 tasks/svc) | $456 |
| Database (RDS db.r6g.large, Multi-AZ) | $389 |
| Cache (ElastiCache cache.r6g.large, 2-node) | $391 |
| Search (OpenSearch r6g.large, 3-node) | $404 |
| Networking (ALB + NAT Gateway) | $169 |
| CDN (CloudFront) | $50 |
| Security (WAF) | $21 |
| Other Services (incl. X-Ray) | $66 |
| **Subtotal** | **$1,946** |
| **Buffer (20%)** | **$389** |
| **Total** | **~$2,335** |

> **Note**: Production compute at 2 tasks/svc is lower than Phase 4's auto-scaling baseline. Exact costs depend on traffic patterns.

### Staging Environment (Introduced in Phase 3)

At this user scale, changes should be validated before production. Staging is introduced:

| Category | Monthly Cost |
|----------|--------------|
| Compute (ECS Fargate, 2 tasks/svc) | $228 |
| Database (RDS db.t3.medium) | $60 |
| Cache (ElastiCache cache.t3.medium) | $49 |
| Search (OpenSearch t3.small.search) | $29 |
| Networking (ALB + NAT Gateway) | $92 |
| Other Services | $15 |
| **Subtotal** | **$473** |
| **Buffer (20%)** | **$95** |
| **Total** | **~$570** |

### Phase 3 Combined Total

| Environment | Monthly Cost |
|-------------|--------------|
| Production (with buffer) | ~$2,335 |
| Staging (with buffer) | ~$570 |
| **Total** | **~$2,905** |

---

## Phase 4 Cost Projection (Full Production)

The target-state infrastructure with auto-scaling, cross-region DR, and reserved instances.

### Production Environment

| Category | On-Demand | With Reserved Instances |
|----------|-----------|-------------------------|
| Compute (Fargate, auto-scaling baseline) | $485 | $485 |
| Database (RDS) | $389 | $249 |
| Cache (Redis) | $391 | $234 |
| Search (OpenSearch) | $404 | $247 |
| Networking | $169 | $169 |
| CDN (CloudFront) | $50 | $50 |
| Security (WAF) | $21 | $21 |
| Other Services | $66 | $66 |
| **Subtotal** | $1,975 | $1,521 |
| **Buffer (20%)** | $395 | $304 |
| **Total** | **~$2,370** | **~$1,825** |

### Staging Environment

Unchanged from Phase 3: **~$570/month**

### Phase 4 Combined Total

| Configuration | Production | Staging | Total |
|---------------|------------|---------|-------|
| On-Demand | ~$2,370 | ~$570 | **~$2,940** |
| With Reserved Instances | ~$1,825 | ~$570 | **~$2,395** |

---

## Annual Cost Summary

| Phase | Monthly | Annual | Notes |
|-------|---------|--------|-------|
| Phase 1 (Year 1) | ~$162 | ~$1,944 | Mapbox free tier covers API usage |
| Phase 1 (After Year 1) | ~$179 | ~$2,148 | Mapbox free tier covers API usage |
| Phase 2 | ~$525 | ~$6,300 | Mapbox free tier covers API usage |
| Phase 3 | ~$2,905 | ~$34,860 | Prod + staging, review Mapbox usage |
| Phase 4 (On-Demand) | ~$2,940 | ~$35,280 | Prod + staging |
| Phase 4 (Reserved) | ~$2,395 | ~$28,740 | Prod + staging |

**Savings with Reserved Instances (Phase 4)**: ~$6,500/year (18%)

---

## Cost Optimization Recommendations

### Phase 1 (Current)
1. **Leverage free tier**: RDS db.t4g.micro is free for 12 months — plan Phase 2 migration timing accordingly
2. **Monitor EC2 utilization**: Right-size if CPU stays below 40% (consider t3.large) or triggers Phase 2 if above 70%
3. **Set billing alerts**: Configure AWS Budgets at $200, $300, and $500 monthly thresholds
4. **Aggressive caching**: Redis caching for geocoding (30-day TTL) and YouTube metadata (24-hour TTL) keeps API costs stable (~$25/month) regardless of traffic growth. See [05-DataArchitecture.md](05-DataArchitecture.md) for cache key patterns.

### Phase 2+
5. **Use Spot instances for staging** Fargate tasks where interruption is acceptable (saves 70%)
6. **Purchase Reserved Instances** when committing to Phase 4 (saves ~$6,500/year for RDS, ElastiCache, OpenSearch)
7. **Right-size instances** based on actual utilization data collected during earlier phases

---

## Required Accounts and Payment Setup

| Service | Account Required | Payment Method |
|---------|------------------|----------------|
| AWS | AWS Account | Credit card or invoicing |
| Mapbox | Mapbox Account | Credit card (free tier available) |
| Google OAuth | Google Cloud Console | Free |
| Apple OAuth | Apple Developer Account | $99/year |
| GitHub | GitHub Organization | Free (public) or $4/user/month |
| Domain (accountabilityatlas.com) | Registrar | ~$12/year |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-01-31 | Claude | Initial cost estimate |
| 1.1 | 2025-01-31 | Claude | Document caching strategy, fix cost calculations, add subtotals |
| 2.0 | 2025-02-02 | Claude | Restructure around 4-phase deployment strategy, Phase 1 as current |
