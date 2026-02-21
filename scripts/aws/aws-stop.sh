#!/bin/bash
#
# Stop the AWS demo environment to minimize costs
#
# Shuts down in order:
#   1. Docker Compose services on EC2
#   2. EC2 compute instance
#   3. RDS database instance
#
# Usage:
#   ./scripts/aws/aws-stop.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
load_config

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}   AccountabilityAtlas - Stop Environment   ${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# --- Step 1: Stop Docker Compose on EC2 ---
info "Stopping Docker Compose services on EC2..."
ssh_ec2 "cd ~/app && docker compose down" 2>/dev/null || warn "Could not reach EC2 (may already be stopped)"

# --- Step 2: Stop EC2 ---
info "Stopping EC2 instance ($EC2_INSTANCE_ID)..."
aws ec2 stop-instances \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" > /dev/null
success "EC2 stop initiated"

# --- Step 3: Stop RDS ---
info "Stopping RDS instance ($RDS_INSTANCE_ID)..."
aws rds stop-db-instance \
    --db-instance-identifier "$RDS_INSTANCE_ID" \
    --region "$AWS_REGION" 2>/dev/null || warn "RDS may already be stopped"
success "RDS stop initiated"

# --- Done ---
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}        Environment is shutting down        ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "  EC2 and RDS will finish stopping in the background."
echo "  No charges accrue while instances are stopped."
echo ""
echo -e "  ${YELLOW}[WARN]${NC} AWS automatically restarts stopped RDS instances after 7 days."
echo "  If the demo will be idle longer, consider running this script weekly"
echo "  or setting up a scheduled Lambda to re-stop the instance."
echo ""
