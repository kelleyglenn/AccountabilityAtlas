#!/usr/bin/env bash
# Reset all development databases to seed data only.
# Usage: ./scripts/reset-dev-data.sh
#
# This script:
# 1. Truncates all data tables (preserving Flyway migration history)
# 2. Restarts backend services so Flyway repeatable migrations re-seed data
#
# Requires: docker, docker compose

set -euo pipefail

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-accountabilityatlas-postgres-1}"

echo "=== Resetting development databases ==="

# Helper: run SQL against a specific database
run_sql() {
  local db_user="$1" db_name="$2" sql="$3"
  docker exec "$POSTGRES_CONTAINER" psql -U "$db_user" -d "$db_name" -c "$sql"
}

echo ""
echo "--- user_service ---"
run_sql user_service user_service "
  TRUNCATE users.sessions CASCADE;
  TRUNCATE users.password_resets CASCADE;
  TRUNCATE users.oauth_links CASCADE;
  TRUNCATE users.oauth_links_history CASCADE;
  TRUNCATE users.user_stats CASCADE;
  TRUNCATE users.users_history CASCADE;
  TRUNCATE users.users CASCADE;
"

echo ""
echo "--- video_service ---"
run_sql video_service video_service "
  TRUNCATE videos.video_locations CASCADE;
  TRUNCATE videos.videos CASCADE;
"

echo ""
echo "--- location_service ---"
run_sql location_service location_service "
  TRUNCATE locations.location_stats CASCADE;
  TRUNCATE locations.locations CASCADE;
"

echo ""
echo "--- search_service ---"
run_sql search_service search_service "
  TRUNCATE search.search_videos CASCADE;
"

echo ""
echo "--- moderation_service ---"
run_sql moderation_service moderation_service "
  TRUNCATE moderation.abuse_reports CASCADE;
  TRUNCATE moderation.abuse_reports_history CASCADE;
  TRUNCATE moderation.audit_log CASCADE;
  TRUNCATE moderation.moderation_items_history CASCADE;
  TRUNCATE moderation.moderation_items CASCADE;
"

echo ""
echo "=== All tables truncated. Restarting backend services to re-seed... ==="

# Restart backend services so Flyway repeatable migrations reload seed data
cd "$(dirname "$0")/.."
docker compose --profile backend restart

echo ""
echo "=== Waiting for services to become healthy... ==="
docker compose --profile backend --profile frontend ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null || true

echo ""
echo "=== Done. Seed data has been reloaded. ==="
