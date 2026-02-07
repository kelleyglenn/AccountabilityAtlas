#!/bin/bash
#
# Docker Mode Stop Script
#
# Stops all Docker containers and optionally the Web App.
#
# Usage:
#   ./scripts/docker-stop.sh [--volumes] [--all]
#
# Options:
#   --volumes    Also remove Docker volumes (deletes database data)
#   --all        Also stop Web App (npm dev process)
#

set -e

# Load common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Parse arguments
REMOVE_VOLUMES=false
STOP_WEBAPP=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --volumes)
            REMOVE_VOLUMES=true
            shift
            ;;
        --all)
            STOP_WEBAPP=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo ""
info "Stopping Docker services..."
echo ""

cd "$ROOT_DIR"

# Stop Web App if requested
if [ "$STOP_WEBAPP" = true ]; then
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
fi

# Stop Docker services
if [ "$REMOVE_VOLUMES" = true ]; then
    warn "Stopping containers and removing volumes (database data will be deleted)..."
    docker-compose --profile backend down --volumes
else
    info "Stopping containers (volumes preserved)..."
    docker-compose --profile backend down
fi

# Clean up PID files if we stopped the web app
if [ "$STOP_WEBAPP" = true ]; then
    rm -f "$LOGS_DIR"/*.pid
fi

echo ""
success "Docker services stopped!"
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

if [ "$STOP_WEBAPP" = false ]; then
    WEB_PID=$(get_pid "web-app")
    if [ -n "$WEB_PID" ] && kill -0 "$WEB_PID" 2>/dev/null; then
        info "Web App is still running (PID: $WEB_PID)"
        echo "  To stop it: ./scripts/docker-stop.sh --all"
        echo ""
    fi
fi
