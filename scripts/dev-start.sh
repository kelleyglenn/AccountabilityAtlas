#!/bin/bash
#
# Local Development Startup Script
#
# Starts all services for local development:
#   - PostgreSQL and Redis via Docker
#   - User Service and API Gateway via Gradle bootRun
#   - Web App via npm run dev
#
# Usage:
#   ./scripts/dev-start.sh
#
# To stop services:
#   ./scripts/dev-stop.sh
#

set -e

# Load common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

print_banner
info "Starting local development environment..."
echo ""

# Change to root directory
cd "$ROOT_DIR"

# Step 1: Start Docker services (postgres, redis)
info "Starting PostgreSQL and Redis via Docker..."
docker-compose up -d postgres redis

# Step 2: Wait for Docker services to be healthy
wait_for_docker_healthy postgres 30
wait_for_docker_healthy redis 15

# Step 3: Start User Service
info "Starting User Service..."
cd "$ROOT_DIR/AcctAtlas-user-service"

# Kill any existing gradle daemon for this project
pkill -f "GradleDaemon.*AcctAtlas-user-service" 2>/dev/null || true

# Start bootRun in background
nohup ./gradlew bootRun --args='--spring.profiles.active=local' > "$LOGS_DIR/user-service.log" 2>&1 &
USER_SERVICE_PID=$!
save_pid "user-service" $USER_SERVICE_PID
info "User Service started (PID: $USER_SERVICE_PID, log: logs/user-service.log)"

# Step 4: Start API Gateway
info "Starting API Gateway..."
cd "$ROOT_DIR/AcctAtlas-api-gateway"

# Kill any existing gradle daemon for this project
pkill -f "GradleDaemon.*AcctAtlas-api-gateway" 2>/dev/null || true

# Start bootRun in background
nohup ./gradlew bootRun --args='--spring.profiles.active=local' > "$LOGS_DIR/api-gateway.log" 2>&1 &
API_GATEWAY_PID=$!
save_pid "api-gateway" $API_GATEWAY_PID
info "API Gateway started (PID: $API_GATEWAY_PID, log: logs/api-gateway.log)"

# Step 5: Wait for Java services to be ready
cd "$ROOT_DIR"
wait_for_health "http://localhost:8081/actuator/health" "User Service" 60 3
wait_for_health "http://localhost:8080/actuator/health" "API Gateway" 60 3

# Step 6: Start Web App
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

# Step 7: Wait for Web App to be ready
cd "$ROOT_DIR"
wait_for_health "http://localhost:3000" "Web App" 30 2

# Step 8: Open browser
open_browser "http://localhost:3000"

# Step 9: Print status
print_status

echo "Logs:"
echo "  - User Service:  tail -f logs/user-service.log"
echo "  - API Gateway:   tail -f logs/api-gateway.log"
echo "  - Web App:       tail -f logs/web-app.log"
echo ""
echo "To stop all services:"
echo "  ./scripts/dev-stop.sh"
echo ""
