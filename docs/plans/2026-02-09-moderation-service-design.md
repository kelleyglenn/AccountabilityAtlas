# Moderation Service - Design Document

**Date:** 2026-02-09
**Status:** Approved
**Issue:** AcctAtlas-moderation-service#2

## Overview

The moderation-service manages the content quality control workflow for AccountabilityAtlas. It handles the moderation queue, content approval/rejection, abuse reporting, and trust tier progression logic. This service is central to ensuring content quality while allowing trusted users to bypass moderation.

## Responsibilities

- Moderation queue management (create, review items)
- Content approval/rejection workflow
- Auto-approval for trusted users
- Trust tier promotion logic execution
- Abuse report handling
- Moderation audit trail

## Project Structure

```
AcctAtlas-moderation-service/
├── build.gradle              # OpenAPI generator + Spring Boot
├── settings.gradle
├── gradle.properties
├── docker-compose.yml        # PostgreSQL + service
├── src/main/java/com/accountabilityatlas/moderationservice/
│   ├── ModerationServiceApplication.java
│   ├── config/
│   │   ├── SecurityConfig.java       # JWT validation
│   │   └── VideoServiceClientConfig.java
│   ├── domain/
│   │   ├── ModerationItem.java       # JPA entity (temporal)
│   │   ├── AbuseReport.java          # JPA entity (temporal)
│   │   ├── AuditLogEntry.java        # JPA entity (append-only)
│   │   ├── ContentType.java          # Enum (VIDEO only for now)
│   │   ├── ModerationStatus.java     # Enum (PENDING, APPROVED, REJECTED)
│   │   ├── ReportStatus.java         # Enum (OPEN, RESOLVED, DISMISSED)
│   │   └── AbuseReason.java          # Enum
│   ├── repository/
│   │   ├── ModerationItemRepository.java
│   │   ├── AbuseReportRepository.java
│   │   └── AuditLogRepository.java
│   ├── service/
│   │   ├── ModerationService.java    # Queue management
│   │   ├── AbuseReportService.java   # Report handling
│   │   ├── TrustPromotionService.java # Trust tier logic
│   │   ├── VideoServiceClient.java   # REST client to video-service
│   │   ├── UserServiceClient.java    # REST client to user-service
│   │   └── ModerationEventPublisher.java
│   ├── web/
│   │   ├── ModerationQueueController.java
│   │   ├── VideoTweakController.java
│   │   └── AbuseReportController.java
│   └── exception/
│       ├── GlobalExceptionHandler.java
│       └── ...custom exceptions
├── src/main/resources/
│   ├── application.yml
│   ├── application-local.yml
│   └── db/migration/
│       ├── V1__create_moderation_schema.sql
│       ├── V2__create_abuse_reports.sql
│       └── V3__create_audit_log.sql
└── src/test/java/...
```

## Database Schema

### Tables (in `moderation` schema)

| Table | Temporal | Description |
|-------|----------|-------------|
| `moderation.moderation_items` | Yes | Content awaiting review |
| `moderation.moderation_items_history` | - | Automatic history |
| `moderation.abuse_reports` | Yes | User-submitted abuse reports |
| `moderation.abuse_reports_history` | - | Automatic history |
| `moderation.audit_log` | No | Append-only moderation actions |

### ModerationItem Entity

```java
@Entity
@Table(name = "moderation_items", schema = "moderation")
public class ModerationItem {
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ContentType contentType;      // VIDEO (LOCATION can be added later)

    @Column(nullable = false)
    private UUID contentId;               // Reference to actual content

    @Column(nullable = false)
    private UUID submitterId;             // Who submitted the content

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ModerationStatus status;      // PENDING, APPROVED, REJECTED

    private int priority;                 // Higher = review first

    private UUID reviewerId;              // Who reviewed (nullable)
    private Instant reviewedAt;           // When reviewed (nullable)
    private String rejectionReason;       // If rejected (nullable)

    private Instant createdAt;
    private String sysPeriod;             // Read-only, managed by trigger
}
```

### AbuseReport Entity

```java
@Entity
@Table(name = "abuse_reports", schema = "moderation")
public class AbuseReport {
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ContentType contentType;

    @Column(nullable = false)
    private UUID contentId;

    @Column(nullable = false)
    private UUID reporterId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private AbuseReason reason;           // SPAM, INAPPROPRIATE, COPYRIGHT, MISINFORMATION, OTHER

    @Column(length = 2000)
    private String description;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ReportStatus status;          // OPEN, RESOLVED, DISMISSED

    private UUID resolvedBy;              // Moderator who resolved
    private String resolution;            // Resolution notes

    private Instant createdAt;
    private String sysPeriod;
}
```

### AuditLogEntry Entity

```java
@Entity
@Table(name = "audit_log", schema = "moderation")
public class AuditLogEntry {
    @Id @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(nullable = false)
    private UUID actorId;                 // Who performed the action

    @Column(nullable = false)
    private String action;                // e.g., "APPROVE", "REJECT", "DISMISS_REPORT"

    @Column(nullable = false)
    private String targetType;            // e.g., "VIDEO", "ABUSE_REPORT"

    @Column(nullable = false)
    private UUID targetId;

    @Column(columnDefinition = "jsonb")
    private String details;               // Additional context as JSON

    @Column(nullable = false)
    private Instant createdAt;
}
```

### Indexes

| Index | Column(s) | Purpose |
|-------|-----------|---------|
| `idx_moderation_items_status` | `status` | Filter pending items |
| `idx_moderation_items_content_id` | `content_id` | Find item by content |
| `idx_moderation_items_submitter` | `submitter_id` | User's pending submissions |
| `idx_abuse_reports_status` | `status` | Filter open reports |
| `idx_abuse_reports_content_id` | `content_id` | Reports against content |
| `idx_audit_log_actor` | `actor_id` | Actions by moderator |
| `idx_audit_log_target` | `target_type, target_id` | Actions on content |

## API Endpoints

### Queue Management

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /moderation/queue | Mod/Admin | Get pending items (paginated) |
| GET | /moderation/queue/{id} | Mod/Admin | Get item details |
| POST | /moderation/queue/{id}/approve | Mod/Admin | Approve content (409 if already reviewed) |
| POST | /moderation/queue/{id}/reject | Mod/Admin | Reject with reason (409 if already reviewed) |
| GET | /moderation/queue/stats | Mod/Admin | Queue statistics |

### Video Tweaks During Moderation

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| PUT | /moderation/queue/{id}/video | Mod/Admin | Update video metadata |
| POST | /moderation/queue/{id}/locations | Mod/Admin | Add location to video |
| DELETE | /moderation/queue/{id}/locations/{locId} | Mod/Admin | Remove location |

**Status restrictions:**
- **Moderators**: Can only modify videos with status = PENDING
- **Admins**: Can modify videos with any status (PENDING, APPROVED, REJECTED)

These endpoints call video-service internal APIs (`/internal/videos/*`) to apply changes.

### Abuse Reports

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /moderation/reports | Mod/Admin | Get abuse reports |
| POST | /moderation/reports | User | Submit abuse report |
| GET | /moderation/reports/{id} | Mod/Admin | Get report details |
| POST | /moderation/reports/{id}/resolve | Mod/Admin | Resolve report (informational only) |
| POST | /moderation/reports/{id}/dismiss | Mod/Admin | Dismiss report (invalid/spam) |

**Note:** Abuse reports are informational - they don't automatically trigger content status changes. Moderators check reports periodically and take manual action as needed. See [#17](https://github.com/kelleyglenn/AccountabilityAtlas/issues/17) for future automation options.

### Query Parameters (GET /moderation/queue)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| status | String | PENDING | Filter by status |
| contentType | String | - | Filter by content type (VIDEO only for now) |
| sortBy | String | createdAt | Sort by: createdAt, priority |
| page | Int | 0 | Page number |
| size | Int | 20 | Page size (max 100) |

## video-service Integration

### Internal API Client

Used for moderation tweaks (service-to-service, no JWT required):

```java
@Component
public class VideoServiceClient {
    public void updateVideoMetadata(UUID videoId, VideoUpdateRequest request);
    public void updateVideoStatus(UUID videoId, VideoStatus status);
    public void addLocation(UUID videoId, UUID locationId, boolean isPrimary);
    public void removeLocation(UUID videoId, UUID locationId);
}
```

| Method | video-service Endpoint |
|--------|------------------------|
| updateVideoMetadata | PUT /internal/videos/{id} |
| updateVideoStatus | PUT /internal/videos/{id}/status |
| addLocation | POST /internal/videos/{id}/locations |
| removeLocation | DELETE /internal/videos/{id}/locations/{locId} |

### Access Control

Internal endpoints secured by IP/CIDR allowlist on video-service side.

## user-service Integration

### User/Stats Queries

```java
@Component
public class UserServiceClient {
    public Optional<UserSummary> getUser(UUID userId);
    public Optional<UserStats> getUserStats(UUID userId);
    public void updateTrustTier(UUID userId, TrustTier newTier);
}
```

Used for:
- Checking submitter trust tier (auto-approval decision)
- Trust tier promotion checks
- Updating user trust tier on promotion

## Moderation Workflow

```
┌─────────────────┐
│ VideoSubmitted  │
│    (Event)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Check Submitter │
│   Trust Tier    │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌───────┐ ┌───────────┐
│TRUSTED│ │    NEW    │
│  or   │ │           │
│higher │ │           │
└───┬───┘ └─────┬─────┘
    │           │
    │           ▼
    │     ┌───────────┐
    │     │Add to Mod │
    │     │   Queue   │
    │     └─────┬─────┘
    │           │
    │     ┌─────┴─────┐
    │     ▼           ▼
    │ ┌───────┐  ┌────────┐
    │ │Approve│  │ Reject │
    │ └───┬───┘  └────┬───┘
    │     │           │
    ▼     ▼           ▼
┌─────────────┐  ┌─────────────┐
│VideoApproved│  │VideoRejected│
│   (Event)   │  │   (Event)   │
└─────────────┘  └─────────────┘
```

## Trust Tier Changes

### Promotion (NEW → TRUSTED)

Automatic promotion from NEW to TRUSTED:

```java
public boolean checkTrustPromotion(UUID userId) {
    User user = userService.getUser(userId);
    UserStats stats = userService.getUserStats(userId);

    if (user.getTrustTier() != TrustTier.NEW) {
        return false;
    }

    Duration accountAge = Duration.between(user.getCreatedAt(), Instant.now());
    int recentRejections = moderationRepository
        .countRejectionsSince(userId, Instant.now().minus(30, ChronoUnit.DAYS));
    int activeReports = abuseReportRepository
        .countActiveReportsAgainst(userId);

    return accountAge.toDays() >= 30
        && stats.getApprovedCount() >= 10
        && recentRejections == 0
        && activeReports == 0;
}
```

### Promotion Criteria

| Criterion | Threshold |
|-----------|-----------|
| Account age | >= 30 days |
| Approved submissions | >= 10 |
| Rejections (last 30 days) | 0 |
| Active abuse reports | 0 |

Promotion check triggered after each VideoApproved event.

### Demotion (TRUSTED → NEW)

Automatic demotion when trust is violated:

```java
public boolean checkTrustDemotion(UUID userId) {
    User user = userService.getUser(userId);

    if (user.getTrustTier() != TrustTier.TRUSTED) {
        return false;  // Only TRUSTED can be auto-demoted
    }

    int recentRejections = moderationRepository
        .countRejectionsSince(userId, Instant.now().minus(30, ChronoUnit.DAYS));
    int activeReports = abuseReportRepository
        .countActiveReportsAgainst(userId);

    return recentRejections >= 3 || activeReports >= 3;
}
```

### Demotion Criteria

| Criterion | Threshold |
|-----------|-----------|
| Rejections (last 30 days) | >= 3 |
| Active abuse reports | >= 3 |

Either condition triggers demotion. Demotion check triggered after each VideoRejected event.

### Manual Trust Tier Changes

Admins can manually promote or demote users via user-service API:

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| PUT | /users/{id}/trust-tier | Admin | Set user's trust tier |

This allows admins to:
- Demote MODERATOR → TRUSTED → NEW for policy violations
- Promote users who don't meet automatic criteria (edge cases)
- Handle appeals after automatic demotion

## Events

### Events Consumed

| Event | Source | Action |
|-------|--------|--------|
| VideoSubmitted | video-service | Create moderation item (or auto-approve for trusted users) |
| UserTrustTierChanged | user-service | Re-evaluate pending items (if promoted to trusted) |

### Events Published

| Event | Trigger | Consumers |
|-------|---------|-----------|
| VideoApproved | Content approved | video-service, search-service |
| VideoRejected | Content rejected | video-service, notification-service |

Note: Trust tier changes are published by user-service as `UserTrustTierChanged` after moderation-service calls the trust tier API.

### Implementation

Spring ApplicationEventPublisher for local development. SQS integration added in Phase 2.

## Testing Strategy

### Unit Tests

| Layer | What to Test | Mocking |
|-------|--------------|---------|
| ModerationService | Queue management, approval/rejection | Repository, VideoServiceClient |
| TrustPromotionService | Promotion logic | UserServiceClient, repositories |
| AbuseReportService | Report lifecycle | Repository |
| Controllers | Request validation, auth | Services |

### Integration Tests

| Test | Dependencies | Purpose |
|------|--------------|---------|
| ModerationRepositoryIT | PostgreSQL | Query methods, status transitions |
| ModerationServiceIT | PostgreSQL, WireMock | Full approval/rejection flows |
| TrustPromotionIT | PostgreSQL, WireMock | Promotion criteria evaluation |

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Optimistic locking for reviews | No claim step - just check status=PENDING before approve/reject, return 409 if already reviewed |
| Moderation item per content | Not per report - multiple reports can reference same content |
| Temporal tables for items/reports | Track moderation history for audit |
| Append-only audit log | Immutable record of all moderation actions |
| Auto-approval by trust tier | Reduce moderator workload for trusted users |
| Video tweaks via internal APIs | Moderators don't need video-service auth, audit stays in moderation |
| Priority field on moderation items | Allow escalation of high-priority content |
| Separate AbuseReport from ModerationItem | Reports from users != queue items for moderators |
| VIDEO content type only | LOCATION moderation can be added later if needed |
| Abuse reports are informational | No auto-actions on content; revisit in [#17](https://github.com/kelleyglenn/AccountabilityAtlas/issues/17) |
| Auto-demotion + manual override | 3 rejections or 3 reports triggers demotion; admins can manually adjust |

## References

- [Map Browsing Design](2026-02-07-map-browsing-design.md)
- [Video Service Design](2026-02-08-video-service-design.md)
- [Development Standards](../08-DevelopmentStandards.md)
- [Security Architecture](../06-SecurityArchitecture.md)
- [video-service](https://github.com/kelleyglenn/AcctAtlas-video-service) - internal APIs consumed
