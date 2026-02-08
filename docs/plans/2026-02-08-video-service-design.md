# Video Service - Design Document

**Date:** 2026-02-08
**Status:** Approved
**Issue:** AcctAtlas-video-service#1

## Overview

The video-service is the core content management service for AccountabilityAtlas. It manages video records, integrates with YouTube for metadata, handles amendment categorization, and manages video-location associations.

## Project Structure

```
AcctAtlas-video-service/
├── build.gradle              # OpenAPI generator + Spring Boot
├── settings.gradle
├── gradle.properties
├── docker-compose.yml        # PostgreSQL + Redis + service
├── src/main/java/com/accountabilityatlas/videoservice/
│   ├── VideoServiceApplication.java
│   ├── config/
│   │   ├── SecurityConfig.java       # JWT validation
│   │   ├── YouTubeProperties.java    # API key config
│   │   └── WebClientConfig.java      # YouTube client setup
│   ├── domain/
│   │   ├── Video.java               # JPA entity
│   │   ├── VideoLocation.java       # Join entity with cached location data
│   │   ├── Amendment.java           # Enum
│   │   ├── Participant.java         # Enum
│   │   └── VideoStatus.java         # Enum
│   ├── repository/
│   │   ├── VideoRepository.java
│   │   └── VideoLocationRepository.java
│   ├── service/
│   │   ├── VideoService.java
│   │   ├── YouTubeService.java      # External API client
│   │   ├── LocationClient.java      # REST client to location-service
│   │   └── VideoEventPublisher.java
│   ├── web/
│   │   ├── VideoController.java
│   │   ├── VideoLocationController.java
│   │   └── InternalVideoController.java
│   └── exception/
│       ├── GlobalExceptionHandler.java
│       └── ...custom exceptions
├── src/main/resources/
│   ├── application.yml
│   ├── application-local.yml
│   └── db/migration/
│       ├── V1__create_videos_schema.sql
│       └── V2__create_video_locations.sql
└── src/test/java/...
```

## Database Schema

### Tables (in `videos` schema)

| Table | Temporal | Description |
|-------|----------|-------------|
| `videos.videos` | Yes | Core video metadata, YouTube info, status |
| `videos.videos_history` | - | Automatic history for videos |
| `videos.video_locations` | Yes | Video-to-location associations with cached location data |
| `videos.video_locations_history` | - | Automatic history for associations |

### Video Entity

```java
@Entity
@Table(name = "videos", schema = "videos")
public class Video {
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "youtube_id", unique = true, nullable = false, length = 11)
    private String youtubeId;

    private String title;                    // From YouTube
    private String description;              // From YouTube
    private String thumbnailUrl;             // From YouTube
    private Integer durationSeconds;         // From YouTube
    private String channelId;                // From YouTube
    private String channelName;              // From YouTube
    private Instant publishedAt;             // From YouTube

    private LocalDate videoDate;             // User-provided incident date

    @ElementCollection @Enumerated(EnumType.STRING)
    private Set<Amendment> amendments;       // FIRST, SECOND, FOURTH, FIFTH

    @ElementCollection @Enumerated(EnumType.STRING)
    private Set<Participant> participants;   // POLICE, GOVERNMENT, BUSINESS, CITIZEN

    @Enumerated(EnumType.STRING)
    private VideoStatus status;              // PENDING, APPROVED, REJECTED, DELETED

    private UUID submittedBy;                // FK to user (not enforced cross-service)

    @OneToMany(mappedBy = "video", cascade = CascadeType.ALL)
    private List<VideoLocation> locations;

    private Instant createdAt;
    private String sysPeriod;                // Read-only, managed by trigger
}
```

### VideoLocation Entity (with cached location data)

```java
@Entity
@Table(name = "video_locations", schema = "videos")
public class VideoLocation {
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "video_id")
    private Video video;

    private UUID locationId;
    private boolean isPrimary;

    // Cached location data (denormalized for read performance)
    private String displayName;
    private String city;
    private String state;
    private Double latitude;
    private Double longitude;

    private Instant createdAt;
    private String sysPeriod;
}
```

### Indexes

| Index | Column(s) | Purpose |
|-------|-----------|---------|
| `idx_videos_youtube_id` | `youtube_id` | Duplicate detection |
| `idx_videos_status` | `status` | Filter by approval status |
| `idx_videos_submitted_by` | `submitted_by` | User's submissions |
| `idx_video_locations_video_id` | `video_id` | Join queries |
| `idx_video_locations_location_id` | `location_id` | Reverse lookup |

## YouTube Integration

### Supported URL Patterns

```java
private static final List<Pattern> YOUTUBE_PATTERNS = List.of(
    Pattern.compile("youtube\\.com/watch\\?v=([\\w-]{11})"),
    Pattern.compile("youtu\\.be/([\\w-]{11})"),
    Pattern.compile("youtube\\.com/embed/([\\w-]{11})")
);
```

Note: YouTube Shorts (`/shorts/`) not supported. Live videos (`/live/`) deferred to issue #11.

### YouTubeService

```java
@Service
public class YouTubeService {
    public record YouTubeMetadata(
        String videoId,
        String title,
        String description,
        String thumbnailUrl,
        Integer durationSeconds,
        String channelId,
        String channelName,
        Instant publishedAt
    ) {}

    public String extractVideoId(String url);
    public YouTubeMetadata fetchMetadata(String videoId);
}
```

### Resilience Patterns

| Pattern | Implementation |
|---------|----------------|
| Circuit Breaker | Resilience4j, 5-call sliding window |
| Caching | Redis, 24-hour TTL (reduce quota usage) |
| Rate Limiting | Client-side limiter (10,000 units/day quota) |
| Retry | Exponential backoff (1s, 2s, 4s) |
| Timeout | 5 seconds per API call |

### Error Handling

| YouTube Error | Response to Client |
|---------------|-------------------|
| 404 Not Found | 422 "Video not found" |
| 403 Forbidden | 422 "Video is private or restricted" |
| 429 Rate Limited | Retry with backoff, then 503 |
| 5xx Server Error | Retry, fallback to cache if available |

## API Endpoints

### Public Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /videos | Public | List videos (paginated, filtered) |
| GET | /videos/{id} | Public* | Get video details (*visibility rules apply) |
| POST | /videos | User | Submit new video |
| PUT | /videos/{id} | Owner | Update video metadata (non-approved only) |
| DELETE | /videos/{id} | Owner | Delete video (non-approved only) |
| GET | /videos/{id}/locations | Public | Get video locations |
| POST | /videos/{id}/locations | Owner | Add location (non-approved only) |
| DELETE | /videos/{id}/locations/{locId} | Owner | Remove location (non-approved only) |
| GET | /videos/user/{userId} | Public | Get user's submissions |

### Internal Endpoints (service-to-service)

Used by moderation-service. Not exposed via API Gateway.

| Method | Path | Caller | Description |
|--------|------|--------|-------------|
| PUT | /internal/videos/{id} | moderation-service | Update metadata |
| PUT | /internal/videos/{id}/status | moderation-service | Set APPROVED/REJECTED |
| POST | /internal/videos/{id}/locations | moderation-service | Add location |
| DELETE | /internal/videos/{id}/locations/{locId} | moderation-service | Remove location |

Access controlled by IP/CIDR allowlist.

### Visibility Rules

| Video Status | Who Can View |
|--------------|--------------|
| APPROVED | Anyone |
| PENDING | Admin, Moderator, or Submitter |
| REJECTED | Admin, Moderator, or Submitter |
| DELETED | Admin only |

Returns 404 (not 403) for unauthorized access.

## Location Integration

### LocationClient

Validates locations exist and caches data:

```java
@Component
public class LocationClient {
    public Optional<LocationSummary> getLocation(UUID locationId);

    public record LocationSummary(
        UUID id,
        String displayName,
        String city,
        String state,
        Coordinates coordinates
    ) {}
}
```

### Caching Strategy

Location data is cached in VideoLocation table for read performance. Locations rarely change, and this avoids N+1 calls on the map page.

## Events

### Events Published

| Event | Trigger | Queue | Consumers |
|-------|---------|-------|-----------|
| VideoSubmitted | New video created | video-events | moderation-service, search-service |
| VideoUpdated | Metadata changed | video-events | search-service |
| VideoDeleted | Video soft-deleted | video-events | search-service, location-service |

### Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| VideoApproved | moderation-service | Update status to APPROVED |
| VideoRejected | moderation-service | Update status to REJECTED |

### Implementation

Spring ApplicationEventPublisher for now. SQS integration added in Phase 2.

## Testing Strategy

### Unit Tests

| Layer | What to Test | Mocking |
|-------|--------------|---------|
| VideoService | Business logic, validation | Repository, LocationClient, YouTubeService |
| YouTubeService | URL parsing, metadata mapping | WebClient |
| VideoAuthorizationService | Visibility rules | None (pure logic) |
| VideoController | Request validation | VideoService |

### Integration Tests

| Test | Dependencies | Purpose |
|------|--------------|---------|
| VideoRepositoryIT | PostgreSQL | Query methods, filtering |
| YouTubeServiceIT | WireMock | YouTube API responses |
| VideoServiceIT | PostgreSQL, WireMock | Full flows |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Original 3 YouTube URL patterns | No shorts support; live deferred to issue #11 |
| Moderation tweaks via moderation-service | Clean separation, audit trail in one place |
| Cache location data in VideoLocation | Read performance for map page |
| Spring events first, SQS later | Service works standalone, messaging in Phase 2 |
| Internal endpoints secured by IP/CIDR | Simple, no JWT for service-to-service |

## Implementation Order

1. Project scaffolding - Gradle build, docker-compose, application.yml
2. Domain layer - Entities, enums, repositories
3. Database migrations - Flyway scripts for videos schema
4. YouTube integration - URL parsing, API client, caching
5. Video CRUD - Service layer, public controller
6. Location integration - LocationClient, VideoLocation endpoints
7. Internal APIs - Endpoints for moderation-service
8. Events - VideoSubmitted/Updated/Deleted publishing
9. Documentation - README, database-schema.md updates
10. Tests - Unit and integration tests

## References

- [Map Browsing Design](2026-02-07-map-browsing-design.md)
- [Development Standards](../08-DevelopmentStandards.md)
- [location-service](https://github.com/kelleyglenn/AcctAtlas-location-service) - reference implementation
- Live video support: AccountabilityAtlas#11
