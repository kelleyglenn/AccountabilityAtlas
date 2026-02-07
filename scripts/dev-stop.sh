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

# Also kill any orphaned npm processes on port 3000
if command -v lsof &> /dev/null; then
    WEB_PID=$(lsof -t -i:3000 2>/dev/null || true)
    if [ -n "$WEB_PID" ]; then
        info "Killing process on port 3000 (PID: $WEB_PID)"
        kill $WEB_PID 2>/dev/null || true
    fi
fi

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
for port in 8080 8081; do
    if command -v lsof &> /dev/null; then
        JAVA_PID=$(lsof -t -i:$port 2>/dev/null || true)
        if [ -n "$JAVA_PID" ]; then
            info "Killing Java process on port $port (PID: $JAVA_PID)"
            kill $JAVA_PID 2>/dev/null || true
        fi
    fi
done

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
    if command -v lsof &> /dev/null; then
        PID=$(lsof -t -i:$port 2>/dev/null || true)
        if [ -n "$PID" ]; then
            echo "  Port $port: PID $PID (still running)"
        else
            echo "  Port $port: free"
        fi
    fi
done
echo ""
