# Development Standards

## Technology Stack

### Backend Services

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Java | 21 LTS |
| Framework | Spring Boot | 3.2.x |
| Build Tool | Gradle | 8.x |
| JDK | Amazon Corretto | 21 LTS |
| Container | Docker | 24.x |
| API Documentation | OpenAPI / Springdoc | 3.0 |

### Dependencies

| Purpose | Library |
|---------|---------|
| Database Access | Spring Data JPA |
| Database Migrations | Flyway |
| JSON Processing | Jackson |
| HTTP Client | Spring WebClient |
| Validation | Jakarta Bean Validation |
| Testing | JUnit 5, Mockito, TestContainers |
| Logging | SLF4J + Logback |
| Metrics | Micrometer |

---

## Project Structure

### Standard Service Layout

```
service-name/
├── build.gradle
├── settings.gradle
├── Dockerfile
├── docker-compose.yml
├── TechnicalDocumentation/
│   ├── api-specification.yaml
│   ├── database-schema.md
│   └── design-decisions.md
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/accountabilityatlas/servicename/
│   │   │       ├── ServiceNameApplication.java
│   │   │       ├── config/
│   │   │       │   ├── SecurityConfig.java
│   │   │       │   └── DatabaseConfig.java
│   │   │       ├── controller/
│   │   │       │   └── VideoController.java
│   │   │       ├── service/
│   │   │       │   └── VideoService.java
│   │   │       ├── repository/
│   │   │       │   └── VideoRepository.java
│   │   │       ├── domain/
│   │   │       │   ├── model/
│   │   │       │   │   └── Video.java
│   │   │       │   └── event/
│   │   │       │       └── VideoEvents.java
│   │   │       ├── dto/
│   │   │       │   ├── request/
│   │   │       │   │   └── CreateVideoRequest.java
│   │   │       │   └── response/
│   │   │       │       └── VideoResponse.java
│   │   │       ├── exception/
│   │   │       │   └── VideoNotFoundException.java
│   │   │       └── client/
│   │   │           └── YouTubeClient.java
│   │   └── resources/
│   │       ├── application.yml
│   │       ├── application-dev.yml
│   │       ├── application-staging.yml
│   │       ├── application-prod.yml
│   │       └── db/migration/
│   │           ├── V1__initial_schema.sql
│   │           └── V2__add_indexes.sql
│   └── test/
│       ├── java/
│       │   └── com/accountabilityatlas/servicename/
│       │       ├── controller/
│       │       │   └── VideoControllerTest.java
│       │       ├── service/
│       │       │   └── VideoServiceTest.java
│       │       └── integration/
│       │           └── VideoIntegrationTest.java
│       └── resources/
│           └── application-test.yml
└── .github/
    └── workflows/
        └── ci.yml
```

---

## Coding Standards

### Java Style Guide

Follow the [Google Java Style Guide](https://google.github.io/styleguide/javaguide.html) with these additions:

```java
// Package naming: lowercase, no underscores
package com.accountabilityatlas.videoservice;

// Class naming: PascalCase
public class VideoService { }

// Method naming: camelCase
public Optional<Video> findVideoById(UUID id) { }

// Constants: SCREAMING_SNAKE_CASE
public static final int MAX_TITLE_LENGTH = 500;

// Use records for DTOs (Java 17+)
public record CreateVideoRequest(
    String youtubeUrl,
    Set<Amendment> amendments,
    List<LocationInput> locations
) { }

// Use sealed classes for domain events (Java 17+)
public sealed interface VideoEvent permits
    VideoEvent.Submitted,
    VideoEvent.Approved,
    VideoEvent.Rejected {

    record Submitted(UUID videoId, UUID submitterId) implements VideoEvent { }
    record Approved(UUID videoId, UUID reviewerId) implements VideoEvent { }
    record Rejected(UUID videoId, String reason) implements VideoEvent { }
}

// Mapper method example
public VideoResponse toResponse(Video video) {
    return new VideoResponse(
        video.getId(),
        video.getTitle(),
        video.getThumbnailUrl()
    );
}
```

### Error Handling

```java
// Define domain exceptions
public class VideoNotFoundException extends RuntimeException {
    public VideoNotFoundException(UUID videoId) {
        super("Video not found: " + videoId);
    }
}

public class VideoValidationException extends RuntimeException {
    public VideoValidationException(String message) {
        super(message);
    }
}

// Global exception handler
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(VideoNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(VideoNotFoundException ex) {
        return ResponseEntity
            .status(HttpStatus.NOT_FOUND)
            .body(new ErrorResponse(
                "VIDEO_NOT_FOUND",
                ex.getMessage(),
                null,
                Instant.now()
            ));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
        List<String> errors = ex.getBindingResult().getFieldErrors().stream()
            .map(e -> e.getField() + ": " + e.getDefaultMessage())
            .toList();

        return ResponseEntity
            .status(HttpStatus.BAD_REQUEST)
            .body(new ErrorResponse(
                "VALIDATION_ERROR",
                "Invalid request",
                errors,
                Instant.now()
            ));
    }
}

// Standard error response format
public record ErrorResponse(
    String code,
    String message,
    List<String> details,
    Instant timestamp
) { }
```

### Logging Standards

```java
// Use structured logging with context
@Slf4j
public class VideoService {

    public Video submitVideo(CreateVideoRequest request, UUID userId) {
        log.info("Submitting video: youtubeId={}, userId={}, amendmentCount={}",
            extractYouTubeId(request.youtubeUrl()),
            userId,
            request.amendments().size()
        );

        try {
            Video video = createVideo(request, userId);
            log.info("Video submitted successfully: videoId={}, status={}",
                video.getId(),
                video.getStatus()
            );
            return video;
        } catch (Exception ex) {
            log.error("Failed to submit video: youtubeUrl={}, userId={}, error={}",
                request.youtubeUrl(),
                userId,
                ex.getMessage(),
                ex
            );
            throw ex;
        }
    }
}
```

---

## API Design Standards

### REST Conventions

```yaml
# Endpoint patterns
GET    /api/v1/videos              # List videos
POST   /api/v1/videos              # Create video
GET    /api/v1/videos/{id}         # Get video by ID
PUT    /api/v1/videos/{id}         # Update video
DELETE /api/v1/videos/{id}         # Delete video
GET    /api/v1/videos/{id}/locations  # Get video locations

# Query parameters for filtering
GET /api/v1/videos?amendments=FIRST,FOURTH&status=APPROVED&page=0&size=20

# Standard response envelope for lists
{
  "data": [...],
  "pagination": {
    "page": 0,
    "size": 20,
    "totalElements": 156,
    "totalPages": 8
  }
}

# Standard error response
{
  "code": "VIDEO_NOT_FOUND",
  "message": "Video with ID xyz not found",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### OpenAPI Documentation

Every service must provide an OpenAPI 3.0 specification:

```yaml
# TechnicalDocumentation/api-specification.yaml
openapi: 3.0.3
info:
  title: Video Service API
  version: 1.0.0
  description: Manages video records and metadata

servers:
  - url: https://api.accountabilityatlas.com/api/v1
    description: Production
  - url: https://api.staging.accountabilityatlas.com/api/v1
    description: Staging

paths:
  /videos:
    post:
      summary: Submit a new video
      operationId: submitVideo
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateVideoRequest'
      responses:
        '201':
          description: Video created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/VideoResponse'
        '400':
          $ref: '#/components/responses/BadRequest'
        '401':
          $ref: '#/components/responses/Unauthorized'
```

---

## Testing Standards

### Test Categories

| Type | Purpose | Tools | Coverage Target |
|------|---------|-------|-----------------|
| Unit | Single class/method | JUnit 5, Mockito | 80% |
| Integration | Service + dependencies | TestContainers | Key paths |
| Contract | API compatibility | Spring Cloud Contract | All endpoints |
| E2E | Full user flows | (Client team) | Critical paths |

### Unit Test Example

```java
@ExtendWith(MockitoExtension.class)
class VideoServiceTest {

    @Mock
    private VideoRepository videoRepository;

    @Mock
    private YouTubeClient youtubeClient;

    @Mock
    private VideoEventPublisher eventPublisher;

    @InjectMocks
    private VideoService videoService;

    @Test
    void submitVideo_createsVideoWithPendingStatus_forNewUsers() {
        // Given
        var request = new CreateVideoRequest(
            "https://youtube.com/watch?v=abc123",
            Set.of(Amendment.FIRST),
            List.of(new LocationInput(40.7, -74.0))
        );
        var user = new User(UUID.randomUUID(), TrustTier.NEW);

        when(youtubeClient.getVideoMetadata("abc123")).thenReturn(new YouTubeMetadata(
            "Test Video",
            "Description",
            "https://img.youtube.com/..."
        ));
        when(videoRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        // When
        Video result = videoService.submitVideo(request, user);

        // Then
        assertThat(result.getStatus()).isEqualTo(VideoStatus.PENDING);
        assertThat(result.getYoutubeId()).isEqualTo("abc123");
        verify(eventPublisher).publish(any(VideoEvent.Submitted.class));
    }
}
```

### Integration Test Example

```java
@SpringBootTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Testcontainers
class VideoIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgis/postgis:15-3.3")
        .withDatabaseName("test");

    @Autowired
    private VideoRepository videoRepository;

    @Autowired
    private MockMvc mockMvc;

    @Test
    void postVideos_returns201_forValidSubmission() throws Exception {
        String request = """
            {
                "youtubeUrl": "https://youtube.com/watch?v=test123",
                "amendments": ["FIRST"],
                "locations": [{"lat": 40.7128, "lng": -74.0060}]
            }
            """;

        mockMvc.perform(post("/api/v1/videos")
                .contentType(MediaType.APPLICATION_JSON)
                .content(request)
                .header("Authorization", "Bearer " + validToken))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.youtubeId").value("test123"))
            .andExpect(jsonPath("$.status").value("PENDING"));
    }
}
```

---

## Database Migration Standards

### Flyway Naming

```
V{version}__{description}.sql

Examples:
V1__initial_schema.sql
V2__add_video_locations_table.sql
V3__add_amendments_index.sql
V4__add_participant_column.sql
```

### Migration Guidelines

1. **Backward Compatible**: Migrations must not break running services
2. **Idempotent**: Use `IF NOT EXISTS` where possible
3. **Small Changes**: One logical change per migration
4. **No Data Loss**: Never drop columns/tables without data migration plan

```sql
-- V2__add_video_date_column.sql
-- Add optional video_date column for when incident occurred

ALTER TABLE content.videos
ADD COLUMN IF NOT EXISTS video_date DATE;

COMMENT ON COLUMN content.videos.video_date IS
    'Date when the recorded incident occurred (may differ from upload date)';

-- Backfill can be done separately if needed
```

---

## Git Workflow

### Branch Strategy

```
main (protected)
├── Production deployments
├── Requires PR approval
└── Triggers staging deploy on merge

develop
├── Integration branch
├── Auto-deploys to dev environment
└── PRs merged here first

feature/AA-123-add-video-search
├── Feature development
├── Named: feature/{ticket}-{description}
└── PR to develop

hotfix/AA-456-fix-auth-bug
├── Production fixes
├── PR to main AND develop
└── Named: hotfix/{ticket}-{description}
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(video): add amendment filtering to video list

fix(auth): correct JWT expiry calculation

docs(api): update OpenAPI spec for search endpoint

refactor(location): extract clustering logic to separate service

test(video): add integration tests for submission flow
```

### Pull Request Requirements

- Descriptive title and description
- Link to related ticket/issue
- All tests passing
- Code review approval (1 minimum)
- No merge conflicts
- Passing linter checks

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  build:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgis/postgis:15-3.3
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 21
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'corretto'

      - name: Cache Gradle
        uses: actions/cache@v4
        with:
          path: ~/.gradle/caches
          key: ${{ runner.os }}-gradle-${{ hashFiles('**/*.gradle') }}

      - name: Run Checkstyle
        run: ./gradlew checkstyleMain checkstyleTest

      - name: Run tests
        run: ./gradlew test

      - name: Build
        run: ./gradlew build

      - name: Build Docker image
        run: docker build -t ${{ github.repository }}:${{ github.sha }} .

  deploy-dev:
    needs: build
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to dev
        run: echo "Deploy to dev environment"
        # AWS deployment steps
```

---

## Local Development

### Prerequisites

- JDK 21 (Amazon Corretto recommended)
- Docker Desktop
- IntelliJ IDEA (recommended) or VS Code with Java extensions

### Setup

```bash
# Clone repository
git clone https://github.com/org/accountabilityatlas.git
cd accountabilityatlas

# Start local dependencies
docker-compose up -d postgres redis

# Run database migrations
./gradlew flywayMigrate

# Run service
./gradlew bootRun

# Run tests
./gradlew test

# Run Checkstyle
./gradlew checkstyleMain
```

### docker-compose.yml (Local Development)

```yaml
version: '3.8'

services:
  postgres:
    image: postgis/postgis:15-3.3
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: accountabilityatlas
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  opensearch:
    image: opensearchproject/opensearch:2.11.0
    ports:
      - "9200:9200"
    environment:
      - discovery.type=single-node
      - DISABLE_SECURITY_PLUGIN=true
    volumes:
      - opensearch_data:/usr/share/opensearch/data

volumes:
  postgres_data:
  opensearch_data:
```
