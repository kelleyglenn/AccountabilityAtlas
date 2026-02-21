# AWS Demo Deployment Design

## Overview

Deploy AccountabilityAtlas to AWS for demo purposes using OpenTofu infrastructure-as-code, with scripts to start, stop, and deploy the environment on demand.

**Issues covered:** #54 (OpenTofu bootstrap), #26 (shared JWT keys), user-service #36 (stable JWT signing keys), video-service #3 (YouTube API key for production)

**Deferred:** #56 (GitHub Actions deploy workflow), #10 (Docker base image SHA pinning)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| AWS region | us-east-2 (Ohio) | Same pricing as us-east-1, fewer historical outages, all needed services available |
| IaC tool | OpenTofu | Open-source Terraform fork (MPL 2.0), already documented in architecture |
| IaC layout | Flat directory (`infra/`) | ~25-30 resources for Phase 1; modules are over-engineering at this scale |
| Start/stop strategy | Stop both EC2 and RDS | ~$5-8/month idle vs ~$135/month running; accept 7-day RDS auto-restart quirk |
| Deploy gate | Require `integration-tested-*` tag | Only deploy code that passed the full integration test suite; no override |
| Notification service | Excluded | Status is "Planned", not implemented; add later |
| Secrets | Never in checked-in files | Secrets Manager + gitignored `.tfvars` and `config.env`; `example` templates checked in with placeholders |

## Section 1: Bootstrap (One-Time Manual Setup)

Before OpenTofu can manage infrastructure, these resources must be created manually. Exact CLI commands will be documented in `infra/README.md`.

### Steps

1. **Create S3 bucket** `accountabilityatlas-tfstate`
   - Versioning enabled
   - Server-side encryption (AES-256)
   - Block all public access

2. **Create DynamoDB table** `terraform-locks`
   - Partition key: `LockID` (String)
   - Billing: on-demand

3. **Store secrets in Secrets Manager** (all in us-east-2)
   - RSA private key for JWT signing (generate via `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048`)
   - RDS master password
   - YouTube Data API key
   - Mapbox access token
   - Admin password hash

After bootstrap, all infrastructure changes go through `tofu plan` / `tofu apply` from a local machine using your own AWS credentials.

## Section 2: OpenTofu Configuration

All files in `infra/` directory.

### File Layout

| File | Purpose |
|------|---------|
| `backend.tf` | S3 state backend + DynamoDB lock table |
| `providers.tf` | AWS provider (us-east-2), pinned version |
| `variables.tf` | Input variables (see below) |
| `networking.tf` | VPC, subnets, internet gateway, Elastic IP, security groups |
| `compute.tf` | EC2 t3.xlarge, key pair, user data script |
| `database.tf` | RDS PostgreSQL (db.t4g.micro) |
| `messaging.tf` | SQS queues + dead-letter queues |
| `registry.tf` | ECR repositories (7 services) |
| `secrets.tf` | Data sources reading from Secrets Manager |
| `dns.tf` | Route 53 hosted zone, A record, www CNAME |
| `monitoring.tf` | CloudWatch alarms + SNS topic |
| `outputs.tf` | EC2 IP, RDS endpoint, ECR URLs, SQS URLs |

### Variables

Non-sensitive variables with defaults:
- `environment` (default: `"prod"`)
- `region` (default: `"us-east-2"`)

Sensitive/personal variables (no defaults, set in gitignored `terraform.tfvars`):
- `domain_name`
- `db_password`
- `ssh_public_key`
- `allowed_ssh_cidr` (your IP for SSH access)
- `alert_email` (CloudWatch alarm notifications)

### Networking (VPC)

```
VPC CIDR: 10.0.0.0/16

Subnets:
  Public (EC2):       10.0.1.0/24  (us-east-2a)
  Data (RDS):         10.0.20.0/24 (us-east-2a)
  Data (RDS backup):  10.0.21.0/24 (us-east-2b)  # required for RDS subnet group
```

### Security Groups

**sg-ec2-web:**
- Inbound: TCP 80 (0.0.0.0/0), TCP 443 (0.0.0.0/0), TCP 22 (allowed_ssh_cidr)
- Outbound: all

**sg-rds:**
- Inbound: TCP 5432 from sg-ec2-web only

### Compute (EC2)

- Instance: t3.xlarge (4 vCPU, 16 GB RAM)
- AMI: Amazon Linux 2023
- Root volume: 30 GB gp3
- Elastic IP for stable address across stop/start cycles
- User data installs: Docker, Docker Compose, CloudWatch agent

### Database (RDS)

- Engine: PostgreSQL 17
- Instance: db.t4g.micro (free tier eligible)
- Storage: 20 GB gp3
- Backup retention: 7 days
- Skip final snapshot (demo environment)
- PostGIS extension
- Subnet group spanning both data subnets

### Messaging (SQS)

Queues matching local dev LocalStack setup:
- video-events, moderation-events, search-moderation-events, user-events, notification-events
- Dead-letter queue for each

### Container Registry (ECR)

One repository per service:
- acct-atlas-api-gateway
- acct-atlas-user-service
- acct-atlas-video-service
- acct-atlas-location-service
- acct-atlas-search-service
- acct-atlas-moderation-service
- acct-atlas-web-app

Lifecycle policy: retain 5 most recent images per repository.

### DNS (Route 53)

- Hosted zone for the domain
- A record pointing to the Elastic IP
- www CNAME pointing to the apex domain

### Monitoring (CloudWatch)

Alarms (all notify via SNS email):

| Alarm | Threshold |
|-------|-----------|
| EC2 High CPU | >70% for 10 min |
| EC2 High Memory | >80% for 10 min |
| EC2 Low Disk | >85% |
| RDS High CPU | >80% for 10 min |
| SQS Queue Depth | >1,000 |
| EC2 Status Check | Failed for 5 min (auto-recover) |

### Gitignore Additions

```
infra/.terraform/
infra/*.tfstate
infra/*.tfstate.backup
infra/*.tfvars
!infra/example.tfvars
```

An `example.tfvars` is checked in with placeholder values:
```
domain_name      = "yourdomain.com"
db_password      = "CHANGE_ME"
ssh_public_key   = "ssh-rsa AAAA..."
allowed_ssh_cidr = "YOUR_IP/32"
alert_email      = "you@example.com"
```

## Section 3: Production Docker Compose & Nginx

Files live in `infra/docker/` and are SCPed to EC2 by the deploy script.

### docker-compose.prod.yml

10 containers:

| Container | Image Source | CPU | Memory |
|-----------|-------------|-----|--------|
| nginx | nginx:alpine | 0.25 | 256 MB |
| api-gateway | ECR | 0.50 | 1024 MB |
| user-service | ECR | 0.50 | 1024 MB |
| video-service | ECR | 0.50 | 1024 MB |
| location-service | ECR | 0.50 | 1024 MB |
| search-service | ECR | 0.50 | 1024 MB |
| moderation-service | ECR | 0.25 | 512 MB |
| web-app | ECR | 0.50 | 1024 MB |
| redis | redis:7-alpine | 0.15 | 640 MB |
| **Total** | | **~3.65** | **~6,528 MB** |

Key configuration:
- Images from ECR: `${ECR_REGISTRY}/acct-atlas-<service>:${TAG}`
- `SPRING_PROFILES_ACTIVE=prod` for all Java services
- `SPRING_PROFILES_ACTIVE=prod,fts` for search-service (PostgreSQL full-text search)
- Environment variables for RDS endpoint, SQS URLs, service URLs, JWT key
- Secrets sourced from `.env` file (populated by deploy script from Secrets Manager)
- `awslogs` log driver for CloudWatch Logs
- `restart: always` on all containers

### nginx.conf

- Port 80: redirect to HTTPS
- Port 443: TLS with Let's Encrypt certificates
- `/api/v1/auth/*` → api-gateway:8080 (rate limit: 5r/s, burst 5)
- `/api/*` → api-gateway:8080 (rate limit: 30r/s, burst 20)
- `/*` → web-app:3000 (rate limit: 30r/s, burst 20)
- Proxy headers: X-Real-IP, X-Forwarded-For, X-Forwarded-Proto

### .env.example

Checked in with placeholder values showing required variables. Actual `.env` is gitignored and generated by the deploy script.

## Section 4: Scripts

All in `scripts/aws/`. Require AWS CLI configured locally and EC2 SSH key.

Common configuration in gitignored `scripts/aws/config.env` (with `config.env.example` checked in).

### aws-start.sh

1. Start RDS instance
2. Start EC2 instance
3. Wait for RDS available
4. Wait for EC2 status checks
5. SSH into EC2, run `docker compose up -d`
6. Wait for health checks (`/actuator/health` on api-gateway, `/` on web-app)
7. Print access URL

### aws-deploy.sh

1. Accept optional `--tag <name>` argument; default to latest `integration-tested-*` tag
2. **Fail if no `integration-tested-*` tags exist** (no override)
3. `git fetch --tags` in each service repo
4. `git checkout <tag>` in each repo (detached HEAD)
5. Build Docker images (`./gradlew jibDockerBuild` for Java, `docker build` for web-app)
6. Tag images with the integration test tag name + push to ECR
7. Fetch secrets from Secrets Manager, write `.env` file
8. SCP `docker-compose.prod.yml`, `nginx.conf`, `.env` to EC2
9. SSH into EC2: pull images, `docker compose up -d`
10. Wait for health checks
11. Clean up local `.env`, restore repos to previous branches
12. Print deployed tag name

### aws-stop.sh

1. SSH into EC2, run `docker compose down`
2. Stop EC2 instance
3. Stop RDS instance
4. Print reminder: RDS auto-restarts after 7 days if not manually stopped again

## Section 5: Stable JWT Signing Keys

**Issues:** #26 (infrastructure), user-service #36 (code)

### user-service Code Change

1. **`JwtConfig`** — check for `app.jwt.private-key` Spring property:
   - If present: decode PEM-encoded RSA private key, derive public key
   - If absent: generate key pair (existing behavior, used in local/docker profiles)

2. **`application-prod.yml`** — add:
   ```yaml
   app:
     jwt:
       private-key: ${APP_JWT_PRIVATE_KEY}
   ```

3. No changes to local or docker profiles.

### Infrastructure Side

- RSA private key stored in Secrets Manager (bootstrap step)
- Deploy script reads it and writes `APP_JWT_PRIVATE_KEY` to `.env`
- `docker-compose.prod.yml` passes it to user-service as environment variable

## Section 6: API Key Wiring

**Issue:** video-service #3

No application code changes. Both services already read these environment variables.

**Secrets Manager → deploy script → `.env` → docker-compose → container:**
- `YOUTUBE_API_KEY` → video-service
- `NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN` → web-app (build arg + runtime env)

## Cost

### Running (~$135-162/month)

| Resource | Monthly Cost |
|----------|-------------|
| EC2 t3.xlarge | $122.64 |
| RDS db.t4g.micro | $1.40 (free tier yr 1) |
| SQS | $0.20 |
| Other (Route 53, Secrets Manager, ECR, CloudWatch, S3, Elastic IP) | ~$10.27 |
| **Total** | **~$135 (yr 1) / ~$149 (after)** |

### Stopped (~$5-8/month)

| Resource | Monthly Cost |
|----------|-------------|
| EBS volume (30 GB) | ~$2.40 |
| RDS storage (20 GB) | ~$2.30 |
| Elastic IP (unattached) | $3.65 |
| Route 53 + S3 + Secrets Manager | ~$3.50 |
| **Total** | **~$12** |
