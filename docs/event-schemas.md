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
