# Data Architecture

## Overview

AccountabilityAtlas uses a polyglot persistence strategy with three primary data stores, each optimized for specific access patterns.

## Data Store Summary

| Store | Technology | Purpose | Services |
|-------|------------|---------|----------|
| Primary Database | PostgreSQL 15 + PostGIS | Transactional data, spatial queries | All services |
| Search Index | OpenSearch 2.x | Full-text search, faceting | search-service |
| Cache | Redis 7.x | Sessions, caching, rate limiting | api-gateway, user-service, location-service |
| Message Queue | Amazon SQS | Async events, decoupling | All services |

---

## Temporal Tables

AccountabilityAtlas uses PostgreSQL's `temporal_tables` extension to maintain complete audit history for static and semi-static data. Temporal tables automatically track all changes over time, enabling point-in-time queries and full change history.

### Why Temporal Tables?

- **Audit compliance**: Full history of all data changes without custom triggers
- **Point-in-time queries**: Retrieve data as it existed at any moment
- **Simplified application code**: No manual `created_at`/`updated_at` management
- **Debugging**: Trace exactly when and how data changed

### How It Works

Each temporal table has a `sys_period` column of type `tstzrange` (timestamp range):
- Lower bound: when the row version became valid
- Upper bound: when the row version was superseded (NULL for current)

A corresponding `*_history` table stores previous versions automatically via triggers.

```sql
-- Enable the extension
CREATE EXTENSION IF NOT EXISTS temporal_tables;

-- Example: Create history table and trigger
CREATE TABLE schema.table_history (LIKE schema.table);
CREATE TRIGGER versioning_trigger
  BEFORE INSERT OR UPDATE OR DELETE ON schema.table
  FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'schema.table_history', true);
```

### Temporal vs. Non-Temporal Classification

| Temporal Tables (with history) | Non-Temporal Tables | Rationale |
|--------------------------------|---------------------|-----------|
| users.users | users.user_stats | Counters change frequently |
| users.oauth_links | users.sessions | Sessions are transient |
| content.videos | users.password_resets | Tokens are transient |
| content.locations | content.location_stats | Counters change frequently |
| content.video_locations | moderation.audit_log | Already append-only |
| moderation.moderation_items | notifications.delivery_log | Already append-only |
| moderation.abuse_reports | | |
| notifications.preferences | | |

**Key principle**: Temporal tables use `sys_period` for versioning, so `created_at`, `updated_at`, `linked_at`, and `added_at` columns are removed (redundant with system period).

---

## PostgreSQL Schema Design

### Database Topology
```
┌─────────────────────────────────────────────────────────────────────────┐
│                    accountabilityatlas (Primary)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Schema: users              │  Schema: content            │             │
│  ├── users          [T][H]  │  ├── videos         [T][H]  │             │
│  ├── users_history          │  ├── videos_history         │             │
│  ├── user_stats             │  ├── video_locations [T][H] │             │
│  ├── oauth_links    [T][H]  │  ├── video_locations_history│             │
│  ├── oauth_links_history    │  ├── locations       [T][H] │             │
│  ├── sessions               │  ├── locations_history      │             │
│  └── password_resets        │  └── location_stats         │             │
├─────────────────────────────────────────────────────────────────────────┤
│  Schema: moderation         │  Schema: notifications      │             │
│  ├── moderation_items[T][H] │  ├── preferences    [T][H]  │             │
│  ├── moderation_items_hist  │  ├── preferences_history    │             │
│  ├── abuse_reports  [T][H]  │  └── delivery_log           │             │
│  ├── abuse_reports_history  │                             │             │
│  └── audit_log              │                             │             │
└─────────────────────────────────────────────────────────────────────────┘

Legend: [T] = Temporal table  [H] = Has history table
```

### Schema: users

```sql
-- Core user table (TEMPORAL)
CREATE TABLE users.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    password_hash VARCHAR(255),  -- NULL for OAuth-only users
    display_name VARCHAR(100) NOT NULL,
    avatar_url VARCHAR(500),
    trust_tier VARCHAR(20) NOT NULL DEFAULT 'NEW',
    sys_period tstzrange NOT NULL DEFAULT tstzrange(NOW(), NULL),

    CONSTRAINT valid_trust_tier CHECK (
        trust_tier IN ('NEW', 'TRUSTED', 'MODERATOR', 'ADMIN')
    )
);

CREATE TABLE users.users_history (LIKE users.users);
CREATE TRIGGER users_versioning_trigger
  BEFORE INSERT OR UPDATE OR DELETE ON users.users
  FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'users.users_history', true);

CREATE INDEX idx_users_email ON users.users(email);
CREATE INDEX idx_users_trust_tier ON users.users(trust_tier);

-- User statistics (NON-TEMPORAL - counters change frequently)
CREATE TABLE users.user_stats (
    user_id UUID PRIMARY KEY REFERENCES users.users(id) ON DELETE CASCADE,
    submission_count INTEGER NOT NULL DEFAULT 0,
    approved_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- OAuth provider links (TEMPORAL)
CREATE TABLE users.oauth_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users.users(id) ON DELETE CASCADE,
    provider VARCHAR(20) NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    sys_period tstzrange NOT NULL DEFAULT tstzrange(NOW(), NULL),

    CONSTRAINT valid_provider CHECK (provider IN ('GOOGLE', 'APPLE')),
    UNIQUE (provider, provider_id)
);

CREATE TABLE users.oauth_links_history (LIKE users.oauth_links);
CREATE TRIGGER oauth_links_versioning_trigger
  BEFORE INSERT OR UPDATE OR DELETE ON users.oauth_links
  FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'users.oauth_links_history', true);

CREATE INDEX idx_oauth_links_user ON users.oauth_links(user_id);

-- Active sessions (NON-TEMPORAL - transient, high churn)
CREATE TABLE users.sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users.users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL,
    device_info VARCHAR(500),
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX idx_sessions_user ON users.sessions(user_id);
CREATE INDEX idx_sessions_expires ON users.sessions(expires_at);

-- Password reset tokens (NON-TEMPORAL - transient, expires in 24 hours)
CREATE TABLE users.password_resets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users.users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ
);

CREATE INDEX idx_password_resets_token ON users.password_resets(token_hash);
```

### Schema: content

```sql
-- Enable PostGIS and temporal_tables
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS temporal_tables;

-- Videos table (TEMPORAL)
CREATE TABLE content.videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    youtube_id VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    thumbnail_url VARCHAR(500),
    duration_seconds INTEGER,
    channel_id VARCHAR(50),           -- YouTube channel ID
    channel_name VARCHAR(255),        -- YouTube channel name
    published_at TIMESTAMPTZ,         -- When video was published on YouTube
    video_date DATE,                  -- When the incident occurred (user-provided)
    amendments VARCHAR(10)[] NOT NULL DEFAULT '{}',
    participants VARCHAR(20)[] NOT NULL DEFAULT '{}',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    submitted_by UUID NOT NULL REFERENCES users.users(id),
    sys_period tstzrange NOT NULL DEFAULT tstzrange(NOW(), NULL),

    CONSTRAINT valid_status CHECK (
        status IN ('PENDING', 'APPROVED', 'REJECTED', 'DELETED')
    ),
    CONSTRAINT valid_amendments CHECK (
        amendments <@ ARRAY['FIRST', 'SECOND', 'FOURTH', 'FIFTH']::VARCHAR[]
    ),
    CONSTRAINT valid_participants CHECK (
        participants <@ ARRAY['POLICE', 'GOVERNMENT', 'BUSINESS', 'CITIZEN']::VARCHAR[]
    )
);

CREATE TABLE content.videos_history (LIKE content.videos);
CREATE TRIGGER videos_versioning_trigger
  BEFORE INSERT OR UPDATE OR DELETE ON content.videos
  FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'content.videos_history', true);

CREATE INDEX idx_videos_youtube ON content.videos(youtube_id);
CREATE INDEX idx_videos_status ON content.videos(status);
CREATE INDEX idx_videos_submitted_by ON content.videos(submitted_by);
CREATE INDEX idx_videos_channel ON content.videos(channel_id);
CREATE INDEX idx_videos_amendments ON content.videos USING GIN(amendments);
CREATE INDEX idx_videos_participants ON content.videos USING GIN(participants);
CREATE INDEX idx_videos_sys_period ON content.videos USING GIST(sys_period);

-- Locations table (TEMPORAL - PostGIS enabled)
CREATE TABLE content.locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coordinates GEOGRAPHY(POINT, 4326) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(50) NOT NULL DEFAULT 'USA',
    sys_period tstzrange NOT NULL DEFAULT tstzrange(NOW(), NULL)
);

CREATE TABLE content.locations_history (LIKE content.locations);
CREATE TRIGGER locations_versioning_trigger
  BEFORE INSERT OR UPDATE OR DELETE ON content.locations
  FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'content.locations_history', true);

CREATE INDEX idx_locations_geo ON content.locations USING GIST(coordinates);
CREATE INDEX idx_locations_state ON content.locations(state);

-- Location statistics (NON-TEMPORAL - counters change frequently)
CREATE TABLE content.location_stats (
    location_id UUID PRIMARY KEY REFERENCES content.locations(id) ON DELETE CASCADE,
    video_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Video-Location junction table (TEMPORAL)
CREATE TABLE content.video_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES content.videos(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES content.locations(id) ON DELETE CASCADE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    sys_period tstzrange NOT NULL DEFAULT tstzrange(NOW(), NULL),

    UNIQUE (video_id, location_id)
);

CREATE TABLE content.video_locations_history (LIKE content.video_locations);
CREATE TRIGGER video_locations_versioning_trigger
  BEFORE INSERT OR UPDATE OR DELETE ON content.video_locations
  FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'content.video_locations_history', true);

CREATE INDEX idx_video_locations_video ON content.video_locations(video_id);
CREATE INDEX idx_video_locations_location ON content.video_locations(location_id);
```

### Schema: moderation

```sql
-- Moderation queue items (TEMPORAL)
CREATE TABLE moderation.moderation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type VARCHAR(20) NOT NULL,
    content_id UUID NOT NULL,
    submitter_id UUID NOT NULL REFERENCES users.users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    priority INTEGER NOT NULL DEFAULT 0,
    reviewer_id UUID REFERENCES users.users(id),
    reviewed_at TIMESTAMPTZ,
    rejection_reason TEXT,
    sys_period tstzrange NOT NULL DEFAULT tstzrange(NOW(), NULL),

    CONSTRAINT valid_content_type CHECK (content_type IN ('VIDEO', 'LOCATION')),
    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))
);

CREATE TABLE moderation.moderation_items_history (LIKE moderation.moderation_items);
CREATE TRIGGER moderation_items_versioning_trigger
  BEFORE INSERT OR UPDATE OR DELETE ON moderation.moderation_items
  FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'moderation.moderation_items_history', true);

CREATE INDEX idx_moderation_status ON moderation.moderation_items(status);
CREATE INDEX idx_moderation_submitter ON moderation.moderation_items(submitter_id);
CREATE INDEX idx_moderation_content ON moderation.moderation_items(content_type, content_id);
CREATE INDEX idx_moderation_sys_period ON moderation.moderation_items USING GIST(sys_period);

-- Abuse reports (TEMPORAL)
CREATE TABLE moderation.abuse_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type VARCHAR(20) NOT NULL,
    content_id UUID NOT NULL,
    reporter_id UUID NOT NULL REFERENCES users.users(id),
    reason VARCHAR(50) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    resolved_by UUID REFERENCES users.users(id),
    resolution TEXT,
    sys_period tstzrange NOT NULL DEFAULT tstzrange(NOW(), NULL),

    CONSTRAINT valid_reason CHECK (
        reason IN ('SPAM', 'INAPPROPRIATE', 'COPYRIGHT', 'MISINFORMATION', 'OTHER')
    ),
    CONSTRAINT valid_report_status CHECK (status IN ('OPEN', 'RESOLVED', 'DISMISSED'))
);

CREATE TABLE moderation.abuse_reports_history (LIKE moderation.abuse_reports);
CREATE TRIGGER abuse_reports_versioning_trigger
  BEFORE INSERT OR UPDATE OR DELETE ON moderation.abuse_reports
  FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'moderation.abuse_reports_history', true);

CREATE INDEX idx_abuse_reports_status ON moderation.abuse_reports(status);
CREATE INDEX idx_abuse_reports_content ON moderation.abuse_reports(content_type, content_id);
CREATE INDEX idx_abuse_reports_sys_period ON moderation.abuse_reports USING GIST(sys_period);

-- Audit log for moderation actions (NON-TEMPORAL - already append-only/immutable)
CREATE TABLE moderation.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID NOT NULL REFERENCES users.users(id),
    action VARCHAR(50) NOT NULL,
    target_type VARCHAR(20) NOT NULL,
    target_id UUID NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_actor ON moderation.audit_log(actor_id);
CREATE INDEX idx_audit_log_target ON moderation.audit_log(target_type, target_id);
CREATE INDEX idx_audit_log_created ON moderation.audit_log(created_at DESC);
```

### Schema: notifications

```sql
-- User notification preferences (TEMPORAL)
CREATE TABLE notifications.preferences (
    user_id UUID PRIMARY KEY REFERENCES users.users(id) ON DELETE CASCADE,
    email_on_approval BOOLEAN NOT NULL DEFAULT TRUE,
    email_on_rejection BOOLEAN NOT NULL DEFAULT TRUE,
    email_on_promotion BOOLEAN NOT NULL DEFAULT TRUE,
    email_digest BOOLEAN NOT NULL DEFAULT FALSE,
    sys_period tstzrange NOT NULL DEFAULT tstzrange(NOW(), NULL)
);

CREATE TABLE notifications.preferences_history (LIKE notifications.preferences);
CREATE TRIGGER preferences_versioning_trigger
  BEFORE INSERT OR UPDATE OR DELETE ON notifications.preferences
  FOR EACH ROW EXECUTE FUNCTION versioning('sys_period', 'notifications.preferences_history', true);

-- Email delivery log (NON-TEMPORAL - already append-only/immutable)
CREATE TABLE notifications.delivery_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users.users(id),
    notification_type VARCHAR(50) NOT NULL,
    email_address VARCHAR(255) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL,
    provider_message_id VARCHAR(255),
    error_message TEXT,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (status IN ('SENT', 'DELIVERED', 'BOUNCED', 'FAILED'))
);

CREATE INDEX idx_delivery_log_user ON notifications.delivery_log(user_id);
CREATE INDEX idx_delivery_log_sent ON notifications.delivery_log(sent_at DESC);
```

### Temporal Query Examples

```sql
-- Query current data (unchanged - same as before)
SELECT * FROM content.videos WHERE status = 'APPROVED';

-- Query data as it existed at a specific point in time
SELECT * FROM content.videos
WHERE sys_period @> '2025-06-15 12:00:00'::timestamptz;

-- Query when a record was created (lower bound of earliest sys_period)
SELECT v.id, v.title, lower(h.sys_period) AS created_at
FROM content.videos v
LEFT JOIN content.videos_history h ON v.id = h.id
WHERE v.id = '550e8400-e29b-41d4-a716-446655440000'
ORDER BY h.sys_period ASC
LIMIT 1;

-- Alternative: Get creation time from current row if never updated
SELECT id, title, lower(sys_period) AS created_at
FROM content.videos
WHERE id = '550e8400-e29b-41d4-a716-446655440000';

-- Query full change history for a record
SELECT * FROM (
    SELECT *, 'current' AS version_type FROM content.videos WHERE id = $1
    UNION ALL
    SELECT *, 'historical' AS version_type FROM content.videos_history WHERE id = $1
) combined
ORDER BY lower(sys_period) ASC;

-- Find all changes to a user's profile
SELECT
    lower(sys_period) AS changed_at,
    upper(sys_period) AS superseded_at,
    display_name,
    trust_tier
FROM (
    SELECT * FROM users.users WHERE id = $1
    UNION ALL
    SELECT * FROM users.users_history WHERE id = $1
) all_versions
ORDER BY lower(sys_period) ASC;

-- Find records that existed during a time range
SELECT * FROM content.videos
WHERE sys_period && tstzrange('2025-01-01', '2025-06-01');
```

---

## OpenSearch Index Design

### videos Index

```json
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "video_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "asciifolding", "video_synonyms"]
        }
      },
      "filter": {
        "video_synonyms": {
          "type": "synonym",
          "synonyms": [
            "cop, police, officer, law enforcement",
            "1a, first amendment, free speech",
            "2a, second amendment, gun rights",
            "4a, fourth amendment, search seizure",
            "5a, fifth amendment, self incrimination"
          ]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "youtubeId": { "type": "keyword" },
      "title": {
        "type": "text",
        "analyzer": "video_analyzer",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "description": { "type": "text", "analyzer": "video_analyzer" },
      "channelId": { "type": "keyword" },
      "channelName": {
        "type": "text",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "publishedAt": { "type": "date" },
      "amendments": { "type": "keyword" },
      "participants": { "type": "keyword" },
      "videoDate": { "type": "date" },
      "submitterName": { "type": "keyword" },
      "locations": {
        "type": "nested",
        "properties": {
          "id": { "type": "keyword" },
          "coordinates": { "type": "geo_point" },
          "displayName": { "type": "text" },
          "city": { "type": "keyword" },
          "state": { "type": "keyword" }
        }
      },
      "createdAt": { "type": "date" },
      "suggest": {
        "type": "completion",
        "analyzer": "simple"
      }
    }
  }
}
```

---

## Redis Data Structures

### Key Patterns

| Pattern | Type | TTL | Purpose |
|---------|------|-----|---------|
| `session:{userId}:{sessionId}` | String | 7 days | Refresh token data |
| `rate:{userId}:{endpoint}` | String | 1 min | Rate limit counter |
| `rate:ip:{ip}:{endpoint}` | String | 1 min | Anonymous rate limit |
| `cache:video:{id}` | String | 5 min | Video detail cache |
| `cache:cluster:{bbox}:{zoom}` | String | 1 min | Map cluster cache |
| `cache:user:{id}` | String | 5 min | User profile cache |
| `extapi:youtube:{videoId}` | String | 24 hours | YouTube video metadata |
| `extapi:geocode:{hash}` | String | 30 days | Geocoding result (address → coordinates) |
| `extapi:reverse:{lat}:{lng}` | String | 30 days | Reverse geocoding (coordinates → address) |

### External API Cache Structures

Caching external API responses reduces costs and improves latency.

**YouTube Metadata Cache**
```
Key: extapi:youtube:dQw4w9WgXcQ
Value: {
  "title": "Video Title",
  "description": "Video description...",
  "channelTitle": "Channel Name",
  "thumbnailUrl": "https://img.youtube.com/...",
  "duration": "PT4M20S",
  "fetchedAt": "2025-01-31T12:00:00Z"
}
TTL: 86400 (24 hours)
```

**Geocoding Cache**
```
Key: extapi:geocode:a1b2c3d4  (hash of normalized address string)
Value: {
  "input": "123 Main St, Springfield, IL",
  "lat": 39.7817,
  "lng": -89.6501,
  "formattedAddress": "123 Main St, Springfield, IL 62701, USA",
  "placeId": "ChIJ...",
  "fetchedAt": "2025-01-31T12:00:00Z"
}
TTL: 2592000 (30 days)

Note: Geocoding results rarely change; long TTL reduces Google Maps API costs.
```

**Reverse Geocoding Cache**
```
Key: extapi:reverse:39.7817:-89.6501  (rounded to 4 decimal places)
Value: {
  "lat": 39.7817,
  "lng": -89.6501,
  "formattedAddress": "123 Main St, Springfield, IL 62701, USA",
  "placeId": "ChIJ...",
  "fetchedAt": "2025-01-31T12:00:00Z"
}
TTL: 2592000 (30 days)
```

### Rate Limiting Structure

```
Key: rate:{userId}:videos:submit
Value: { "count": 5, "window_start": 1704067200 }
TTL: 86400 (24 hours)

Limits by trust tier:
- NEW: 5 submissions/day
- TRUSTED: 50 submissions/day
- MODERATOR: unlimited
- ADMIN: unlimited
```

---

## Data Flow Patterns

### Video Submission Flow

```
1. Client → API Gateway → Video Service
   - Validate YouTube URL
   - Fetch YouTube metadata
   - Create video record (PENDING)
   - Create video_locations records

2. Video Service → SQS (VideoSubmitted event)

3. Moderation Service ← SQS
   - Create moderation_item record
   - If submitter is TRUSTED+, auto-approve

4. (If approved) Video Service → SQS (VideoApproved event)

5. Search Service ← SQS
   - Index video document in OpenSearch

6. Location Service ← SQS
   - Update location_stats.video_count

7. Notification Service ← SQS
   - Send approval email to submitter
```

### Search Query Flow

```
1. Client → API Gateway → Search Service

2. Search Service → OpenSearch
   - Execute search query
   - Apply filters and facets
   - Return paginated results

3. Search Service → Redis (optional)
   - Cache frequent queries

4. Response → Client
```

---

## Backup and Recovery

### PostgreSQL
- Automated daily snapshots via RDS
- Point-in-time recovery enabled (5-minute granularity)
- Cross-region replica for DR

### OpenSearch
- Automated hourly snapshots to S3
- Rebuild-from-source capability (PostgreSQL is source of truth)

### Redis
- No backup required (cache only)
- Rebuild from source on failure

---

## Data Retention

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| User accounts | Indefinite (soft delete) | User may return |
| Videos | Indefinite | Core content |
| Temporal history tables | 2 years | Audit compliance, debugging |
| Sessions | 7 days after expiry | Security cleanup |
| Password resets | 24 hours after use/expiry | Security |
| Moderation audit log | 2 years | Compliance |
| Notification delivery log | 90 days | Debugging |
