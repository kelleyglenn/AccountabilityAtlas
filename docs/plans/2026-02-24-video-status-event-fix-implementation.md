# VideoStatusChanged Event Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix two bugs — video-service #49 (VideoStatusChanged events not published due to race condition) and location-service #17 (map shows locations with zero videos).

**Architecture:** Move location linking into `VideoService.createVideo()` so locations are persisted before the `VideoSubmitted` SQS event is published. Add `video_count > 0` filter to the location-service bounding box query.

**Tech Stack:** Java 21, Spring Boot 3.4.x, JPA/Hibernate, PostGIS, Mockito, TestContainers

---

## Task 1: Update `VideoServiceTest` — add `VideoLocationService` mock and update existing tests

**Files:**
- Modify: `AcctAtlas-video-service/src/test/java/com/accountabilityatlas/videoservice/service/VideoServiceTest.java`

**Step 1: Add `VideoLocationService` mock to the test class**

Add a mock field after the existing mocks (line ~43):

```java
@Mock private VideoLocationService videoLocationService;
```

This is needed because `VideoService` will gain a `VideoLocationService` dependency. The `@InjectMocks` annotation will automatically inject it.

**Step 2: Update `createVideo_validRequest_savesMetadataAndSetsPending` test**

The existing test passes `Collections.emptyList()` for locationIds. Update it to pass a real locationId and verify `addLocationInternal` is called before the event is published:

```java
@Test
void createVideo_validRequest_savesMetadataAndSetsPending() {
  // Arrange
  UUID locationId = UUID.randomUUID();
  when(youTubeService.extractVideoId("url")).thenReturn("abc123def45");
  when(videoRepository.existsByYoutubeId("abc123def45")).thenReturn(false);

  YouTubeMetadata metadata =
      new YouTubeMetadata(
          "abc123def45",
          "Title",
          "Desc",
          "http://thumb",
          120,
          "channel",
          "Channel Name",
          Instant.parse("2024-01-01T00:00:00Z"),
          null);
  when(youTubeService.fetchMetadata("abc123def45")).thenReturn(metadata);
  when(videoRepository.save(any(Video.class)))
      .thenAnswer(invocation -> invocation.getArgument(0));

  // Act
  Video created =
      videoService.createVideo(
          "url",
          Set.of(Amendment.FIRST),
          Set.of(Participant.POLICE),
          LocalDate.of(2024, 1, 2),
          userId,
          "NEW",
          List.of(locationId));

  // Assert
  assertThat(created.getYoutubeId()).isEqualTo("abc123def45");
  assertThat(created.getTitle()).isEqualTo("Title");
  assertThat(created.getStatus()).isEqualTo(VideoStatus.PENDING);
  assertThat(created.getSubmittedBy()).isEqualTo(userId);
  verify(videoLocationService).addLocationInternal(any(), eq(locationId), eq(true));
}
```

**Step 3: Add test verifying location is linked before event publish**

Add a new test that verifies the ordering — `addLocationInternal` must be called before `publishVideoSubmitted`:

```java
@Test
void createVideo_linksLocationBeforePublishingEvent() {
  // Arrange
  UUID locationId = UUID.randomUUID();
  when(youTubeService.extractVideoId("url")).thenReturn("abc123def45");
  when(videoRepository.existsByYoutubeId("abc123def45")).thenReturn(false);

  YouTubeMetadata metadata =
      new YouTubeMetadata(
          "abc123def45",
          "Title",
          "Desc",
          "http://thumb",
          120,
          "channel",
          "Channel Name",
          Instant.parse("2024-01-01T00:00:00Z"),
          null);
  when(youTubeService.fetchMetadata("abc123def45")).thenReturn(metadata);
  when(videoRepository.save(any(Video.class)))
      .thenAnswer(invocation -> invocation.getArgument(0));

  // Act
  videoService.createVideo(
      "url",
      Set.of(Amendment.FIRST),
      Set.of(Participant.POLICE),
      null,
      userId,
      "ADMIN",
      List.of(locationId));

  // Assert — verify ordering: location linked before event published
  var inOrder = inOrder(videoLocationService, videoEventPublisher);
  inOrder.verify(videoLocationService).addLocationInternal(any(), eq(locationId), eq(true));
  inOrder.verify(videoEventPublisher).publishVideoSubmitted(any(), eq("ADMIN"), eq(List.of(locationId)));
}
```

**Step 4: Run tests to verify they fail**

Run: `cd AcctAtlas-video-service && ./gradlew test --tests "*.VideoServiceTest" --no-daemon`
Expected: FAIL — `VideoService` doesn't call `addLocationInternal` yet.

---

## Task 2: Update `VideoService.createVideo()` — link locations before publishing event

**Files:**
- Modify: `AcctAtlas-video-service/src/main/java/com/accountabilityatlas/videoservice/service/VideoService.java`

**Step 1: Add `VideoLocationService` field**

Add to the field list (around line 24, after the existing fields):

```java
private final VideoLocationService videoLocationService;
```

Also add to constructor parameters. The class uses `@RequiredArgsConstructor` (from Lombok), so just adding the `final` field is sufficient.

**Step 2: Add location linking in `createVideo()` before event publish**

Replace lines 102-107 (the save + publish section) with:

```java
Video saved = videoRepository.save(video);

// Link locations before publishing event — ensures locations are committed
// before moderation-service callback queries for them (fixes #49)
for (int i = 0; i < locationIds.size(); i++) {
  videoLocationService.addLocationInternal(saved.getId(), locationIds.get(i), i == 0);
}

// Publish event after successful save
videoEventPublisher.publishVideoSubmitted(saved, submitterTrustTier, locationIds);

return saved;
```

**Step 3: Run tests to verify they pass**

Run: `cd AcctAtlas-video-service && ./gradlew test --tests "*.VideoServiceTest" --no-daemon`
Expected: PASS

**Step 4: Commit**

```
fix(video): link locations before publishing VideoSubmitted event (#49)
```

---

## Task 3: Remove redundant `addLocationInternal` call from `VideoController`

**Files:**
- Modify: `AcctAtlas-video-service/src/main/java/com/accountabilityatlas/videoservice/web/VideoController.java`
- Check: `AcctAtlas-video-service/src/test/java/com/accountabilityatlas/videoservice/web/VideoControllerTest.java`

**Step 1: Remove the redundant call**

In `createVideo()` method (around line 152), remove the line:

```java
videoLocationService.addLocationInternal(video.getId(), locationId, true);
```

The method should now be:

```java
public ResponseEntity<VideoDetail> createVideo(CreateVideoRequest request) {
  UUID userId = requireCurrentUserId();
  UUID locationId = request.getLocationId();
  String trustTier = getCurrentTrustTierOrNull();

  Video video =
      videoService.createVideo(
          request.getYoutubeUrl().toString(),
          request.getAmendments().stream()
              .map(a -> Amendment.valueOf(a.name()))
              .collect(Collectors.toSet()),
          request.getParticipants().stream()
              .map(p -> Participant.valueOf(p.name()))
              .collect(Collectors.toSet()),
          request.getVideoDate(),
          userId,
          trustTier != null ? trustTier : "NEW",
          List.of(locationId));

  return ResponseEntity.status(HttpStatus.CREATED).body(toVideoDetail(video));
}
```

**Step 2: Check if `VideoLocationService` is still injected into the controller**

Check if `VideoController` still needs `VideoLocationService` for other endpoints (addVideoLocation, removeVideoLocation, getVideoLocations). If so, keep the injection. If those endpoints also exist, the injection stays.

**Step 3: Run all video-service tests**

Run: `cd AcctAtlas-video-service && ./gradlew test --no-daemon`
Expected: PASS (all tests including VideoControllerTest)

**Step 4: Run full quality check**

Run: `cd AcctAtlas-video-service && ./gradlew check --no-daemon`
Expected: PASS (spotless, error-prone, all tests)

**Step 5: Commit**

```
refactor(video): remove redundant addLocationInternal from controller (#49)
```

---

## Task 4: Fix `LocationRepository.findWithinBoundingBox` — filter by video_count > 0

**Files:**
- Modify: `AcctAtlas-location-service/src/main/java/com/accountabilityatlas/locationservice/repository/LocationRepository.java`

**Step 1: Update the JPQL query**

Change the `findWithinBoundingBox` query from:

```java
@Query(
    """
    SELECT l FROM Location l
    LEFT JOIN FETCH l.stats
    WHERE ST_Within(l.coordinates, :bbox) = true
    """)
List<Location> findWithinBoundingBox(@Param("bbox") Polygon bbox);
```

To:

```java
@Query(
    """
    SELECT l FROM Location l
    JOIN FETCH l.stats ls
    WHERE ST_Within(l.coordinates, :bbox) = true
      AND ls.videoCount > 0
    """)
List<Location> findWithinBoundingBox(@Param("bbox") Polygon bbox);
```

Key changes:
- `LEFT JOIN FETCH` → `JOIN FETCH` (locations without stats records should not appear)
- Added `AND ls.videoCount > 0` filter (uses JPA field name, not column name)
- Added alias `ls` for the stats join

**Step 2: Run existing tests**

Run: `cd AcctAtlas-location-service && ./gradlew test --no-daemon`
Expected: The existing `shouldFindLocationsWithinBoundingBox` test may fail because it doesn't create `LocationStats` records. Check the result.

---

## Task 5: Update `LocationRepositoryIntegrationTest` for the new filter

**Files:**
- Modify: `AcctAtlas-location-service/src/test/java/com/accountabilityatlas/locationservice/integration/LocationRepositoryIntegrationTest.java`

**Step 1: Add `LocationStatsRepository` or EntityManager to the test**

Add to the test class:

```java
@Autowired private LocationStatsRepository locationStatsRepository;
```

Or if `LocationStatsRepository` doesn't exist, use `TestEntityManager`:

```java
@Autowired private TestEntityManager entityManager;
```

Note: `@DataJpaTest` provides `TestEntityManager` automatically.

**Step 2: Update `shouldFindLocationsWithinBoundingBox` test**

The existing test creates locations without `LocationStats`, which will now return empty results due to the `video_count > 0` filter. Update to create stats:

```java
@Test
void shouldFindLocationsWithinBoundingBox() {
  // Create location inside bbox (San Francisco) with video_count > 0
  Point sfPoint = GEOMETRY_FACTORY.createPoint(new Coordinate(-122.4194, 37.7749));
  Location sfLocation =
      Location.builder()
          .coordinates(sfPoint)
          .displayName("San Francisco")
          .city("San Francisco")
          .state("CA")
          .country("USA")
          .build();
  sfLocation = locationRepository.save(sfLocation);

  LocationStats sfStats = new LocationStats();
  sfStats.setLocation(sfLocation);
  sfStats.setVideoCount(1);
  entityManager.persist(sfStats);

  // Create location outside bbox (Los Angeles)
  Point laPoint = GEOMETRY_FACTORY.createPoint(new Coordinate(-118.2437, 34.0522));
  Location laLocation =
      Location.builder()
          .coordinates(laPoint)
          .displayName("Los Angeles")
          .city("Los Angeles")
          .state("CA")
          .country("USA")
          .build();
  laLocation = locationRepository.save(laLocation);

  LocationStats laStats = new LocationStats();
  laStats.setLocation(laLocation);
  laStats.setVideoCount(1);
  entityManager.persist(laStats);

  entityManager.flush();

  // Bounding box around San Francisco only
  Polygon bbox =
      GEOMETRY_FACTORY.createPolygon(
          new Coordinate[] {
            new Coordinate(-123.0, 37.0),
            new Coordinate(-122.0, 37.0),
            new Coordinate(-122.0, 38.0),
            new Coordinate(-123.0, 38.0),
            new Coordinate(-123.0, 37.0)
          });

  List<Location> results = locationRepository.findWithinBoundingBox(bbox);

  assertThat(results).hasSize(1);
  assertThat(results.get(0).getDisplayName()).isEqualTo("San Francisco");
}
```

**Step 3: Add test for the zero-video-count filter**

```java
@Test
void shouldExcludeLocationsWithZeroVideoCount() {
  // Create location with video_count = 0
  Point point = GEOMETRY_FACTORY.createPoint(new Coordinate(-122.4194, 37.7749));
  Location location =
      Location.builder()
          .coordinates(point)
          .displayName("Empty Location")
          .city("San Francisco")
          .state("CA")
          .country("USA")
          .build();
  location = locationRepository.save(location);

  LocationStats stats = new LocationStats();
  stats.setLocation(location);
  stats.setVideoCount(0);
  entityManager.persist(stats);
  entityManager.flush();

  Polygon bbox =
      GEOMETRY_FACTORY.createPolygon(
          new Coordinate[] {
            new Coordinate(-123.0, 37.0),
            new Coordinate(-122.0, 37.0),
            new Coordinate(-122.0, 38.0),
            new Coordinate(-123.0, 38.0),
            new Coordinate(-123.0, 37.0)
          });

  List<Location> results = locationRepository.findWithinBoundingBox(bbox);

  assertThat(results).isEmpty();
}
```

**Step 4: Run tests**

Run: `cd AcctAtlas-location-service && ./gradlew test --no-daemon`
Expected: PASS

**Step 5: Run full quality check**

Run: `cd AcctAtlas-location-service && ./gradlew check --no-daemon`
Expected: PASS

**Step 6: Commit**

```
fix(location): filter map locations by video_count > 0 (#17)
```

---

## Task 6: Deploy and verify with seed data

**Step 1: Deploy both services**

```bash
./scripts/deploy.sh video-service location-service
```

**Step 2: Clean test data**

```bash
bash scripts/clean-test-data.sh
```

**Step 3: Seed videos and capture logs**

```bash
docker logs accountabilityatlas-video-service-1 --since 1m -f > /tmp/video-logs.txt 2>&1 &
docker logs accountabilityatlas-location-service-1 --since 1m -f > /tmp/location-logs.txt 2>&1 &

ADMIN_EMAIL=seedadmin@test.com ADMIN_PASSWORD=AdminPass1234 \
  bash scripts/seed-videos.sh --file seed-data/LIA-just-10-enriched-locations.json
```

**Step 4: Verify results**

Check video-service logs — all 9 videos should produce `VideoStatusChanged` events:
```bash
grep "VideoStatusChanged" /tmp/video-logs.txt | wc -l
# Expected: 9
```

Check location-service logs — all 9 events should be received:
```bash
grep "VideoStatusChanged" /tmp/location-logs.txt | wc -l
# Expected: 9
```

Check database — all location video_counts should be 1:
```bash
docker exec accountabilityatlas-postgres-1 psql -U postgres -d location_service -c \
  "SELECT ls.video_count, COUNT(*) FROM locations.location_stats ls WHERE ls.video_count > 0 GROUP BY ls.video_count;"
```

---

## Task 7: Run integration tests and create PRs

**Step 1: Run full integration test suite**

```bash
cd AcctAtlas-integration-tests && npm run test:all
```

Expected: All tests pass.

**Step 2: Create video-service PR**

Create issue and PR for video-service fixing #49.

**Step 3: Create location-service PR**

Create issue and PR for location-service fixing #17.

**Step 4: Check CI on both PRs**

Wait for CI pipelines to pass on both PRs before marking ready for review.
