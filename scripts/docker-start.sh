#!/bin/bash
#
# Docker Mode Startup Script
#
# Starts all services via Docker containers:
#   - PostgreSQL, Redis, LocalStack (infrastructure)
#   - User Service, Location Service, Video Service, Search Service, Moderation Service
#   - API Gateway, Web App
#
# Prerequisites:
#   - Java service images must be built first:
#     ./gradlew jibDockerBuildAll
#   - Web App image is built automatically by docker-compose
#
# Usage:
#   ./scripts/docker-start.sh
#
# To stop services:
#   ./scripts/docker-stop.sh
#

set -e

# Load common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

print_banner
info "Starting Docker environment..."
echo ""

# Change to root directory
cd "$ROOT_DIR"

# Step 1: Check if Docker images exist
info "Checking for Docker images..."

REQUIRED_IMAGES=(
    "acctatlas/user-service:latest"
    "acctatlas/location-service:latest"
    "acctatlas/video-service:latest"
    "acctatlas/search-service:latest"
    "acctatlas/moderation-service:latest"
    "acctatlas/api-gateway:latest"
)

IMAGES_MISSING=false
for image in "${REQUIRED_IMAGES[@]}"; do
    if ! docker image inspect "$image" > /dev/null 2>&1; then
        warn "Image $image not found"
        IMAGES_MISSING=true
    fi
done

if [ "$IMAGES_MISSING" = true ]; then
    echo ""
    warn "Docker images are missing. Build them with:"
    echo ""
    echo "  ./gradlew jibDockerBuildAll"
    echo ""
    read -p "Would you like to build them now? [y/N] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Building all service images..."
        ./gradlew jibDockerBuildAll
        success "Docker images built successfully"
    else
        error "Cannot start without Docker images. Please build them first."
        exit 1
    fi
fi

# Step 2: Start all services via docker-compose
info "Starting all services via docker-compose..."
docker-compose --profile backend --profile frontend up -d

# Step 3: Wait for infrastructure to be healthy
wait_for_docker_healthy postgres 30
wait_for_docker_healthy redis 15
wait_for_docker_healthy localstack 30

# Step 4: Wait for Java services (they depend on infrastructure)
info "Waiting for User Service to be ready..."
wait_for_health "http://localhost:8081/actuator/health" "User Service" 60 3

info "Waiting for Location Service to be ready..."
wait_for_health "http://localhost:8083/actuator/health" "Location Service" 60 3

info "Waiting for Video Service to be ready..."
wait_for_health "http://localhost:8082/actuator/health" "Video Service" 60 3

info "Waiting for Search Service to be ready..."
wait_for_health "http://localhost:8084/actuator/health" "Search Service" 60 3

info "Waiting for Moderation Service to be ready..."
wait_for_health "http://localhost:8085/actuator/health" "Moderation Service" 60 3

info "Waiting for API Gateway to be ready..."
wait_for_health "http://localhost:8080/actuator/health" "API Gateway" 60 3

# Step 5: Wait for Web App to be ready
info "Waiting for Web App to be ready..."
wait_for_health "http://localhost:3000" "Web App" 60 3

# Step 6: Open browser
open_browser "http://localhost:3000"

# Step 7: Print status
print_status

echo "Docker containers:"
docker-compose --profile backend --profile frontend ps
echo ""
echo "Logs:"
echo "  - All services:     docker-compose --profile backend --profile frontend logs -f"
echo "  - Specific service: docker-compose logs -f <service-name>"
echo ""
echo "To stop all services:"
echo "  ./scripts/docker-stop.sh"
echo ""
