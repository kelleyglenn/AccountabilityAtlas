# Spring Cloud Stream SQS Integration

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Retrofit video-service and moderation-service to use Spring Cloud Stream with SQS for async messaging, enabling true inter-service event-driven communication.

**Architecture:** Spring Cloud Stream provides broker-agnostic messaging. Services publish/consume via bindings configured in YAML. The SQS binder connects to LocalStack locally and AWS SQS in production.

**Tech Stack:** Java 21, Spring Boot 3.4.x, Spring Cloud Stream 4.x, Spring Cloud AWS 3.x

**Prerequisites:** LocalStack SQS infrastructure (PR #23)

---

## Overview

### Current State (Broken)

```
video-service                      moderation-service
      │                                   │
      │ ApplicationEventPublisher         │ @EventListener
      │ (publishes locally)               │ (listens locally)
      │                                   │
      └───────── X ────────────────────────┘
            (events don't cross process boundaries)
```

### Target State (Working)

```
video-service                      moderation-service                 search-service
      │                                   │                                │
      │ StreamBridge                      │ Consumer<VideoSubmittedEvent>  │
      ├──────────────────────────────────►│                                │
      │    video-events queue             │                                │
      │                                   │ StreamBridge                   │ Consumer<VideoApprovedEvent>
      │                                   ├───────────────────────────────►│
      │                                   │    moderation-events queue     │
```

---

## Dependencies (All Services)

Add to `build.gradle`:

```gradle
// Spring Cloud BOM
implementation platform('org.springframework.cloud:spring-cloud-dependencies:2024.0.0')

// Spring Cloud Stream
implementation 'org.springframework.cloud:spring-cloud-stream'

// Spring Cloud AWS SQS Binder
implementation 'io.awspring.cloud:spring-cloud-aws-starter-sqs:3.3.0'
implementation 'io.awspring.cloud:spring-cloud-aws-sqs:3.3.0'

// For StreamBridge (if publishing)
implementation 'org.springframework.cloud:spring-cloud-stream'
```

---

## Configuration Pattern

### application.yml (base)

```yaml
spring:
  cloud:
    aws:
      region:
        static: ${AWS_REGION:us-east-1}
      credentials:
        access-key: ${AWS_ACCESS_KEY_ID:test}
        secret-key: ${AWS_SECRET_ACCESS_KEY:test}
    stream:
      bindings:
        # Defined per-service
```

### application-local.yml (LocalStack)

```yaml
spring:
  cloud:
    aws:
      sqs:
        endpoint: http://localhost:4566
      credentials:
        access-key: test
        secret-key: test
```

### application-docker.yml (LocalStack in Docker)

```yaml
spring:
  cloud:
    aws:
      sqs:
        endpoint: http://localstack:4566
```

---

## Phase 1: video-service Refactor

### Task 1: Add Spring Cloud Stream dependencies to video-service

**Files:**
- Modify: `AcctAtlas-video-service/build.gradle`

**Step 1: Add dependencies**

Add to the dependencies block:

```gradle
// Spring Cloud BOM
implementation platform('org.springframework.cloud:spring-cloud-dependencies:2024.0.0')

// Spring Cloud Stream + AWS SQS
implementation 'org.springframework.cloud:spring-cloud-stream'
implementation 'io.awspring.cloud:spring-cloud-aws-starter-sqs:3.3.0'
```

**Step 2: Verify build compiles**

Run:
```bash
cd AcctAtlas-video-service && ./gradlew compileJava
```

Expected: BUILD SUCCESSFUL

**Step 3: Commit**

```bash
git add build.gradle
git commit -m "build: add Spring Cloud Stream and SQS dependencies"
```

---

### Task 2: Add Spring Cloud Stream configuration to video-service

**Files:**
- Modify: `AcctAtlas-video-service/src/main/resources/application.yml`
- Create: `AcctAtlas-video-service/src/main/resources/application-local.yml` (if not exists)

**Step 1: Add base configuration**

Add to application.yml:

```yaml
spring:
  cloud:
    aws:
      region:
        static: ${AWS_REGION:us-east-1}
      credentials:
        access-key: ${AWS_ACCESS_KEY_ID:test}
        secret-key: ${AWS_SECRET_ACCESS_KEY:test}
    stream:
      bindings:
        videoSubmitted-out-0:
          destination: video-events
    function:
      definition: ""  # No consumers in video-service
```

**Step 2: Add LocalStack configuration**

Create or update application-local.yml:

```yaml
spring:
  cloud:
    aws:
      sqs:
        endpoint: http://localhost:4566
```

**Step 3: Add Docker configuration**

Create or update application-docker.yml:

```yaml
spring:
  cloud:
    aws:
      sqs:
        endpoint: http://localstack:4566
```

**Step 4: Commit**

```bash
git add src/main/resources/
git commit -m "feat: add Spring Cloud Stream SQS configuration"
```

---

### Task 3: Refactor VideoEventPublisher to use StreamBridge

**Files:**
- Modify: `AcctAtlas-video-service/src/main/java/.../event/VideoEventPublisher.java`
- Modify: `AcctAtlas-video-service/src/test/java/.../event/VideoEventPublisherTest.java`

**Step 1: Update the test**

```java
package com.accountabilityatlas.videoservice.event;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

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
import org.springframework.cloud.stream.function.StreamBridge;

@ExtendWith(MockitoExtension.class)
class VideoEventPublisherTest {

  @Mock private StreamBridge streamBridge;
  private VideoEventPublisher videoEventPublisher;

  @BeforeEach
  void setUp() {
    videoEventPublisher = new VideoEventPublisher(streamBridge);
  }

  @Test
  void publishVideoSubmitted_validVideo_sendsToStreamBridge() {
    // Arrange
    Video video = new Video();
    video.setId(UUID.randomUUID());
    video.setTitle("Test Video");
    video.setSubmittedBy(UUID.randomUUID());
    video.setAmendments(Set.of(Amendment.FIRST, Amendment.FOURTH));
    String trustTier = "NEW";
    when(streamBridge.send(eq("videoSubmitted-out-0"), any())).thenReturn(true);

    // Act
    videoEventPublisher.publishVideoSubmitted(video, trustTier, Collections.emptyList());

    // Assert
    ArgumentCaptor<VideoSubmittedEvent> captor = ArgumentCaptor.forClass(VideoSubmittedEvent.class);
    verify(streamBridge).send(eq("videoSubmitted-out-0"), captor.capture());

    VideoSubmittedEvent event = captor.getValue();
    assertThat(event.videoId()).isEqualTo(video.getId());
    assertThat(event.submitterId()).isEqualTo(video.getSubmittedBy());
    assertThat(event.submitterTrustTier()).isEqualTo("NEW");
    assertThat(event.title()).isEqualTo("Test Video");
    assertThat(event.amendments()).containsExactlyInAnyOrder("FIRST", "FOURTH");
  }
}
```

**Step 2: Update the implementation**

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
import org.springframework.cloud.stream.function.StreamBridge;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class VideoEventPublisher {

  private static final String VIDEO_SUBMITTED_BINDING = "videoSubmitted-out-0";

  private final StreamBridge streamBridge;

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

    log.info("Publishing VideoSubmitted event for video {} to SQS", video.getId());
    boolean sent = streamBridge.send(VIDEO_SUBMITTED_BINDING, event);
    if (sent) {
      log.debug("Published VideoSubmitted event: {}", event);
    } else {
      log.error("Failed to publish VideoSubmitted event for video {}", video.getId());
    }
  }
}
```

**Step 3: Run tests**

```bash
./gradlew test --tests VideoEventPublisherTest
```

Expected: Tests pass

**Step 4: Commit**

```bash
git add src/
git commit -m "refactor: use StreamBridge instead of ApplicationEventPublisher"
```

---

### Task 4: Update VideoEventPublisher tests in VideoServiceTest

**Files:**
- Modify: `AcctAtlas-video-service/src/test/java/.../service/VideoServiceTest.java`

**Step 1: Update mock**

Change `@Mock ApplicationEventPublisher` to use the VideoEventPublisher mock (already there, but verify it works with StreamBridge-based implementation).

**Step 2: Run all tests**

```bash
./gradlew test
```

Expected: All tests pass

**Step 3: Commit if changes needed**

```bash
git commit -am "test: update tests for StreamBridge-based event publishing"
```

---

## Phase 2: moderation-service Refactor

### Task 5: Add Spring Cloud Stream dependencies to moderation-service

**Files:**
- Modify: `AcctAtlas-moderation-service/build.gradle`

**Step 1: Add dependencies**

```gradle
// Spring Cloud BOM
implementation platform('org.springframework.cloud:spring-cloud-dependencies:2024.0.0')

// Spring Cloud Stream + AWS SQS
implementation 'org.springframework.cloud:spring-cloud-stream'
implementation 'io.awspring.cloud:spring-cloud-aws-starter-sqs:3.3.0'
```

**Step 2: Verify build**

```bash
cd AcctAtlas-moderation-service && ./gradlew compileJava
```

**Step 3: Commit**

```bash
git add build.gradle
git commit -m "build: add Spring Cloud Stream and SQS dependencies"
```

---

### Task 6: Add Spring Cloud Stream configuration to moderation-service

**Files:**
- Modify: `AcctAtlas-moderation-service/src/main/resources/application.yml`

**Step 1: Add configuration**

```yaml
spring:
  cloud:
    aws:
      region:
        static: ${AWS_REGION:us-east-1}
      credentials:
        access-key: ${AWS_ACCESS_KEY_ID:test}
        secret-key: ${AWS_SECRET_ACCESS_KEY:test}
    stream:
      bindings:
        # Consumer: video-events queue
        handleVideoSubmitted-in-0:
          destination: video-events
          group: moderation-service
        # Producer: moderation-events queue
        moderationEvent-out-0:
          destination: moderation-events
    function:
      definition: handleVideoSubmitted
```

**Step 2: Add LocalStack configuration**

```yaml
# application-local.yml
spring:
  cloud:
    aws:
      sqs:
        endpoint: http://localhost:4566
```

**Step 3: Commit**

```bash
git add src/main/resources/
git commit -m "feat: add Spring Cloud Stream SQS configuration"
```

---

### Task 7: Create functional consumer for VideoSubmittedEvent

**Files:**
- Create: `AcctAtlas-moderation-service/src/main/java/.../event/VideoSubmittedHandler.java`
- Create: `AcctAtlas-moderation-service/src/test/java/.../event/VideoSubmittedHandlerTest.java`

**Step 1: Write the test**

```java
package com.accountabilityatlas.moderationservice.event;

import static org.mockito.Mockito.*;

import com.accountabilityatlas.moderationservice.client.VideoServiceClient;
import com.accountabilityatlas.moderationservice.domain.ContentType;
import com.accountabilityatlas.moderationservice.service.ModerationService;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.function.Consumer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class VideoSubmittedHandlerTest {

  @Mock private ModerationService moderationService;
  @Mock private VideoServiceClient videoServiceClient;
  @Mock private ModerationEventPublisher moderationEventPublisher;
  @InjectMocks private VideoSubmittedHandler handler;

  @Test
  void handleVideoSubmitted_newUser_queuesForModeration() {
    // Arrange
    UUID videoId = UUID.randomUUID();
    UUID submitterId = UUID.randomUUID();
    VideoSubmittedEvent event = new VideoSubmittedEvent(
        videoId, submitterId, "NEW", "Test Video",
        Set.of("FIRST"), List.of(), Instant.now()
    );

    // Act
    handler.handleVideoSubmitted().accept(event);

    // Assert
    verify(moderationService).createItem(ContentType.VIDEO, videoId, submitterId);
    verifyNoInteractions(videoServiceClient);
  }

  @Test
  void handleVideoSubmitted_trustedUser_autoApproves() {
    // Arrange
    UUID videoId = UUID.randomUUID();
    UUID submitterId = UUID.randomUUID();
    VideoSubmittedEvent event = new VideoSubmittedEvent(
        videoId, submitterId, "TRUSTED", "Test Video",
        Set.of("FIRST"), List.of(), Instant.now()
    );

    // Act
    handler.handleVideoSubmitted().accept(event);

    // Assert
    verify(videoServiceClient).updateVideoStatus(videoId, "APPROVED");
    verify(moderationEventPublisher).publishVideoApproved(videoId, submitterId);
    verifyNoInteractions(moderationService);
  }
}
```

**Step 2: Implement the handler**

```java
package com.accountabilityatlas.moderationservice.event;

import com.accountabilityatlas.moderationservice.client.VideoServiceClient;
import com.accountabilityatlas.moderationservice.domain.ContentType;
import com.accountabilityatlas.moderationservice.service.ModerationService;
import java.util.function.Consumer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@RequiredArgsConstructor
@Slf4j
public class VideoSubmittedHandler {

  private final ModerationService moderationService;
  private final VideoServiceClient videoServiceClient;
  private final ModerationEventPublisher moderationEventPublisher;

  @Bean
  public Consumer<VideoSubmittedEvent> handleVideoSubmitted() {
    return event -> {
      log.info(
          "Received VideoSubmittedEvent from SQS: videoId={}, submitterId={}, trustTier={}",
          event.videoId(),
          event.submitterId(),
          event.submitterTrustTier());

      if (event.requiresModeration()) {
        log.info("Queuing video {} for moderation (trust tier NEW)", event.videoId());
        moderationService.createItem(ContentType.VIDEO, event.videoId(), event.submitterId());
      } else {
        log.info("Auto-approving video {} (trust tier {})", event.videoId(), event.submitterTrustTier());
        videoServiceClient.updateVideoStatus(event.videoId(), "APPROVED");
        moderationEventPublisher.publishVideoApproved(event.videoId(), event.submitterId());
      }
    };
  }
}
```

**Step 3: Run tests**

```bash
./gradlew test --tests VideoSubmittedHandlerTest
```

**Step 4: Commit**

```bash
git add src/
git commit -m "feat: add functional consumer for VideoSubmittedEvent"
```

---

### Task 8: Refactor ModerationEventPublisher to use StreamBridge

**Files:**
- Modify: `AcctAtlas-moderation-service/src/main/java/.../event/ModerationEventPublisher.java`
- Modify: `AcctAtlas-moderation-service/src/test/java/.../event/ModerationEventPublisherTest.java`

**Step 1: Update the test**

```java
package com.accountabilityatlas.moderationservice.event;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.cloud.stream.function.StreamBridge;

import static org.assertj.core.api.Assertions.assertThat;

@ExtendWith(MockitoExtension.class)
class ModerationEventPublisherTest {

  @Mock private StreamBridge streamBridge;
  private ModerationEventPublisher publisher;

  @BeforeEach
  void setUp() {
    publisher = new ModerationEventPublisher(streamBridge);
  }

  @Test
  void publishVideoApproved_sendsToStreamBridge() {
    UUID videoId = UUID.randomUUID();
    UUID reviewerId = UUID.randomUUID();
    when(streamBridge.send(eq("moderationEvent-out-0"), any())).thenReturn(true);

    publisher.publishVideoApproved(videoId, reviewerId);

    ArgumentCaptor<VideoApprovedEvent> captor = ArgumentCaptor.forClass(VideoApprovedEvent.class);
    verify(streamBridge).send(eq("moderationEvent-out-0"), captor.capture());
    assertThat(captor.getValue().videoId()).isEqualTo(videoId);
  }

  @Test
  void publishVideoRejected_sendsToStreamBridge() {
    UUID videoId = UUID.randomUUID();
    UUID reviewerId = UUID.randomUUID();
    when(streamBridge.send(eq("moderationEvent-out-0"), any())).thenReturn(true);

    publisher.publishVideoRejected(videoId, reviewerId, "OFF_TOPIC");

    ArgumentCaptor<VideoRejectedEvent> captor = ArgumentCaptor.forClass(VideoRejectedEvent.class);
    verify(streamBridge).send(eq("moderationEvent-out-0"), captor.capture());
    assertThat(captor.getValue().videoId()).isEqualTo(videoId);
    assertThat(captor.getValue().reason()).isEqualTo("OFF_TOPIC");
  }
}
```

**Step 2: Update implementation**

```java
package com.accountabilityatlas.moderationservice.event;

import java.time.Instant;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.stream.function.StreamBridge;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class ModerationEventPublisher {

  private static final String MODERATION_EVENT_BINDING = "moderationEvent-out-0";

  private final StreamBridge streamBridge;

  public void publishVideoApproved(UUID videoId, UUID reviewerId) {
    VideoApprovedEvent event = new VideoApprovedEvent(videoId, reviewerId, Instant.now());
    log.info("Publishing VideoApprovedEvent to SQS: videoId={}", videoId);
    boolean sent = streamBridge.send(MODERATION_EVENT_BINDING, event);
    if (!sent) {
      log.error("Failed to publish VideoApprovedEvent for video {}", videoId);
    }
  }

  public void publishVideoRejected(UUID videoId, UUID reviewerId, String reason) {
    VideoRejectedEvent event = new VideoRejectedEvent(videoId, reviewerId, reason, Instant.now());
    log.info("Publishing VideoRejectedEvent to SQS: videoId={}", videoId);
    boolean sent = streamBridge.send(MODERATION_EVENT_BINDING, event);
    if (!sent) {
      log.error("Failed to publish VideoRejectedEvent for video {}", videoId);
    }
  }
}
```

**Step 3: Run tests**

```bash
./gradlew test
```

**Step 4: Commit**

```bash
git add src/
git commit -m "refactor: use StreamBridge for moderation event publishing"
```

---

### Task 9: Remove old VideoSubmittedEventListener

**Files:**
- Delete: `AcctAtlas-moderation-service/src/main/java/.../event/VideoSubmittedEventListener.java`
- Delete or update related tests

**Step 1: Remove the old listener**

The functionality is now in VideoSubmittedHandler. Delete the old listener.

**Step 2: Run tests to ensure nothing breaks**

```bash
./gradlew test
```

**Step 3: Commit**

```bash
git rm src/main/java/.../event/VideoSubmittedEventListener.java
git commit -m "refactor: remove old @EventListener in favor of Spring Cloud Stream"
```

---

## Phase 3: Integration Testing

### Task 10: Test video-service → moderation-service flow

**Step 1: Start infrastructure**

```bash
cd /c/code/AccountabilityAtlas
docker-compose up -d postgres redis localstack
```

**Step 2: Start moderation-service**

```bash
cd AcctAtlas-moderation-service
SPRING_PROFILES_ACTIVE=local ./gradlew bootRun
```

**Step 3: Start video-service**

```bash
cd AcctAtlas-video-service
SPRING_PROFILES_ACTIVE=local ./gradlew bootRun
```

**Step 4: Submit a video and verify**

```bash
# Create a video (this should publish to video-events queue)
curl -X POST http://localhost:8082/videos \
  -H "Authorization: Bearer <jwt-with-NEW-trust-tier>" \
  -H "Content-Type: application/json" \
  -d '{"youtubeUrl": "https://youtube.com/watch?v=test123", ...}'

# Check moderation queue (should have new item)
curl http://localhost:8085/moderation/queue \
  -H "Authorization: Bearer <moderator-jwt>"
```

**Step 5: Verify SQS message flow**

```bash
# Check video-events queue is empty (message consumed)
docker exec accountabilityatlas-localstack-1 awslocal sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/video-events \
  --attribute-names ApproximateNumberOfMessages
```

---

## Summary

| Task | Service | Description |
|------|---------|-------------|
| 1-4 | video-service | Add dependencies, config, refactor to StreamBridge |
| 5-9 | moderation-service | Add dependencies, config, consumer, refactor publisher |
| 10 | Integration | Test end-to-end flow |

**Estimated effort:** 4-6 hours

---

## Notes

### Event Serialization

Spring Cloud Stream uses JSON by default. Ensure event records are serializable:

```java
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

### Error Handling

For production, configure DLQ routing:

```yaml
spring:
  cloud:
    stream:
      bindings:
        handleVideoSubmitted-in-0:
          destination: video-events
          group: moderation-service
      sqs:
        bindings:
          handleVideoSubmitted-in-0:
            consumer:
              snsFanout: false
```

### Consumer Groups

Using `group: moderation-service` ensures:
- Only one instance processes each message (competing consumers)
- Messages are acknowledged after successful processing
