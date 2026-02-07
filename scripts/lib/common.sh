#!/bin/bash
#
# Common utilities for startup scripts
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOGS_DIR="$ROOT_DIR/logs"

# Ensure logs directory exists
mkdir -p "$LOGS_DIR"

# Print colored messages
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Wait for a health endpoint to be ready
# Usage: wait_for_health <url> <name> [max_attempts] [interval]
wait_for_health() {
    local url=$1
    local name=$2
    local max_attempts=${3:-30}
    local interval=${4:-2}
    local attempt=1

    info "Waiting for $name at $url..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" > /dev/null 2>&1; then
            success "$name is ready!"
            return 0
        fi
        echo -n "."
        sleep $interval
        attempt=$((attempt + 1))
    done

    echo ""
    error "$name failed to start after $max_attempts attempts"
    return 1
}

# Wait for a TCP port to be ready
# Usage: wait_for_port <host> <port> <name> [max_attempts]
wait_for_port() {
    local host=$1
    local port=$2
    local name=$3
    local max_attempts=${4:-30}
    local attempt=1

    info "Waiting for $name on $host:$port..."

    while [ $attempt -le $max_attempts ]; do
        if nc -z "$host" "$port" 2>/dev/null || (echo > /dev/tcp/$host/$port) 2>/dev/null; then
            success "$name is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done

    echo ""
    error "$name failed to start after $max_attempts attempts"
    return 1
}

# Open browser (cross-platform)
# Usage: open_browser <url>
open_browser() {
    local url=$1

    info "Opening browser to $url"

    case "$(uname -s)" in
        MINGW*|CYGWIN*|MSYS*)
            # Windows (Git Bash, Cygwin, MSYS2)
            start "$url" 2>/dev/null || cmd.exe /c start "$url"
            ;;
        Darwin)
            # macOS
            open "$url"
            ;;
        *)
            # Linux and others
            xdg-open "$url" 2>/dev/null || sensible-browser "$url" 2>/dev/null || echo "Please open $url in your browser"
            ;;
    esac
}

# Save PID to file for later cleanup
# Usage: save_pid <name> <pid>
save_pid() {
    local name=$1
    local pid=$2
    echo "$pid" > "$LOGS_DIR/${name}.pid"
}

# Get saved PID
# Usage: get_pid <name>
get_pid() {
    local name=$1
    local pid_file="$LOGS_DIR/${name}.pid"
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    fi
}

# Kill process by saved PID
# Usage: kill_saved_pid <name>
kill_saved_pid() {
    local name=$1
    local pid=$(get_pid "$name")

    if [ -n "$pid" ]; then
        if kill -0 "$pid" 2>/dev/null; then
            info "Stopping $name (PID: $pid)..."
            kill "$pid" 2>/dev/null
            # Wait a moment then force kill if needed
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                warn "Force killing $name..."
                kill -9 "$pid" 2>/dev/null
            fi
            success "$name stopped"
        else
            warn "$name (PID: $pid) is not running"
        fi
        rm -f "$LOGS_DIR/${name}.pid"
    else
        warn "No PID file found for $name"
    fi
}

# Kill process tree (for Windows compatibility)
# Usage: kill_tree <pid>
kill_tree() {
    local pid=$1

    case "$(uname -s)" in
        MINGW*|CYGWIN*|MSYS*)
            # Windows - use taskkill to kill process tree
            taskkill //F //T //PID "$pid" 2>/dev/null
            ;;
        *)
            # Unix - kill process group
            kill -TERM -"$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
            ;;
    esac
}

# Get PID of process listening on a port (cross-platform)
# Usage: get_pid_on_port <port>
get_pid_on_port() {
    local port=$1

    case "$(uname -s)" in
        MINGW*|CYGWIN*|MSYS*)
            # Windows - use netstat
            netstat -ano 2>/dev/null | grep ":$port " | grep "LISTENING" | awk '{print $5}' | head -1
            ;;
        *)
            # Unix - use lsof
            if command -v lsof &> /dev/null; then
                lsof -t -i:$port 2>/dev/null | head -1
            fi
            ;;
    esac
}

# Kill process on a specific port (cross-platform)
# Usage: kill_process_on_port <port> [name]
kill_process_on_port() {
    local port=$1
    local name=${2:-"process"}

    local pid=$(get_pid_on_port $port)

    if [ -n "$pid" ]; then
        info "Killing $name on port $port (PID: $pid)..."
        case "$(uname -s)" in
            MINGW*|CYGWIN*|MSYS*)
                # Windows - use taskkill with /T to kill process tree
                taskkill //F //T //PID "$pid" 2>/dev/null || true
                ;;
            *)
                # Unix - regular kill
                kill -9 "$pid" 2>/dev/null || true
                ;;
        esac
        success "Killed $name on port $port"
    fi
}

# Check if docker-compose services are healthy
# Usage: check_docker_healthy <service>
check_docker_healthy() {
    local service=$1
    local status=$(docker-compose ps -q "$service" 2>/dev/null)

    if [ -z "$status" ]; then
        return 1
    fi

    docker inspect --format='{{.State.Health.Status}}' "$status" 2>/dev/null | grep -q "healthy"
}

# Wait for docker-compose service to be healthy
# Usage: wait_for_docker_healthy <service> [max_attempts]
wait_for_docker_healthy() {
    local service=$1
    local max_attempts=${2:-30}
    local attempt=1

    info "Waiting for docker service $service to be healthy..."

    while [ $attempt -le $max_attempts ]; do
        if check_docker_healthy "$service"; then
            success "$service is healthy!"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done

    echo ""
    error "$service failed to become healthy after $max_attempts attempts"
    return 1
}

# Print banner
print_banner() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}       AccountabilityAtlas Startup          ${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

# Print status summary
print_status() {
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}             All Services Running           ${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "Services:"
    echo "  - PostgreSQL:    localhost:5432"
    echo "  - Redis:         localhost:6379"
    echo "  - User Service:  http://localhost:8081"
    echo "  - API Gateway:   http://localhost:8080"
    echo "  - Web App:       http://localhost:3000"
    echo ""
}
