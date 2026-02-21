# AWS Demo Deployment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deploy AccountabilityAtlas to AWS for demo purposes with start/stop/deploy scripts.

**Architecture:** OpenTofu provisions Phase 1 infrastructure (EC2 + Docker Compose, RDS, SQS, ECR) in us-east-2. Three shell scripts manage the lifecycle: start, deploy, stop. User-service gets a code change for stable JWT signing keys.

**Tech Stack:** OpenTofu (HCL), Bash, AWS CLI, Docker, Spring Boot (Java 21), Gradle

**Issues:** AccountabilityAtlas #54, #26; user-service #36; video-service #3

---

## Task 1: Gitignore Updates

**Files:**
- Modify: `C:\code\AccountabilityAtlas\.gitignore`

**Step 1: Add infra and AWS script ignores to .gitignore**

Append to the existing `.gitignore`:

```
# OpenTofu / Terraform
infra/.terraform/
infra/*.tfstate
infra/*.tfstate.backup
infra/*.tfvars
!infra/example.tfvars

# AWS deployment config
scripts/aws/config.env
infra/docker/.env
```

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add OpenTofu and AWS deploy ignores to .gitignore"
```

---

## Task 2: OpenTofu Backend and Provider

**Files:**
- Create: `infra/backend.tf`
- Create: `infra/providers.tf`

**Step 1: Create `infra/backend.tf`**

```hcl
terraform {
  backend "s3" {
    bucket         = "accountabilityatlas-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
```

**Step 2: Create `infra/providers.tf`**

```hcl
terraform {
  required_version = ">= 1.8"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "accountabilityatlas"
      Environment = var.environment
      ManagedBy   = "opentofu"
    }
  }
}
```

**Step 3: Commit**

```bash
git add infra/backend.tf infra/providers.tf
git commit -m "infra: add OpenTofu backend and provider configuration (#54)"
```

---

## Task 3: OpenTofu Variables and Example Tfvars

**Files:**
- Create: `infra/variables.tf`
- Create: `infra/example.tfvars`

**Step 1: Create `infra/variables.tf`**

```hcl
variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "accountabilityatlas"
}

variable "domain_name" {
  description = "Domain name for Route 53 and TLS"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key for EC2 access"
  type        = string
  sensitive   = true
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH into EC2 (e.g. YOUR_IP/32)"
  type        = string
  sensitive   = true
}

variable "alert_email" {
  description = "Email address for CloudWatch alarm notifications"
  type        = string
  sensitive   = true
}
```

**Step 2: Create `infra/example.tfvars`**

```hcl
domain_name      = "yourdomain.com"
db_password      = "CHANGE_ME"
ssh_public_key   = "ssh-rsa AAAA..."
allowed_ssh_cidr = "YOUR_IP/32"
alert_email      = "you@example.com"
```

**Step 3: Commit**

```bash
git add infra/variables.tf infra/example.tfvars
git commit -m "infra: add OpenTofu variables and example tfvars (#54)"
```

---

## Task 4: Networking (VPC, Subnets, Security Groups)

**Files:**
- Create: `infra/networking.tf`

**Step 1: Create `infra/networking.tf`**

```hcl
# --- VPC ---

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.project_name}-vpc" }
}

# --- Subnets ---

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.region}a"
  map_public_ip_on_launch = true

  tags = { Name = "${var.project_name}-public-a" }
}

resource "aws_subnet" "data_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.20.0/24"
  availability_zone = "${var.region}a"

  tags = { Name = "${var.project_name}-data-a" }
}

resource "aws_subnet" "data_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.21.0/24"
  availability_zone = "${var.region}b"

  tags = { Name = "${var.project_name}-data-b" }
}

# --- Internet Gateway ---

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${var.project_name}-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${var.project_name}-public-rt" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# --- Elastic IP ---

resource "aws_eip" "ec2" {
  domain = "vpc"

  tags = { Name = "${var.project_name}-ec2-eip" }
}

# --- Security Groups ---

resource "aws_security_group" "ec2_web" {
  name        = "${var.project_name}-ec2-web"
  description = "Allow HTTP, HTTPS, and SSH from admin IP"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.project_name}-ec2-web" }
}

resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.ec2_web.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.ec2_web.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.ec2_web.id
  cidr_ipv4         = var.allowed_ssh_cidr
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "ec2_all_out" {
  security_group_id = aws_security_group.ec2_web.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds"
  description = "Allow PostgreSQL from EC2 security group only"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.project_name}-rds" }
}

resource "aws_vpc_security_group_ingress_rule" "rds_from_ec2" {
  security_group_id            = aws_security_group.rds.id
  referenced_security_group_id = aws_security_group.ec2_web.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}
```

**Step 2: Commit**

```bash
git add infra/networking.tf
git commit -m "infra: add VPC, subnets, and security groups (#54)"
```

---

## Task 5: Compute (EC2 Instance)

**Files:**
- Create: `infra/compute.tf`

**Step 1: Create `infra/compute.tf`**

The EC2 user data script installs Docker, Docker Compose, and the CloudWatch agent. The instance is configured with a key pair for SSH access.

```hcl
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_key_pair" "deploy" {
  key_name   = "${var.project_name}-deploy"
  public_key = var.ssh_public_key
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = "t3.xlarge"
  key_name               = aws_key_pair.deploy.key_name
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.ec2_web.id]

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
  }

  user_data = <<-EOF
    #!/bin/bash
    set -e

    # Install Docker
    dnf update -y
    dnf install -y docker
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ec2-user

    # Install Docker Compose plugin
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

    # Install CloudWatch agent
    dnf install -y amazon-cloudwatch-agent
    cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json <<'CWCONFIG'
    {
      "agent": { "metrics_collection_interval": 60 },
      "metrics": {
        "namespace": "AccountabilityAtlas",
        "append_dimensions": { "InstanceId": "$${aws:InstanceId}" },
        "metrics_collected": {
          "mem": { "measurement": ["mem_used_percent"] },
          "disk": {
            "measurement": ["disk_used_percent"],
            "resources": ["/"]
          }
        }
      },
      "logs": {
        "logs_collected": {
          "files": {
            "collect_list": [
              {
                "file_path": "/var/log/messages",
                "log_group_name": "/accountabilityatlas/prod/system",
                "log_stream_name": "{instance_id}"
              }
            ]
          }
        }
      }
    }
    CWCONFIG
    /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
      -a fetch-config -m ec2 \
      -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s

    # Create app directory
    mkdir -p /home/ec2-user/app
    chown ec2-user:ec2-user /home/ec2-user/app
  EOF

  iam_instance_profile = aws_iam_instance_profile.ec2.name

  tags = { Name = "${var.project_name}-app" }
}

resource "aws_eip_association" "ec2" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.ec2.id
}

# --- IAM Role for EC2 (ECR pull, CloudWatch, Secrets Manager read) ---

resource "aws_iam_role" "ec2" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy" "sqs_access" {
  name = "${var.project_name}-sqs-access"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueUrl",
        "sqs:GetQueueAttributes"
      ]
      Resource = "arn:aws:sqs:${var.region}:*:${var.project_name}-*"
    }]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2.name
}
```

**Step 2: Commit**

```bash
git add infra/compute.tf
git commit -m "infra: add EC2 instance with Docker and CloudWatch agent (#54)"
```

---

## Task 6: Database (RDS PostgreSQL)

**Files:**
- Create: `infra/database.tf`

**Step 1: Create `infra/database.tf`**

```hcl
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = [aws_subnet.data_a.id, aws_subnet.data_b.id]

  tags = { Name = "${var.project_name}-db-subnet-group" }
}

resource "aws_db_instance" "postgres" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = "17"
  instance_class = "db.t4g.micro"

  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = "accountabilityatlas"
  username = "postgres"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az            = false
  publicly_accessible = false

  backup_retention_period = 7
  skip_final_snapshot     = true

  tags = { Name = "${var.project_name}-db" }
}
```

**Note on per-service databases:** The RDS instance creates a single `accountabilityatlas` database. The deploy script must run the same per-service database/user initialization from `docker/postgres/init-databases.sql` on first deploy. This is documented in Task 11 (deploy script).

**Step 2: Commit**

```bash
git add infra/database.tf
git commit -m "infra: add RDS PostgreSQL instance (#54)"
```

---

## Task 7: Messaging (SQS Queues)

**Files:**
- Create: `infra/messaging.tf`

**Step 1: Create `infra/messaging.tf`**

Queue names match `docker/localstack/init-queues.sh`. Each main queue has a dead-letter queue with `maxReceiveCount: 3`.

```hcl
locals {
  sqs_queues = [
    "video-events",
    "video-status-events",
    "moderation-events",
    "search-moderation-events",
    "user-events",
  ]
}

resource "aws_sqs_queue" "dlq" {
  for_each = toset(local.sqs_queues)

  name = "${var.project_name}-${each.key}-dlq"
}

resource "aws_sqs_queue" "main" {
  for_each = toset(local.sqs_queues)

  name = "${var.project_name}-${each.key}"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = 3
  })
}
```

**Step 2: Commit**

```bash
git add infra/messaging.tf
git commit -m "infra: add SQS queues with dead-letter queues (#54)"
```

---

## Task 8: Container Registry (ECR)

**Files:**
- Create: `infra/registry.tf`

**Step 1: Create `infra/registry.tf`**

```hcl
locals {
  services = [
    "api-gateway",
    "user-service",
    "video-service",
    "location-service",
    "search-service",
    "moderation-service",
    "web-app",
  ]
}

resource "aws_ecr_repository" "services" {
  for_each = toset(local.services)

  name                 = "acct-atlas-${each.key}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "keep_recent" {
  for_each = aws_ecr_repository.services

  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}
```

**Step 2: Commit**

```bash
git add infra/registry.tf
git commit -m "infra: add ECR repositories with lifecycle policies (#54)"
```

---

## Task 9: Secrets, DNS, Monitoring, Outputs

**Files:**
- Create: `infra/secrets.tf`
- Create: `infra/dns.tf`
- Create: `infra/monitoring.tf`
- Create: `infra/outputs.tf`

**Step 1: Create `infra/secrets.tf`**

Data sources read secrets that were stored manually during bootstrap (Section 1 of design).

```hcl
data "aws_secretsmanager_secret_version" "jwt_private_key" {
  secret_id = "${var.project_name}/jwt-private-key"
}

data "aws_secretsmanager_secret_version" "youtube_api_key" {
  secret_id = "${var.project_name}/youtube-api-key"
}

data "aws_secretsmanager_secret_version" "mapbox_token" {
  secret_id = "${var.project_name}/mapbox-access-token"
}

data "aws_secretsmanager_secret_version" "admin_password_hash" {
  secret_id = "${var.project_name}/admin-password-hash"
}
```

**Step 2: Create `infra/dns.tf`**

```hcl
resource "aws_route53_zone" "main" {
  name = var.domain_name
}

resource "aws_route53_record" "apex" {
  zone_id = aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.ec2.public_ip]
}

resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "www.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = [var.domain_name]
}
```

**Step 3: Create `infra/monitoring.tf`**

```hcl
resource "aws_sns_topic" "alarms" {
  name = "${var.project_name}-alarms"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "ec2_high_cpu" {
  alarm_name          = "${var.project_name}-ec2-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 70
  alarm_description   = "EC2 CPU >70% for 10 minutes"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = { InstanceId = aws_instance.app.id }
}

resource "aws_cloudwatch_metric_alarm" "ec2_high_memory" {
  alarm_name          = "${var.project_name}-ec2-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "mem_used_percent"
  namespace           = "AccountabilityAtlas"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "EC2 memory >80% for 10 minutes"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = { InstanceId = aws_instance.app.id }
}

resource "aws_cloudwatch_metric_alarm" "ec2_low_disk" {
  alarm_name          = "${var.project_name}-ec2-low-disk"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "disk_used_percent"
  namespace           = "AccountabilityAtlas"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "EC2 disk usage >85%"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = {
    InstanceId = aws_instance.app.id
    path       = "/"
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_high_cpu" {
  alarm_name          = "${var.project_name}-rds-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU >80% for 10 minutes"
  alarm_actions       = [aws_sns_topic.alarms.arn]

  dimensions = { DBInstanceIdentifier = aws_db_instance.postgres.identifier }
}

resource "aws_cloudwatch_metric_alarm" "ec2_status_check" {
  alarm_name          = "${var.project_name}-ec2-status-check"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "StatusCheckFailed"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "EC2 status check failed for 5 minutes"
  alarm_actions       = [aws_sns_topic.alarms.arn, "arn:aws:automate:${var.region}:ec2:recover"]

  dimensions = { InstanceId = aws_instance.app.id }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/accountabilityatlas/prod"
  retention_in_days = 30
}
```

**Step 4: Create `infra/outputs.tf`**

```hcl
output "ec2_public_ip" {
  description = "Elastic IP address of the EC2 instance"
  value       = aws_eip.ec2.public_ip
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_address" {
  description = "RDS PostgreSQL hostname (without port)"
  value       = aws_db_instance.postgres.address
}

output "ecr_registry" {
  description = "ECR registry URL"
  value       = split("/", aws_ecr_repository.services["user-service"].repository_url)[0]
}

output "ecr_repository_urls" {
  description = "ECR repository URLs by service"
  value       = { for k, v in aws_ecr_repository.services : k => v.repository_url }
}

output "sqs_queue_urls" {
  description = "SQS queue URLs by name"
  value       = { for k, v in aws_sqs_queue.main : k => v.url }
}

output "route53_nameservers" {
  description = "Route 53 nameservers (set these at your domain registrar)"
  value       = aws_route53_zone.main.name_servers
}

output "ec2_instance_id" {
  description = "EC2 instance ID (for start/stop scripts)"
  value       = aws_instance.app.id
}

output "rds_instance_id" {
  description = "RDS instance identifier (for start/stop scripts)"
  value       = aws_db_instance.postgres.identifier
}

output "ssh_command" {
  description = "SSH command to connect to the EC2 instance"
  value       = "ssh ec2-user@${aws_eip.ec2.public_ip}"
}
```

**Step 5: Commit**

```bash
git add infra/secrets.tf infra/dns.tf infra/monitoring.tf infra/outputs.tf
git commit -m "infra: add secrets, DNS, monitoring, and outputs (#54)"
```

---

## Task 10: Bootstrap README

**Files:**
- Create: `infra/README.md`

**Step 1: Create `infra/README.md`**

Document the one-time manual bootstrap steps with exact AWS CLI commands. Include:

1. **Prerequisites**: AWS CLI configured, OpenTofu installed
2. **Create S3 state bucket**:
   ```bash
   aws s3api create-bucket --bucket accountabilityatlas-tfstate \
     --region us-east-2 --create-bucket-configuration LocationConstraint=us-east-2
   aws s3api put-bucket-versioning --bucket accountabilityatlas-tfstate \
     --versioning-configuration Status=Enabled
   aws s3api put-bucket-encryption --bucket accountabilityatlas-tfstate \
     --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
   aws s3api put-public-access-block --bucket accountabilityatlas-tfstate \
     --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
   ```
3. **Create DynamoDB lock table**:
   ```bash
   aws dynamodb create-table --table-name terraform-locks \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --billing-mode PAY_PER_REQUEST --region us-east-2
   ```
4. **Generate and store JWT RSA key**:
   ```bash
   openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out jwt-private.pem
   aws secretsmanager create-secret --name accountabilityatlas/jwt-private-key \
     --secret-string file://jwt-private.pem --region us-east-2
   rm jwt-private.pem
   ```
5. **Store remaining secrets** (RDS password, YouTube API key, Mapbox token, admin password hash) with similar `aws secretsmanager create-secret` commands
6. **Create terraform.tfvars** from `example.tfvars`
7. **Initialize and apply**:
   ```bash
   tofu init
   tofu plan
   tofu apply
   ```
8. **Update domain registrar** with Route 53 nameservers from output

**Step 2: Commit**

```bash
git add infra/README.md
git commit -m "infra: add bootstrap README with manual setup instructions (#54)"
```

---

## Task 11: Production Docker Compose

**Files:**
- Create: `infra/docker/docker-compose.prod.yml`
- Create: `infra/docker/.env.example`

**Step 1: Create `infra/docker/docker-compose.prod.yml`**

Reference the existing `docker-compose.yml` at the project root for service names, ports, dependencies, and health checks. Key differences from local dev:

- Images from ECR (`${ECR_REGISTRY}/acct-atlas-<service>:${TAG}`) instead of local builds
- `SPRING_PROFILES_ACTIVE=prod` (or `prod,fts` for search-service)
- Database URLs point to RDS endpoint (`${RDS_ENDPOINT}`) instead of local postgres
- Real SQS queue URLs instead of LocalStack endpoint
- No LocalStack container
- No postgres container (using RDS)
- Add nginx container (ports 80/443)
- Add `awslogs` log driver on every container
- Add resource limits matching design doc
- `restart: always` on all containers
- All secrets from environment variables (sourced from `.env`)

Services to include: nginx, api-gateway, user-service, video-service, location-service, search-service, moderation-service, web-app, redis (10 total).

Environment variable mapping (each service needs as appropriate):
- `SPRING_DATASOURCE_URL=jdbc:postgresql://${RDS_ENDPOINT}/<service_db>`
- `SPRING_DATASOURCE_USERNAME=<service_user>`
- `SPRING_DATASOURCE_PASSWORD=${DB_PASSWORD}`
- `SPRING_FLYWAY_URL`, `SPRING_FLYWAY_USER`, `SPRING_FLYWAY_PASSWORD` (same as datasource)
- `SPRING_DATA_REDIS_HOST=redis`
- `AWS_REGION=us-east-2`
- SQS queue names: `APP_SQS_VIDEO_EVENTS_QUEUE=${SQS_PREFIX}-video-events` (etc.)
- Service URLs: `USER_SERVICE_URL=http://user-service:8081` (etc.)
- `USER_SERVICE_JWKS_URL=http://user-service:8081/.well-known/jwks.json` (for video-service, location-service)
- `APP_JWT_PRIVATE_KEY=${JWT_PRIVATE_KEY}` (user-service only)
- `YOUTUBE_API_KEY=${YOUTUBE_API_KEY}` (video-service only)
- `MAPBOX_ACCESS_TOKEN=${MAPBOX_TOKEN}` (location-service only)
- `ADMIN_EMAIL=${ADMIN_EMAIL}` and `ADMIN_PASSWORD_HASH=${ADMIN_PASSWORD_HASH}` (user-service only)

Note: `SPRING_CLOUD_AWS_SQS_ENDPOINT` should NOT be set in prod — services connect to real SQS using IAM role credentials from the EC2 instance profile. `SPRING_CLOUD_AWS_REGION_STATIC=us-east-2` should be set.

**Step 2: Create `infra/docker/.env.example`**

```bash
# AWS
ECR_REGISTRY=123456789012.dkr.ecr.us-east-2.amazonaws.com
TAG=latest
AWS_REGION=us-east-2

# Database
RDS_ENDPOINT=accountabilityatlas-db.xxxx.us-east-2.rds.amazonaws.com:5432
DB_PASSWORD=CHANGE_ME

# SQS queue name prefix
SQS_PREFIX=accountabilityatlas

# Secrets
JWT_PRIVATE_KEY=CHANGE_ME
YOUTUBE_API_KEY=CHANGE_ME
MAPBOX_TOKEN=CHANGE_ME
ADMIN_EMAIL=CHANGE_ME
ADMIN_PASSWORD_HASH=CHANGE_ME

# Web app
NEXT_PUBLIC_API_URL=https://yourdomain.com/api/v1
NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN=CHANGE_ME

# Domain (for nginx and certbot)
DOMAIN_NAME=yourdomain.com
```

**Step 3: Commit**

```bash
git add infra/docker/docker-compose.prod.yml infra/docker/.env.example
git commit -m "infra: add production Docker Compose and env template (#54)"
```

---

## Task 12: Nginx Configuration

**Files:**
- Create: `infra/docker/nginx.conf`

**Step 1: Create `infra/docker/nginx.conf`**

Use the nginx config from `docs/07-InfrastructureArchitecture.md` lines 230-295 as the template. Key elements:

- `events { worker_connections 1024; }`
- Rate limit zones: `general` (30r/s) and `auth` (5r/s)
- HTTP server block: listen 80, redirect all to HTTPS
- HTTPS server block: listen 443 ssl
  - SSL certificate paths: `/etc/letsencrypt/live/${DOMAIN}/fullchain.pem` and `privkey.pem`
  - `ssl_protocols TLSv1.2 TLSv1.3`
  - Location `/api/v1/auth/`: rate limit `auth`, proxy to `api-gateway:8080`
  - Location `/api/`: rate limit `general`, proxy to `api-gateway:8080`
  - Location `/`: rate limit `general`, proxy to `web-app:3000`
  - All proxy locations set: `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` headers

Note: The domain name in `server_name` should use the `DOMAIN_NAME` variable. Since nginx.conf doesn't support env vars natively, the deploy script will use `envsubst` to template it before SCPing, or we use a static domain and the deploy script generates the final config.

**Step 2: Commit**

```bash
git add infra/docker/nginx.conf
git commit -m "infra: add nginx reverse proxy configuration (#54)"
```

---

## Task 13: AWS Scripts — Config Template and Common Utilities

**Files:**
- Create: `scripts/aws/config.env.example`
- Create: `scripts/aws/lib/common.sh`

**Step 1: Create `scripts/aws/config.env.example`**

```bash
# AWS configuration for start/stop/deploy scripts
# Copy to config.env and fill in values from 'tofu output'

AWS_REGION=us-east-2
EC2_INSTANCE_ID=i-0xxxxxxxxxxxx
RDS_INSTANCE_ID=accountabilityatlas-db
EC2_IP=x.x.x.x
SSH_KEY_PATH=~/.ssh/your-key.pem
SSH_USER=ec2-user
ECR_REGISTRY=123456789012.dkr.ecr.us-east-2.amazonaws.com
RDS_ENDPOINT=accountabilityatlas-db.xxxx.us-east-2.rds.amazonaws.com:5432
DOMAIN_NAME=yourdomain.com
SQS_PREFIX=accountabilityatlas
```

**Step 2: Create `scripts/aws/lib/common.sh`**

Source the existing `scripts/lib/common.sh` for colored output functions (`info`, `success`, `warn`, `error`). Add AWS-specific utilities:

- `load_config()` — source `config.env`, validate required vars are set
- `ssh_ec2()` — SSH wrapper: `ssh -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=accept-new "$SSH_USER@$EC2_IP" "$@"`
- `scp_ec2()` — SCP wrapper: `scp -i "$SSH_KEY_PATH" -o StrictHostKeyChecking=accept-new "$@" "$SSH_USER@$EC2_IP:~/app/"`
- `wait_for_url()` — poll a URL until it returns 200 (with timeout)

**Step 3: Commit**

```bash
git add scripts/aws/config.env.example scripts/aws/lib/common.sh
git commit -m "infra: add AWS script config template and common utilities"
```

---

## Task 14: AWS Start Script

**Files:**
- Create: `scripts/aws/aws-start.sh`

**Step 1: Create `scripts/aws/aws-start.sh`**

```bash
#!/bin/bash
# Start the AWS demo environment (RDS + EC2 + Docker Compose)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
load_config

info "Starting RDS instance..."
aws rds start-db-instance --db-instance-identifier "$RDS_INSTANCE_ID" --region "$AWS_REGION" 2>/dev/null || true

info "Starting EC2 instance..."
aws ec2 start-instances --instance-ids "$EC2_INSTANCE_ID" --region "$AWS_REGION" > /dev/null

info "Waiting for RDS to become available (this may take a few minutes)..."
aws rds wait db-instance-available --db-instance-identifier "$RDS_INSTANCE_ID" --region "$AWS_REGION"
success "RDS is available"

info "Waiting for EC2 status checks..."
aws ec2 wait instance-status-ok --instance-ids "$EC2_INSTANCE_ID" --region "$AWS_REGION"
success "EC2 is ready"

info "Starting Docker Compose on EC2..."
ssh_ec2 "cd ~/app && docker compose up -d"

info "Waiting for health checks..."
wait_for_url "http://$EC2_IP:8080/actuator/health" "api-gateway" 60 5
wait_for_url "http://$EC2_IP:3000" "web-app" 30 5

success "Environment is up!"
info "Access the app at: https://$DOMAIN_NAME"
info "SSH: ssh -i $SSH_KEY_PATH $SSH_USER@$EC2_IP"
```

**Step 2: Make executable and commit**

```bash
chmod +x scripts/aws/aws-start.sh
git add scripts/aws/aws-start.sh
git commit -m "infra: add AWS start script"
```

---

## Task 15: AWS Stop Script

**Files:**
- Create: `scripts/aws/aws-stop.sh`

**Step 1: Create `scripts/aws/aws-stop.sh`**

```bash
#!/bin/bash
# Stop the AWS demo environment to minimize costs
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
load_config

info "Stopping Docker Compose on EC2..."
ssh_ec2 "cd ~/app && docker compose down" 2>/dev/null || warn "Could not stop containers (EC2 may already be stopped)"

info "Stopping EC2 instance..."
aws ec2 stop-instances --instance-ids "$EC2_INSTANCE_ID" --region "$AWS_REGION" > /dev/null

info "Stopping RDS instance..."
aws rds stop-db-instance --db-instance-identifier "$RDS_INSTANCE_ID" --region "$AWS_REGION" 2>/dev/null || true

success "Environment stopped"
warn "REMINDER: AWS auto-restarts stopped RDS instances after 7 days."
warn "If you won't demo within 7 days, check and re-stop the RDS instance."
```

**Step 2: Make executable and commit**

```bash
chmod +x scripts/aws/aws-stop.sh
git add scripts/aws/aws-stop.sh
git commit -m "infra: add AWS stop script"
```

---

## Task 16: AWS Deploy Script

**Files:**
- Create: `scripts/aws/aws-deploy.sh`

This is the most complex script. Follow the design doc Section 4 closely.

**Step 1: Create `scripts/aws/aws-deploy.sh`**

Logic flow:

1. Parse arguments: `--tag <name>` or use latest `integration-tested-*` tag
2. Validate tag exists — `git tag -l "$TAG"` in the first service repo. If no `integration-tested-*` tags exist, exit with error.
3. Define service repos array (paths relative to project root):
   ```bash
   JAVA_SERVICES=(AcctAtlas-api-gateway AcctAtlas-user-service AcctAtlas-video-service
                  AcctAtlas-location-service AcctAtlas-search-service AcctAtlas-moderation-service)
   NODE_SERVICES=(AcctAtlas-web-app)
   ```
4. Save current branch in each repo: `git -C "$repo" rev-parse --abbrev-ref HEAD`
5. Fetch tags and checkout the deploy tag in each repo:
   ```bash
   git -C "$repo" fetch --tags
   git -C "$repo" checkout "$TAG"
   ```
6. Build Java services: `./gradlew jibDockerBuild` in each repo
7. Build web-app: `docker build -t acctatlas/web-app:latest .` in web-app repo
8. Log in to ECR: `aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY`
9. Tag and push images to ECR for each service
10. Fetch secrets from Secrets Manager, generate `.env` file
11. Generate nginx.conf with domain substituted (use `sed` to replace domain placeholder)
12. SCP `docker-compose.prod.yml`, `nginx.conf`, `.env` to EC2 `~/app/`
13. SSH to EC2:
    - `aws ecr get-login-password | docker login ...` (ECR login on EC2)
    - `docker compose pull`
    - `docker compose up -d`
14. Wait for health checks
15. Clean up: delete local `.env`, restore each repo to its previous branch
16. Print success message with deployed tag name

**Step 2: Make executable and commit**

```bash
chmod +x scripts/aws/aws-deploy.sh
git add scripts/aws/aws-deploy.sh
git commit -m "infra: add AWS deploy script with integration-tested tag gate"
```

---

## Task 17: Stable JWT Signing Keys — User Service Code Change

**Files:**
- Modify: `AcctAtlas-user-service/src/main/java/com/accountabilityatlas/userservice/config/JwtConfig.java`
- Modify: `AcctAtlas-user-service/src/main/java/com/accountabilityatlas/userservice/config/JwtProperties.java`
- Create: `AcctAtlas-user-service/src/main/resources/application-prod.yml`
- Modify: `AcctAtlas-user-service/src/test/java/com/accountabilityatlas/userservice/config/JwtAuthenticationFilterTest.java` (verify no breakage)

This task happens in the **user-service repo** (separate git history).

**Step 1: Add `private-key` property to `JwtProperties`**

In `JwtProperties.java`, add:

```java
private String privateKey;
```

Lombok `@Getter`/`@Setter` generates the accessors. This maps to `app.jwt.private-key` from YAML.

**Step 2: Modify `JwtConfig.jwtKeyPair()` to use configured key when present**

Replace the current `JwtConfig.java` with:

```java
package com.accountabilityatlas.userservice.config;

import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.RSAPrivateCrtKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.RSAPublicKeySpec;
import java.util.Base64;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class JwtConfig {

  @Bean
  public KeyPair jwtKeyPair(JwtProperties properties) throws Exception {
    if (properties.getPrivateKey() != null && !properties.getPrivateKey().isBlank()) {
      return loadKeyPair(properties.getPrivateKey());
    }
    KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
    generator.initialize(2048);
    return generator.generateKeyPair();
  }

  private KeyPair loadKeyPair(String pem) throws Exception {
    String base64 =
        pem.replace("-----BEGIN PRIVATE KEY-----", "")
            .replace("-----END PRIVATE KEY-----", "")
            .replaceAll("\\s", "");
    byte[] decoded = Base64.getDecoder().decode(base64);

    KeyFactory keyFactory = KeyFactory.getInstance("RSA");
    PKCS8EncodedKeySpec privateSpec = new PKCS8EncodedKeySpec(decoded);
    RSAPrivateCrtKey privateKey = (RSAPrivateCrtKey) keyFactory.generatePrivate(privateSpec);

    RSAPublicKeySpec publicSpec =
        new RSAPublicKeySpec(privateKey.getModulus(), privateKey.getPublicExponent());

    return new KeyPair(keyFactory.generatePublic(publicSpec), privateKey);
  }
}
```

**Step 3: Create `application-prod.yml`**

```yaml
spring:
  flyway:
    locations:
      - classpath:db/migration

app:
  jwt:
    private-key: ${APP_JWT_PRIVATE_KEY}
```

Note: Unlike the docker profile, prod does NOT include `classpath:db/devdata` for Flyway — no seed data in production.

**Step 4: Run existing tests to verify no breakage**

Run: `./gradlew test` in the user-service repo.

All existing tests should pass because:
- Tests use the default profile (no `app.jwt.private-key` set) → auto-generation path
- `JwtConfig` now takes `JwtProperties` as a parameter (Spring injects it), but in tests `JwtProperties` is a component that's auto-created

**Step 5: Write a test for the configured key path**

Add a test in a new file `AcctAtlas-user-service/src/test/java/com/accountabilityatlas/userservice/config/JwtConfigTest.java`:

```java
package com.accountabilityatlas.userservice.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.RSAPublicKey;
import java.util.Base64;
import org.junit.jupiter.api.Test;

class JwtConfigTest {

  private final JwtConfig jwtConfig = new JwtConfig();

  @Test
  void jwtKeyPair_withNoPrivateKey_generatesNewKeyPair() throws Exception {
    JwtProperties properties = new JwtProperties();

    KeyPair keyPair = jwtConfig.jwtKeyPair(properties);

    assertThat(keyPair).isNotNull();
    assertThat(keyPair.getPrivate().getAlgorithm()).isEqualTo("RSA");
    assertThat(keyPair.getPublic().getAlgorithm()).isEqualTo("RSA");
  }

  @Test
  void jwtKeyPair_withConfiguredPrivateKey_loadsThatKey() throws Exception {
    // Generate a key pair and extract the PEM-encoded private key
    KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
    generator.initialize(2048);
    KeyPair original = generator.generateKeyPair();
    String pem =
        "-----BEGIN PRIVATE KEY-----\n"
            + Base64.getMimeEncoder(64, "\n".getBytes()).encodeToString(original.getPrivate().getEncoded())
            + "\n-----END PRIVATE KEY-----";

    JwtProperties properties = new JwtProperties();
    properties.setPrivateKey(pem);

    KeyPair loaded = jwtConfig.jwtKeyPair(properties);

    // Private key bytes should match
    assertThat(loaded.getPrivate().getEncoded()).isEqualTo(original.getPrivate().getEncoded());
    // Derived public key should match
    RSAPublicKey originalPublic = (RSAPublicKey) original.getPublic();
    RSAPublicKey loadedPublic = (RSAPublicKey) loaded.getPublic();
    assertThat(loadedPublic.getModulus()).isEqualTo(originalPublic.getModulus());
    assertThat(loadedPublic.getPublicExponent()).isEqualTo(originalPublic.getPublicExponent());
  }
}
```

**Step 6: Run tests**

Run: `./gradlew test`
Expected: All tests pass (existing + new).

**Step 7: Commit (in user-service repo)**

```bash
cd AcctAtlas-user-service
git add -A
git commit -m "feat(auth): support stable JWT signing key from config property (#36)

When app.jwt.private-key is set (prod profile), loads the PEM-encoded RSA
key instead of generating a new one on startup. Local/docker profiles
continue with auto-generated keys.

Closes #36"
```

---

## Task 18: Production Profile for Other Services

**Files (one per service repo):**
- Create: `AcctAtlas-api-gateway/src/main/resources/application-prod.yml`
- Create: `AcctAtlas-video-service/src/main/resources/application-prod.yml`
- Create: `AcctAtlas-location-service/src/main/resources/application-prod.yml`
- Create: `AcctAtlas-search-service/src/main/resources/application-prod.yml`
- Create: `AcctAtlas-moderation-service/src/main/resources/application-prod.yml`

Each service needs an `application-prod.yml` that differs from `application-docker.yml` in:
- No LocalStack SQS endpoint override (use real AWS SQS with IAM credentials)
- No dev seed data in Flyway locations
- Datasource credentials from environment variables (not hardcoded `local_dev`)
- Logging level set to INFO instead of DEBUG

Check each service's existing `application-docker.yml` and `application.yml` to understand what needs to change. The key pattern:

```yaml
spring:
  flyway:
    locations:
      - classpath:db/migration
  cloud:
    aws:
      region:
        static: ${AWS_REGION:us-east-2}
logging:
  level:
    com.accountabilityatlas: INFO
    org.springframework.security: WARN
```

Note: Database credentials and service URLs don't need to be in `application-prod.yml` — they come from environment variables set in `docker-compose.prod.yml` which Spring Boot auto-binds (e.g., `SPRING_DATASOURCE_URL`).

Each service gets its own commit in its own repo, referencing a relevant issue or the top-level #54.

---

## Task 19: Database Initialization Script for RDS

**Files:**
- Create: `infra/docker/init-databases.sql`

**Step 1: Create `infra/docker/init-databases.sql`**

Adapt `docker/postgres/init-databases.sql` for RDS. Key differences:
- RDS connects as the master user (set during `tofu apply`), not `postgres`
- Passwords come from the `DB_PASSWORD` environment variable — but since this is a SQL script run manually, use a placeholder and document the replacement
- PostGIS extension installation (`CREATE EXTENSION IF NOT EXISTS postgis`) requires `rds_superuser` role — the master user has this by default

The deploy script runs this on first deploy via `psql` through an SSH tunnel or from the EC2 instance.

**Step 2: Commit**

```bash
git add infra/docker/init-databases.sql
git commit -m "infra: add RDS database initialization script"
```

---

## Task 20: Final Validation and Documentation

**Step 1: Run `tofu validate` to check HCL syntax**

From the `infra/` directory:
```bash
tofu init -backend=false
tofu validate
```

Fix any syntax errors. This validates the HCL without connecting to AWS.

**Step 2: Review all committed files**

Verify no secrets, passwords, emails, or personal information in any tracked file:
```bash
git log --oneline --all
git diff master~N..master  # review all changes
```

**Step 3: Final commit if any fixes needed**

```bash
git commit -m "infra: fix validation issues"
```

---

## Summary: Git Operations by Repository

| Repository | Tasks | Branch | Issue |
|------------|-------|--------|-------|
| AccountabilityAtlas (top-level) | 1-16, 19-20 | Feature branch from master | #54 |
| AcctAtlas-user-service | 17 | Feature branch from master | #36 |
| AcctAtlas-api-gateway | 18 | Feature branch from master | — |
| AcctAtlas-video-service | 18 | Feature branch from master | #3 |
| AcctAtlas-location-service | 18 | Feature branch from master | — |
| AcctAtlas-search-service | 18 | Feature branch from master | — |
| AcctAtlas-moderation-service | 18 | Feature branch from master | — |

Each repo gets its own feature branch, PR, and merge. The top-level repo PR references #54. The user-service PR references user-service #36. Service prod profiles can reference the top-level #54 or be standalone.
