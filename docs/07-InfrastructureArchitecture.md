# Infrastructure Architecture

## Cloud Platform

**Primary Region**: us-east-1 (N. Virginia)
**DR Region**: us-west-2 (Oregon) — Phase 4
**Cloud Provider**: Amazon Web Services (AWS)
**Current Phase**: 1 (Launch)

---

## Deployment Phases Overview

Infrastructure scales incrementally across 4 phases. Each phase is triggered by measurable thresholds, not calendar dates.

| Phase | Name | ~Cost/mo | Compute | Search | Key Additions |
|-------|------|----------|---------|--------|---------------|
| **1** | **Launch** | **$150-200** | **EC2 t3.xlarge + Docker Compose** | **PostgreSQL FTS** | **RDS, SQS, CloudWatch** |
| 2 | Growth | $500-800 | ECS Fargate (1 task/svc) + ALB | PostgreSQL FTS | ALB, NAT Gateway, private subnets |
| 3 | Scale | $2,300-2,900* | ECS Fargate (2 tasks/svc, HA) + Staging | OpenSearch | OpenSearch, WAF, X-Ray, Multi-AZ, staging env |
| 4 | Full Prod | $2,400-2,900* | ECS auto-scaling + DR | OpenSearch cluster | Cross-region DR, reserved instances, blue-green canary |

*Phases 3-4 include a staging environment (~$570/mo). See [09-CostEstimate.md](09-CostEstimate.md) for detailed breakdowns.

See [ADR-006: Phased Deployment Strategy](03-ArchitectureOverview.md#adr-006-phased-deployment-strategy) for rationale.

---

## Phase 1 — Current Deployment (Launch)

### AWS Service Inventory (Phase 1)

| Service | Purpose |
|---------|---------|
| EC2 (t3.xlarge) | Docker host for all containers |
| RDS PostgreSQL | Primary database |
| SQS | Message queuing |
| S3 | Backups, static assets |
| Route 53 | DNS |
| ECR | Container registry |
| CloudWatch | Logging, monitoring |
| Secrets Manager | Secrets storage |

### Environment Topology

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       PRODUCTION (us-east-1)                                  │
│                                                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │                    EC2 t3.xlarge (4 vCPU, 16 GB)                     │    │
│  │                                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────────┐     │    │
│  │  │                     Docker Compose                           │     │    │
│  │  │                                                              │     │    │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │     │    │
│  │  │  │  nginx   │ │api-gw   │ │user-svc │ │video-svc│          │     │    │
│  │  │  │ :80/:443│ │  :8080  │ │  :8081  │ │  :8082  │          │     │    │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │     │    │
│  │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │     │    │
│  │  │  │location │ │ search  │ │mod-svc  │ │notif-svc│          │     │    │
│  │  │  │  :8083  │ │  :8084  │ │  :8085  │ │  :8086  │          │     │    │
│  │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘          │     │    │
│  │  │  ┌─────────┐ ┌─────────┐                                   │     │    │
│  │  │  │ web-app │ │  redis  │                                   │     │    │
│  │  │  │  :3000  │ │  :6379  │                                   │     │    │
│  │  │  └─────────┘ └─────────┘                                   │     │    │
│  │  └─────────────────────────────────────────────────────────────┘     │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                              │                                                │
│                              ▼                                                │
│  ┌────────────────┐    ┌──────────┐    ┌──────────┐                          │
│  │  RDS PostgreSQL│    │   SQS    │    │    S3    │                          │
│  │ db.t4g.micro   │    │  Queues  │    │ Backups  │                          │
│  │ (2 vCPU, 1 GB) │    └──────────┘    └──────────┘                          │
│  └────────────────┘                                                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Docker Compose Configuration

```yaml
# docker-compose.prod.yml
version: "3.8"

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/certs:/etc/letsencrypt:ro
    depends_on:
      - api-gateway
      - web-app
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 256M
    restart: always

  api-gateway:
    image: ${ECR_REGISTRY}/acct-atlas-api-gateway:${TAG}
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    deploy:
      resources:
        limits:
          cpus: "0.50"
          memory: 1024M
    restart: always

  user-service:
    image: ${ECR_REGISTRY}/acct-atlas-user-service:${TAG}
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    deploy:
      resources:
        limits:
          cpus: "0.50"
          memory: 1024M
    restart: always

  video-service:
    image: ${ECR_REGISTRY}/acct-atlas-video-service:${TAG}
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    deploy:
      resources:
        limits:
          cpus: "0.50"
          memory: 1024M
    restart: always

  location-service:
    image: ${ECR_REGISTRY}/acct-atlas-location-service:${TAG}
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    deploy:
      resources:
        limits:
          cpus: "0.50"
          memory: 1024M
    restart: always

  search-service:
    image: ${ECR_REGISTRY}/acct-atlas-search-service:${TAG}
    environment:
      - SPRING_PROFILES_ACTIVE=prod,fts
    deploy:
      resources:
        limits:
          cpus: "0.50"
          memory: 1024M
    restart: always

  moderation-service:
    image: ${ECR_REGISTRY}/acct-atlas-moderation-service:${TAG}
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 512M
    restart: always

  notification-service:
    image: ${ECR_REGISTRY}/acct-atlas-notification-service:${TAG}
    environment:
      - SPRING_PROFILES_ACTIVE=prod
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 512M
    restart: always

  web-app:
    image: ${ECR_REGISTRY}/acct-atlas-web-app:${TAG}
    environment:
      - NODE_ENV=production
    deploy:
      resources:
        limits:
          cpus: "0.50"
          memory: 1024M
    restart: always

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    deploy:
      resources:
        limits:
          cpus: "0.15"
          memory: 640M
    restart: always

volumes:
  redis-data:
```

#### Resource Allocation Summary

| Container | CPU Limit | Memory Limit |
|-----------|-----------|-------------|
| nginx | 0.25 vCPU | 256 MB |
| api-gateway | 0.50 vCPU | 1,024 MB |
| user-service | 0.50 vCPU | 1,024 MB |
| video-service | 0.50 vCPU | 1,024 MB |
| location-service | 0.50 vCPU | 1,024 MB |
| search-service | 0.50 vCPU | 1,024 MB |
| moderation-service | 0.25 vCPU | 512 MB |
| notification-service | 0.25 vCPU | 512 MB |
| web-app | 0.50 vCPU | 1,024 MB |
| redis | 0.15 vCPU | 640 MB |
| **Total** | **~3.90 vCPU** | **~7,040 MB** |

The t3.xlarge instance (4 vCPU, 16 GB RAM) provides headroom for the OS, Docker daemon, and CloudWatch agent beyond container limits.

### Nginx Reverse Proxy

```nginx
# nginx/nginx.conf
events {
    worker_connections 1024;
}

http {
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=general:10m rate=30r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/s;

    upstream api_gateway {
        server api-gateway:8080;
    }

    upstream web_app {
        server web-app:3000;
    }

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name accountabilityatlas.com www.accountabilityatlas.com;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        server_name accountabilityatlas.com www.accountabilityatlas.com;

        ssl_certificate /etc/letsencrypt/live/accountabilityatlas.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/accountabilityatlas.com/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_prefer_server_ciphers on;

        # API routes
        location /api/ {
            limit_req zone=general burst=20 nodelay;
            proxy_pass http://api_gateway;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Auth routes (stricter rate limiting)
        location /api/v1/auth/ {
            limit_req zone=auth burst=5 nodelay;
            proxy_pass http://api_gateway;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Web application (everything else)
        location / {
            limit_req zone=general burst=20 nodelay;
            proxy_pass http://web_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

### TLS Configuration

Phase 1 uses Let's Encrypt with certbot for free TLS certificates:

```bash
# Initial certificate request (run on EC2 instance)
sudo certbot certonly --standalone -d accountabilityatlas.com -d www.accountabilityatlas.com

# Auto-renewal via cron (certbot installs this automatically)
# 0 0,12 * * * certbot renew --quiet --deploy-hook "docker compose restart nginx"
```

### Database Configuration

| Setting | Phase 1 Value |
|---------|---------------|
| Instance | db.t4g.micro (2 vCPU, 1 GB) |
| Storage | 20 GB gp3 |
| Multi-AZ | No |
| Read Replicas | 0 |
| Backup Retention | 7 days |
| PITR | Disabled |
| Performance Insights | Disabled |
| Extensions | postgis, temporal_tables |

> **Note**: db.t4g.micro is included in the RDS free tier for the first 12 months. See [09-CostEstimate.md](09-CostEstimate.md) for cost implications.

### Redis Configuration

Phase 1 runs Redis as a Docker container (not ElastiCache) to minimize cost:

| Setting | Value |
|---------|-------|
| Image | redis:7-alpine |
| Max Memory | 512 MB |
| Eviction Policy | allkeys-lru |
| Persistence | RDB snapshots to container volume |
| Backup | Not required (cache only — rebuilds on restart) |

### Networking

#### Simplified VPC (Phase 1)

```
VPC CIDR: 10.0.0.0/16

Subnets:
├── Public (EC2 instance)
│   └── us-east-1a: 10.0.1.0/24
└── Data (RDS)
    └── us-east-1a: 10.0.20.0/24
    └── us-east-1b: 10.0.21.0/24  (required for RDS subnet group)
```

No NAT Gateway, no private subnets, no ALB. The EC2 instance sits in a public subnet with a public IP. RDS sits in a data subnet accessible only from the EC2 security group.

#### DNS Configuration (Route 53)

| Record | Type | Value |
|--------|------|-------|
| accountabilityatlas.com | A | EC2 Elastic IP |
| www.accountabilityatlas.com | CNAME | accountabilityatlas.com |

### Security Groups

**EC2 Security Group** (`sg-ec2-web`):

| Direction | Protocol | Port | Source | Description |
|-----------|----------|------|--------|-------------|
| Inbound | TCP | 80 | 0.0.0.0/0 | HTTP (redirect to HTTPS) |
| Inbound | TCP | 443 | 0.0.0.0/0 | HTTPS |
| Inbound | TCP | 22 | Admin IP | SSH (deployment, maintenance) |
| Outbound | All | All | 0.0.0.0/0 | Internet access |

**RDS Security Group** (`sg-rds`):

| Direction | Protocol | Port | Source | Description |
|-----------|----------|------|--------|-------------|
| Inbound | TCP | 5432 | sg-ec2-web | PostgreSQL from EC2 only |

### Infrastructure as Code

Phase 1 infrastructure is provisioned and managed with **OpenTofu** (open-source Terraform fork, MPL 2.0 license). Configuration lives in `AccountabilityAtlas/infra/`.

| Component | Details |
|-----------|---------|
| Tool | OpenTofu |
| Config location | `AccountabilityAtlas/infra/` (top-level repo) |
| State backend | S3 bucket + DynamoDB lock table |
| CI execution | GitHub Actions — `tofu plan` on PR, `tofu apply` on merge |
| AWS authentication | GitHub Actions OIDC federation (no stored credentials) |

OpenTofu manages: VPC, subnets, security groups, EC2, RDS, ECR, SQS, S3, Route 53, Secrets Manager, CloudWatch alarms, and IAM roles.

### CI/CD Pipeline

Phase 1 uses GitHub Actions for CI and SSH-based deployment. Deployment is triggered after integration tests pass on master:

```
┌──────────┐    ┌───────────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  PR      │───▶│  Per-service  │───▶│ Merge to │───▶│Integ.    │───▶│  Deploy  │
│  opened  │    │  CI (check)   │    │  master  │    │tests pass│    │  to EC2  │
└──────────┘    └───────────────┘    └──────────┘    └──────────┘    └──────────┘
                                                           │
                                                     ┌─────┴─────┐
                                                     ▼           ▼
                                                ┌────────┐  ┌─────────┐
                                                │API tests│  │E2E tests│
                                                │(Playwrt)│  │(browser)│
                                                └────────┘  └─────────┘
```

**Deployment flow:**
1. Each service repo has a `check.yaml` workflow (unit tests, service tests, formatting, static analysis)
2. PRs are merged to master after per-service CI passes
3. Integration tests (`AcctAtlas-integration-tests`) run against master — triggered by merge or manual `workflow_dispatch`
4. On integration test success → deploy workflow builds images, pushes to ECR, deploys via SSH to EC2

#### GitHub Actions Deploy Workflow

```yaml
# .github/workflows/deploy.yml (top-level repo)
name: Deploy

on:
  workflow_run:
    workflows: ["Integration Tests"]
    types: [completed]
    branches: [master]

permissions:
  id-token: write   # OIDC
  contents: read

env:
  AWS_REGION: us-east-1

jobs:
  deploy:
    if: ${{ github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ${{ env.AWS_REGION }}
      - uses: aws-actions/amazon-ecr-login@v2
      # Build and push all service images to ECR
      # SSH to EC2, pull new images, docker compose up -d
      # Wait for health checks
```

> **Note**: The deploy workflow above is a template. Full implementation will include building all service images, pushing to ECR, and SSH-based deployment with health checks. AWS authentication uses OIDC federation — no long-lived access keys stored as GitHub secrets.

### Secrets Management

All secrets are stored in AWS Secrets Manager, never in git:

| Secret | Used By | Notes |
|--------|---------|-------|
| JWT RSA key pair | user-service | Loaded via Spring config property, injected as env var from Secrets Manager |
| Database password | All services | RDS master password |
| Mapbox access token | web-app | Client-side map rendering |
| YouTube API key | video-service | Metadata fetching |
| Admin password hash | user-service | Initial admin account setup (ApplicationRunner) |

Services consume secrets as **environment variables** injected at the container level — no AWS SDK code in application services. See [JWT key stability](#jwt-key-stability) below.

### Seed Data

**Admin account:** The user-service includes an `ApplicationRunner` that checks for `ADMIN_EMAIL` and `ADMIN_PASSWORD_HASH` environment variables on startup. If an admin account doesn't exist, it creates one. In AWS, these values come from Secrets Manager. Locally, the existing dev seed data (`db/devdata/R__dev_seed_users.sql`) continues to work unchanged.

**Bulk video data:** A checked-in seed script (`scripts/seed-videos.sh`) reads a local data file (`seed-data/videos.json`, gitignored) and submits videos via the API, authenticating as admin. Run manually as needed — e.g., once after initial deployment or after a database reset. The data file contains only public information (YouTube URLs, coordinates) but is kept out of git to avoid committing personal curation choices.

### JWT Key Stability

The user-service currently generates a new RSA key pair on every startup, invalidating existing access tokens. For production:

- The `JwtConfig` bean reads the RSA private key from a Spring configuration property (`app.jwt.private-key`)
- In the `prod` profile, this property is populated from an environment variable sourced from Secrets Manager
- In `local`/`docker` profiles, the property is absent and the existing auto-generation behavior continues
- Key rotation: store a new key with a new `kid` in Secrets Manager, deploy — the JWKS endpoint exposes both keys during the transition window, and old tokens validate against the old key until they expire

This approach is **vendor-neutral** — the application code has no AWS dependencies. The container runtime (ECS or Docker Compose with env file) handles the Secrets Manager integration.

### Monitoring

Phase 1 uses the CloudWatch Agent on the EC2 instance for basic monitoring:

#### CloudWatch Alarms

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| EC2 High CPU | CPUUtilization | >70% for 10 min | Email notification |
| EC2 High Memory | mem_used_percent (CW Agent) | >80% for 10 min | Email notification |
| EC2 Low Disk | disk_used_percent (CW Agent) | >85% | Email notification |
| RDS High CPU | CPUUtilization | >80% for 10 min | Email notification |
| SQS Queue Depth | ApproximateNumberOfMessages | >1,000 | Email notification |
| EC2 Status Check | StatusCheckFailed | >0 for 5 min | EC2 auto-recover |

> **Note**: The EC2 High CPU alarm at 70% also serves as a **Phase 2 migration trigger**. Sustained CPU above 70% indicates the single instance is approaching capacity.

#### Application Logging

All containers log to stdout/stderr. Docker's `awslogs` log driver forwards logs to CloudWatch Logs:

```yaml
# Added to each service in docker-compose.prod.yml
logging:
  driver: awslogs
  options:
    awslogs-region: us-east-1
    awslogs-group: /accountabilityatlas/prod
    awslogs-stream-prefix: ${SERVICE_NAME}
```

### Backup and Disaster Recovery

| Resource | Backup Type | Frequency | Retention |
|----------|-------------|-----------|-----------|
| RDS | Automated snapshot | Daily | 7 days |
| EC2 | Manual AMI | Before major changes | 2 most recent |
| Docker Compose config | Git repository | Every commit | Indefinite |

**Recovery procedures**:
- **Service failure**: `docker compose up -d` restarts failed containers (automatic via `restart: always`)
- **EC2 failure**: Launch new instance from AMI, pull latest images from ECR, start Docker Compose (~30 min RTO)
- **Database failure**: Restore from RDS snapshot (~15 min RTO)
- **Full recovery**: Launch EC2 from AMI + restore RDS snapshot (~30 min RTO, same AZ)

### Phase 1 → Phase 2 Migration Triggers

Migrate to Phase 2 (ECS Fargate) when **any** of these thresholds are sustained:

| Trigger | Threshold | Measurement |
|---------|-----------|-------------|
| EC2 CPU utilization | >70% sustained for 1 week | CloudWatch metric |
| Concurrent users | >200 | Application metrics |
| Need for zero-downtime deploys | Business requirement | Manual assessment |
| Single point of failure unacceptable | Business requirement | Manual assessment |

---

## Phase 2 — Growth

### Migration Triggers (from Phase 1)
See [Phase 1 → Phase 2 Migration Triggers](#phase-1--phase-2-migration-triggers) above.

### Key Changes from Phase 1

| Component | Phase 1 | Phase 2 |
|-----------|---------|---------|
| Compute | EC2 t3.xlarge + Docker Compose | ECS Fargate (1 task per service) |
| Load Balancer | Nginx on EC2 | Application Load Balancer (ALB) |
| Redis | Docker container | ElastiCache (cache.t3.medium) |
| Network | Public subnet only | VPC with public/private/data subnets + NAT Gateway |
| TLS | Let's Encrypt | ACM (ALB-terminated) |
| Deployment | SSH pull | ECS rolling deployment |
| Search | PostgreSQL FTS | PostgreSQL FTS (unchanged) |

### AWS Services Added

| Service | Purpose |
|---------|---------|
| ECS Fargate | Container orchestration |
| ALB | Load balancing, health checks |
| ElastiCache Redis | Managed cache (cache.t3.medium) |
| NAT Gateway | Outbound internet for private subnets |
| ACM | Managed TLS certificates |

### ECS Task Definitions

| Service | CPU | Memory | Port | Health Check |
|---------|-----|--------|------|--------------|
| api-gateway | 512 | 1024 | 8080 | /actuator/health |
| user-service | 512 | 1024 | 8081 | /actuator/health |
| video-service | 512 | 1024 | 8082 | /actuator/health |
| location-service | 512 | 1024 | 8083 | /actuator/health |
| search-service | 512 | 1024 | 8084 | /actuator/health |
| moderation-service | 256 | 512 | 8085 | /actuator/health |
| notification-service | 256 | 512 | 8086 | /actuator/health |
| web-app | 512 | 1024 | 3000 | /api/health |

### VPC Configuration

```
VPC CIDR: 10.0.0.0/16

Subnets:
├── Public (NAT Gateway, ALB)
│   ├── us-east-1a: 10.0.1.0/24
│   └── us-east-1b: 10.0.2.0/24
├── Private (ECS Services)
│   ├── us-east-1a: 10.0.10.0/24
│   └── us-east-1b: 10.0.11.0/24
└── Data (RDS, ElastiCache)
    ├── us-east-1a: 10.0.20.0/24
    └── us-east-1b: 10.0.21.0/24
```

### DNS Configuration (Route 53)

| Record | Type | Value |
|--------|------|-------|
| accountabilityatlas.com | A | ALB |
| api.accountabilityatlas.com | A | ALB |

### Database Configuration

| Setting | Phase 2 Value |
|---------|---------------|
| Instance | db.t3.medium (2 vCPU, 4 GB) |
| Storage | 50 GB gp3 |
| Multi-AZ | No |
| Read Replicas | 0 |
| Backup Retention | 7 days |
| PITR | Enabled |

### Phase 2 → Phase 3 Migration Triggers

| Trigger | Threshold | Measurement |
|---------|-----------|-------------|
| Active registered users | >1,000 | Application metrics |
| Search P95 latency | >500ms | CloudWatch / application metrics |
| Need for staging environment | Business/compliance requirement | Manual assessment |
| Need for fuzzy search / "did you mean" | Feature requirement | Manual assessment |

---

## Phase 3 — Scale

### Migration Triggers (from Phase 2)
See [Phase 2 → Phase 3 Migration Triggers](#phase-2--phase-3-migration-triggers) above.

### Key Changes from Phase 2

| Component | Phase 2 | Phase 3 |
|-----------|---------|---------|
| ECS tasks | 1 per service | 2 per service (HA) |
| Search | PostgreSQL FTS | OpenSearch (t3.small.search) |
| Database | db.t3.medium, single-AZ | db.r6g.large, Multi-AZ |
| Redis | cache.t3.medium, single node | cache.r6g.large, 2-node cluster |
| Security | ALB + security groups | ALB + WAF + security groups |
| Tracing | None | AWS X-Ray |
| Environments | Production only | **Staging + Production** |

### AWS Services Added

| Service | Purpose |
|---------|---------|
| OpenSearch Service | Full-text search (replaces PostgreSQL FTS) |
| WAF | Web application firewall |
| X-Ray | Distributed tracing |
| CloudFront | CDN for static assets |

### Staging Environment

At this user scale, changes should be validated before production. A staging environment is introduced:

```
┌─────────────────────────────────────────────────────────────┐
│                   STAGING (us-east-1)                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                 ECS Cluster (staging)                 │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │   │
│  │  │api-gw   │ │user-svc │ │video-svc│ │location │    │   │
│  │  │(2 tasks)│ │(2 tasks)│ │(2 tasks)│ │(2 tasks)│    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                │   │
│  │  │search   │ │mod-svc  │ │notif-svc│                │   │
│  │  │(2 tasks)│ │(2 tasks)│ │(2 tasks)│                │   │
│  │  └─────────┘ └─────────┘ └─────────┘                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │RDS Postgres │  │ ElastiCache │  │  OpenSearch │         │
│  │db.t3.medium │  │cache.t3.med │  │t3.small.srch│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘

Note: Instance types abbreviated. Full names: cache.t3.medium, t3.small.search
```

### OpenSearch Configuration

| Setting | Staging | Production |
|---------|---------|------------|
| Instance | t3.small.search | r6g.large.search |
| Nodes | 1 | 3 |
| Storage | 20 GB | 100 GB |
| Encryption | Yes | Yes |
| Fine-grained Access | Yes | Yes |

### Database Configuration

| Setting | Staging | Production |
|---------|---------|------------|
| Instance | db.t3.medium | db.r6g.large |
| Storage | 50 GB | 100 GB |
| Multi-AZ | No | Yes |
| Read Replicas | 0 | 1 |
| Backup Retention | 7 days | 30 days |
| PITR | Enabled | Enabled |
| Performance Insights | Enabled | Enabled |

### ElastiCache Redis

| Setting | Staging | Production |
|---------|---------|------------|
| Node Type | cache.t3.medium | cache.r6g.large |
| Nodes | 1 | 2 (cluster) |
| Multi-AZ | No | Yes |
| Encryption at Rest | Yes | Yes |
| Encryption in Transit | Yes | Yes |

### Phase 3 → Phase 4 Migration Triggers

| Trigger | Threshold | Measurement |
|---------|-----------|-------------|
| Active registered users | >5,000 | Application metrics |
| Need for cross-region DR | Compliance/business requirement | Manual assessment |
| Need for auto-scaling | Sustained traffic spikes | CloudWatch metrics |

---

## Phase 4 — Full Production

### Migration Triggers (from Phase 3)
See [Phase 3 → Phase 4 Migration Triggers](#phase-3--phase-4-migration-triggers) above.

### Key Changes from Phase 3

| Component | Phase 3 | Phase 4 |
|-----------|---------|---------|
| ECS scaling | Fixed 2 tasks/svc | Auto-scaling (min 2, max 10) |
| DR | Single region | Cross-region (us-west-2) |
| Deployment | Rolling | Blue-green with canary |
| CI/CD | GitHub Actions → ECS | CodePipeline → CodeBuild → ECS |
| Cost optimization | On-demand | Reserved instances |

### Production Environment

```
┌─────────────────────────────────────────────────────────────┐
│                  PRODUCTION (us-east-1)                      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                        ALB                            │   │
│  │            (Application Load Balancer)                │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                              │                               │
│  ┌──────────────────────────┼───────────────────────────┐   │
│  │                 ECS Cluster (prod)                    │   │
│  │                          │                            │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │   │
│  │  │api-gw   │ │user-svc │ │video-svc│ │location │    │   │
│  │  │(3 tasks)│ │(3 tasks)│ │(3 tasks)│ │(3 tasks)│    │   │
│  │  │min:2    │ │min:2    │ │min:2    │ │min:2    │    │   │
│  │  │max:10   │ │max:10   │ │max:10   │ │max:10   │    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                │   │
│  │  │search   │ │mod-svc  │ │notif-svc│                │   │
│  │  │(3 tasks)│ │(2 tasks)│ │(2 tasks)│                │   │
│  │  │min:2    │ │min:1    │ │min:1    │                │   │
│  │  │max:10   │ │max:5    │ │max:5    │                │   │
│  │  └─────────┘ └─────────┘ └─────────┘                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │RDS Postgres │  │ ElastiCache │  │  OpenSearch │         │
│  │db.r6g.large │  │cache.r6g.lg │  │r6g.large.src│         │
│  │Multi-AZ     │  │ 2-node clust│  │ 3-node clust│         │
│  │Read replica │  └─────────────┘  └─────────────┘         │
│  └─────────────┘                                            │
└─────────────────────────────────────────────────────────────┘

Note: Instance types abbreviated. Full names: db.r6g.large, cache.r6g.large, r6g.large.search
```

### Auto-Scaling Configuration

```yaml
# Production auto-scaling policy
scaling_policy:
  metric: ECSServiceAverageCPUUtilization
  target_value: 70
  scale_in_cooldown: 300
  scale_out_cooldown: 60

  # Per-service limits
  services:
    api-gateway: { min: 2, max: 10 }
    user-service: { min: 2, max: 10 }
    video-service: { min: 2, max: 10 }
    location-service: { min: 2, max: 10 }
    search-service: { min: 2, max: 10 }
    moderation-service: { min: 1, max: 5 }
    notification-service: { min: 1, max: 5 }
```

### Web Application Hosting

The Next.js web application runs as a containerized ECS service, with static assets served through CloudFront:

| Environment | Tasks | CloudFront | Notes |
|-------------|-------|------------|-------|
| Staging | 2 | No | Direct ALB access |
| Production | 2-5 | Yes | CloudFront CDN for static assets |

**Production architecture**:
- CloudFront serves static assets (JS, CSS, images) from S3
- Dynamic requests (SSR, API routes) route to ECS via ALB
- Next.js runs in standalone output mode for container deployment

### CI/CD Pipeline

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  GitHub │───▶│CodeBuild │───▶│   ECR    │───▶│   ECS    │
│  (Push) │    │ (Build)  │    │ (Image)  │    │ (Deploy) │
└─────────┘    └──────────┘    └──────────┘    └──────────┘
                    │
              ┌─────┴─────┐
              ▼           ▼
         ┌────────┐  ┌─────────────┐
         │ Tests  │  │ Lint/Analyze│
         │(JUnit) │  │(Spotless,   │
         └────────┘  │Error Prone) │
                     └─────────────┘
```

**Pipeline stages**:
1. **Source**: GitHub webhook on push to main
2. **Build**: Tests, code quality checks, Docker image build, push to ECR
3. **Deploy Staging**: Auto-deploy on main branch
4. **Deploy Production**: Manual approval required

### Deployment Strategy

- **Staging**: Blue-green deployment
- **Production**: Blue-green deployment with canary

```yaml
# Production deployment configuration
deployment:
  type: CODE_DEPLOY
  config:
    deployment_config: CodeDeployDefault.ECSCanary10Percent5Minutes
    termination_wait_time: 5  # minutes
    auto_rollback:
      enabled: true
      events:
        - DEPLOYMENT_FAILURE
        - DEPLOYMENT_STOP_ON_ALARM
```

### DNS Configuration (Route 53)

| Record | Type | Value |
|--------|------|-------|
| accountabilityatlas.com | A | CloudFront distribution |
| api.accountabilityatlas.com | A | ALB (prod) |
| api.staging.accountabilityatlas.com | A | ALB (staging) |

### Disaster Recovery

#### Backup Strategy

| Resource | Backup Type | Frequency | Retention | Location |
|----------|-------------|-----------|-----------|----------|
| RDS | Automated snapshot | Daily | 30 days | Same region |
| RDS | Cross-region snapshot | Daily | 7 days | us-west-2 |
| OpenSearch | Automated snapshot | Hourly | 14 days | S3 |
| S3 | Cross-region replication | Continuous | - | us-west-2 |

#### Recovery Procedures

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| Single service failure | 5 min | 0 | ECS auto-recovery |
| AZ failure | 10 min | 0 | Multi-AZ failover |
| Database failure | 15 min | 5 min | RDS failover |
| Region failure | 4 hours | 1 hour | DR region activation |

### Reserved Instances

| Service | Instance | Term | Savings |
|---------|----------|------|---------|
| RDS | db.r6g.large | 1 year | ~40% |
| ElastiCache | cache.r6g.large | 1 year | ~40% |
| OpenSearch | r6g.large.search | 1 year | ~40% |

---

## Monitoring and Observability

Monitoring capabilities scale with phase:

| Capability | Phase 1 | Phase 2 | Phase 3+ |
|------------|---------|---------|----------|
| Logging | CloudWatch Agent (awslogs driver) | CloudWatch Logs | CloudWatch Logs |
| Metrics | CloudWatch Agent (CPU, memory, disk) | CloudWatch Metrics | CloudWatch Metrics + Prometheus |
| Tracing | None | None | AWS X-Ray (5% sampling) |
| Dashboards | None (alarms only) | 1 overview dashboard | 3 dashboards (overview, DB, search) |
| Alerting | Basic alarms (email) | Full alarm suite (email) | Full alarms (email + SMS for critical) |

### CloudWatch Alarms (Phase 3+)

| Alarm | Metric | Threshold | Severity | Action |
|-------|--------|-----------|----------|--------|
| High Error Rate | 5XX errors | > 5% for 5 min | Critical | SMS + Email |
| High Latency | P95 latency | > 1s for 5 min | Warning | Email |
| Low Healthy Hosts | Healthy count | < 2 for 2 min | Critical | SMS + Email |
| Database CPU | CPU utilization | > 80% for 10 min | Warning | Email |
| Database Connections | Connection count | > 80% max for 5 min | Warning | Email |
| Search Cluster Red | Cluster status | RED | Critical | SMS + Email |
| Queue Depth | ApproximateNumberOfMessages | > 1000 | Warning | Email |

**Scaling alerting infrastructure**: As user base grows significantly, consider upgrading to:
- **PagerDuty** for critical alarms — adds on-call scheduling, escalation policies, and acknowledgment tracking
- **Slack** for warning alarms — improves team visibility and enables quick collaboration on issues

### Distributed Tracing (Phase 3+)

- All services instrumented with AWS X-Ray SDK
- Trace sampling: 5% in production
- Service map visualization
- Latency analysis by segment

---

## Cost Allocation Tags

All resources tagged with:
- `Environment`: dev/staging/prod
- `Service`: service name
- `Project`: accountabilityatlas
- `CostCenter`: engineering
