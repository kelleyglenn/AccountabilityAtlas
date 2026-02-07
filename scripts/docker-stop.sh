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
    kill_process_on_port 3000 "node"
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
    PID=$(get_pid_on_port $port)
    if [ -n "$PID" ]; then
        echo "  Port $port: PID $PID (still running)"
    else
        echo "  Port $port: free"
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
