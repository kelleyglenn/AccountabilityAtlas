# Infrastructure Bootstrap

One-time manual steps to prepare AWS for OpenTofu. Run these before `tofu init`.

## Prerequisites

- AWS CLI v2 configured with appropriate IAM permissions
- OpenTofu >= 1.8 installed
- An SSH key pair (for EC2 access)
- Domain name registered

## 1. Create S3 State Bucket

```bash
aws s3api create-bucket --bucket accountabilityatlas-tfstate \
  --region us-east-2 --create-bucket-configuration LocationConstraint=us-east-2

aws s3api put-bucket-versioning --bucket accountabilityatlas-tfstate \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption --bucket accountabilityatlas-tfstate \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-public-access-block --bucket accountabilityatlas-tfstate \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

## 2. Create DynamoDB Lock Table

```bash
aws dynamodb create-table --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region us-east-2
```

## 3. Generate and Store JWT RSA Key

All Spring services share this key for JWT signing and verification.

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out jwt-private.pem

aws secretsmanager create-secret --name accountabilityatlas/jwt-private-key \
  --secret-string file://jwt-private.pem --region us-east-2

rm jwt-private.pem
```

## 4. Store Remaining Secrets

```bash
aws secretsmanager create-secret --name accountabilityatlas/db-password \
  --secret-string 'YOUR_RDS_MASTER_PASSWORD' --region us-east-2

aws secretsmanager create-secret --name accountabilityatlas/youtube-api-key \
  --secret-string 'YOUR_YOUTUBE_API_KEY' --region us-east-2

aws secretsmanager create-secret --name accountabilityatlas/mapbox-access-token \
  --secret-string 'YOUR_MAPBOX_ACCESS_TOKEN' --region us-east-2
```

Generate a bcrypt hash for the admin password, then store it:

```bash
htpasswd -nbBC 12 "" 'your-password' | cut -d: -f2
```

```bash
aws secretsmanager create-secret --name accountabilityatlas/admin-password-hash \
  --secret-string 'BCRYPT_HASH_FROM_ABOVE' --region us-east-2
```

**Important:** The `db-password` value must match the `db_password` in your `terraform.tfvars`.

## 5. Create terraform.tfvars

```bash
cp example.tfvars terraform.tfvars
```

Fill in all values. This file is gitignored and must never be committed.

## 6. Initialize and Apply

```bash
tofu init
tofu plan
tofu apply
```

## 7. Post-Apply Steps

Update your domain registrar's nameservers with the Route 53 values:

```bash
tofu output route53_nameservers
```

Note the instance IDs for the start/stop scripts:

```bash
tofu output ec2_instance_id
tofu output rds_instance_id
```

Copy output values into `scripts/aws/config.env`.

## 8. First Deployment

The first deployment requires several manual steps on the EC2 instance before running the deploy script.

### 8a. Install tools on EC2

SSH into the instance and install psql (for database init) and certbot (for TLS):

```bash
ssh -i ~/.ssh/accountabilityatlas-deploy ec2-user@<EC2_IP>
sudo dnf install -y postgresql16 certbot
```

### 8b. Initialize databases

Each service needs its own database and user in RDS. From the EC2 instance:

```bash
export PGHOST=<RDS_ENDPOINT_HOST>   # e.g. accountabilityatlas-db.xxx.us-east-2.rds.amazonaws.com
export PGUSER=postgres
export PGPASSWORD='<master_password>'
```

Run each statement individually (CREATE DATABASE cannot run inside a transaction on RDS). Replace `CHANGE_ME_DB_PASSWORD` with the password stored in Secrets Manager as `accountabilityatlas/db-password`:

```bash
# For each service (user_service, video_service, location_service, search_service, moderation_service):
psql -d accountabilityatlas -c "CREATE USER user_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';"
psql -d accountabilityatlas -c "GRANT user_service TO postgres;"
psql -d accountabilityatlas -c "CREATE DATABASE user_service OWNER user_service;"
psql -d user_service -c "GRANT ALL ON SCHEMA public TO user_service;"
# ... repeat for each service (see infra/docker/init-databases.sql for full list)
```

Note: location_service also needs PostGIS: `psql -d location_service -c "CREATE EXTENSION IF NOT EXISTS postgis;"`

### 8c. Create bootstrap tag

The deploy script requires an `integration-tested-*` tag. For the very first deployment (before any integration tests have run), create a bootstrap tag across all service repos:

```bash
TAG="integration-tested-$(date +%Y-%m-%d)-bootstrap"
for repo in AcctAtlas-api-gateway AcctAtlas-user-service AcctAtlas-video-service \
            AcctAtlas-location-service AcctAtlas-search-service \
            AcctAtlas-moderation-service AcctAtlas-web-app; do
    git -C "$repo" tag "$TAG"
    git -C "$repo" push origin "$TAG"
done
```

### 8d. Run deploy script

```bash
../scripts/aws/aws-deploy.sh
```

### 8e. Obtain TLS certificate

Stop nginx (so certbot can use port 80), obtain the certificate, then start nginx:

```bash
ssh -i ~/.ssh/accountabilityatlas-deploy ec2-user@<EC2_IP>

# Stop nginx to free port 80
cd ~/app && docker compose stop nginx

# Obtain certificate
sudo certbot certonly --standalone \
    -d accountabilityatlas.com -d www.accountabilityatlas.com \
    --non-interactive --agree-tos --email admin@accountabilityatlas.com

# Enable auto-renewal
sudo systemctl enable --now certbot-renew.timer

# Add hook to reload nginx after renewal
sudo sh -c 'cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh << "HOOK"
#!/bin/bash
docker compose -f /home/ec2-user/app/docker-compose.yml exec nginx nginx -s reload
HOOK
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh'

# Start nginx (certs now exist)
docker compose up -d nginx
```

## 9. Start/Stop

To minimize costs when the environment is not in use:

```bash
../scripts/aws/aws-stop.sh   # Stop EC2 + RDS
../scripts/aws/aws-start.sh  # Start EC2 + RDS
```

Note: AWS automatically restarts stopped RDS instances after 7 days. The stop script will need to be re-run if the environment should remain off longer.
