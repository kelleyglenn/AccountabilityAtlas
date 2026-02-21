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

Run the deploy script to build, push, and start all services:

```bash
../scripts/aws/aws-deploy.sh
```

The first deployment must also initialize per-service databases. See `infra/docker/init-databases.sql` for the SQL that creates each service's database and user.

## 9. Start/Stop

To minimize costs when the environment is not in use:

```bash
../scripts/aws/aws-stop.sh   # Stop EC2 + RDS
../scripts/aws/aws-start.sh  # Start EC2 + RDS
```

Note: AWS automatically restarts stopped RDS instances after 7 days. The stop script will need to be re-run if the environment should remain off longer.
