# Infrastructure Architecture

## Cloud Platform

**Primary Region**: us-east-1 (N. Virginia)
**DR Region**: us-west-2 (Oregon)
**Cloud Provider**: Amazon Web Services (AWS)

---

## AWS Service Inventory

| Service | Purpose | Environment |
|---------|---------|-------------|
| ECS Fargate | Container orchestration | Dev, Staging, Prod |
| ALB | Load balancing | Dev, Staging, Prod |
| RDS PostgreSQL | Primary database | Dev, Staging, Prod |
| ElastiCache Redis | Caching, sessions | Dev, Staging, Prod |
| OpenSearch Service | Full-text search | Staging, Prod |
| SQS | Message queuing | Dev, Staging, Prod |
| S3 | Static assets, backups | All |
| CloudFront | CDN | Prod |
| Route 53 | DNS | All |
| ACM | SSL/TLS certificates | All |
| Secrets Manager | Secrets storage | All |
| CloudWatch | Logging, monitoring | All |
| X-Ray | Distributed tracing | Staging, Prod |
| WAF | Web application firewall | Prod |
| ECR | Container registry | All |
| CodePipeline | CI/CD | All |
| CodeBuild | Build service | All |

---

## Environment Topology

### Development Environment

```
┌─────────────────────────────────────────────────────────────┐
│                    DEV (us-east-1)                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  ECS Cluster (dev)                    │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │   │
│  │  │api-gw   │ │user-svc │ │video-svc│ │location │    │   │
│  │  │(1 task) │ │(1 task) │ │(1 task) │ │(1 task) │    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐                │   │
│  │  │search   │ │mod-svc  │ │notif-svc│                │   │
│  │  │(1 task) │ │(1 task) │ │(1 task) │                │   │
│  │  └─────────┘ └─────────┘ └─────────┘                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │RDS Postgres │  │ ElastiCache │  │     SQS     │         │
│  │(db.t3.small)│  │(cache.t3.sm)│  │   Queues    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘

Note: Dev uses local OpenSearch or shared staging instance
```

### Staging Environment

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
│  │(db.t3.medium│  │(cache.t3.med│  │(t3.small.se)│         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

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
│  │(db.r6g.large│  │(cache.r6g.lg│  │(r6g.large.se│         │
│  │Multi-AZ    │  │ 2-node clust│  │ 3-node clust│         │
│  │Read replica│  └─────────────┘  └─────────────┘         │
│  └─────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Container Configuration

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

---

## Database Configuration

### RDS PostgreSQL

| Setting | Dev | Staging | Production |
|---------|-----|---------|------------|
| Instance | db.t3.small | db.t3.medium | db.r6g.large |
| Storage | 20 GB | 50 GB | 100 GB |
| Multi-AZ | No | No | Yes |
| Read Replicas | 0 | 0 | 1 |
| Backup Retention | 1 day | 7 days | 30 days |
| PITR | Disabled | Enabled | Enabled |
| Performance Insights | Disabled | Enabled | Enabled |
| Extensions | postgis | postgis | postgis |

### ElastiCache Redis

| Setting | Dev | Staging | Production |
|---------|-----|---------|------------|
| Node Type | cache.t3.small | cache.t3.medium | cache.r6g.large |
| Nodes | 1 | 1 | 2 (cluster) |
| Multi-AZ | No | No | Yes |
| Encryption at Rest | Yes | Yes | Yes |
| Encryption in Transit | Yes | Yes | Yes |

### OpenSearch

| Setting | Staging | Production |
|---------|---------|------------|
| Instance | t3.small.search | r6g.large.search |
| Nodes | 1 | 3 |
| Storage | 20 GB | 100 GB |
| Encryption | Yes | Yes |
| Fine-grained Access | Yes | Yes |

---

## Networking

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
└── Data (RDS, ElastiCache, OpenSearch)
    ├── us-east-1a: 10.0.20.0/24
    └── us-east-1b: 10.0.21.0/24
```

### DNS Configuration (Route 53)

| Record | Type | Value |
|--------|------|-------|
| accountabilityatlas.com | A | CloudFront distribution |
| api.accountabilityatlas.com | A | ALB (prod) |
| api.staging.accountabilityatlas.com | A | ALB (staging) |
| api.dev.accountabilityatlas.com | A | ALB (dev) |

---

## CI/CD Pipeline

### Pipeline Architecture

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  GitHub │───▶│CodeBuild │───▶│   ECR    │───▶│   ECS    │
│  (Push) │    │ (Build)  │    │ (Image)  │    │ (Deploy) │
└─────────┘    └──────────┘    └──────────┘    └──────────┘
                    │
              ┌─────┴─────┐
              ▼           ▼
         ┌────────┐  ┌────────┐
         │ Tests  │  │ Lint   │
         │(JUnit) │  │(ktlint)│
         └────────┘  └────────┘
```

### Pipeline Stages

1. **Source**: GitHub webhook on push to main/develop
2. **Build**:
   - Run tests (JUnit, integration tests)
   - Run linter (ktlint)
   - Build Docker image
   - Push to ECR
3. **Deploy Dev**: Auto-deploy on develop branch
4. **Deploy Staging**: Auto-deploy on main branch
5. **Deploy Production**: Manual approval required

### Deployment Strategy

- **Development**: Rolling deployment
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

---

## Monitoring and Observability

### CloudWatch Dashboards

1. **Overview Dashboard**
   - Request count by service
   - Error rates
   - Latency percentiles
   - Active tasks per service

2. **Database Dashboard**
   - CPU utilization
   - Connection count
   - Read/write IOPS
   - Replication lag

3. **Search Dashboard**
   - Query latency
   - Index size
   - Document count
   - JVM metrics

### Alarms

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| High Error Rate | 5XX errors | > 5% for 5 min | PagerDuty |
| High Latency | P95 latency | > 1s for 5 min | Slack |
| Low Healthy Hosts | Healthy count | < 2 for 2 min | PagerDuty |
| Database CPU | CPU utilization | > 80% for 10 min | Slack |
| Database Connections | Connection count | > 80% max for 5 min | Slack |
| Search Cluster Red | Cluster status | RED | PagerDuty |
| Queue Depth | ApproximateNumberOfMessages | > 1000 | Slack |

### Distributed Tracing (X-Ray)

- All services instrumented with AWS X-Ray SDK
- Trace sampling: 5% in production
- Service map visualization
- Latency analysis by segment

---

## Disaster Recovery

### Backup Strategy

| Resource | Backup Type | Frequency | Retention | Location |
|----------|-------------|-----------|-----------|----------|
| RDS | Automated snapshot | Daily | 30 days | Same region |
| RDS | Cross-region snapshot | Daily | 7 days | us-west-2 |
| OpenSearch | Automated snapshot | Hourly | 14 days | S3 |
| S3 | Cross-region replication | Continuous | - | us-west-2 |

### Recovery Procedures

| Scenario | RTO | RPO | Procedure |
|----------|-----|-----|-----------|
| Single service failure | 5 min | 0 | ECS auto-recovery |
| AZ failure | 10 min | 0 | Multi-AZ failover |
| Database failure | 15 min | 5 min | RDS failover |
| Region failure | 4 hours | 1 hour | DR region activation |

---

## Cost Optimization

### Reserved Instances (Production)

| Service | Instance | Term | Savings |
|---------|----------|------|---------|
| RDS | db.r6g.large | 1 year | ~40% |
| ElastiCache | cache.r6g.large | 1 year | ~40% |
| OpenSearch | r6g.large.search | 1 year | ~40% |

### Cost Allocation Tags

All resources tagged with:
- `Environment`: dev/staging/prod
- `Service`: service name
- `Project`: accountabilityatlas
- `CostCenter`: engineering
