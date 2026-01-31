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

## PostgreSQL Schema Design

### Database Topology
```
┌─────────────────────────────────────────────────────────────────┐
│                    accountabilityatlas (Primary)                 │
├─────────────────────────────────────────────────────────────────┤
│  Schema: users          │  Schema: content        │             │
│  ├── users              │  ├── videos             │             │
│  ├── oauth_links        │  ├── video_locations    │             │
│  ├── sessions           │  ├── locations          │             │
│  └── password_resets    │  └── location_videos    │             │
├─────────────────────────────────────────────────────────────────┤
│  Schema: moderation     │  Schema: notifications  │             │
│  ├── moderation_items   │  ├── preferences        │             │
│  ├── abuse_reports      │  └── delivery_log       │             │
│  └── audit_log          │                         │             │
└─────────────────────────────────────────────────────────────────┘
```

### Schema: users

```sql
-- Core user table
CREATE TABLE users.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    password_hash VARCHAR(255),  -- NULL for OAuth-only users
    display_name VARCHAR(100) NOT NULL,
    avatar_url VARCHAR(500),
    trust_tier VARCHAR(20) NOT NULL DEFAULT 'NEW',
    submission_count INTEGER NOT NULL DEFAULT 0,
    approved_count INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_trust_tier CHECK (
        trust_tier IN ('NEW', 'TRUSTED', 'MODERATOR', 'ADMIN')
    )
);

CREATE INDEX idx_users_email ON users.users(email);
CREATE INDEX idx_users_trust_tier ON users.users(trust_tier);

-- OAuth provider links
CREATE TABLE users.oauth_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users.users(id) ON DELETE CASCADE,
    provider VARCHAR(20) NOT NULL,
    provider_id VARCHAR(255) NOT NULL,
    linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_provider CHECK (provider IN ('GOOGLE', 'APPLE')),
    UNIQUE (provider, provider_id)
);

CREATE INDEX idx_oauth_links_user ON users.oauth_links(user_id);

-- Active sessions (for token revocation)
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

-- Password reset tokens
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
-- Enable PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Videos table
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

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

CREATE INDEX idx_videos_youtube ON content.videos(youtube_id);
CREATE INDEX idx_videos_status ON content.videos(status);
CREATE INDEX idx_videos_submitted_by ON content.videos(submitted_by);
CREATE INDEX idx_videos_channel ON content.videos(channel_id);
CREATE INDEX idx_videos_amendments ON content.videos USING GIN(amendments);
CREATE INDEX idx_videos_participants ON content.videos USING GIN(participants);
CREATE INDEX idx_videos_created ON content.videos(created_at DESC);

-- Locations table (PostGIS enabled)
CREATE TABLE content.locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coordinates GEOGRAPHY(POINT, 4326) NOT NULL,
    display_name VARCHAR(200) NOT NULL,
    address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(50) NOT NULL DEFAULT 'USA',
    video_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_locations_geo ON content.locations USING GIST(coordinates);
CREATE INDEX idx_locations_state ON content.locations(state);

-- Video-Location junction table
CREATE TABLE content.video_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES content.videos(id) ON DELETE CASCADE,
    location_id UUID NOT NULL REFERENCES content.locations(id) ON DELETE CASCADE,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (video_id, location_id)
);

CREATE INDEX idx_video_locations_video ON content.video_locations(video_id);
CREATE INDEX idx_video_locations_location ON content.video_locations(location_id);
```

### Schema: moderation

```sql
-- Moderation queue items
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_content_type CHECK (content_type IN ('VIDEO', 'LOCATION')),
    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'))
);

CREATE INDEX idx_moderation_status ON moderation.moderation_items(status, created_at);
CREATE INDEX idx_moderation_submitter ON moderation.moderation_items(submitter_id);
CREATE INDEX idx_moderation_content ON moderation.moderation_items(content_type, content_id);

-- Abuse reports
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    CONSTRAINT valid_reason CHECK (
        reason IN ('SPAM', 'INAPPROPRIATE', 'COPYRIGHT', 'MISINFORMATION', 'OTHER')
    ),
    CONSTRAINT valid_report_status CHECK (status IN ('OPEN', 'RESOLVED', 'DISMISSED'))
);

CREATE INDEX idx_abuse_reports_status ON moderation.abuse_reports(status, created_at);
CREATE INDEX idx_abuse_reports_content ON moderation.abuse_reports(content_type, content_id);

-- Audit log for moderation actions
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
-- User notification preferences
CREATE TABLE notifications.preferences (
    user_id UUID PRIMARY KEY REFERENCES users.users(id) ON DELETE CASCADE,
    email_on_approval BOOLEAN NOT NULL DEFAULT TRUE,
    email_on_rejection BOOLEAN NOT NULL DEFAULT TRUE,
    email_on_promotion BOOLEAN NOT NULL DEFAULT TRUE,
    email_digest BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Email delivery log
CREATE TABLE notifications.delivery_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users.users(id),
    notification_type VARCHAR(50) NOT NULL,
    email_address VARCHAR(255) NOT NULL,
    subject VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL,
    provider_message_id VARCHAR(255),
    error_message TEXT,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_delivery_log_user ON notifications.delivery_log(user_id);
CREATE INDEX idx_delivery_log_sent ON notifications.delivery_log(sent_at DESC);
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
   - Update location.video_count

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
| Sessions | 7 days after expiry | Security cleanup |
| Password resets | 24 hours after use/expiry | Security |
| Moderation audit log | 2 years | Compliance |
| Notification delivery log | 90 days | Debugging |
