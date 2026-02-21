#!/bin/bash
#
# Start the AWS demo environment (RDS + EC2 + Docker Compose)
#
# Brings up the full stack in order:
#   1. RDS database instance
#   2. EC2 compute instance
#   3. Docker Compose services on EC2
#
# Usage:
#   ./scripts/aws/aws-start.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
load_config

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   AccountabilityAtlas - Start Environment  ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# --- Step 1: Start RDS ---
info "Starting RDS instance ($RDS_INSTANCE_ID)..."
aws rds start-db-instance \
    --db-instance-identifier "$RDS_INSTANCE_ID" \
    --region "$AWS_REGION" 2>/dev/null || warn "RDS may already be running"

# --- Step 2: Start EC2 ---
info "Starting EC2 instance ($EC2_INSTANCE_ID)..."
aws ec2 start-instances \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" > /dev/null

# --- Step 3: Wait for RDS ---
info "Waiting for RDS to become available (this may take several minutes)..."
aws rds wait db-instance-available \
    --db-instance-identifier "$RDS_INSTANCE_ID" \
    --region "$AWS_REGION"
success "RDS is available"

# --- Step 4: Wait for EC2 ---
info "Waiting for EC2 status checks to pass..."
aws ec2 wait instance-status-ok \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION"
success "EC2 is ready"

# --- Step 5: Start Docker Compose on EC2 ---
info "Starting Docker Compose services on EC2..."
ssh_ec2 "cd ~/app && docker compose up -d"

# --- Step 6: Health checks ---
echo ""
info "Waiting for services to become healthy..."

HEALTH_FAILED=false

if ! wait_for_url "http://$EC2_IP:8080/actuator/health" "api-gateway" 60 5; then
    HEALTH_FAILED=true
fi

if ! wait_for_url "http://$EC2_IP:3000" "web-app" 30 5; then
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
echo -e "${GREEN}       Environment is up and running!       ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  Application:  https://$DOMAIN_NAME"
echo "  API Gateway:  http://$EC2_IP:8080/actuator/health"
echo "  Web App:      http://$EC2_IP:3000"
echo ""
echo "  SSH access:"
echo "    ssh -i $SSH_KEY_PATH $SSH_USER@$EC2_IP"
echo ""
