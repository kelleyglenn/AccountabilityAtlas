# video-service Event Publishing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add VideoSubmitted event publishing so moderation-service can handle new video submissions.

**Architecture:** Use Spring ApplicationEventPublisher for local dev (same pattern as moderation-service). SQS integration comes in Phase 2.

**Tech Stack:** Java 21, Spring Boot 3.4.x

**Related Issue:** Create issue in AcctAtlas-video-service before starting

---

## Current State

### Already Exists
- `VideoService.createVideo()` creates videos with PENDING status
- `Video` entity with all required fields (id, title, amendments, submittedBy, etc.)
- Internal APIs for moderation-service to update video status

### Missing
- No event publishing infrastructure
- No VideoSubmitted event when videos are created
- No way for moderation-service to know when videos are submitted

---

## Event Definition

From the map-browsing design doc, VideoSubmitted event:

```json
{
  "eventType": "VideoSubmitted",
  "videoId": "uuid",
  "submitterId": "uuid",
  "submitterTrustTier": "NEW|TRUSTED|MODERATOR|ADMIN",
  "title": "string",
  "amendments": [1, 4],
  "locationIds": ["uuid"],
  "timestamp": "ISO8601"
}
```

**Note:** `submitterTrustTier` requires knowing the user's trust tier. For now, we'll include what we have (submitterId) and let moderation-service look up the trust tier if needed. Or we can require the trust tier to be passed in when creating a video.

---

## Phase 1: Event Infrastructure

### Task 1: Create VideoSubmittedEvent record

**Files:**
- Create: `src/main/java/com/accountabilityatlas/videoservice/event/VideoSubmittedEvent.java`

**Step 1: Create the event record**

```java
package com.accountabilityatlas.videoservice.event;

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
    Instant timestamp
) {}
```

**Step 2: Commit**

```bash
git commit -m "feat: add VideoSubmittedEvent record"
```

---

### Task 2: Create VideoEventPublisher

**Files:**
- Create: `src/main/java/com/accountabilityatlas/videoservice/event/VideoEventPublisher.java`
- Create: `src/test/java/com/accountabilityatlas/videoservice/event/VideoEventPublisherTest.java`

**Step 1: Write the test**

```java
package com.accountabilityatlas.videoservice.event;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;

import com.accountabilityatlas.videoservice.domain.Amendment;
import com.accountabilityatlas.videoservice.domain.Video;
import java.util.Collections;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(MockitoExtension.class)
class VideoEventPublisherTest {

  @Mock private ApplicationEventPublisher applicationEventPublisher;
  private VideoEventPublisher videoEventPublisher;

  @BeforeEach
  void setUp() {
    videoEventPublisher = new VideoEventPublisher(applicationEventPublisher);
  }

  @Test
  void publishVideoSubmitted_validVideo_publishesEvent() {
    // Arrange
    Video video = new Video();
    video.setId(UUID.randomUUID());
    video.setTitle("Test Video");
    video.setSubmittedBy(UUID.randomUUID());
    video.setAmendments(Set.of(Amendment.FIRST, Amendment.FOURTH));
    String trustTier = "NEW";

    // Act
    videoEventPublisher.publishVideoSubmitted(video, trustTier, Collections.emptyList());

    // Assert
    ArgumentCaptor<VideoSubmittedEvent> captor = ArgumentCaptor.forClass(VideoSubmittedEvent.class);
    verify(applicationEventPublisher).publishEvent(captor.capture());

    VideoSubmittedEvent event = captor.getValue();
    assertThat(event.videoId()).isEqualTo(video.getId());
    assertThat(event.submitterId()).isEqualTo(video.getSubmittedBy());
    assertThat(event.submitterTrustTier()).isEqualTo("NEW");
    assertThat(event.title()).isEqualTo("Test Video");
    assertThat(event.amendments()).containsExactlyInAnyOrder("FIRST", "FOURTH");
  }
}
```

**Step 2: Implement the publisher**

```java
package com.accountabilityatlas.videoservice.event;

import com.accountabilityatlas.videoservice.domain.Amendment;
import com.accountabilityatlas.videoservice.domain.Video;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class VideoEventPublisher {

  private final ApplicationEventPublisher applicationEventPublisher;

  public void publishVideoSubmitted(Video video, String submitterTrustTier, List<UUID> locationIds) {
    VideoSubmittedEvent event = new VideoSubmittedEvent(
        video.getId(),
        video.getSubmittedBy(),
        submitterTrustTier,
        video.getTitle(),
        video.getAmendments().stream()
            .map(Amendment::name)
            .collect(Collectors.toSet()),
        locationIds,
        Instant.now()
    );

    log.info("Publishing VideoSubmitted event for video {}", video.getId());
    applicationEventPublisher.publishEvent(event);
    log.debug("Published VideoSubmitted event: {}", event);
  }
}
```

**Step 3: Run tests and commit**

```bash
./gradlew test --tests VideoEventPublisherTest
git commit -m "feat: add VideoEventPublisher"
```

---

## Phase 2: Integration with VideoService

### Task 3: Integrate event publishing into createVideo

**Files:**
- Modify: `src/main/java/com/accountabilityatlas/videoservice/service/VideoService.java`
- Modify: `src/test/java/com/accountabilityatlas/videoservice/service/VideoServiceTest.java`
- Modify: `src/main/java/com/accountabilityatlas/videoservice/web/VideosController.java`

**Challenge:** The `createVideo` method currently doesn't know the submitter's trust tier. We have two options:

**Option A:** Pass trust tier as a parameter to createVideo
**Option B:** Look up trust tier from user-service

For simplicity, we'll use **Option A** - the controller extracts trust tier from the JWT and passes it to the service.

**Step 1: Update VideoService to accept trust tier and publish event**

```java
// Add to constructor
private final VideoEventPublisher videoEventPublisher;

@Transactional
public Video createVideo(
    String youtubeUrl,
    Set<Amendment> amendments,
    Set<Participant> participants,
    LocalDate videoDate,
    UUID submittedBy,
    String submitterTrustTier,
    List<UUID> locationIds) {

  // ... existing video creation code ...

  Video saved = videoRepository.save(video);

  // Publish event after successful save
  videoEventPublisher.publishVideoSubmitted(saved, submitterTrustTier, locationIds);

  return saved;
}
```

**Step 2: Update VideoServiceTest**

Add mock for VideoEventPublisher and verify it's called on createVideo.

**Step 3: Update VideosController**

Extract trust tier from JWT and pass to service:

```java
@Override
public ResponseEntity<VideoResponse> createVideo(CreateVideoRequest request) {
  UUID userId = getCurrentUserId();
  String trustTier = getCurrentUserTrustTier();

  Video video = videoService.createVideo(
      request.getYoutubeUrl(),
      // ... other params ...
      userId,
      trustTier,
      request.getLocationIds() != null ? request.getLocationIds() : Collections.emptyList()
  );

  return ResponseEntity.status(HttpStatus.CREATED).body(toVideoResponse(video));
}

private String getCurrentUserTrustTier() {
  Jwt jwt = (Jwt) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
  // Extract trust tier from JWT claims - adjust based on actual JWT structure
  return jwt.getClaimAsString("trustTier");
}
```

**Step 4: Run all tests and commit**

```bash
./gradlew test
git commit -m "feat: publish VideoSubmitted event on video creation"
```

---

### Task 4: Handle trust tier from JWT

**Files:**
- Check JWT structure and ensure trust tier is included
- May need coordination with user-service to include trust tier in JWT claims

**Note:** If trust tier is not in JWT, we have two options:
1. Add trust tier to JWT claims (requires user-service change)
2. Default to "NEW" and let moderation-service look it up

For now, we can default to checking the claim and falling back to "NEW":

```java
private String getCurrentUserTrustTier() {
  try {
    Jwt jwt = (Jwt) SecurityContextHolder.getContext().getAuthentication().getPrincipal();
    String tier = jwt.getClaimAsString("trustTier");
    return tier != null ? tier : "NEW";
  } catch (Exception e) {
    log.warn("Could not extract trust tier from JWT, defaulting to NEW");
    return "NEW";
  }
}
```

---

## Summary

| Task | Description | Complexity |
|------|-------------|------------|
| 1 | Create VideoSubmittedEvent record | Low |
| 2 | Create VideoEventPublisher | Low |
| 3 | Integrate into createVideo | Medium |
| 4 | Handle trust tier from JWT | Low |

**Estimated effort:** 1-2 hours

---

## Testing Checklist

- [ ] VideoSubmittedEvent contains all required fields
- [ ] VideoEventPublisher publishes events correctly
- [ ] createVideo publishes VideoSubmittedEvent after save
- [ ] Trust tier is extracted from JWT or defaults to NEW
- [ ] All existing tests still pass

---

## Future Work (Phase 2 - SQS)

- Replace ApplicationEventPublisher with SQS client
- Add SQS queue configuration
- Add retry logic for failed publishes
- Add dead letter queue for unprocessable messages
