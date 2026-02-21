#!/bin/bash
#
# Common utilities for AWS lifecycle scripts
#
# Extends scripts/lib/common.sh with AWS-specific helpers:
#   load_config  - source config.env and validate required variables
#   ssh_ec2      - run a command on the EC2 instance over SSH
#   scp_ec2      - copy files to ~/app/ on the EC2 instance
#   wait_for_url - poll a URL until it returns HTTP 200
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the project-wide common utilities (colored output, health checks, etc.)
source "$SCRIPT_DIR/../../lib/common.sh"

# ---------------------------------------------------------------------------
# load_config - source config.env and validate that all required vars are set
# ---------------------------------------------------------------------------
load_config() {
    local config_file="$SCRIPT_DIR/../config.env"

    if [ ! -f "$config_file" ]; then
        error "Config file not found: $config_file"
        echo ""
        echo "  Copy the example and fill in your values:"
        echo "    cp scripts/aws/config.env.example scripts/aws/config.env"
        echo ""
        exit 1
    fi

    source "$config_file"

    local required_vars=(
        AWS_REGION
        EC2_INSTANCE_ID
        RDS_INSTANCE_ID
        EC2_IP
        SSH_KEY_PATH
        SSH_USER
        ECR_REGISTRY
        RDS_ENDPOINT
        DOMAIN_NAME
        SQS_PREFIX
    )

    local missing=()
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing+=("$var")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        error "Missing required variables in config.env:"
        for var in "${missing[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo "  See config.env.example for reference."
        exit 1
    fi

    success "Config loaded (region=$AWS_REGION, ec2=$EC2_INSTANCE_ID)"
}

# ---------------------------------------------------------------------------
# ssh_ec2 - run a command on the EC2 instance
# Usage: ssh_ec2 "cd ~/app && docker compose up -d"
# ---------------------------------------------------------------------------
ssh_ec2() {
    ssh -i "$SSH_KEY_PATH" \
        -o StrictHostKeyChecking=accept-new \
        "$SSH_USER@$EC2_IP" \
        "$@"
}

# ---------------------------------------------------------------------------
# scp_ec2 - copy files to ~/app/ on the EC2 instance
# Usage: scp_ec2 file1 file2
# ---------------------------------------------------------------------------
scp_ec2() {
    scp -i "$SSH_KEY_PATH" \
        -o StrictHostKeyChecking=accept-new \
        "$@" \
        "$SSH_USER@$EC2_IP:~/app/"
}

# ---------------------------------------------------------------------------
# wait_for_url - poll a URL until HTTP 200
# Usage: wait_for_url <url> <name> [max_attempts] [interval]
# ---------------------------------------------------------------------------
wait_for_url() {
    local url=$1
    local name=$2
    local max_attempts=${3:-30}
    local interval=${4:-5}
    local attempt=1

    info "Waiting for $name at $url..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s -f -o /dev/null "$url" 2>/dev/null; then
            success "$name is ready!"
            return 0
        fi
        echo -n "."
        sleep "$interval"
        attempt=$((attempt + 1))
    done

    echo ""
    error "$name failed to respond after $max_attempts attempts ($(( max_attempts * interval ))s)"
    return 1
}

# ---------------------------------------------------------------------------
# wait_for_health_ssh - poll a localhost URL on EC2 via SSH until HTTP 200
# Usage: wait_for_health_ssh <url> <name> [max_attempts] [interval]
# ---------------------------------------------------------------------------
wait_for_health_ssh() {
    local url=$1
    local name=$2
    local max_attempts=${3:-30}
    local interval=${4:-5}
    local attempt=1

    info "Waiting for $name ($url via SSH)..."

    while [ $attempt -le $max_attempts ]; do
        if ssh_ec2 "curl -s -f -o /dev/null '$url'" 2>/dev/null; then
            success "$name is ready!"
            return 0
        fi
        echo -n "."
        sleep "$interval"
        attempt=$((attempt + 1))
    done

    echo ""
    error "$name failed to respond after $max_attempts attempts ($(( max_attempts * interval ))s)"
    return 1
}
