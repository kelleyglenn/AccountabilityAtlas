#!/bin/bash
#
# Docker Mode Stop Script
#
# Stops all Docker containers.
#
# Usage:
#   ./scripts/docker-stop.sh [--volumes]
#
# Options:
#   --volumes    Also remove Docker volumes (deletes database data)
#

set -e

# Load common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# Parse arguments
REMOVE_VOLUMES=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --volumes)
            REMOVE_VOLUMES=true
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

# Stop Docker services
if [ "$REMOVE_VOLUMES" = true ]; then
    warn "Stopping containers and removing volumes (database data will be deleted)..."
    docker-compose --profile backend --profile frontend down --volumes
else
    info "Stopping containers (volumes preserved)..."
    docker-compose --profile backend --profile frontend down
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
