#!/bin/bash
#
# Deploy to AWS from an integration-tested tag
#
# Builds all services from a known-good tag, pushes images to ECR,
# and deploys to the EC2 instance via Docker Compose.
#
# Usage:
#   ./scripts/aws/aws-deploy.sh                    # deploy latest integration-tested-* tag
#   ./scripts/aws/aws-deploy.sh --tag <tag-name>   # deploy a specific tag
#
# The script will FAIL if no integration-tested tags exist. There is no
# override or force flag -- only tested code gets deployed.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
load_config

PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- Service definitions ---

JAVA_SERVICES=(AcctAtlas-api-gateway AcctAtlas-user-service AcctAtlas-video-service \
               AcctAtlas-location-service AcctAtlas-search-service AcctAtlas-moderation-service)
NODE_SERVICES=(AcctAtlas-web-app)
ALL_SERVICES=("${JAVA_SERVICES[@]}" "${NODE_SERVICES[@]}")

# Files generated during deploy that must be cleaned up
GENERATED_ENV=""
GENERATED_NGINX=""
SAVED_BRANCHES=()

# ---------------------------------------------------------------------------
# cleanup - restore repos and remove generated files (runs on EXIT)
# ---------------------------------------------------------------------------
cleanup() {
    info "Restoring repos to original branches..."
    for i in "${!ALL_SERVICES[@]}"; do
        if [ -n "${SAVED_BRANCHES[$i]:-}" ]; then
            git -C "$PROJECT_ROOT/${ALL_SERVICES[$i]}" checkout "${SAVED_BRANCHES[$i]}" 2>/dev/null || true
        fi
    done
    rm -f "$GENERATED_ENV" "$GENERATED_NGINX" 2>/dev/null || true
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# image_name - map repo name to local Docker image name
# e.g. AcctAtlas-user-service -> acctatlas/user-service
# ---------------------------------------------------------------------------
image_name() {
    local repo=$1
    local svc="${repo#AcctAtlas-}"
    echo "acctatlas/${svc}"
}

# ---------------------------------------------------------------------------
# ecr_name - map repo name to ECR repository name
# e.g. AcctAtlas-user-service -> acct-atlas-user-service
# ---------------------------------------------------------------------------
ecr_name() {
    local repo=$1
    local svc="${repo#AcctAtlas-}"
    echo "acct-atlas-${svc}"
}

# --- Parse arguments ---

DEPLOY_TAG=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tag)
            DEPLOY_TAG="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--tag <tag-name>]"
            echo ""
            echo "Options:"
            echo "  --tag <name>  Deploy a specific integration-tested tag"
            echo "                (default: latest integration-tested-* tag)"
            exit 0
            ;;
        *)
            error "Unknown argument: $1"
            echo "Usage: $0 [--tag <tag-name>]"
            exit 1
            ;;
    esac
done

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   AccountabilityAtlas - Deploy to AWS      ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# --- Step 1: Resolve deploy tag ---

if [ -z "$DEPLOY_TAG" ]; then
    info "Finding latest integration-tested tag..."
    git -C "$PROJECT_ROOT/AcctAtlas-user-service" fetch --tags --quiet
    DEPLOY_TAG=$(git -C "$PROJECT_ROOT/AcctAtlas-user-service" tag -l "integration-tested-*" --sort=-creatordate | head -1)

    if [ -z "$DEPLOY_TAG" ]; then
        error "No integration-tested tags found."
        echo ""
        echo "  Tags are created by the CI pipeline after all integration tests pass."
        echo "  Run the full test suite first, then tag the repos:"
        echo "    integration-tested-YYYY-MM-DD-HHMMSS"
        echo ""
        exit 1
    fi
fi

success "Deploy tag: $DEPLOY_TAG"

# --- Step 2: Save current branches and checkout deploy tag ---

info "Checking out $DEPLOY_TAG in all service repos..."

for i in "${!ALL_SERVICES[@]}"; do
    repo="${ALL_SERVICES[$i]}"
    repo_dir="$PROJECT_ROOT/$repo"

    if [ ! -d "$repo_dir" ]; then
        error "Repo directory not found: $repo_dir"
        exit 1
    fi

    # Save current branch/ref for cleanup
    SAVED_BRANCHES[$i]=$(git -C "$repo_dir" rev-parse --abbrev-ref HEAD 2>/dev/null || \
                          git -C "$repo_dir" rev-parse HEAD)

    # Fetch tags and checkout
    git -C "$repo_dir" fetch --tags --quiet
    git -C "$repo_dir" checkout "$DEPLOY_TAG" --quiet 2>/dev/null
    success "  $repo -> $DEPLOY_TAG"
done

# --- Step 3: Build Java services ---

echo ""
info "Building Java services..."

for repo in "${JAVA_SERVICES[@]}"; do
    local_img=$(image_name "$repo")
    info "  Building $local_img..."
    (cd "$PROJECT_ROOT/$repo" && ./gradlew jibDockerBuild -q)
    success "  $local_img built"
done

# --- Step 4: Fetch secrets for web-app build args ---

echo ""
info "Fetching secrets from AWS Secrets Manager..."

MAPBOX_TOKEN=$(aws secretsmanager get-secret-value \
    --secret-id accountabilityatlas/mapbox-access-token \
    --region "$AWS_REGION" \
    --query SecretString --output text)
success "Secrets retrieved"

# --- Step 5: Build web-app ---

info "Building web-app Docker image..."
docker build \
    --build-arg NEXT_PUBLIC_API_URL="https://$DOMAIN_NAME/api/v1" \
    --build-arg NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN="$MAPBOX_TOKEN" \
    -t acctatlas/web-app:latest \
    "$PROJECT_ROOT/AcctAtlas-web-app"
success "web-app built"

# --- Step 6: ECR login ---

echo ""
info "Logging in to ECR ($ECR_REGISTRY)..."
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ECR_REGISTRY"
success "ECR login successful"

# --- Step 7: Tag and push images ---

echo ""
info "Tagging and pushing images to ECR..."

for repo in "${ALL_SERVICES[@]}"; do
    local_img="$(image_name "$repo"):latest"
    ecr_repo="$ECR_REGISTRY/$(ecr_name "$repo")"

    docker tag "$local_img" "$ecr_repo:$DEPLOY_TAG"
    docker tag "$local_img" "$ecr_repo:latest"

    info "  Pushing $(ecr_name "$repo")..."
    docker push "$ecr_repo:$DEPLOY_TAG" --quiet
    docker push "$ecr_repo:latest" --quiet
    success "  $(ecr_name "$repo") pushed"
done

# --- Step 8: Fetch remaining secrets and generate .env ---

echo ""
info "Generating .env file for EC2..."

JWT_PRIVATE_KEY=$(aws secretsmanager get-secret-value \
    --secret-id accountabilityatlas/jwt-private-key \
    --region "$AWS_REGION" \
    --query SecretString --output text)

YOUTUBE_API_KEY=$(aws secretsmanager get-secret-value \
    --secret-id accountabilityatlas/youtube-api-key \
    --region "$AWS_REGION" \
    --query SecretString --output text)

ADMIN_PASSWORD_HASH=$(aws secretsmanager get-secret-value \
    --secret-id accountabilityatlas/admin-password-hash \
    --region "$AWS_REGION" \
    --query SecretString --output text)

DB_PASSWORD=$(aws secretsmanager get-secret-value \
    --secret-id accountabilityatlas/db-password \
    --region "$AWS_REGION" \
    --query SecretString --output text)

GENERATED_ENV="$SCRIPT_DIR/.env.generated"
cat > "$GENERATED_ENV" <<EOF
# Generated by aws-deploy.sh — do not edit
TAG=$DEPLOY_TAG
AWS_REGION=$AWS_REGION
ECR_REGISTRY=$ECR_REGISTRY
RDS_ENDPOINT=$RDS_ENDPOINT
SQS_PREFIX=$SQS_PREFIX
DOMAIN_NAME=$DOMAIN_NAME
DB_PASSWORD=$DB_PASSWORD
JWT_PRIVATE_KEY=$JWT_PRIVATE_KEY
YOUTUBE_API_KEY=$YOUTUBE_API_KEY
MAPBOX_TOKEN=$MAPBOX_TOKEN
ADMIN_EMAIL=admin@$DOMAIN_NAME
ADMIN_PASSWORD_HASH=$ADMIN_PASSWORD_HASH
NEXT_PUBLIC_API_URL=https://$DOMAIN_NAME/api/v1
NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN=$MAPBOX_TOKEN
EOF

success ".env file generated"

# --- Step 9: Generate nginx.conf from template ---

info "Generating nginx.conf..."

GENERATED_NGINX="$SCRIPT_DIR/nginx.conf.generated"
sed "s/DOMAIN_PLACEHOLDER/$DOMAIN_NAME/g" \
    "$PROJECT_ROOT/infra/docker/nginx.conf" > "$GENERATED_NGINX"

success "nginx.conf generated (domain=$DOMAIN_NAME)"

# --- Step 10: Copy files to EC2 ---

echo ""
info "Copying deployment files to EC2..."

ssh_ec2 "mkdir -p ~/app"
scp_ec2 "$PROJECT_ROOT/infra/docker/docker-compose.prod.yml"
scp_ec2 "$GENERATED_NGINX"
scp_ec2 "$GENERATED_ENV"

# Rename files on EC2 to their expected names
ssh_ec2 "cd ~/app && mv docker-compose.prod.yml docker-compose.yml \
    && mv nginx.conf.generated nginx.conf \
    && mv .env.generated .env"

success "Files deployed to EC2"

# --- Step 11: Pull and start on EC2 ---

echo ""
info "Pulling images and starting services on EC2..."

ssh_ec2 "cd ~/app \
    && aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY \
    && docker compose pull \
    && docker compose up -d"

# --- Step 12: Health checks ---

echo ""
info "Waiting for services to become healthy..."

HEALTH_FAILED=false

if ! wait_for_health_ssh "http://localhost:8080/actuator/health" "api-gateway" 60 5; then
    HEALTH_FAILED=true
fi

if ! wait_for_health_ssh "http://localhost:3000" "web-app" 30 5; then
    HEALTH_FAILED=true
fi

# --- Done ---

echo ""
if [ "$HEALTH_FAILED" = true ]; then
    warn "Some services did not become healthy. SSH in to check logs:"
    echo "  ssh -i $SSH_KEY_PATH $SSH_USER@$EC2_IP"
    echo "  cd ~/app && docker compose logs -f"
    exit 1
fi

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}        Deployment complete!                ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Tag:          $DEPLOY_TAG"
echo "  Application:  https://$DOMAIN_NAME"
echo ""
echo "  SSH access:"
echo "    ssh -i $SSH_KEY_PATH $SSH_USER@$EC2_IP"
echo ""
