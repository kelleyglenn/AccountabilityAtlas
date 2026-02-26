# User Stats Event Handling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make user-service consume video events from SQS to keep `user_stats` counters (`submission_count`, `approved_count`, `rejected_count`) accurate.

**Architecture:** Video-service publishes to dedicated user-service SQS queues (dual-queue fan-out pattern). User-service adds `@SqsListener` handlers that delegate to a new `UserStatsService`. Video-service event is enriched with `submittedBy` and its publishing condition is broadened to fire on all status transitions.

**Tech Stack:** Java 21, Spring Boot 3.4.x, Spring Cloud AWS SQS 3.3.0, JUnit 5, Mockito, Gradle

**Design doc:** `docs/plans/2026-02-25-user-stats-events-design.md`

---

### Task 1: Infrastructure — Queues, Terraform, Docker Compose, Scripts

All changes in the **top-level** `AccountabilityAtlas` repo.

**Files:**
- Modify: `docker/localstack/init-queues.sh:28` (add after user-events-dlq line)
- Modify: `infra/messaging.tf:2-8` (add to sqs_queues list)
- Modify: `infra/docker/docker-compose.prod.yml:83-84` (user-service env), `:119-121` (video-service env)
- Modify: `scripts/clean-test-data.sh:52-61` (user stats reset), `:120-135` (location stats reset), `:190` (queue purge loop)

**Step 1: Add new queues to LocalStack init script**

In `docker/localstack/init-queues.sh`, add after the `user-events-dlq` line (after line 29):

```bash
# User video events queue (user-service consumer — submission counting)
awslocal sqs create-queue --queue-name user-video-events
awslocal sqs create-queue --queue-name user-video-events-dlq

# User video status events queue (user-service consumer — approved/rejected counting)
awslocal sqs create-queue --queue-name user-video-status-events
awslocal sqs create-queue --queue-name user-video-status-events-dlq
```

**Step 2: Add queues to Terraform**

In `infra/messaging.tf`, update the `sqs_queues` local:

```hcl
locals {
  sqs_queues = [
    "video-events",
    "video-status-events",
    "moderation-events",
    "search-moderation-events",
    "user-events",
    "user-video-events",
    "user-video-status-events",
  ]
}
```

**Step 3: Add env vars to production Docker Compose**

In `infra/docker/docker-compose.prod.yml`:

User-service section (after line 84, `APP_SQS_USER_EVENTS_QUEUE`). Also **remove** the existing `APP_SQS_VIDEO_EVENTS_QUEUE` on line 83 — it's unused and misleading. Replace with the correct queues:

```yaml
      APP_SQS_USER_EVENTS_QUEUE: ${SQS_PREFIX}-user-events
      APP_SQS_USER_VIDEO_EVENTS_QUEUE: ${SQS_PREFIX}-user-video-events
      APP_SQS_USER_VIDEO_STATUS_EVENTS_QUEUE: ${SQS_PREFIX}-user-video-status-events
```

Video-service section (after line 121, `APP_SQS_VIDEO_STATUS_EVENTS_QUEUE`):

```yaml
      APP_SQS_USER_VIDEO_EVENTS_QUEUE: ${SQS_PREFIX}-user-video-events
      APP_SQS_USER_VIDEO_STATUS_EVENTS_QUEUE: ${SQS_PREFIX}-user-video-status-events
```

**Step 4: Update clean-test-data.sh — reset seed stats and purge new queues**

After the user_stats DELETE block (after line 61), add:

```bash
# Reset seed user stats to match seed video data
# (non-seed videos may have inflated counters before being deleted above)
run_sql user_service user_service "
  UPDATE users.user_stats SET
      submission_count = 0, approved_count = 0, rejected_count = 0, updated_at = NOW();
  UPDATE users.user_stats SET
      submission_count = 10, approved_count = 10, rejected_count = 0
  WHERE user_id = '00000000-0000-0000-0000-000000000003';
"
```

After the location_stats DELETE block (after line 135), add:

```bash
# Reset seed location stats to match seed video data
# (non-seed videos at seed locations may have inflated video_count)
run_sql location_service location_service "
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
"
```

Update the SQS queue purge loop (line 190) to include the 4 new queues:

```bash
for queue in video-events video-events-dlq moderation-events moderation-events-dlq search-moderation-events search-moderation-events-dlq user-events user-events-dlq video-status-events video-status-events-dlq user-video-events user-video-events-dlq user-video-status-events user-video-status-events-dlq; do
```

**Step 5: Commit**

```bash
git add docker/localstack/init-queues.sh infra/messaging.tf infra/docker/docker-compose.prod.yml scripts/clean-test-data.sh
git commit -m "feat(infra): add user-video SQS queues and fix seed stats reset (#47)"
```

---

### Task 2: Video-Service — Event Schema, Publisher, and Publishing Condition

All changes in `AcctAtlas-video-service`. Create feature branch from master.

**Reference docs:**
- Design: `docs/plans/2026-02-25-user-stats-events-design.md` (Video-Service section)
- Existing handler pattern: `AcctAtlas-location-service/.../event/VideoStatusChangedHandler.java`

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/videoservice/event/VideoStatusChangedEvent.java`
- Modify: `src/main/java/com/accountabilityatlas/videoservice/event/VideoEventPublisher.java`
- Modify: `src/main/java/com/accountabilityatlas/videoservice/service/VideoService.java:175-197`
- Modify: `src/main/resources/application.yml:56-60`
- Modify: `src/test/java/com/accountabilityatlas/videoservice/event/VideoEventPublisherTest.java`
- Modify: `src/test/java/com/accountabilityatlas/videoservice/service/VideoServiceTest.java`

**Step 1: Add `submittedBy` to VideoStatusChangedEvent**

Replace the entire file `src/main/java/.../event/VideoStatusChangedEvent.java`:

```java
package com.accountabilityatlas.videoservice.event;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record VideoStatusChangedEvent(
    UUID videoId,
    UUID submittedBy,
    List<UUID> locationIds,
    String previousStatus,
    String newStatus,
    Instant timestamp) {}
```

**Step 2: Update VideoEventPublisherTest — add dual-queue assertions**

In `src/test/java/.../event/VideoEventPublisherTest.java`:

Add new queue constants at the top (after line 29):

```java
private static final String USER_VIDEO_EVENTS_QUEUE = "user-video-events";
private static final String USER_VIDEO_STATUS_EVENTS_QUEUE = "user-video-status-events";
```

In **every** test method, add `ReflectionTestUtils.setField` calls for the new queue fields. For example, in `publishVideoSubmitted_validVideo_sendsToSqs`, after the existing `setField` call:

```java
ReflectionTestUtils.setField(videoEventPublisher, "userVideoEventsQueue", USER_VIDEO_EVENTS_QUEUE);
```

Update all `publishVideoSubmitted` tests to verify dual publishing:

```java
verify(sqsTemplate).send(eq(VIDEO_EVENTS_QUEUE), any(VideoSubmittedEvent.class));
verify(sqsTemplate).send(eq(USER_VIDEO_EVENTS_QUEUE), any(VideoSubmittedEvent.class));
```

Update all `publishVideoStatusChanged` tests:
- Add `UUID submittedBy = UUID.randomUUID();` to Arrange sections
- Pass `submittedBy` as the second argument to `publishVideoStatusChanged`
- Assert `event.submittedBy()` in captors
- Verify sends to both queues:

```java
verify(sqsTemplate).send(eq(VIDEO_STATUS_EVENTS_QUEUE), captor.capture());
verify(sqsTemplate).send(eq(USER_VIDEO_STATUS_EVENTS_QUEUE), any(VideoStatusChangedEvent.class));
```

For the SQS failure tests, update to verify that the failure prevents the second send:

```java
// Only one send should have been attempted (it failed)
verify(sqsTemplate, times(1)).send(any(String.class), any(VideoSubmittedEvent.class));
```

**Step 3: Run tests to verify they fail**

Run: `./gradlew unitTest`
Expected: Tests fail because publisher doesn't have new fields or dual-queue logic yet.

**Step 4: Update VideoEventPublisher for dual-queue publishing**

In `src/main/java/.../event/VideoEventPublisher.java`:

Add two new queue properties (after line 27):

```java
@Value("${app.sqs.user-video-events-queue:user-video-events}")
private String userVideoEventsQueue;

@Value("${app.sqs.user-video-status-events-queue:user-video-status-events}")
private String userVideoStatusEventsQueue;
```

Update `publishVideoSubmitted` to send to both queues. After the existing `sqsTemplate.send(videoEventsQueue, event);` line, add:

```java
sqsTemplate.send(userVideoEventsQueue, event);
```

Update `publishVideoStatusChanged` signature to accept `submittedBy`:

```java
public void publishVideoStatusChanged(
    UUID videoId, UUID submittedBy, List<UUID> locationIds, String previousStatus, String newStatus) {
  VideoStatusChangedEvent event =
      new VideoStatusChangedEvent(videoId, submittedBy, locationIds, previousStatus, newStatus, Instant.now());
```

And add the second send after the existing one:

```java
sqsTemplate.send(userVideoStatusEventsQueue, event);
```

**Step 5: Update application.yml**

In `src/main/resources/application.yml`, add under the existing `app.sqs` section:

```yaml
app:
  sqs:
    video-events-queue: video-events
    moderation-events-queue: moderation-events
    video-status-events-queue: video-status-events
    user-video-events-queue: user-video-events
    user-video-status-events-queue: user-video-status-events
```

**Step 6: Update VideoServiceTest — broaden condition expectations**

In `src/test/java/.../service/VideoServiceTest.java`:

Update `updateVideoStatus_validRequest_updatesStatus` (line 389): This test has no locations and goes PENDING→APPROVED. With the broadened condition, it WILL now publish an event. Change assertion from `never()` to `verify`:

```java
verify(videoEventPublisher)
    .publishVideoStatusChanged(videoId, video.getSubmittedBy(), Collections.emptyList(), "PENDING", "APPROVED");
```

You'll need to set `video.setSubmittedBy(userId)` in the Arrange section.

Update `updateVideoStatus_nonApprovedTransition_doesNotPublishEvent` (line 408): This test goes PENDING→REJECTED. With the broadened condition, it WILL now publish. Change from `never()` to:

```java
verify(videoEventPublisher)
    .publishVideoStatusChanged(videoId, video.getSubmittedBy(), List.of(locationId), "PENDING", "REJECTED");
```

You'll need to set `video.setSubmittedBy(userId)` in the Arrange section.

Update `updateVideoStatus_toApproved_publishesStatusChangedEvent` (line 430): Add `submittedBy` to the verify:

```java
verify(videoEventPublisher)
    .publishVideoStatusChanged(videoId, video.getSubmittedBy(), List.of(locationId), "PENDING", "APPROVED");
```

You'll need to set `video.setSubmittedBy(userId)` in the Arrange section.

Update `updateVideoStatus_fromApprovedToRejected_publishesStatusChangedEvent` (line 453): Same pattern.

**Step 7: Run tests to verify they fail**

Run: `./gradlew unitTest`
Expected: Tests fail because VideoService still has old condition and method signature.

**Step 8: Update VideoService — broaden condition, pass submittedBy**

In `src/main/java/.../service/VideoService.java`, replace lines 186-194:

```java
    // Publish status change event for downstream services
    List<UUID> locationIds =
        saved.getLocations().stream().map(VideoLocation::getLocationId).toList();
    if (previousStatus != newStatus) {
      videoEventPublisher.publishVideoStatusChanged(
          saved.getId(), saved.getSubmittedBy(), locationIds, previousStatus.name(), newStatus.name());
    }
```

**Step 9: Run tests and verify they pass**

Run: `./gradlew unitTest`
Expected: All tests PASS.

**Step 10: Run full check**

Run: `./gradlew check`
Expected: PASS (spotless, error-prone, tests, coverage).

**Step 11: Commit**

```bash
git add -A
git commit -m "feat(event): add submittedBy to VideoStatusChanged and dual-queue publishing

Closes #XX

- Add submittedBy UUID to VideoStatusChangedEvent
- Publish VideoSubmitted to both video-events and user-video-events
- Publish VideoStatusChanged to both video-status-events and user-video-status-events
- Broaden publishing condition: fire on any status change (not just APPROVED)
- Update all related tests"
```

---

### Task 3: User-Service — Event DTOs and UserStatsService (TDD)

All changes in `AcctAtlas-user-service`. Create feature branch from master.

**Reference docs:**
- Design: `docs/plans/2026-02-25-user-stats-events-design.md` (User-Service section)
- Pattern to follow: `AcctAtlas-location-service/.../service/LocationStatsService.java`
- Existing entity: `src/main/java/.../domain/UserStats.java`
- Existing repo: `src/main/java/.../repository/UserStatsRepository.java`

**Files:**
- Create: `src/main/java/com/accountabilityatlas/userservice/event/VideoSubmittedEvent.java`
- Create: `src/main/java/com/accountabilityatlas/userservice/event/VideoStatusChangedEvent.java`
- Create: `src/main/java/com/accountabilityatlas/userservice/service/UserStatsService.java`
- Create: `src/test/java/com/accountabilityatlas/userservice/service/UserStatsServiceTest.java`

**Step 1: Create VideoSubmittedEvent record**

Create `src/main/java/com/accountabilityatlas/userservice/event/VideoSubmittedEvent.java`:

```java
package com.accountabilityatlas.userservice.event;

import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.UUID;

public record VideoSubmittedEvent(
    UUID videoId,
    UUID submitterId,
    String submitterTrustTier,
    String title,
    Set<String> amendments,
    List<UUID> locationIds,
    Instant timestamp) {}
```

**Step 2: Create VideoStatusChangedEvent record**

Create `src/main/java/com/accountabilityatlas/userservice/event/VideoStatusChangedEvent.java`:

```java
package com.accountabilityatlas.userservice.event;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record VideoStatusChangedEvent(
    UUID videoId,
    UUID submittedBy,
    List<UUID> locationIds,
    String previousStatus,
    String newStatus,
    Instant timestamp) {}
```

**Step 3: Write UserStatsServiceTest**

Create `src/test/java/com/accountabilityatlas/userservice/service/UserStatsServiceTest.java`:

```java
package com.accountabilityatlas.userservice.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.accountabilityatlas.userservice.domain.UserStats;
import com.accountabilityatlas.userservice.repository.UserStatsRepository;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class UserStatsServiceTest {

  @Mock private UserStatsRepository userStatsRepository;
  @InjectMocks private UserStatsService userStatsService;

  private UserStats createStats(UUID userId, int submissions, int approved, int rejected) {
    UserStats stats = new UserStats();
    stats.setUserId(userId);
    stats.setSubmissionCount(submissions);
    stats.setApprovedCount(approved);
    stats.setRejectedCount(rejected);
    stats.setUpdatedAt(Instant.now());
    return stats;
  }

  @Test
  void incrementSubmissionCount_userExists_incrementsByOne() {
    UUID userId = UUID.randomUUID();
    UserStats stats = createStats(userId, 5, 3, 1);
    when(userStatsRepository.findById(userId)).thenReturn(Optional.of(stats));

    userStatsService.incrementSubmissionCount(userId);

    ArgumentCaptor<UserStats> captor = ArgumentCaptor.forClass(UserStats.class);
    verify(userStatsRepository).save(captor.capture());
    assertThat(captor.getValue().getSubmissionCount()).isEqualTo(6);
  }

  @Test
  void incrementSubmissionCount_userNotFound_doesNothing() {
    UUID userId = UUID.randomUUID();
    when(userStatsRepository.findById(userId)).thenReturn(Optional.empty());

    userStatsService.incrementSubmissionCount(userId);

    verify(userStatsRepository).findById(userId);
  }

  @Test
  void handleStatusChange_toApproved_incrementsApprovedCount() {
    UUID userId = UUID.randomUUID();
    UserStats stats = createStats(userId, 5, 3, 1);
    when(userStatsRepository.findById(userId)).thenReturn(Optional.of(stats));

    userStatsService.handleStatusChange(userId, "PENDING", "APPROVED");

    ArgumentCaptor<UserStats> captor = ArgumentCaptor.forClass(UserStats.class);
    verify(userStatsRepository).save(captor.capture());
    assertThat(captor.getValue().getApprovedCount()).isEqualTo(4);
    assertThat(captor.getValue().getRejectedCount()).isEqualTo(1);
  }

  @Test
  void handleStatusChange_fromApproved_decrementsApprovedCount() {
    UUID userId = UUID.randomUUID();
    UserStats stats = createStats(userId, 5, 3, 1);
    when(userStatsRepository.findById(userId)).thenReturn(Optional.of(stats));

    userStatsService.handleStatusChange(userId, "APPROVED", "REJECTED");

    ArgumentCaptor<UserStats> captor = ArgumentCaptor.forClass(UserStats.class);
    verify(userStatsRepository).save(captor.capture());
    assertThat(captor.getValue().getApprovedCount()).isEqualTo(2);
    assertThat(captor.getValue().getRejectedCount()).isEqualTo(2);
  }

  @Test
  void handleStatusChange_toRejected_incrementsRejectedCount() {
    UUID userId = UUID.randomUUID();
    UserStats stats = createStats(userId, 5, 3, 0);
    when(userStatsRepository.findById(userId)).thenReturn(Optional.of(stats));

    userStatsService.handleStatusChange(userId, "PENDING", "REJECTED");

    ArgumentCaptor<UserStats> captor = ArgumentCaptor.forClass(UserStats.class);
    verify(userStatsRepository).save(captor.capture());
    assertThat(captor.getValue().getApprovedCount()).isEqualTo(3);
    assertThat(captor.getValue().getRejectedCount()).isEqualTo(1);
  }

  @Test
  void handleStatusChange_fromRejected_decrementsRejectedCount() {
    UUID userId = UUID.randomUUID();
    UserStats stats = createStats(userId, 5, 3, 2);
    when(userStatsRepository.findById(userId)).thenReturn(Optional.of(stats));

    userStatsService.handleStatusChange(userId, "REJECTED", "APPROVED");

    ArgumentCaptor<UserStats> captor = ArgumentCaptor.forClass(UserStats.class);
    verify(userStatsRepository).save(captor.capture());
    assertThat(captor.getValue().getApprovedCount()).isEqualTo(4);
    assertThat(captor.getValue().getRejectedCount()).isEqualTo(1);
  }

  @Test
  void handleStatusChange_approvedCountFloorAtZero() {
    UUID userId = UUID.randomUUID();
    UserStats stats = createStats(userId, 1, 0, 0);
    when(userStatsRepository.findById(userId)).thenReturn(Optional.of(stats));

    userStatsService.handleStatusChange(userId, "APPROVED", "REJECTED");

    ArgumentCaptor<UserStats> captor = ArgumentCaptor.forClass(UserStats.class);
    verify(userStatsRepository).save(captor.capture());
    assertThat(captor.getValue().getApprovedCount()).isEqualTo(0);
    assertThat(captor.getValue().getRejectedCount()).isEqualTo(1);
  }

  @Test
  void handleStatusChange_rejectedCountFloorAtZero() {
    UUID userId = UUID.randomUUID();
    UserStats stats = createStats(userId, 1, 0, 0);
    when(userStatsRepository.findById(userId)).thenReturn(Optional.of(stats));

    userStatsService.handleStatusChange(userId, "REJECTED", "PENDING");

    ArgumentCaptor<UserStats> captor = ArgumentCaptor.forClass(UserStats.class);
    verify(userStatsRepository).save(captor.capture());
    assertThat(captor.getValue().getRejectedCount()).isEqualTo(0);
  }

  @Test
  void handleStatusChange_userNotFound_doesNothing() {
    UUID userId = UUID.randomUUID();
    when(userStatsRepository.findById(userId)).thenReturn(Optional.empty());

    userStatsService.handleStatusChange(userId, "PENDING", "APPROVED");

    verify(userStatsRepository).findById(userId);
  }
}
```

**Step 4: Run tests to verify they fail**

Run: `./gradlew unitTest --tests "*UserStatsServiceTest*"`
Expected: Compilation fails — `UserStatsService` does not exist yet.

**Step 5: Implement UserStatsService**

Create `src/main/java/com/accountabilityatlas/userservice/service/UserStatsService.java`:

```java
package com.accountabilityatlas.userservice.service;

import com.accountabilityatlas.userservice.repository.UserStatsRepository;
import java.time.Instant;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Slf4j
public class UserStatsService {

  private final UserStatsRepository userStatsRepository;

  @Transactional
  public void incrementSubmissionCount(UUID userId) {
    userStatsRepository
        .findById(userId)
        .ifPresentOrElse(
            stats -> {
              stats.setSubmissionCount(stats.getSubmissionCount() + 1);
              stats.setUpdatedAt(Instant.now());
              userStatsRepository.save(stats);
              log.debug("Incremented submission count for user {}", userId);
            },
            () -> log.warn("UserStats not found for user {}, skipping submission count", userId));
  }

  @Transactional
  public void handleStatusChange(UUID userId, String previousStatus, String newStatus) {
    userStatsRepository
        .findById(userId)
        .ifPresentOrElse(
            stats -> {
              if ("APPROVED".equals(newStatus)) {
                stats.setApprovedCount(stats.getApprovedCount() + 1);
              } else if ("APPROVED".equals(previousStatus)) {
                stats.setApprovedCount(Math.max(0, stats.getApprovedCount() - 1));
              }

              if ("REJECTED".equals(newStatus)) {
                stats.setRejectedCount(stats.getRejectedCount() + 1);
              } else if ("REJECTED".equals(previousStatus)) {
                stats.setRejectedCount(Math.max(0, stats.getRejectedCount() - 1));
              }

              stats.setUpdatedAt(Instant.now());
              userStatsRepository.save(stats);
              log.debug(
                  "Updated stats for user {} ({} -> {}): approved={}, rejected={}",
                  userId,
                  previousStatus,
                  newStatus,
                  stats.getApprovedCount(),
                  stats.getRejectedCount());
            },
            () -> log.warn("UserStats not found for user {}, skipping status change", userId));
  }
}
```

**Step 6: Run tests and verify they pass**

Run: `./gradlew unitTest --tests "*UserStatsServiceTest*"`
Expected: All 9 tests PASS.

**Step 7: Commit**

```bash
git add -A
git commit -m "feat(stats): add UserStatsService and event DTOs for video events

- Add VideoSubmittedEvent and VideoStatusChangedEvent records
- Implement UserStatsService with incrementSubmissionCount and handleStatusChange
- Full test coverage for all counter transitions and edge cases"
```

---

### Task 4: User-Service — SQS Handlers, Config, and Seed Data

Continues on the same feature branch in `AcctAtlas-user-service`.

**Reference docs:**
- Handler pattern: `AcctAtlas-location-service/.../event/VideoStatusChangedHandler.java`
- Test pattern: `AcctAtlas-user-service/.../event/SqsEventPublisherTest.java`

**Files:**
- Create: `src/main/java/com/accountabilityatlas/userservice/event/VideoSubmittedHandler.java`
- Create: `src/main/java/com/accountabilityatlas/userservice/event/VideoStatusChangedHandler.java`
- Create: `src/test/java/com/accountabilityatlas/userservice/event/VideoSubmittedHandlerTest.java`
- Create: `src/test/java/com/accountabilityatlas/userservice/event/VideoStatusChangedHandlerTest.java`
- Modify: `src/main/resources/application.yml:47-49`
- Modify: `src/main/resources/db/devdata/R__dev_seed_users.sql:23-25`

**Step 1: Write VideoSubmittedHandlerTest**

Create `src/test/java/com/accountabilityatlas/userservice/event/VideoSubmittedHandlerTest.java`:

```java
package com.accountabilityatlas.userservice.event;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;

import com.accountabilityatlas.userservice.service.UserStatsService;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class VideoSubmittedHandlerTest {

  @Mock private UserStatsService userStatsService;
  @InjectMocks private VideoSubmittedHandler videoSubmittedHandler;

  @Test
  void handleVideoSubmitted_delegatesToUserStatsService() {
    UUID submitterId = UUID.randomUUID();
    VideoSubmittedEvent event =
        new VideoSubmittedEvent(
            UUID.randomUUID(),
            submitterId,
            "NEW",
            "Test Video",
            Set.of("FIRST"),
            List.of(UUID.randomUUID()),
            Instant.now());

    videoSubmittedHandler.handleVideoSubmitted(event);

    verify(userStatsService).incrementSubmissionCount(submitterId);
  }

  @Test
  void handleVideoSubmitted_serviceFailure_rethrowsException() {
    UUID submitterId = UUID.randomUUID();
    VideoSubmittedEvent event =
        new VideoSubmittedEvent(
            UUID.randomUUID(),
            submitterId,
            "TRUSTED",
            "Test",
            Set.of(),
            List.of(),
            Instant.now());

    RuntimeException exception = new RuntimeException("DB error");
    doThrow(exception).when(userStatsService).incrementSubmissionCount(submitterId);

    assertThatThrownBy(() -> videoSubmittedHandler.handleVideoSubmitted(event))
        .isSameAs(exception);
  }
}
```

**Step 2: Write VideoStatusChangedHandlerTest**

Create `src/test/java/com/accountabilityatlas/userservice/event/VideoStatusChangedHandlerTest.java`:

```java
package com.accountabilityatlas.userservice.event;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;

import com.accountabilityatlas.userservice.service.UserStatsService;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class VideoStatusChangedHandlerTest {

  @Mock private UserStatsService userStatsService;
  @InjectMocks private VideoStatusChangedHandler videoStatusChangedHandler;

  @Test
  void handleVideoStatusChanged_delegatesToUserStatsService() {
    UUID submittedBy = UUID.randomUUID();
    VideoStatusChangedEvent event =
        new VideoStatusChangedEvent(
            UUID.randomUUID(),
            submittedBy,
            List.of(UUID.randomUUID()),
            "PENDING",
            "APPROVED",
            Instant.now());

    videoStatusChangedHandler.handleVideoStatusChanged(event);

    verify(userStatsService).handleStatusChange(submittedBy, "PENDING", "APPROVED");
  }

  @Test
  void handleVideoStatusChanged_serviceFailure_rethrowsException() {
    UUID submittedBy = UUID.randomUUID();
    VideoStatusChangedEvent event =
        new VideoStatusChangedEvent(
            UUID.randomUUID(), submittedBy, List.of(), "APPROVED", "REJECTED", Instant.now());

    RuntimeException exception = new RuntimeException("DB error");
    doThrow(exception)
        .when(userStatsService)
        .handleStatusChange(submittedBy, "APPROVED", "REJECTED");

    assertThatThrownBy(() -> videoStatusChangedHandler.handleVideoStatusChanged(event))
        .isSameAs(exception);
  }
}
```

**Step 3: Run tests to verify they fail**

Run: `./gradlew unitTest --tests "*VideoSubmittedHandlerTest*" --tests "*VideoStatusChangedHandlerTest*"`
Expected: Compilation fails — handler classes don't exist yet.

**Step 4: Implement VideoSubmittedHandler**

Create `src/main/java/com/accountabilityatlas/userservice/event/VideoSubmittedHandler.java`:

```java
package com.accountabilityatlas.userservice.event;

import com.accountabilityatlas.userservice.service.UserStatsService;
import io.awspring.cloud.sqs.annotation.SqsListener;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class VideoSubmittedHandler {

  private final UserStatsService userStatsService;

  @SqsListener("${app.sqs.user-video-events-queue:user-video-events}")
  public void handleVideoSubmitted(VideoSubmittedEvent event) {
    log.info(
        "Received VideoSubmitted event for video {} from submitter {}",
        event.videoId(),
        event.submitterId());
    try {
      userStatsService.incrementSubmissionCount(event.submitterId());
    } catch (Exception e) {
      log.error(
          "Failed to handle VideoSubmitted event for video {}: {}",
          event.videoId(),
          e.getMessage(),
          e);
      throw e;
    }
  }
}
```

**Step 5: Implement VideoStatusChangedHandler**

Create `src/main/java/com/accountabilityatlas/userservice/event/VideoStatusChangedHandler.java`:

```java
package com.accountabilityatlas.userservice.event;

import com.accountabilityatlas.userservice.service.UserStatsService;
import io.awspring.cloud.sqs.annotation.SqsListener;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class VideoStatusChangedHandler {

  private final UserStatsService userStatsService;

  @SqsListener("${app.sqs.user-video-status-events-queue:user-video-status-events}")
  public void handleVideoStatusChanged(VideoStatusChangedEvent event) {
    log.info(
        "Received VideoStatusChanged event for video {} ({} -> {})",
        event.videoId(),
        event.previousStatus(),
        event.newStatus());
    try {
      userStatsService.handleStatusChange(
          event.submittedBy(), event.previousStatus(), event.newStatus());
    } catch (Exception e) {
      log.error(
          "Failed to handle VideoStatusChanged event for video {}: {}",
          event.videoId(),
          e.getMessage(),
          e);
      throw e;
    }
  }
}
```

**Step 6: Add queue config to application.yml**

In `src/main/resources/application.yml`, update the `app.sqs` section:

```yaml
app:
  sqs:
    user-events-queue: user-events
    user-video-events-queue: user-video-events
    user-video-status-events-queue: user-video-status-events
```

**Step 7: Fix seed data**

In `src/main/resources/db/devdata/R__dev_seed_users.sql`, change line 25 from:

```sql
    ('00000000-0000-0000-0000-000000000003', 10, 8, 2),
```

to:

```sql
    ('00000000-0000-0000-0000-000000000003', 10, 10, 0),
```

**Step 8: Run all tests**

Run: `./gradlew unitTest`
Expected: All tests PASS (including new handler tests and existing tests).

**Step 9: Run full check**

Run: `./gradlew check`
Expected: PASS (spotless, error-prone, tests, coverage).

Note: If spotless fails, run `./gradlew spotlessApply` first, then re-run `./gradlew check`.

**Step 10: Commit**

```bash
git add -A
git commit -m "feat(stats): add SQS handlers for video events to update user stats

Closes #47

- Add VideoSubmittedHandler listening on user-video-events queue
- Add VideoStatusChangedHandler listening on user-video-status-events queue
- Both delegate to UserStatsService for counter updates
- Fix seed data: Trusted User stats now match seed videos (10, 10, 0)
- Full test coverage for all handlers"
```

---

### Verification Checklist

After all tasks are complete:

1. **Deploy affected services:**
   ```bash
   ./scripts/deploy.sh user-service video-service
   ```

2. **Run full integration test suite:**
   ```bash
   cd AcctAtlas-integration-tests
   npm run test:all
   ```

3. **Manual smoke test:** Submit a video as a test user, verify the user profile shows updated stats.

4. **Create PRs** (in order):
   - Top-level repo PR (infra changes)
   - Video-service PR
   - User-service PR
   - Integration-tests PR (only after service PRs are merged, if needed)

5. **Check CI status** on all PRs before considering them ready.
