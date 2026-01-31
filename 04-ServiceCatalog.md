# Service Catalog

## Service Summary

| Service | Port | Repository | Status |
|---------|------|------------|--------|
| api-gateway | 8080 | /AcctAtlas-api-gateway | Planned |
| user-service | 8081 | /AcctAtlas-user-service | Planned |
| video-service | 8082 | /AcctAtlas-video-service | Planned |
| location-service | 8083 | /AcctAtlas-location-service | Planned |
| search-service | 8084 | /AcctAtlas-search-service | Planned |
| moderation-service | 8085 | /AcctAtlas-moderation-service | Planned |
| notification-service | 8086 | /AcctAtlas-notification-service | Planned |
| web-app | 3000 | /AcctAtlas-web-app | Planned |

---

## API Gateway

### Overview
Central entry point for all client traffic. Handles cross-cutting concerns before routing to backend services.

### Technology Stack
| Component | Technology |
|-----------|------------|
| Framework | Spring Cloud Gateway |
| Language | Java 21 |
| Build Tool | Gradle |

### Responsibilities
- Request routing based on path/headers
- JWT token validation
- Rate limiting (token bucket algorithm)
- Request/response logging
- CORS configuration
- Health check aggregation

### API Endpoints
| Method | Path | Routes To | Description |
|--------|------|-----------|-------------|
| * | /api/v1/auth/** | user-service | Authentication endpoints |
| * | /api/v1/users/** | user-service | User management |
| * | /api/v1/videos/** | video-service | Video CRUD |
| * | /api/v1/locations/** | location-service | Location operations |
| * | /api/v1/search/** | search-service | Search queries |
| * | /api/v1/moderation/** | moderation-service | Moderation queue |
| GET | /health | - | Gateway health check |

### Dependencies
- Redis (rate limiting, session cache)
- All backend services (routing targets)

---

## User Service

### Overview
Manages user identity, authentication, authorization, and trust tiers.

### Technology Stack
| Component | Technology |
|-----------|------------|
| Framework | Spring Boot 3.x |
| Language | Java 21 |
| Build Tool | Gradle |
| Database | PostgreSQL |
| Cache | Redis |

### Responsibilities
- User registration (email/password)
- OAuth 2.0 authentication (Google, Apple)
- JWT token issuance and refresh
- User profile CRUD
- Trust tier management
- Password reset flow

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/register | Public | Create new account |
| POST | /auth/login | Public | Email/password login |
| POST | /auth/oauth/{provider} | Public | OAuth login |
| POST | /auth/refresh | Refresh Token | Refresh access token |
| POST | /auth/logout | User | Invalidate session |
| GET | /users/me | User | Get current user profile |
| PUT | /users/me | User | Update current user profile |
| GET | /users/{id} | User | Get user public profile |
| PUT | /users/{id}/trust-tier | Moderator | Update user trust tier |

### Domain Model
```
User
├── id: UUID
├── email: String
├── passwordHash: String (nullable for OAuth)
├── displayName: String
├── avatarUrl: String
├── trustTier: Enum (NEW, TRUSTED, MODERATOR, ADMIN)
├── oauthProviders: List<OAuthLink>
├── createdAt: Timestamp
└── updatedAt: Timestamp

OAuthLink
├── provider: Enum (GOOGLE, APPLE)
├── providerId: String
└── linkedAt: Timestamp
```

### Events Published
| Event | Trigger | Consumers |
|-------|---------|-----------|
| UserRegistered | New registration | notification-service |
| UserTrustTierChanged | Tier promotion/demotion | moderation-service |

### Dependencies
- PostgreSQL (user data)
- Redis (sessions, rate limiting)
- SQS (event publishing)

---

## Video Service

### Overview
Core content service managing video records, metadata, and associations.

### Technology Stack
| Component | Technology |
|-----------|------------|
| Framework | Spring Boot 3.x |
| Language | Java 21 |
| Build Tool | Gradle |
| Database | PostgreSQL |

### Responsibilities
- Video record CRUD
- YouTube metadata fetching and validation
- Amendment categorization
- Participant tagging
- Video-location associations
- Ownership tracking

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /videos | Public | List videos (paginated) |
| GET | /videos/{id} | Public | Get video details |
| POST | /videos | User | Submit new video |
| PUT | /videos/{id} | Owner | Update video |
| DELETE | /videos/{id} | Owner/Mod | Delete video |
| GET | /videos/{id}/locations | Public | Get video locations |
| POST | /videos/{id}/locations | Owner | Add location to video |
| DELETE | /videos/{id}/locations/{locId} | Owner | Remove location |

### Domain Model
```
Video
├── id: UUID
├── youtubeId: String
├── title: String
├── description: String
├── thumbnailUrl: String
├── duration: Duration
├── channelId: String
├── channelName: String
├── publishedAt: Timestamp (YouTube publish date)
├── videoDate: Date (incident date, user-provided)
├── amendments: Set<Amendment> (FIRST, SECOND, FOURTH, FIFTH)
├── participants: Set<Participant> (POLICE, GOVERNMENT, BUSINESS, CITIZEN)
├── status: Enum (PENDING, APPROVED, REJECTED)
├── submittedBy: UUID (User reference)
├── locations: List<VideoLocation>
├── createdAt: Timestamp
└── updatedAt: Timestamp

VideoLocation
├── id: UUID
├── videoId: UUID
├── locationId: UUID (Location reference)
├── isPrimary: Boolean
└── addedAt: Timestamp
```

### Events Published
| Event | Trigger | Consumers |
|-------|---------|-----------|
| VideoSubmitted | New submission | moderation-service |
| VideoApproved | Moderation approval | search-service, location-service |
| VideoUpdated | Metadata update | search-service |
| VideoDeleted | Video removal | search-service, location-service |

### Dependencies
- PostgreSQL (video data)
- YouTube Data API (metadata fetching)
- location-service (location validation)
- SQS (event publishing)

---

## Location Service

### Overview
Manages geospatial data, provides spatial queries, and handles map clustering.

### Technology Stack
| Component | Technology |
|-----------|------------|
| Framework | Spring Boot 3.x |
| Language | Java 21 |
| Build Tool | Gradle |
| Database | PostgreSQL + PostGIS |
| Cache | Redis |

### Responsibilities
- Location storage with coordinates
- Bounding box queries for map viewport
- Marker clustering algorithm
- Geocoding (address → coordinates)
- Reverse geocoding (coordinates → address)

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /locations | Public | List locations in bounding box |
| GET | /locations/{id} | Public | Get location details |
| POST | /locations | User | Create new location |
| GET | /locations/cluster | Public | Get clustered markers for viewport |
| GET | /locations/geocode | User | Geocode address to coordinates |
| GET | /locations/reverse | User | Reverse geocode coordinates |

### Query Parameters
```
GET /locations
├── bbox: String (minLng,minLat,maxLng,maxLat)
├── zoom: Integer (map zoom level for clustering)
├── amendments: String (comma-separated filter)
└── limit: Integer (max results)

GET /locations/cluster
├── bbox: String (minLng,minLat,maxLng,maxLat)
├── zoom: Integer
└── gridSize: Integer (clustering grid size in pixels)
```

### Domain Model
```
Location
├── id: UUID
├── coordinates: Point (PostGIS)
├── displayName: String
├── address: String (optional)
├── city: String
├── state: String
├── country: String
├── videoCount: Integer (denormalized)
├── createdAt: Timestamp
└── updatedAt: Timestamp
```

### Clustering Algorithm
- Server-side grid-based clustering using PostGIS
- Cluster size adapts to zoom level
- Returns cluster centroid, count, and sample video IDs

### Dependencies
- PostgreSQL + PostGIS (spatial data)
- Redis (cluster caching)
- Google Maps Geocoding API

---

## Search Service

### Overview
Provides full-text and faceted search across video content.

### Technology Stack
| Component | Technology |
|-----------|------------|
| Framework | Spring Boot 3.x |
| Language | Java 21 |
| Build Tool | Gradle |
| Search Engine | OpenSearch |

### Responsibilities
- Index video documents
- Full-text search execution
- Faceted filtering
- Autocomplete suggestions
- Search result ranking
- Synonym handling

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /search | Public | Execute search query |
| GET | /search/suggest | Public | Autocomplete suggestions |
| GET | /search/facets | Public | Get available facet values |

### Query Parameters
```
GET /search
├── q: String (search query)
├── amendments: String[] (filter)
├── participants: String[] (filter)
├── channelId: String (filter)
├── dateFrom: Date (filter)
├── dateTo: Date (filter)
├── state: String (filter)
├── bbox: String (geo filter)
├── sort: String (relevance, date, distance)
├── page: Integer
└── size: Integer
```

### Search Document Schema
```json
{
  "id": "uuid",
  "youtubeId": "string",
  "title": "string",
  "description": "string",
  "channelId": "string",
  "channelName": "string",
  "publishedAt": "2024-01-01T00:00:00Z",
  "amendments": ["FIRST", "FOURTH"],
  "participants": ["POLICE", "CITIZEN"],
  "submitterName": "string",
  "locations": [
    {
      "id": "uuid",
      "coordinates": { "lat": 0.0, "lon": 0.0 },
      "city": "string",
      "state": "string"
    }
  ],
  "createdAt": "2024-01-01T00:00:00Z",
  "videoDate": "2024-01-01"
}
```

### Events Consumed
| Event | Action |
|-------|--------|
| VideoApproved | Index document |
| VideoUpdated | Update document |
| VideoDeleted | Remove document |

### Dependencies
- OpenSearch (search index)
- SQS (event consumption)

---

## Moderation Service

### Overview
Manages content moderation workflow and user trust progression.

### Technology Stack
| Component | Technology |
|-----------|------------|
| Framework | Spring Boot 3.x |
| Language | Java 21 |
| Build Tool | Gradle |
| Database | PostgreSQL |

### Responsibilities
- Moderation queue management
- Content approval/rejection
- Trust tier promotion logic
- Abuse report handling
- Moderation audit trail

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /moderation/queue | Moderator | Get pending items |
| GET | /moderation/queue/{id} | Moderator | Get item details |
| POST | /moderation/queue/{id}/approve | Moderator | Approve content |
| POST | /moderation/queue/{id}/reject | Moderator | Reject with reason |
| GET | /moderation/reports | Moderator | Get abuse reports |
| POST | /moderation/reports | User | Submit abuse report |
| POST | /moderation/reports/{id}/resolve | Moderator | Resolve report |

### Domain Model
```
ModerationItem
├── id: UUID
├── contentType: Enum (VIDEO, LOCATION)
├── contentId: UUID
├── submitterId: UUID
├── status: Enum (PENDING, APPROVED, REJECTED)
├── reviewerId: UUID (nullable)
├── reviewedAt: Timestamp (nullable)
├── rejectionReason: String (nullable)
├── createdAt: Timestamp
└── updatedAt: Timestamp

AbuseReport
├── id: UUID
├── contentType: Enum
├── contentId: UUID
├── reporterId: UUID
├── reason: Enum (SPAM, INAPPROPRIATE, COPYRIGHT, OTHER)
├── description: String
├── status: Enum (OPEN, RESOLVED, DISMISSED)
├── resolvedBy: UUID (nullable)
├── resolution: String (nullable)
└── createdAt: Timestamp
```

### Trust Tier Promotion Logic
```
NEW → TRUSTED:
  - Account age > 30 days
  - >= 10 approved submissions
  - 0 rejected submissions in last 30 days
  - No active abuse reports

TRUSTED → MODERATOR:
  - Manual promotion by Admin only
```

### Events Published/Consumed
| Event | Type | Description |
|-------|------|-------------|
| VideoSubmitted | Consumed | Create moderation item |
| VideoApproved | Published | Trigger indexing |
| VideoRejected | Published | Notify submitter |

### Dependencies
- PostgreSQL (moderation data)
- video-service (content details)
- user-service (trust tier updates)
- SQS (events)

---

## Notification Service

### Overview
Handles all user-facing communications via email.

### Technology Stack
| Component | Technology |
|-----------|------------|
| Framework | Spring Boot 3.x |
| Language | Java 21 |
| Build Tool | Gradle |
| Database | PostgreSQL |
| Email Provider | Amazon SES |

### Responsibilities
- Email notification delivery
- Template management
- Notification preferences
- Delivery tracking
- Retry handling

### API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /notifications/preferences | User | Get notification settings |
| PUT | /notifications/preferences | User | Update settings |

### Notification Types
| Type | Trigger | Template |
|------|---------|----------|
| WELCOME | User registration | welcome.html |
| VIDEO_APPROVED | Content approved | video-approved.html |
| VIDEO_REJECTED | Content rejected | video-rejected.html |
| TRUST_PROMOTED | Tier upgrade | trust-promoted.html |
| PASSWORD_RESET | Reset requested | password-reset.html |

### Events Consumed
| Event | Action |
|-------|--------|
| UserRegistered | Send welcome email |
| VideoApproved | Notify submitter |
| VideoRejected | Notify with reason |
| UserTrustTierChanged | Notify on promotion |

### Dependencies
- PostgreSQL (preferences, logs)
- Amazon SES (email delivery)
- SQS (event consumption)
