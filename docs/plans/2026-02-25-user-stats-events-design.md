# User Stats Event Handling Design

**Issue**: [user-service#47](https://github.com/kelleyglenn/AcctAtlas-user-service/issues/47) — User stats counters never updated by video status events

**Date**: 2026-02-25

## Problem

`user_stats.approved_count`, `submission_count`, and `rejected_count` are always 0. The user-service does not subscribe to any video event queues. This also breaks `TrustPromotionService` in moderation-service, which reads `approvedCount` to decide auto-promotions.

## Approach: Dual-Queue Fan-Out

Follow the established pattern (like `moderation-events` + `search-moderation-events`): video-service publishes to additional dedicated queues for user-service.

No data backfill — stats will be accurate going forward from deployment.

## Changes by Repo

### Video-Service

**1. Add `submittedBy` to `VideoStatusChangedEvent`**

```java
public record VideoStatusChangedEvent(
    UUID videoId,
    UUID submittedBy,      // NEW
    List<UUID> locationIds,
    String previousStatus,
    String newStatus,
    Instant timestamp) {}
```

The location-service's copy does NOT need updating — Jackson ignores unknown fields (`FAIL_ON_UNKNOWN_PROPERTIES = false` is Spring Boot's default).

**2. Broaden the publishing condition**

Current condition only publishes for APPROVED transitions when locations exist. Change to publish on ANY status change:

```java
// Before (VideoService.java line 189-194):
if (!locationIds.isEmpty()
    && ((newStatus == VideoStatus.APPROVED && previousStatus != VideoStatus.APPROVED)
        || (previousStatus == VideoStatus.APPROVED && newStatus != VideoStatus.APPROVED)))

// After:
if (previousStatus != newStatus)
```

Safe because location-service self-filters (only acts on APPROVED transitions) and handles empty `locationIds` gracefully (loop does nothing).

**3. Dual publishing**

`VideoEventPublisher` publishes each event to both the original and user-service queues:
- `VideoSubmittedEvent` → `video-events` + `user-video-events`
- `VideoStatusChangedEvent` → `video-status-events` + `user-video-status-events`

New config properties:
```yaml
app:
  sqs:
    user-video-events-queue: user-video-events
    user-video-status-events-queue: user-video-status-events
```

### User-Service

**1. Event DTOs** (in `com.accountabilityatlas.userservice.event`):

```java
public record VideoSubmittedEvent(
    UUID videoId, UUID submitterId, String submitterTrustTier,
    String title, Set<String> amendments, List<UUID> locationIds,
    Instant timestamp) {}

public record VideoStatusChangedEvent(
    UUID videoId, UUID submittedBy, List<UUID> locationIds,
    String previousStatus, String newStatus, Instant timestamp) {}
```

Each service defines its own copy of the event record (established pattern — avoids shared libraries).

**2. `UserStatsService`** (follows `LocationStatsService` pattern):

```java
@Transactional incrementSubmissionCount(UUID userId)
@Transactional handleStatusChange(UUID userId, String previousStatus, String newStatus)
```

`handleStatusChange` logic:
- Transitioning TO APPROVED → `approvedCount++`
- Transitioning FROM APPROVED → `approvedCount--` (floor at 0)
- Transitioning TO REJECTED → `rejectedCount++`
- Transitioning FROM REJECTED → `rejectedCount--` (floor at 0)

**3. SQS Listeners**:

- `VideoSubmittedHandler` — listens on `user-video-events`, increments `submission_count`
- `VideoStatusChangedHandler` — listens on `user-video-status-events`, updates `approved_count`/`rejected_count`

Both follow the location-service handler pattern: log, delegate to service, re-throw on failure.

**4. Config** (`application.yml`):
```yaml
app:
  sqs:
    user-video-events-queue: user-video-events
    user-video-status-events-queue: user-video-status-events
```

### Infrastructure

**LocalStack** (`docker/localstack/init-queues.sh`):
```bash
awslocal sqs create-queue --queue-name user-video-events
awslocal sqs create-queue --queue-name user-video-events-dlq
awslocal sqs create-queue --queue-name user-video-status-events
awslocal sqs create-queue --queue-name user-video-status-events-dlq
```

**Terraform** (`infra/messaging.tf`): Add `user-video-events` and `user-video-status-events` to `sqs_queues` list.

**Docker Compose**: Add queue name env vars to both video-service and user-service containers.

### Scripts and Seed Data

**1. `clean-test-data.sh` — Add new queues to SQS purge loop**

Add `user-video-events`, `user-video-events-dlq`, `user-video-status-events`, `user-video-status-events-dlq` to the purge loop.

**2. `clean-test-data.sh` — Reset seed user stats after deleting non-seed data**

After deleting non-seed videos, seed users' stats become stale (e.g., Trusted User submitted 5 test videos that were deleted, but stats still reflect them). Reset to known-correct values:

```sql
-- Reset all seed user stats, then set Trusted User to match seed videos
UPDATE users.user_stats SET
    submission_count = 0, approved_count = 0, rejected_count = 0, updated_at = NOW();
UPDATE users.user_stats SET
    submission_count = 10, approved_count = 10, rejected_count = 0
WHERE user_id = '00000000-0000-0000-0000-000000000003';
```

**3. `clean-test-data.sh` — Reset seed location stats after deleting non-seed data**

Same issue: non-seed videos at seed locations inflate `video_count`. Each seed location has exactly 1 seed video:

```sql
UPDATE locations.location_stats SET video_count = 1
WHERE location_id IN (
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
```

**4. `R__dev_seed_users.sql` — Fix Trusted User stats**

Current seed data says `submission_count=10, approved_count=8, rejected_count=2`, but all 10 seed videos are APPROVED with 0 rejected. Fix to `10, 10, 0`.

**5. `seed-videos.sh` — No changes needed**

Seeds via REST API. After this fix, the event flow will naturally update `user_stats` when videos are created/approved through the API.

## Testing

**User-service unit tests**:
- `UserStatsServiceTest` — all counter transitions (PENDING→APPROVED, APPROVED→REJECTED, etc.), floor-at-zero edge case, unknown user
- `VideoSubmittedHandlerTest` — delegates with correct user ID
- `VideoStatusChangedHandlerTest` — delegates with correct arguments

**Video-service unit tests**:
- `VideoEventPublisherTest` — verify dual publishing
- `VideoServiceTest` — broadened condition fires for REJECTED transitions and videos without locations

**Integration**: Existing `test:all` suite covers end-to-end event flow.
