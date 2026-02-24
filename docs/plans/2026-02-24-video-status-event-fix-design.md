# Fix: VideoStatusChanged Events Not Published (video-service #49)

## Problem

When a video is created, the `VideoStatusChanged` event is almost never published to the location-service, so `video_count` stays at 0 for new locations. This makes new videos invisible on the map.

### Root Cause

`VideoController.createVideo()` performs two sequential operations in separate transactions:

1. `videoService.createVideo()` — saves the Video, publishes `VideoSubmitted` to SQS
2. `videoLocationService.addLocationInternal()` — persists the `VideoLocation` association

The moderation-service receives `VideoSubmitted`, auto-approves, and HTTP PUTs back to `updateVideoStatus()` within 30-60ms. At that point, `findByIdWithLocations()` finds no locations because step 2 hasn't committed yet. The `!locationIds.isEmpty()` guard silently skips the `VideoStatusChanged` event.

### Evidence

Seeding 10 videos: only 1/9 produced a `VideoStatusChanged` event (the first video succeeded due to moderation-service cold start adding ~865ms delay). The location-service received only 1 event, leaving 8 locations with `video_count = 0`.

## Solution

### video-service #49: Move location linking into `VideoService.createVideo()`

Move the `addLocationInternal()` call into `createVideo()` so locations are persisted **before** the `VideoSubmitted` event is published.

**VideoService.createVideo()** — add `VideoLocationService` dependency, link locations before publishing:

```java
Video saved = videoRepository.save(video);
for (int i = 0; i < locationIds.size(); i++) {
    videoLocationService.addLocationInternal(saved.getId(), locationIds.get(i), i == 0);
}
videoEventPublisher.publishVideoSubmitted(saved, submitterTrustTier, locationIds);
return saved;
```

**VideoController.createVideo()** — remove redundant `addLocationInternal()` call.

### location-service #17: Filter locations by video_count > 0

Add `AND ls.video_count > 0` to `LocationRepository.findWithinBoundingBox()`, matching the existing filter in `findClustersInBoundingBox()`. This ensures the map only shows locations with approved videos.

## Testing

- Update `VideoServiceTest` to mock `VideoLocationService` and verify call ordering
- Update `LocationRepositoryTest` (if exists) to verify the filter
- Deploy both services, re-seed, verify all videos produce `VideoStatusChanged` events
- Run full integration test suite (`test:all`)

## Scope

- **Changed**: video-service (2 files), location-service (1 file), plus tests
- **Not changed**: moderation-service, web-app, event schemas, SQS queues
