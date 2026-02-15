#!/bin/bash
#
# Deploy Script
#
# Runs quality checks, builds Docker images, and restarts
# the affected docker-compose services.
#
# Usage:
#   ./scripts/deploy.sh user-service video-service web-app
#   ./scripts/deploy.sh api-gateway            # single service
#   ./scripts/deploy.sh --all                  # all deployable sub-projects
#   ./scripts/deploy.sh --skip-checks web-app  # skip quality checks
#

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    echo "Error: This script should be executed, not sourced."
    echo "Usage: ./scripts/deploy.sh [options] <services...>"
    return 1
fi

set -e

# Load common utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"

# --- Sub-project definitions ---

# Parallel arrays: name, directory, type, check command, build command, compose service
KNOWN_NAMES=(
    user-service
    video-service
    location-service
    search-service
    moderation-service
    api-gateway
    web-app
)

declare -A DIR_MAP=(
    [user-service]=AcctAtlas-user-service
    [video-service]=AcctAtlas-video-service
    [location-service]=AcctAtlas-location-service
    [search-service]=AcctAtlas-search-service
    [moderation-service]=AcctAtlas-moderation-service
    [api-gateway]=AcctAtlas-api-gateway
    [web-app]=AcctAtlas-web-app
)

declare -A TYPE_MAP=(
    [user-service]=java
    [video-service]=java
    [location-service]=java
    [search-service]=java
    [moderation-service]=java
    [api-gateway]=java
    [web-app]=node
)

# Health check URLs for each service
declare -A HEALTH_MAP=(
    [user-service]="http://localhost:8081/actuator/health"
    [video-service]="http://localhost:8082/actuator/health"
    [location-service]="http://localhost:8083/actuator/health"
    [search-service]="http://localhost:8084/actuator/health"
    [moderation-service]="http://localhost:8085/actuator/health"
    [api-gateway]="http://localhost:8080/actuator/health"
    [web-app]="http://localhost:3000"
)

# --- Functions ---

usage() {
    echo "Usage: $0 [--skip-checks] [--all | <service> ...]"
    echo ""
    echo "Services:"
    for name in "${KNOWN_NAMES[@]}"; do
        echo "  $name"
    done
    echo ""
    echo "Options:"
    echo "  --all           Deploy all services"
    echo "  --skip-checks   Skip quality checks (faster iteration)"
    echo ""
    echo "Examples:"
    echo "  $0 user-service video-service"
    echo "  $0 --all"
    echo "  $0 --skip-checks web-app"
}

validate_name() {
    local name=$1
    for known in "${KNOWN_NAMES[@]}"; do
        if [ "$name" = "$known" ]; then
            return 0
        fi
    done
    return 1
}

run_check() {
    local name=$1
    local dir="${DIR_MAP[$name]}"
    local type="${TYPE_MAP[$name]}"
    local project_dir="$ROOT_DIR/$dir"

    if [ ! -d "$project_dir" ]; then
        error "Directory $dir does not exist"
        return 1
    fi

    info "Running checks for $name..."

    if [ "$type" = "java" ]; then
        (cd "$project_dir" && ./gradlew check)
    elif [ "$type" = "node" ]; then
        (cd "$project_dir" && npm run check)
    fi
}

run_build() {
    local name=$1
    local dir="${DIR_MAP[$name]}"
    local type="${TYPE_MAP[$name]}"
    local project_dir="$ROOT_DIR/$dir"

    if [ "$type" = "java" ]; then
        info "Building Docker image for $name..."
        (cd "$project_dir" && ./gradlew jibDockerBuild)
    fi
    # web-app is built by docker-compose (--build flag), so nothing to do here
}

# --- Parse arguments ---

SKIP_CHECKS=false
TARGETS=()

for arg in "$@"; do
    case "$arg" in
        --skip-checks)
            SKIP_CHECKS=true
            ;;
        --all)
            TARGETS=("${KNOWN_NAMES[@]}")
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        -*)
            error "Unknown option: $arg"
            usage
            exit 1
            ;;
        *)
            TARGETS+=("$arg")
            ;;
    esac
done

if [ ${#TARGETS[@]} -eq 0 ]; then
    error "No services specified"
    echo ""
    usage
    exit 1
fi

# Validate all targets before doing any work
for target in "${TARGETS[@]}"; do
    if ! validate_name "$target"; then
        error "Unknown service: $target"
        echo ""
        usage
        exit 1
    fi
done

# --- Main ---

echo ""
info "Deploying: ${TARGETS[*]}"
echo ""

# Step 1: Run checks (fail fast — abort before building anything)
if [ "$SKIP_CHECKS" = true ]; then
    warn "Skipping quality checks (--skip-checks)"
else
    for target in "${TARGETS[@]}"; do
        run_check "$target"
        success "Checks passed for $target"
    done
fi

# Step 2: Build images
for target in "${TARGETS[@]}"; do
    run_build "$target"
done

# Step 3: Determine profiles and flags
NEEDS_BUILD=false
SERVICES=()

for target in "${TARGETS[@]}"; do
    SERVICES+=("$target")
    if [ "$target" = "web-app" ]; then
        NEEDS_BUILD=true
    fi
done

# Always include both profiles so docker-compose can resolve cross-profile
# dependencies (e.g. web-app depends_on api-gateway). --no-deps ensures
# only the targeted services are actually restarted.
PROFILE_ARGS=(--profile backend --profile frontend)

UP_ARGS=(up -d --no-deps --force-recreate)
if [ "$NEEDS_BUILD" = true ]; then
    UP_ARGS+=(--build)
fi

# Step 4: Recreate affected services
cd "$ROOT_DIR"
info "Restarting services: ${SERVICES[*]}"
docker-compose "${PROFILE_ARGS[@]}" "${UP_ARGS[@]}" "${SERVICES[@]}"

# Step 5: Wait for health
echo ""
info "Waiting for services to become healthy..."

HEALTH_FAILED=false
for target in "${TARGETS[@]}"; do
    local_url="${HEALTH_MAP[$target]}"
    if ! wait_for_health "$local_url" "$target" 60 3; then
        HEALTH_FAILED=true
    fi
done

echo ""
if [ "$HEALTH_FAILED" = true ]; then
    warn "Some services did not become healthy. Check logs with:"
    echo "  docker-compose logs -f <service-name>"
else
    success "All deployed services are healthy!"
fi

echo ""
info "Deployed services:"
docker-compose "${PROFILE_ARGS[@]}" ps "${SERVICES[@]}"
echo ""
