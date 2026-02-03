# User Service Project Setup Design

Date: 2026-02-03
Service: AcctAtlas-user-service
Status: Approved

## Scope

Initialize the user-service repository for development: Gradle build system, project structure, Docker Compose for local dev, and TDD of the auth flow (registration + login).

## 1. Project Structure

```
AcctAtlas-user-service/
├── build.gradle
├── settings.gradle
├── gradle.properties
├── gradle/wrapper/
├── docker-compose.yml
├── src/
│   ├── main/
│   │   ├── java/com/acctatlas/user/
│   │   │   ├── UserServiceApplication.java
│   │   │   ├── config/             # Spring config (Security, Redis, JPA)
│   │   │   ├── domain/             # JPA entities
│   │   │   ├── repository/         # Spring Data JPA repositories
│   │   │   ├── service/            # Business logic
│   │   │   ├── web/                # Controller implementations
│   │   │   └── event/              # Event publisher interface + stub
│   │   └── resources/
│   │       ├── application.yml
│   │       ├── application-local.yml
│   │       └── db/migration/       # Flyway SQL migrations
│   └── test/
│       ├── java/com/acctatlas/user/
│       │   ├── service/            # Unit tests (Mockito)
│       │   ├── web/                # Controller tests (@WebMvcTest)
│       │   └── integration/        # TestContainers integration tests
│       └── resources/
│           └── application-test.yml
├── docs/                           # Existing documentation
└── .github/workflows/              # Existing CI workflows
```

## 2. Gradle Configuration

### Plugins

| Plugin | Purpose |
|--------|---------|
| `java` | Java 21 toolchain |
| `org.springframework.boot` 3.4.x | Spring Boot packaging |
| `io.spring.dependency-management` | BOM-managed dependencies |
| `com.google.cloud.tools.jib` | Docker image builds (no Dockerfile) |
| `com.diffplug.spotless` | Google Java Format enforcement |
| `net.ltgt.errorprone` | Compile-time bug detection |
| `jacoco` | Code coverage (80% line minimum) |
| `org.flywaydb.flyway` | Database migration management |
| `org.openapi.generator` | Generate controller interfaces + DTOs |

### Key Dependencies

- Spring Boot Starter Web, Security, Data JPA, Data Redis, Validation
- PostgreSQL driver, Flyway
- JJWT (JWT creation/validation)
- BCrypt (via Spring Security)
- JUnit 5, Mockito, TestContainers (Postgres, Redis)

### OpenAPI Code Generation

The `openapi-generator` plugin generates Spring server stubs from `docs/api-specification.yaml`:
- Mode: `interfaceOnly` (generates interfaces + DTOs, not implementations)
- Output: `build/generated/src/main/java`
- Added to main source set automatically
- Spotless and Error Prone skip generated code

### Custom Gradle Tasks

- `composeUp` -- runs `jibDockerBuild` then `docker-compose --profile app up -d`
- Standard tasks: `bootRun`, `test`, `spotlessApply`, `spotlessCheck`, `jibDockerBuild`

## 3. Docker Compose

```yaml
services:
  postgres:
    image: postgres:17
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: user_service
      POSTGRES_USER: user_service
      POSTGRES_PASSWORD: local_dev
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  user-service:
    image: acctatlas/user-service
    ports: ["8081:8081"]
    depends_on: [postgres, redis]
    environment:
      SPRING_PROFILES_ACTIVE: local
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/user_service
      SPRING_DATA_REDIS_HOST: redis
    profiles: ["app"]

volumes:
  pgdata:
```

Default `docker-compose up -d` starts only Postgres + Redis. The `--profile app` flag adds the service container (used by the `composeUp` Gradle task).

### Local Dev Workflow

- `docker-compose up -d` -- start Postgres + Redis
- `./gradlew bootRun` -- run service with hot reload against Docker deps
- `./gradlew jibDockerBuild` -- build Docker image
- `./gradlew composeUp` -- build image + bring up full stack in Docker
- `./gradlew spotlessApply` -- fix code formatting
- `./gradlew test` -- run all tests

## 4. Flyway Migrations

Six initial migrations based on `docs/database-schema.md`:

| Migration | Content |
|-----------|---------|
| `V1__create_users_schema.sql` | `CREATE SCHEMA users;` and `users.users` table (temporal) |
| `V2__create_user_stats_table.sql` | `users.user_stats` (non-temporal, counters) |
| `V3__create_oauth_links_table.sql` | `users.oauth_links` (temporal) |
| `V4__create_sessions_table.sql` | `users.sessions` (non-temporal) |
| `V5__create_password_resets_table.sql` | `users.password_resets` (non-temporal) |
| `V6__setup_temporal_history.sql` | History tables + triggers for temporal tables |

## 5. Spring Configuration

| File | Purpose |
|------|---------|
| `application.yml` | Shared config: JPA, Flyway, server port 8081, Jackson, logging |
| `application-local.yml` | Local dev: datasource URL, Redis host, dev JWT key pair |
| `application-test.yml` | Tests: TestContainers dynamic datasource, test JWT key pair |

### JWT

- Algorithm: RS256 (asymmetric keys per security docs)
- Access token: 15 minutes
- Refresh token: 7 days
- Local dev: generated key pair in config
- Tests: fixed test key pair

## 6. Event Publishing

Define an `EventPublisher` interface with a logging/in-memory stub implementation. The `UserRegistered` event contract is tested via unit tests. SQS implementation added later when AWS infrastructure is available.

```java
public interface EventPublisher {
    void publish(DomainEvent event);
}
```

## 7. TDD Plan: Auth Flow (Register + Login)

### Layer 0 -- Database Foundation (prerequisite)

- Write all 6 Flyway migration files
- Configure Spring application properties
- Verify migrations run against Docker Postgres

### Layer 1 -- Domain Entities (unit tests)

- `User` entity: new users get `NEW` trust tier, email normalized to lowercase
- `UserStats` entity: initialized with zero counters
- Password hashing: bcrypt cost factor 12, round-trip hash/verify

### Layer 2 -- Registration Service (unit tests, Mockito)

- Happy path: valid email + password -> save user, hash password, publish `UserRegistered`, return user
- Duplicate email -> `EmailAlreadyExistsException`
- Weak password -> validation error
- Invalid email format -> validation error

### Layer 3 -- Login Service (unit tests, Mockito)

- Happy path: correct credentials -> JWT access + refresh tokens, create session
- Wrong password -> `InvalidCredentialsException` (generic, no email leak)
- Non-existent email -> same generic error (timing-safe)
- Account locked after 5 failed attempts -> `AccountLockedException`

### Layer 4 -- Controller Tests (`@WebMvcTest`)

- `POST /api/v1/auth/register` -- 201, 409, 422
- `POST /api/v1/auth/login` -- 200, 401, 429
- Controllers implement generated OpenAPI interfaces

### Layer 5 -- Integration Tests (TestContainers)

- Full registration -> login flow against real Postgres + Redis
- Verify Flyway migrations run and data persists
- Verify sessions stored in Redis
- Verify `UserRegistered` event shape (via in-memory stub)

## Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Docker image build | Jib | Fast, reproducible, no Dockerfile needed |
| OpenAPI code gen | Yes, interfaceOnly | Keeps code and spec in sync |
| Quality tools | All from start | Spotless, Error Prone, JaCoCo enforce standards from day one |
| Event publishing | Interface + stub | Keeps setup simple; SQS impl added when infra is ready |
| First TDD scope | Auth flow (register + login) | Core foundation all other features depend on |
| Flyway location | In-service `db/migration/` | Each service owns its schema |
