#!/bin/bash
#
# Docker Mode Startup Script
#
# Starts all backend services via Docker containers:
#   - PostgreSQL, Redis, User Service, API Gateway via docker-compose
#   - Web App via npm run dev (not containerized yet)
#
# Prerequisites:
#   - Docker images must be built first:
#     cd AcctAtlas-user-service && ./gradlew jibDockerBuild && cd ..
#     cd AcctAtlas-api-gateway && ./gradlew jibDockerBuild && cd ..
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

IMAGES_MISSING=false
if ! docker image inspect acctatlas/user-service:latest > /dev/null 2>&1; then
    warn "Image acctatlas/user-service:latest not found"
    IMAGES_MISSING=true
fi

if ! docker image inspect acctatlas/api-gateway:latest > /dev/null 2>&1; then
    warn "Image acctatlas/api-gateway:latest not found"
    IMAGES_MISSING=true
fi

if [ "$IMAGES_MISSING" = true ]; then
    echo ""
    warn "Docker images are missing. Build them with:"
    echo ""
    echo "  cd AcctAtlas-user-service && ./gradlew jibDockerBuild && cd .."
    echo "  cd AcctAtlas-api-gateway && ./gradlew jibDockerBuild && cd .."
    echo ""
    read -p "Would you like to build them now? [y/N] " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Building user-service image..."
        cd "$ROOT_DIR/AcctAtlas-user-service"
        ./gradlew jibDockerBuild

        info "Building api-gateway image..."
        cd "$ROOT_DIR/AcctAtlas-api-gateway"
        ./gradlew jibDockerBuild

        cd "$ROOT_DIR"
        success "Docker images built successfully"
    else
        error "Cannot start without Docker images. Please build them first."
        exit 1
    fi
fi

# Step 2: Start all backend services via docker-compose
info "Starting all backend services via docker-compose..."
docker-compose --profile backend up -d

# Step 3: Wait for services to be healthy
wait_for_docker_healthy postgres 30
wait_for_docker_healthy redis 15

# Wait for the Java services (they depend on postgres/redis)
info "Waiting for User Service container to be ready..."
wait_for_health "http://localhost:8081/actuator/health" "User Service" 60 3

info "Waiting for API Gateway container to be ready..."
wait_for_health "http://localhost:8080/actuator/health" "API Gateway" 60 3

# Step 4: Start Web App
info "Starting Web App..."
cd "$ROOT_DIR/AcctAtlas-web-app"

# Install dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    info "Installing npm dependencies..."
    npm install
fi

# Start dev server in background
nohup npm run dev > "$LOGS_DIR/web-app.log" 2>&1 &
WEB_APP_PID=$!
save_pid "web-app" $WEB_APP_PID
info "Web App started (PID: $WEB_APP_PID, log: logs/web-app.log)"

# Step 5: Wait for Web App to be ready
cd "$ROOT_DIR"
wait_for_health "http://localhost:3000" "Web App" 30 2

# Step 6: Open browser
open_browser "http://localhost:3000"

# Step 7: Print status
print_status

echo "Docker containers:"
docker-compose --profile backend ps
echo ""
echo "Logs:"
echo "  - Backend services: docker-compose logs -f"
echo "  - Web App:          tail -f logs/web-app.log"
echo ""
echo "To stop all services:"
echo "  ./scripts/docker-stop.sh"
echo ""
