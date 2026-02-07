#!/bin/bash
#
# Local Development Stop Script
#
# Stops all local development services:
#   - Gradle bootRun processes (User Service, API Gateway)
#   - npm dev process (Web App)
#   - Docker services (PostgreSQL, Redis)
#
# Usage:
#   ./scripts/dev-stop.sh [--keep-docker]
#
# Options:
#   --keep-docker    Keep PostgreSQL and Redis running
#

set -e

# Load common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Parse arguments
KEEP_DOCKER=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-docker)
            KEEP_DOCKER=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo ""
info "Stopping local development services..."
echo ""

cd "$ROOT_DIR"

# Stop Web App
info "Stopping Web App..."
kill_saved_pid "web-app"

# Also kill any orphaned node processes on port 3000
kill_process_on_port 3000 "node"

# Stop API Gateway
info "Stopping API Gateway..."
kill_saved_pid "api-gateway"

# Stop User Service
info "Stopping User Service..."
kill_saved_pid "user-service"

# Kill any remaining Gradle processes for these projects
info "Cleaning up Gradle processes..."
pkill -f "GradleDaemon.*AcctAtlas-user-service" 2>/dev/null || true
pkill -f "GradleDaemon.*AcctAtlas-api-gateway" 2>/dev/null || true

# Also try to kill Java processes on specific ports
kill_process_on_port 8080 "java"
kill_process_on_port 8081 "java"

# Stop Docker services
if [ "$KEEP_DOCKER" = false ]; then
    info "Stopping Docker services (PostgreSQL, Redis)..."
    docker-compose stop postgres redis
    success "Docker services stopped"
else
    info "Keeping Docker services running (--keep-docker)"
fi

# Clean up PID files
rm -f "$LOGS_DIR"/*.pid

echo ""
success "All services stopped!"
echo ""

# Show any remaining processes on key ports
echo "Port status:"
for port in 3000 5432 6379 8080 8081; do
    PID=$(get_pid_on_port $port)
    if [ -n "$PID" ]; then
        echo "  Port $port: PID $PID (still running)"
    else
        echo "  Port $port: free"
    fi
done
echo ""
