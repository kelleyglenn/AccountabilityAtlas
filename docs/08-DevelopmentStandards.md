# Development Standards

## Technology Stack

### Backend Services

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Java | 21 LTS |
| Framework | Spring Boot | 3.4.x |
| Build Tool | Gradle | 9.x |
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
| Boilerplate Reduction | Lombok |
| Testing | JUnit 5, Mockito, TestContainers |
| Logging | SLF4J + Logback |
| Metrics | Micrometer |
| Code Formatting | Spotless (google-java-format) |
| Static Analysis | Error Prone, SonarLint |

---

## Project Structure

### Standard Service Layout

```
service-name/
├── build.gradle
├── settings.gradle
├── Dockerfile
├── docker-compose.yml
├── docs/
│   ├── technical.md
│   ├── api-specification.yaml
│   ├── database-schema.md
│   └── design-decisions.md
├── src/
│   ├── master/
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

## Code Quality Tools

### Java (Backend Services)

#### Spotless (Code Formatting)

Enforces consistent code style using [google-java-format](https://github.com/google/google-java-format).

```gradle
// build.gradle
plugins {
    id 'com.diffplug.spotless' version '8.2.1'
}

spotless {
    java {
        googleJavaFormat()
        removeUnusedImports()
        trimTrailingWhitespace()
        endWithNewline()
    }
}
```

Commands:
- `./gradlew spotlessCheck` - Check formatting (CI)
- `./gradlew spotlessApply` - Auto-fix formatting issues

#### Error Prone (Static Analysis)

Catches common Java bugs at compile time.

```gradle
// build.gradle
plugins {
    id 'net.ltgt.errorprone' version '5.0.0'
}

dependencies {
    errorprone 'com.google.errorprone:error_prone_core:2.45.0'
}

tasks.withType(JavaCompile).configureEach {
    options.errorprone {
        disableWarningsInGeneratedCode = true
    }
}
```

#### SonarLint (IDE Integration)

Real-time code quality feedback in the IDE.

- **IntelliJ IDEA**: Install SonarLint plugin from Marketplace
- **VS Code**: Install SonarLint extension
- **Configuration**: Connect to SonarCloud for team-shared rules (optional)

SonarLint detects:
- Code smells and maintainability issues
- Security vulnerabilities (OWASP Top 10)
- Bug patterns specific to Spring Boot

#### JaCoCo (Code Coverage)

Enforces minimum test coverage threshold.

```gradle
// build.gradle
plugins {
    id 'jacoco'
}

jacocoTestCoverageVerification {
    violationRules {
        rule {
            limit {
                minimum = 0.80  // 80% coverage required
            }
        }
    }
    afterEvaluate {
        classDirectories.setFrom(files(classDirectories.files.collect {
            fileTree(dir: it, exclude: [
                'com/accountabilityatlas/*/web/api/**',    // Generated API interfaces
                'com/accountabilityatlas/*/web/model/**',  // Generated DTOs
            ])
        }))
    }
}

check.dependsOn jacocoTestCoverageVerification
```

Commands:
- `./gradlew test jacocoTestReport` - Generate coverage report
- `./gradlew check` - Runs tests and verifies coverage threshold

#### OpenAPI Generator

Generates Spring interfaces and DTOs from OpenAPI specifications.

```gradle
// build.gradle
plugins {
    id 'org.openapi.generator' version '7.19.0'
}

openApiGenerate {
    generatorName = 'spring'
    inputSpec = "${projectDir}/docs/api-specification.yaml"
    outputDir = layout.buildDirectory.dir('generated').get().asFile.path
    apiPackage = 'com.accountabilityatlas.servicename.web.api'
    modelPackage = 'com.accountabilityatlas.servicename.web.model'
    configOptions = [
        interfaceOnly        : 'true',
        useTags              : 'true',
        useSpringBoot3       : 'true',
        documentationProvider: 'none',
        openApiNullable      : 'true',
        useJakartaEe         : 'true',
        skipDefaultInterface : 'true',
    ]
}

sourceSets.main.java.srcDir layout.buildDirectory.dir('generated/src/main/java')
compileJava.dependsOn tasks.named('openApiGenerate')
```

#### Jib (Container Images)

Builds optimized Docker images without a Dockerfile.

```gradle
// build.gradle
plugins {
    id 'com.google.cloud.tools.jib' version '3.5.2'
}

jib {
    from {
        image = 'eclipse-temurin:21-jre-alpine'
    }
    to {
        image = 'acctatlas/service-name'
        tags = [version, 'latest']
    }
    container {
        mainClass = 'com.accountabilityatlas.servicename.ServiceNameApplication'
        ports = ['8080']
    }
}
```

Commands:
- `./gradlew jibDockerBuild` - Build image to local Docker daemon
- `./gradlew jib` - Build and push to registry

#### TestContainers

Integration testing with real databases via Docker.

```gradle
// build.gradle (dependencies)
testImplementation 'org.testcontainers:testcontainers:1.21.4'
testImplementation 'org.testcontainers:junit-jupiter:1.21.4'
testImplementation 'org.testcontainers:postgresql:1.21.4'
```

```gradle
// build.gradle (test configuration)
tasks.withType(Test).configureEach {
    useJUnitPlatform()
    jvmArgs '-XX:+EnableDynamicAgentLoading'  // Fixes Mockito dynamic agent warning
}
```

### TypeScript (Frontend / Web App)

#### ESLint (Linting)

```json
// .eslintrc.json
{
  "extends": [
    "next/core-web-vitals",
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
    "prettier"
  ],
  "parser": "@typescript-eslint/parser",
  "plugins": ["@typescript-eslint"],
  "rules": {
    "@typescript-eslint/no-unused-vars": "error",
    "@typescript-eslint/explicit-function-return-type": "off",
    "@typescript-eslint/no-explicit-any": "warn",
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "warn"
  }
}
```

#### Prettier (Code Formatting)

```json
// .prettierrc
{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100
}
```

#### Package Scripts

```json
// package.json
{
  "scripts": {
    "lint": "eslint . --ext .ts,.tsx",
    "lint:fix": "eslint . --ext .ts,.tsx --fix",
    "format": "prettier --write \"src/**/*.{ts,tsx,css,json}\"",
    "format:check": "prettier --check \"src/**/*.{ts,tsx,css,json}\""
  }
}
```

#### Required Dependencies

```bash
npm install -D eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin \
  eslint-config-prettier eslint-plugin-react-hooks prettier
```

### CI Integration Summary

| Language | Formatting | Static Analysis | IDE Support |
|----------|------------|-----------------|-------------|
| Java 21 | Spotless (google-java-format) | Error Prone | SonarLint |
| TypeScript | Prettier | ESLint | ESLint + Prettier extensions |

---

## API Design Standards

### API First

Whenver an addition or modification needs to be made to an API, update the [OpenAPI Documentation](#openapi-documentation) first, and generate the Spring interfaces and DTOs using the [OpenAPI Generator](#openapi-generator).

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

Every service must provide an OpenAPI 3.1 specification:

```yaml
# docs/api-specification.yaml
openapi: 3.1.0
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

| Type | Scope | Tools | Location | Coverage Target |
|------|-------|-------|----------|-----------------|
| Unit | Single class/method, mocked dependencies | JUnit 5, Mockito | Each service repo (`unitTest`) | 80% |
| Service | Single service + real dependencies (DB, Redis) | TestContainers | Each service repo (`integrationTest`) | Key paths |
| Integration | Full stack — all services running together | Playwright (API + E2E browser tests) | `AcctAtlas-integration-tests` repo | Critical paths |

**Terminology note:** "Service tests" test one service with its real dependencies via TestContainers. "Integration tests" test the entire system end-to-end — API contract tests and browser-based E2E tests running against the full Docker Compose stack.

### TDD Approach: Outside-In

We practice outside-in Test-Driven Development. Tests are written from the outermost boundary inward, then implementation proceeds from the innermost layer outward.

**Test writing order** (outermost first):
1. **E2E tests** (Playwright, `AcctAtlas-integration-tests`) — define acceptance criteria for the feature
2. **API integration tests** (`AcctAtlas-integration-tests`) — define the API contract
3. **Service tests** (TestContainers, each service repo) — test service logic with real dependencies
4. **Unit tests** (Mockito, each service repo) — test individual classes in isolation

**Implementation order** (innermost first):
1. **Unit** — implement domain entities, mappers, validators
2. **Service** — implement service-layer logic
3. **API** — wire up controllers, run service tests
4. **E2E** — deploy full stack, run E2E suite

**Branch strategy for TDD:**
- Commit tests to feature branches early (tests will be "red" / failing)
- Create PRs only after all tests pass — CI triggers on PR creation, so committing failing tests to a branch is fine as long as no PR exists yet

This approach ensures that acceptance criteria are defined before any implementation starts, and that each layer's contract is locked in before the next layer is built.

### Unit Test Structure

Unit tests should follow the **Arrange-Act-Assert (AAA)** pattern with comments marking each section:

- **Arrange**: Set up test data, mocks, and preconditions
- **Act**: Execute the method under test
- **Assert**: Verify the expected outcomes

Always include `// Arrange`, `// Act`, `// Assert` comments to clearly delineate each phase.

### Unit Test Naming

Use the strict naming convention:

`<method>_<condition>_<expectedBehavior>`

Example: `submitVideo_newUser_createsPendingVideo`

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
        // Arrange
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

        // Act
        Video result = videoService.submitVideo(request, user);

        // Assert
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

### Common Testing Pitfalls

#### Configuration Class Dependencies

When adding new beans to shared configuration classes (like `SecurityConfig`), you may break unrelated `@WebMvcTest` tests that load that configuration.

**Example problem**: You add a `JwtAuthenticationFilter` to `SecurityConfig`:

```java
@Configuration
public class SecurityConfig {
    private final JwtAuthenticationFilter jwtAuthenticationFilter;

    public SecurityConfig(JwtAuthenticationFilter jwtAuthenticationFilter) {
        this.jwtAuthenticationFilter = jwtAuthenticationFilter;
    }
}
```

Now `AuthControllerTest` fails with `NoSuchBeanDefinitionException` for `JwtAuthenticationFilter`, even though that test doesn't use the filter.

**Solution**: Add a mock bean for the new dependency in affected tests:

```java
@WebMvcTest(AuthController.class)
class AuthControllerTest {
    @MockitoBean private JwtAuthenticationFilter jwtAuthenticationFilter;  // Required for SecurityConfig
    // ... rest of test
}
```

This pattern applies whenever you add constructor dependencies to configuration classes that are loaded by the test context.

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

### Branch Strategy (GitHub Flow)

We use [GitHub Flow](https://docs.github.com/en/get-started/using-github/github-flow), a lightweight branch-based workflow optimized for small teams and continuous deployment.

```
master (protected)
├── Always deployable
├── Requires PR approval
└── Phase 1-2: deploys to production (no staging env)
    Phase 3+: auto-deploys to staging, manual promotion to production

feature/AA-123-add-video-search
├── Created from master
├── Named: feature/{ticket}-{description} or fix/{ticket}-{description}
├── PR to master when ready
└── Delete after merge
```

**Workflow:**
1. Create a branch from `master` with a descriptive name
2. Make changes and commit with conventional commit messages
3. Open a pull request to `master`
4. After review and approval, merge to `master`
5. Phase 1-2: Changes deploy to production. Phase 3+: Changes auto-deploy to staging; promote to production after verification

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/). Include the GitHub issue number when applicable:

```
<type>(<scope>): <description> (#issue)

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
```
feat(video): add amendment filtering to video list (#42)

fix(auth): correct JWT expiry calculation (#15)

docs(api): update OpenAPI spec for search endpoint (#31)

refactor(location): extract clustering logic to separate service (#28)

test(video): add integration tests for submission flow (#45)
```

### Pull Request Requirements

- Descriptive title and description
- Use [GitHub keywords](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue) to link issues: `Closes #42`, `Fixes #15`, or `Resolves #23`
- All tests passing
- Code review approval (1 minimum)
- No merge conflicts
- Passing code quality checks (Spotless, Error Prone, ESLint)

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

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

      - name: Check code formatting (Spotless)
        run: ./gradlew spotlessCheck

      - name: Run static analysis (Error Prone)
        run: ./gradlew compileJava

      - name: Run tests
        run: ./gradlew test

      - name: Build
        run: ./gradlew build

      - name: Build Docker image
        run: docker build -t ${{ github.repository }}:${{ github.sha }} .

  deploy-staging:
    needs: build
    if: github.ref == 'refs/heads/master'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        run: echo "Deploy to staging environment"
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

# Run all tests
./gradlew test

# Run unit tests only (no Docker required)
./gradlew unitTest

# Run integration tests only (requires Docker)
./gradlew integrationTest

# Check code formatting
./gradlew spotlessCheck

# Auto-fix formatting issues
./gradlew spotlessApply
```

Note: `bootRun` automatically activates the `local` profile (`--spring.profiles.active=local`).

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
