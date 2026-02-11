# LocalStack SQS Infrastructure Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add LocalStack SQS to enable async event-driven messaging between services in local development.

**Architecture:** LocalStack emulates AWS SQS locally. Services publish/consume events via SQS queues. Queue initialization happens via init script on container startup. This matches production (AWS SQS) with zero code changes.

**Tech Stack:** LocalStack, AWS SDK for Java 2.x, Docker Compose

**Design Doc:** [05-DataArchitecture.md](../05-DataArchitecture.md) (Message Queue section)

---

## Event Flow Overview

```
video-service                    moderation-service                 search-service
     │                                  │                                │
     │  VideoSubmitted                  │                                │
     ├─────────────────────────────────►│                                │
     │  (video-events queue)            │                                │
     │                                  │  VideoApproved/Rejected        │
     │                                  ├───────────────────────────────►│
     │                                  │  (moderation-events queue)     │
     │                                  │                                │
```

---

## Queue Definitions

| Queue | Publisher | Consumers | Events |
|-------|-----------|-----------|--------|
| `video-events` | video-service | moderation-service | VideoSubmitted |
| `moderation-events` | moderation-service | video-service, search-service | VideoApproved, VideoRejected |
| `user-events` | user-service | moderation-service | UserTrustTierChanged |

---

## Event Schemas

### VideoSubmitted (video-service → moderation-service)

```json
{
  "eventType": "VideoSubmitted",
  "videoId": "uuid",
  "submitterId": "uuid",
  "submitterTrustTier": "NEW|TRUSTED|MODERATOR|ADMIN",
  "title": "string",
  "amendments": ["FIRST", "FOURTH"],
  "locationIds": ["uuid"],
  "timestamp": "2026-02-10T12:00:00Z"
}
```

### VideoApproved (moderation-service → video-service, search-service)

```json
{
  "eventType": "VideoApproved",
  "videoId": "uuid",
  "reviewerId": "uuid",
  "timestamp": "2026-02-10T12:00:00Z"
}
```

### VideoRejected (moderation-service → video-service, search-service)

```json
{
  "eventType": "VideoRejected",
  "videoId": "uuid",
  "reviewerId": "uuid",
  "reason": "DUPLICATE|OFF_TOPIC|INCORRECT_LOCATION|LOW_QUALITY|OTHER",
  "comment": "string (optional)",
  "timestamp": "2026-02-10T12:00:00Z"
}
```

### UserTrustTierChanged (user-service → moderation-service)

```json
{
  "eventType": "UserTrustTierChanged",
  "userId": "uuid",
  "oldTier": "NEW|TRUSTED|MODERATOR|ADMIN",
  "newTier": "NEW|TRUSTED|MODERATOR|ADMIN",
  "reason": "AUTO_PROMOTION|AUTO_DEMOTION|MANUAL",
  "timestamp": "2026-02-10T12:00:00Z"
}
```

---

## Phase 1: LocalStack Setup

### Task 1: Add LocalStack to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add LocalStack service**

Add after the `redis` service:

```yaml
  localstack:
    image: localstack/localstack:3.0
    ports:
      - "4566:4566"
    environment:
      - SERVICES=sqs
      - DEBUG=0
      - DOCKER_HOST=unix:///var/run/docker.sock
    volumes:
      - ./docker/localstack:/etc/localstack/init/ready.d:ro
      - localstack-data:/var/lib/localstack
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 10s
      timeout: 5s
      retries: 5
```

**Step 2: Add volume**

Add to the `volumes` section:

```yaml
  localstack-data:
```

**Step 3: Verify docker-compose syntax**

Run:
```bash
cd /c/code/AccountabilityAtlas && docker-compose config
```

Expected: Valid YAML output, no errors

**Step 4: Commit**

```bash
cd /c/code/AccountabilityAtlas
git add docker-compose.yml
git commit -m "build: add LocalStack to docker-compose"
```

---

### Task 2: Create Queue Initialization Script

**Files:**
- Create: `docker/localstack/init-queues.sh`

**Step 1: Create the localstack directory**

Run:
```bash
mkdir -p /c/code/AccountabilityAtlas/docker/localstack
```

**Step 2: Create init-queues.sh**

```bash
#!/bin/bash
# Initialize SQS queues for local development
# This script runs when LocalStack is ready

set -e

ENDPOINT="http://localhost:4566"

echo "Creating SQS queues..."

# Video events queue
awslocal sqs create-queue --queue-name video-events
awslocal sqs create-queue --queue-name video-events-dlq

# Moderation events queue
awslocal sqs create-queue --queue-name moderation-events
awslocal sqs create-queue --queue-name moderation-events-dlq

# User events queue
awslocal sqs create-queue --queue-name user-events
awslocal sqs create-queue --queue-name user-events-dlq

echo "SQS queues created:"
awslocal sqs list-queues

echo "LocalStack SQS initialization complete!"
```

**Step 3: Make script executable**

Run:
```bash
chmod +x /c/code/AccountabilityAtlas/docker/localstack/init-queues.sh
```

**Step 4: Test LocalStack starts and creates queues**

Run:
```bash
cd /c/code/AccountabilityAtlas && docker-compose up -d localstack
```

Wait 10 seconds, then verify:

```bash
docker-compose logs localstack | grep -i "queue"
```

Expected: Should see queue creation messages

**Step 5: Verify queues exist**

Run:
```bash
aws --endpoint-url=http://localhost:4566 sqs list-queues --region us-east-1
```

Expected: Should list all 6 queues (3 main + 3 DLQ)

**Step 6: Commit**

```bash
cd /c/code/AccountabilityAtlas
git add docker/localstack/
git commit -m "build: add SQS queue initialization script"
```

---

### Task 3: Create Event Schema Documentation

**Files:**
- Create: `docs/event-schemas.md`

**Step 1: Create event-schemas.md**

```markdown
# Event Schemas

This document defines the event schemas used for async messaging between services.

## Transport

- **Local Development**: LocalStack SQS (http://localhost:4566)
- **Production**: AWS SQS

## Queues

| Queue | Publisher | Consumers |
|-------|-----------|-----------|
| `video-events` | video-service | moderation-service |
| `moderation-events` | moderation-service | video-service, search-service |
| `user-events` | user-service | moderation-service |

Each queue has a corresponding dead-letter queue (`*-dlq`) for failed messages.

## Event Envelope

All events are wrapped in a standard envelope:

```json
{
  "eventType": "string",
  "timestamp": "ISO8601",
  ...event-specific fields
}
```

## Video Events

### VideoSubmitted

Published when a new video is submitted.

**Queue:** `video-events`
**Publisher:** video-service
**Consumers:** moderation-service

```json
{
  "eventType": "VideoSubmitted",
  "videoId": "550e8400-e29b-41d4-a716-446655440000",
  "submitterId": "660e8400-e29b-41d4-a716-446655440001",
  "submitterTrustTier": "NEW",
  "title": "First Amendment Audit at City Hall",
  "amendments": ["FIRST", "FOURTH"],
  "locationIds": ["770e8400-e29b-41d4-a716-446655440002"],
  "timestamp": "2026-02-10T15:30:00Z"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| eventType | string | Yes | Always "VideoSubmitted" |
| videoId | UUID | Yes | ID of the submitted video |
| submitterId | UUID | Yes | User who submitted the video |
| submitterTrustTier | enum | Yes | NEW, TRUSTED, MODERATOR, or ADMIN |
| title | string | Yes | Video title |
| amendments | string[] | Yes | Amendment categories |
| locationIds | UUID[] | No | Associated location IDs |
| timestamp | ISO8601 | Yes | When the event occurred |

**Consumer Actions:**
- **moderation-service**: Create moderation queue item (if submitterTrustTier is NEW)

---

## Moderation Events

### VideoApproved

Published when a video passes moderation.

**Queue:** `moderation-events`
**Publisher:** moderation-service
**Consumers:** video-service, search-service

```json
{
  "eventType": "VideoApproved",
  "videoId": "550e8400-e29b-41d4-a716-446655440000",
  "reviewerId": "660e8400-e29b-41d4-a716-446655440001",
  "timestamp": "2026-02-10T16:00:00Z"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| eventType | string | Yes | Always "VideoApproved" |
| videoId | UUID | Yes | ID of the approved video |
| reviewerId | UUID | Yes | Moderator who approved |
| timestamp | ISO8601 | Yes | When the event occurred |

**Consumer Actions:**
- **video-service**: Update video status to APPROVED
- **search-service**: Fetch video details, index in search

### VideoRejected

Published when a video fails moderation.

**Queue:** `moderation-events`
**Publisher:** moderation-service
**Consumers:** video-service, search-service

```json
{
  "eventType": "VideoRejected",
  "videoId": "550e8400-e29b-41d4-a716-446655440000",
  "reviewerId": "660e8400-e29b-41d4-a716-446655440001",
  "reason": "OFF_TOPIC",
  "comment": "Video does not relate to constitutional rights",
  "timestamp": "2026-02-10T16:00:00Z"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| eventType | string | Yes | Always "VideoRejected" |
| videoId | UUID | Yes | ID of the rejected video |
| reviewerId | UUID | Yes | Moderator who rejected |
| reason | enum | Yes | DUPLICATE, OFF_TOPIC, INCORRECT_LOCATION, LOW_QUALITY, OTHER |
| comment | string | No | Optional explanation |
| timestamp | ISO8601 | Yes | When the event occurred |

**Consumer Actions:**
- **video-service**: Update video status to REJECTED
- **search-service**: Remove video from search index (if present)

---

## User Events

### UserTrustTierChanged

Published when a user's trust tier changes.

**Queue:** `user-events`
**Publisher:** user-service
**Consumers:** moderation-service

```json
{
  "eventType": "UserTrustTierChanged",
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "oldTier": "NEW",
  "newTier": "TRUSTED",
  "reason": "AUTO_PROMOTION",
  "timestamp": "2026-02-10T16:00:00Z"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| eventType | string | Yes | Always "UserTrustTierChanged" |
| userId | UUID | Yes | User whose tier changed |
| oldTier | enum | Yes | Previous tier |
| newTier | enum | Yes | New tier |
| reason | enum | Yes | AUTO_PROMOTION, AUTO_DEMOTION, MANUAL |
| timestamp | ISO8601 | Yes | When the event occurred |

**Consumer Actions:**
- **moderation-service**: Re-evaluate pending items from user

---

## Error Handling

### Retry Policy

Messages that fail processing are retried with exponential backoff:
- 1st retry: 10 seconds
- 2nd retry: 30 seconds
- 3rd retry: 60 seconds

After 3 failed attempts, messages move to the dead-letter queue.

### Idempotency

All consumers must be idempotent. The same event may be delivered multiple times.

**Strategies:**
- Use `videoId`/`userId` as idempotency key
- Check current state before applying changes
- Use database upserts where possible
```

**Step 2: Commit**

```bash
cd /c/code/AccountabilityAtlas
git add docs/event-schemas.md
git commit -m "docs: add event schema documentation"
```

---

## Phase 2: Service Configuration

### Task 4: Create Shared SQS Configuration Properties

This task documents the configuration pattern for services. Each service will implement this pattern when they add SQS support.

**Configuration Pattern:**

```yaml
# application.yml
app:
  sqs:
    endpoint: ${AWS_SQS_ENDPOINT:}
    region: ${AWS_REGION:us-east-1}

# application-local.yml
app:
  sqs:
    endpoint: http://localhost:4566
    region: us-east-1
```

**AWS SDK Dependencies (for build.gradle):**

```gradle
// AWS SDK v2 for SQS
implementation platform('software.amazon.awssdk:bom:2.25.0')
implementation 'software.amazon.awssdk:sqs'
```

**SQS Client Configuration Bean:**

```java
@Configuration
@ConfigurationProperties(prefix = "app.sqs")
@Getter
@Setter
public class SqsConfig {
    private String endpoint;
    private String region = "us-east-1";

    @Bean
    public SqsClient sqsClient() {
        SqsClientBuilder builder = SqsClient.builder()
            .region(Region.of(region));

        if (endpoint != null && !endpoint.isBlank()) {
            builder.endpointOverride(URI.create(endpoint));
        }

        return builder.build();
    }
}
```

**No files to create** - this is documentation for service teams. Each service will add SQS support in their own implementation plans.

---

### Task 5: Update Parent docker-compose with Service Dependencies

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add localstack dependency to services that need SQS**

Update `user-service`, `location-service` (future), and add to `video-service`, `moderation-service`, `search-service` when they're added:

For services that will use SQS, add:

```yaml
    depends_on:
      # ...existing dependencies...
      localstack:
        condition: service_healthy
    environment:
      # ...existing environment...
      AWS_SQS_ENDPOINT: http://localstack:4566
      AWS_REGION: us-east-1
```

**Step 2: Update user-service with LocalStack dependency**

Add to the `user-service` environment section:

```yaml
      AWS_SQS_ENDPOINT: http://localstack:4566
      AWS_REGION: us-east-1
```

Add to `user-service` depends_on:

```yaml
      localstack:
        condition: service_healthy
```

**Step 3: Commit**

```bash
cd /c/code/AccountabilityAtlas
git add docker-compose.yml
git commit -m "build: add LocalStack dependency to services"
```

---

### Task 6: Verify End-to-End LocalStack Setup

**Step 1: Start full infrastructure**

Run:
```bash
cd /c/code/AccountabilityAtlas && docker-compose up -d postgres redis localstack
```

**Step 2: Wait for services to be healthy**

Run:
```bash
docker-compose ps
```

Expected: All three services should show "healthy" status

**Step 3: Verify queues are created**

Run:
```bash
aws --endpoint-url=http://localhost:4566 sqs list-queues --region us-east-1
```

Expected output:
```json
{
    "QueueUrls": [
        "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/video-events",
        "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/video-events-dlq",
        "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/moderation-events",
        "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/moderation-events-dlq",
        "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/user-events",
        "http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/user-events-dlq"
    ]
}
```

**Step 4: Test sending a message**

Run:
```bash
aws --endpoint-url=http://localhost:4566 sqs send-message \
  --queue-url http://localhost:4566/000000000000/video-events \
  --message-body '{"eventType":"VideoSubmitted","videoId":"test-123"}' \
  --region us-east-1
```

**Step 5: Test receiving the message**

Run:
```bash
aws --endpoint-url=http://localhost:4566 sqs receive-message \
  --queue-url http://localhost:4566/000000000000/video-events \
  --region us-east-1
```

Expected: Should receive the test message

**Step 6: Clean up test message**

Run:
```bash
aws --endpoint-url=http://localhost:4566 sqs purge-queue \
  --queue-url http://localhost:4566/000000000000/video-events \
  --region us-east-1
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add LocalStack to docker-compose |
| 2 | Create queue initialization script |
| 3 | Document event schemas |
| 4 | Document SQS configuration pattern |
| 5 | Update services with LocalStack dependency |
| 6 | Verify end-to-end setup |

**Total Tasks:** 6

---

## Next Steps (Separate Plans)

After this infrastructure is in place:

1. **Retrofit video-service** - Replace ApplicationEventPublisher with SQS
2. **Retrofit moderation-service** - Add SQS consumption and publishing
3. **Build search-service** - Consume from moderation-events queue

---

## Troubleshooting

### Queues not created

Check LocalStack logs:
```bash
docker-compose logs localstack
```

Manually run init script:
```bash
docker-compose exec localstack /etc/localstack/init/ready.d/init-queues.sh
```

### AWS CLI not configured

For local testing, credentials don't matter but must be set:
```bash
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
```

### Connection refused

Ensure LocalStack is healthy:
```bash
curl http://localhost:4566/_localstack/health
```
