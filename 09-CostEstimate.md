# Cost Estimate

This document provides detailed monthly cost estimates for AccountabilityAtlas infrastructure based on the configurations documented in [07-InfrastructureArchitecture.md](07-InfrastructureArchitecture.md).

**Pricing Region**: us-east-1 (N. Virginia)
**Pricing Date**: January 2025 (prices subject to change)

---

## Summary by Environment

| Environment | Monthly Cost (On-Demand) | With Reserved Instances |
|-------------|--------------------------|-------------------------|
| Development | ~$280 | N/A |
| Staging | ~$570 | N/A |
| Production | ~$2,370 | ~$1,825 |
| External APIs (with caching) | ~$25 | ~$25 |
| **Total** | **~$3,245** | **~$2,700** |

*All estimates include 20% buffer. Caching ensures external API costs remain stable as traffic grows - see [External API Costs](#external-api-costs).*

---

## Development Environment

### Compute (ECS Fargate)

| Service | Tasks | vCPU | Memory (GB) | Hours/Month | Cost |
|---------|-------|------|-------------|-------------|------|
| api-gateway | 1 | 0.5 | 1 | 730 | $18.98 |
| user-service | 1 | 0.5 | 1 | 730 | $18.98 |
| video-service | 1 | 0.5 | 1 | 730 | $18.98 |
| location-service | 1 | 0.5 | 1 | 730 | $18.98 |
| search-service | 1 | 0.5 | 1 | 730 | $18.98 |
| moderation-service | 1 | 0.25 | 0.5 | 730 | $9.49 |
| notification-service | 1 | 0.25 | 0.5 | 730 | $9.49 |

**Fargate Pricing**: $0.04048/vCPU-hour + $0.004445/GB-hour

**Subtotal**: ~$114/month

### Database (RDS PostgreSQL)

| Setting | Value | Monthly Cost |
|---------|-------|--------------|
| Instance | db.t3.small (2 vCPU, 2 GB) | $25.55 |
| Storage | 20 GB gp3 | $2.30 |
| Backup | 1 day retention | Included |

**Subtotal**: ~$28/month

### Cache (ElastiCache Redis)

| Setting | Value | Monthly Cost |
|---------|-------|--------------|
| Node Type | cache.t3.small | $24.82 |
| Nodes | 1 | - |

**Subtotal**: ~$25/month

### Networking

| Service | Monthly Cost |
|---------|--------------|
| ALB (hourly + minimal LCU) | $22.27 |
| NAT Gateway (1 AZ) | $32.85 |
| NAT Data Transfer (50 GB est.) | $2.25 |

**Subtotal**: ~$57/month

### Other Services

| Service | Monthly Cost |
|---------|--------------|
| Route 53 (1 hosted zone) | $0.50 |
| Secrets Manager (~10 secrets) | $4.00 |
| ECR (5 GB storage) | $0.50 |
| CloudWatch Logs (5 GB ingestion) | $2.50 |
| CloudWatch Alarms (5 alarms) | $0.50 |
| SQS (100K requests) | $0.04 |
| S3 (10 GB) | $0.23 |

**Subtotal**: ~$8/month

### Development Environment Total

| Category | Monthly Cost |
|----------|--------------|
| Compute (Fargate) | $114 |
| Database (RDS) | $28 |
| Cache (Redis) | $25 |
| Networking | $57 |
| Other Services | $8 |
| **Subtotal** | $232 |
| **Buffer (20%)** | $46 |
| **Total** | **~$280** |

---

## Staging Environment

### Compute (ECS Fargate)

| Service | Tasks | vCPU | Memory (GB) | Hours/Month | Cost |
|---------|-------|------|-------------|-------------|------|
| api-gateway | 2 | 0.5 | 1 | 1460 | $37.96 |
| user-service | 2 | 0.5 | 1 | 1460 | $37.96 |
| video-service | 2 | 0.5 | 1 | 1460 | $37.96 |
| location-service | 2 | 0.5 | 1 | 1460 | $37.96 |
| search-service | 2 | 0.5 | 1 | 1460 | $37.96 |
| moderation-service | 2 | 0.25 | 0.5 | 1460 | $18.98 |
| notification-service | 2 | 0.25 | 0.5 | 1460 | $18.98 |

**Subtotal**: ~$228/month

### Database (RDS PostgreSQL)

| Setting | Value | Monthly Cost |
|---------|-------|--------------|
| Instance | db.t3.medium (2 vCPU, 4 GB) | $51.10 |
| Storage | 50 GB gp3 | $5.75 |
| Backup | 7 day retention | ~$3.50 |
| Performance Insights | Enabled | Free (7-day retention) |

**Subtotal**: ~$60/month

### Cache (ElastiCache Redis)

| Setting | Value | Monthly Cost |
|---------|-------|--------------|
| Node Type | cache.t3.medium | $49.06 |
| Nodes | 1 | - |

**Subtotal**: ~$49/month

### Search (OpenSearch)

| Setting | Value | Monthly Cost |
|---------|-------|--------------|
| Instance | t3.small.search | $26.28 |
| Nodes | 1 | - |
| Storage | 20 GB | $2.54 |

**Subtotal**: ~$29/month

### Networking

| Service | Monthly Cost |
|---------|--------------|
| ALB | $22.27 |
| NAT Gateway (2 AZ) | $65.70 |
| NAT Data Transfer (100 GB) | $4.50 |

**Subtotal**: ~$92/month

### Other Services

| Service | Monthly Cost |
|---------|--------------|
| Route 53 | $0.50 |
| Secrets Manager | $4.00 |
| ECR (10 GB) | $1.00 |
| CloudWatch Logs (10 GB) | $5.00 |
| CloudWatch Alarms (10) | $1.00 |
| X-Ray (1M traces @ 5%) | $2.50 |
| SQS (500K requests) | $0.20 |
| S3 (25 GB) | $0.58 |

**Subtotal**: ~$15/month

### Staging Environment Total

| Category | Monthly Cost |
|----------|--------------|
| Compute (Fargate) | $228 |
| Database (RDS) | $60 |
| Cache (Redis) | $49 |
| Search (OpenSearch) | $29 |
| Networking | $92 |
| Other Services | $15 |
| **Subtotal** | $473 |
| **Buffer (20%)** | $95 |
| **Total** | **~$570** |

---

## Production Environment

### Compute (ECS Fargate)

Based on baseline 3 tasks per service (scales 2-10 based on load):

| Service | Tasks | vCPU | Memory (GB) | Hours/Month | Cost |
|---------|-------|------|-------------|-------------|------|
| api-gateway | 3 | 0.5 | 1 | 2190 | $56.94 |
| user-service | 3 | 0.5 | 1 | 2190 | $56.94 |
| video-service | 3 | 0.5 | 1 | 2190 | $56.94 |
| location-service | 3 | 0.5 | 1 | 2190 | $56.94 |
| search-service | 3 | 0.5 | 1 | 2190 | $56.94 |
| moderation-service | 2 | 0.25 | 0.5 | 1460 | $18.98 |
| notification-service | 2 | 0.25 | 0.5 | 1460 | $18.98 |

**Subtotal**: ~$323/month (baseline, add 50% for auto-scaling headroom = ~$485)

### Database (RDS PostgreSQL)

| Setting | Value | Monthly Cost (On-Demand) | Reserved (1yr) |
|---------|-------|--------------------------|----------------|
| Primary Instance | db.r6g.large (2 vCPU, 16 GB) | $175.20 | $105.12 |
| Read Replica | db.r6g.large | $175.20 | $105.12 |
| Storage | 100 GB gp3 | $11.50 | $11.50 |
| Multi-AZ | Enabled | Included in instance | - |
| Backup | 30 day retention | ~$15.00 | $15.00 |
| Cross-Region Backup | 7 days to us-west-2 | ~$12.00 | $12.00 |
| Performance Insights | Enabled | Free | Free |

**Subtotal**: ~$389/month on-demand, ~$249/month reserved

### Cache (ElastiCache Redis)

| Setting | Value | Monthly Cost (On-Demand) | Reserved (1yr) |
|---------|-------|--------------------------|----------------|
| Node Type | cache.r6g.large | $195.26 | $117.16 |
| Nodes | 2 (cluster) | $390.52 | $234.32 |
| Multi-AZ | Enabled | Included | - |

**Subtotal**: ~$391/month on-demand, ~$234/month reserved

### Search (OpenSearch)

| Setting | Value | Monthly Cost (On-Demand) | Reserved (1yr) |
|---------|-------|--------------------------|----------------|
| Instance | r6g.large.search | $130.34 | $78.20 |
| Nodes | 3 | $391.02 | $234.60 |
| Storage | 100 GB (across nodes) | $12.70 | $12.70 |

**Subtotal**: ~$404/month on-demand, ~$247/month reserved

### Networking

| Service | Monthly Cost |
|---------|--------------|
| ALB | $22.27 |
| ALB LCU (est. 10 LCU avg) | $58.40 |
| NAT Gateway (2 AZ) | $65.70 |
| NAT Data Transfer (500 GB) | $22.50 |

**Subtotal**: ~$169/month

### CDN (CloudFront)

| Usage | Monthly Cost |
|-------|--------------|
| Data Transfer (500 GB) | $42.50 |
| Requests (10M) | $7.50 |

**Subtotal**: ~$50/month

### Security (WAF)

| Component | Monthly Cost |
|-----------|--------------|
| Web ACL | $5.00 |
| Rules (10) | $10.00 |
| Requests (10M) | $6.00 |

**Subtotal**: ~$21/month

### Other Services

| Service | Monthly Cost |
|---------|--------------|
| Route 53 (queries) | $2.00 |
| Secrets Manager | $4.00 |
| ECR (20 GB) | $2.00 |
| CloudWatch Logs (50 GB) | $25.00 |
| CloudWatch Metrics | $3.00 |
| CloudWatch Alarms (20) | $2.00 |
| CloudWatch Dashboards (3) | $9.00 |
| X-Ray (5M traces @ 5%) | $12.50 |
| SQS (5M requests) | $2.00 |
| S3 (50 GB + DR replication) | $3.00 |
| SES (10K emails) | $1.00 |

**Subtotal**: ~$66/month

### Production Environment Total

| Category | On-Demand | With Reserved Instances |
|----------|-----------|-------------------------|
| Compute (Fargate) | $485 | $485 |
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

---

## External API Costs

### Google Maps Platform

| API | Free Tier | Unit Price | Estimated Monthly Usage | Cost |
|-----|-----------|------------|-------------------------|------|
| Maps JavaScript | $200 credit | $7.00/1K loads | 10K loads | $70 - $200 credit = $0 |
| Geocoding | $200 credit | $5.00/1K requests | 5K requests | $25 |
| Places Autocomplete | $200 credit | $2.83/1K requests | 2K requests | $6 |

**Note**: Google provides $200/month free credit. Light usage stays within free tier.

**Estimated**: ~$25/month

#### Caching Strategy (Implemented)

Per [05-DataArchitecture.md](05-DataArchitecture.md), external API responses are cached in Redis to control costs as traffic grows:

| Cache | TTL | Benefit |
|-------|-----|---------|
| `extapi:geocode:{hash}` | 30 days | Same address lookups hit cache, not API |
| `extapi:reverse:{lat}:{lng}` | 30 days | Same coordinate lookups hit cache |

**Impact**: Caching ensures API costs remain stable (~$25/month) even as user traffic increases significantly. Without caching, costs would scale linearly with usage and quickly exceed the free tier.

### YouTube Data API

| Quota | Limit | Cost |
|-------|-------|------|
| Default | 10,000 units/day | Free |
| Overage | Request quota increase | Free (approval required) |

Per [05-DataArchitecture.md](05-DataArchitecture.md), YouTube metadata is cached at `extapi:youtube:{videoId}` with 24-hour TTL (95%+ cache hit rate expected).

**Estimated**: $0/month (caching keeps usage well within free tier)

---

## Annual Cost Summary

### Year 1 Costs (All Environments)

| Item | Monthly | Annual |
|------|---------|--------|
| Development | $350 | $4,200 |
| Staging | $700 | $8,400 |
| Production (On-Demand) | $2,370 | $28,440 |
| Google Maps (with caching) | $25 | $300 |
| **Total (On-Demand)** | **$3,445** | **$41,340** |

### Year 1 Costs (With Reserved Instances)

| Item | Monthly | Annual |
|------|---------|--------|
| Development | $350 | $4,200 |
| Staging | $700 | $8,400 |
| Production (Reserved) | $1,825 | $21,900 |
| Google Maps (with caching) | $25 | $300 |
| **Total** | **$2,900** | **$34,800** |

**Savings with Reserved Instances**: ~$6,500/year (16%)

*Note: Caching keeps Google Maps costs stable at ~$25/month regardless of traffic growth.*

---

## Cost Scaling Projections

Based on documented growth targets:

| Metric | Year 1 | Year 3 | Year 5 |
|--------|--------|--------|--------|
| Concurrent Users | 500 | 5,000 | 50,000 |
| Estimated Monthly Cost | $3,000 | $8,000 | $25,000 |

**Note**: Costs scale sub-linearly due to:
- Reserved instance discounts at scale
- More efficient resource utilization
- Caching reduces API calls

---

## Cost Optimization Recommendations

1. **Purchase Reserved Instances** for production RDS, ElastiCache, and OpenSearch (saves ~$6,500/year)

2. **Shut down dev environment** outside business hours (saves ~$150/month)

3. **Use Spot instances for staging** Fargate tasks where interruption is acceptable (saves 70%)

4. **Aggressive caching implemented** - Redis caching for geocoding (30-day TTL) and YouTube metadata (24-hour TTL) keeps API costs stable (~$25/month) regardless of traffic growth. See [05-DataArchitecture.md](05-DataArchitecture.md) for cache key patterns.

5. **Right-size instances** based on actual utilization after launch

6. **Set up billing alerts** at $3,000, $4,000, and $5,000 monthly thresholds

---

## Required Accounts and Payment Setup

| Service | Account Required | Payment Method |
|---------|------------------|----------------|
| AWS | AWS Account | Credit card or invoicing |
| Google Cloud (Maps) | Google Cloud Project | Credit card |
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
