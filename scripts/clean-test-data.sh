#!/usr/bin/env bash
# clean-test-data.sh — Delete non-seed test data from all service databases.
#
# Preserves:
#   Users:     00000000-0000-0000-0000-00000000000{1-4}
#   Locations: 20000000-0000-0000-0000-00000000000{1-10}
#   Videos:    10000000-0000-0000-0000-00000000000{1-10}
#   Video locations: 30000000-0000-0000-0000-00000000000{1-10}
#   Search:    10000000-0000-0000-0000-00000000000{1-10}
#
# Deletes all non-seed rows from every table, plus all sessions, password resets,
# history tables, and moderation items (which have no seed data).
#
# Usage: ./scripts/clean-test-data.sh

set -euo pipefail

CONTAINER="accountabilityatlas-postgres-1"

run_sql() {
  local db="$1"
  local user="$2"
  local sql="$3"
  docker exec "$CONTAINER" psql -U "$user" -d "$db" -c "$sql"
}

echo "=== Cleaning test data ==="

# ── User Service ──────────────────────────────────────────────────────
echo ""
echo "--- user_service ---"

# Sessions and password resets: always safe to truncate (no seed data)
run_sql user_service user_service "TRUNCATE users.sessions CASCADE;"
run_sql user_service user_service "TRUNCATE users.password_resets CASCADE;"

# History tables: safe to truncate
run_sql user_service user_service "TRUNCATE users.users_history;"
run_sql user_service user_service "TRUNCATE users.oauth_links_history;"

# OAuth links for non-seed users
run_sql user_service user_service "
  DELETE FROM users.oauth_links
  WHERE user_id NOT IN (
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000003',
    '00000000-0000-0000-0000-000000000004'
  );
"

# User stats for non-seed users (must delete before users due to FK)
run_sql user_service user_service "
  DELETE FROM users.user_stats
  WHERE user_id NOT IN (
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000003',
    '00000000-0000-0000-0000-000000000004'
  );
"

# Non-seed users (cascades to any remaining child rows)
# Temporarily disable the versioning trigger to avoid history inserts
run_sql user_service user_service "
  ALTER TABLE users.users DISABLE TRIGGER users_versioning_trigger;
  DELETE FROM users.users
  WHERE id NOT IN (
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000003',
    '00000000-0000-0000-0000-000000000004'
  );
  ALTER TABLE users.users ENABLE TRIGGER users_versioning_trigger;
"

# ── Video Service ─────────────────────────────────────────────────────
echo ""
echo "--- video_service ---"

# video_amendments, video_participants, video_locations cascade from videos,
# but delete non-seed video_locations explicitly first (some may reference seed videos)
run_sql video_service video_service "
  DELETE FROM videos.video_locations
  WHERE id NOT IN (
    '30000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000002',
    '30000000-0000-0000-0000-000000000003',
    '30000000-0000-0000-0000-000000000004',
    '30000000-0000-0000-0000-000000000005',
    '30000000-0000-0000-0000-000000000006',
    '30000000-0000-0000-0000-000000000007',
    '30000000-0000-0000-0000-000000000008',
    '30000000-0000-0000-0000-000000000009',
    '30000000-0000-0000-0000-000000000010'
  );
"

# Non-seed videos (cascades to amendments, participants, remaining locations)
run_sql video_service video_service "
  DELETE FROM videos.videos
  WHERE id NOT IN (
    '10000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000003',
    '10000000-0000-0000-0000-000000000004',
    '10000000-0000-0000-0000-000000000005',
    '10000000-0000-0000-0000-000000000006',
    '10000000-0000-0000-0000-000000000007',
    '10000000-0000-0000-0000-000000000008',
    '10000000-0000-0000-0000-000000000009',
    '10000000-0000-0000-0000-000000000010'
  );
"

# ── Location Service ──────────────────────────────────────────────────
echo ""
echo "--- location_service ---"

# location_stats for non-seed locations (FK cascade would handle this, but be explicit)
run_sql location_service location_service "
  DELETE FROM locations.location_stats
  WHERE location_id NOT IN (
    '20000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000002',
    '20000000-0000-0000-0000-000000000003',
    '20000000-0000-0000-0000-000000000004',
    '20000000-0000-0000-0000-000000000005',
    '20000000-0000-0000-0000-000000000006',
    '20000000-0000-0000-0000-000000000007',
    '20000000-0000-0000-0000-000000000008',
    '20000000-0000-0000-0000-000000000009',
    '20000000-0000-0000-0000-000000000010'
  );
"

run_sql location_service location_service "
  DELETE FROM locations.locations
  WHERE id NOT IN (
    '20000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000002',
    '20000000-0000-0000-0000-000000000003',
    '20000000-0000-0000-0000-000000000004',
    '20000000-0000-0000-0000-000000000005',
    '20000000-0000-0000-0000-000000000006',
    '20000000-0000-0000-0000-000000000007',
    '20000000-0000-0000-0000-000000000008',
    '20000000-0000-0000-0000-000000000009',
    '20000000-0000-0000-0000-000000000010'
  );
"

# ── Moderation Service ────────────────────────────────────────────────
echo ""
echo "--- moderation_service ---"

# No seed data — truncate everything
run_sql moderation_service moderation_service "
  ALTER TABLE moderation.moderation_items DISABLE TRIGGER moderation_items_versioning;
  TRUNCATE moderation.moderation_items CASCADE;
  TRUNCATE moderation.moderation_items_history;
  ALTER TABLE moderation.moderation_items ENABLE TRIGGER moderation_items_versioning;
"

# ── Search Service ────────────────────────────────────────────────────
echo ""
echo "--- search_service ---"

run_sql search_service search_service "
  DELETE FROM search.search_videos
  WHERE id NOT IN (
    '10000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000002',
    '10000000-0000-0000-0000-000000000003',
    '10000000-0000-0000-0000-000000000004',
    '10000000-0000-0000-0000-000000000005',
    '10000000-0000-0000-0000-000000000006',
    '10000000-0000-0000-0000-000000000007',
    '10000000-0000-0000-0000-000000000008',
    '10000000-0000-0000-0000-000000000009',
    '10000000-0000-0000-0000-000000000010'
  );
"

# ── SQS Queues ────────────────────────────────────────────────────────
echo ""
echo "--- SQS queues ---"

LOCALSTACK="accountabilityatlas-localstack-1"
for queue in video-events video-events-dlq moderation-events moderation-events-dlq search-moderation-events search-moderation-events-dlq user-events user-events-dlq video-status-events video-status-events-dlq; do
  docker exec "$LOCALSTACK" awslocal sqs purge-queue \
    --queue-url "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/$queue" 2>/dev/null \
    && echo "Purged $queue" || echo "Skipped $queue (empty or not found)"
done

echo ""
echo "=== Done. Seed data preserved, test data removed. ==="
