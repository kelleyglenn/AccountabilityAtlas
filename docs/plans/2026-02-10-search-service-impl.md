# Search Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build search-service providing full-text search, faceted filtering, and autocomplete for approved videos using PostgreSQL FTS (Phase 1-2 approach).

**Architecture:** Spring Boot 3.4.x service with its own PostgreSQL database containing a denormalized `search_videos` table with a `search_vector` column (tsvector). Uses Spring Cloud Stream to consume `VideoApproved`/`VideoRejected` events from moderation-events SQS queue, fetches full video details from video-service API, and indexes locally. All search endpoints are public (no auth required).

**Tech Stack:** Java 21, Spring Boot 3.4.x, Spring Cloud Stream 4.x, Spring Cloud AWS 3.x (SQS binder), PostgreSQL 15 (FTS), Flyway, JUnit 5, TestContainers, OpenAPI Generator

**Prerequisites:**
- [LocalStack SQS Infrastructure](2026-02-10-localstack-sqs-infrastructure.md) must be completed first
- [Spring Cloud Stream SQS Integration](2026-02-10-spring-cloud-stream-sqs.md) for moderation-service must publish events

**Design Docs:**
- [event-schemas.md](../event-schemas.md)
- [05-DataArchitecture.md](../05-DataArchitecture.md#full-text-search-configuration-phase-1-2)

---

## Event Flow

```
moderation-service                     search-service                    video-service
       │                                     │                                │
       │  VideoApproved                      │                                │
       ├────────────────────────────────────►│                                │
       │  (moderation-events queue)          │  GET /videos/{id}              │
       │                                     ├───────────────────────────────►│
       │  Consumer<VideoApprovedEvent>       │◄───────────────────────────────┤
       │                                     │  Index video                   │
       │                                     │                                │
       │  VideoRejected                      │                                │
       ├────────────────────────────────────►│                                │
       │  (moderation-events queue)          │  Remove from index             │
       │                                     │                                │
```

---

## Phase 1: Project Foundation

### Task 1: Initialize Git Repository

**Files:**
- Create: `AcctAtlas-search-service/.gitignore`
- Create: `AcctAtlas-search-service/README.md`

**Step 1: Create the directory and initialize git**

Run:
```bash
cd /c/code/AccountabilityAtlas && mkdir -p AcctAtlas-search-service && cd AcctAtlas-search-service && git init
```

**Step 2: Create .gitignore**

```gitignore
# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar

# IDE
.idea/
*.iml
.vscode/
.settings/
.project
.classpath

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Environment
.env
```

**Step 3: Create README.md**

```markdown
# search-service

Full-text search service for AccountabilityAtlas. Provides search, filtering, and autocomplete for video content.

## Prerequisites

- Java 21
- Docker (for PostgreSQL and LocalStack in local development)
- Gradle 9.x (uses wrapper)

## Clone & Build

```bash
git clone <repo-url>
cd AcctAtlas-search-service
./gradlew build
```

## Local Development

```bash
# Start dependencies (from parent directory)
cd .. && docker-compose up -d postgres localstack

# Run service
./gradlew bootRun

# Service available at http://localhost:8084
```

## Docker Image

```bash
./gradlew jibDockerBuild
```

## Project Structure

```
src/main/java/com/accountabilityatlas/searchservice/
├── SearchServiceApplication.java
├── config/          # Security, web config
├── domain/          # Entities and enums
├── event/           # Spring Cloud Stream handlers
├── repository/      # Data access
├── service/         # Business logic
└── web/             # REST controllers
```

## Key Gradle Tasks

| Task | Description |
|------|-------------|
| `bootRun` | Run locally with local profile |
| `test` | Run all tests |
| `unitTest` | Run unit tests only (no Docker) |
| `integrationTest` | Run integration tests (requires Docker) |
| `check` | Full quality gate (tests + coverage) |
| `spotlessApply` | Fix code formatting |
| `jibDockerBuild` | Build Docker image |
| `composeUp` | Build image + start docker-compose |
| `composeDown` | Stop docker-compose services |

## Documentation

- [Technical Documentation](docs/technical.md)
- [API Specification](docs/api-specification.yaml)
```

**Step 4: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add .gitignore README.md
git commit -m "chore: initialize search-service repository"
```

---

### Task 2: Create Gradle Build Files

**Files:**
- Create: `AcctAtlas-search-service/settings.gradle`
- Create: `AcctAtlas-search-service/gradle.properties`
- Create: `AcctAtlas-search-service/build.gradle`

**Step 1: Create settings.gradle**

```gradle
pluginManagement {
    plugins {
        id 'org.springframework.boot' version "${springBootVersion}"
        id 'io.spring.dependency-management' version '1.1.7'
        id 'com.google.cloud.tools.jib' version "${jibVersion}"
        id 'com.diffplug.spotless' version "${spotlessVersion}"
        id 'net.ltgt.errorprone' version "${errorProneVersion}"
        id 'org.openapi.generator' version "${openApiGeneratorVersion}"
    }
}

plugins {
    id 'org.gradle.toolchains.foojay-resolver-convention' version '1.0.0'
}

rootProject.name = 'acctatlas-search-service'
```

**Step 2: Create gradle.properties**

```properties
# Spring Boot
springBootVersion=3.4.13

# Quality tools
spotlessVersion=8.2.1
errorProneVersion=5.0.0
errorProneCoreVersion=2.45.0

# OpenAPI Generator
openApiGeneratorVersion=7.19.0

# Jib
jibVersion=3.5.2

# TestContainers
testcontainersVersion=1.21.4

# springdoc
springdocVersion=2.8.14

# jackson-databind-nullable
jacksonDatabindNullableVersion=0.2.8

# Lombok
lombokVersion=1.18.42

# Spring Cloud
springCloudVersion=2024.0.0

# Spring Cloud AWS
springCloudAwsVersion=3.3.0
```

**Step 3: Create build.gradle**

```gradle
plugins {
    id 'java'
    id 'org.springframework.boot'
    id 'io.spring.dependency-management'
    id 'com.google.cloud.tools.jib'
    id 'com.diffplug.spotless'
    id 'net.ltgt.errorprone'
    id 'jacoco'
    id 'org.openapi.generator'
}

group = 'com.accountabilityatlas'
version = '0.0.1-SNAPSHOT'

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

repositories {
    mavenCentral()
}

dependencyManagement {
    imports {
        mavenBom "org.springframework.cloud:spring-cloud-dependencies:${springCloudVersion}"
    }
}

dependencies {
    // Spring Boot starters
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-actuator'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation 'org.springframework.boot:spring-boot-starter-validation'
    implementation 'org.springframework.boot:spring-boot-starter-webflux'
    implementation 'org.springframework.boot:spring-boot-starter-security'

    // Database
    runtimeOnly 'org.postgresql:postgresql'
    implementation 'org.flywaydb:flyway-core'
    implementation 'org.flywaydb:flyway-database-postgresql'

    // Spring Cloud Stream + AWS SQS
    implementation 'org.springframework.cloud:spring-cloud-stream'
    implementation "io.awspring.cloud:spring-cloud-aws-starter-sqs:${springCloudAwsVersion}"

    // OpenAPI generated code dependencies
    implementation "org.springdoc:springdoc-openapi-starter-webmvc-ui:${springdocVersion}"
    implementation "org.openapitools:jackson-databind-nullable:${jacksonDatabindNullableVersion}"
    implementation 'jakarta.validation:jakarta.validation-api'
    implementation 'jakarta.annotation:jakarta.annotation-api'

    // Lombok
    compileOnly "org.projectlombok:lombok:${lombokVersion}"
    annotationProcessor "org.projectlombok:lombok:${lombokVersion}"
    testCompileOnly "org.projectlombok:lombok:${lombokVersion}"
    testAnnotationProcessor "org.projectlombok:lombok:${lombokVersion}"

    // Error Prone
    errorprone "com.google.errorprone:error_prone_core:${errorProneCoreVersion}"

    // Testing
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'org.springframework.security:spring-security-test'
    testImplementation 'org.springframework.cloud:spring-cloud-stream-test-binder'
    testImplementation "org.testcontainers:testcontainers:${testcontainersVersion}"
    testImplementation "org.testcontainers:junit-jupiter:${testcontainersVersion}"
    testImplementation "org.testcontainers:postgresql:${testcontainersVersion}"
    testImplementation "org.testcontainers:localstack:${testcontainersVersion}"
}

// ---- OpenAPI Generator ----
openApiGenerate {
    generatorName = 'spring'
    inputSpec = "${projectDir}/docs/api-specification.yaml"
    outputDir = layout.buildDirectory.dir('generated').get().asFile.path
    apiPackage = 'com.accountabilityatlas.searchservice.web.api'
    modelPackage = 'com.accountabilityatlas.searchservice.web.model'
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

sourceSets {
    main {
        java {
            srcDir layout.buildDirectory.dir('generated/src/main/java')
        }
    }
}

compileJava.dependsOn tasks.named('openApiGenerate')

// ---- Spotless ----
spotless {
    java {
        targetExclude 'build/generated/**'
        googleJavaFormat()
        removeUnusedImports()
        trimTrailingWhitespace()
        endWithNewline()
    }
}

tasks.named('spotlessJava').configure {
    dependsOn 'openApiGenerate'
}

// ---- Error Prone ----
tasks.withType(JavaCompile).configureEach {
    options.errorprone {
        disableWarningsInGeneratedCode = true
    }
    if (name == 'compileJava') {
        options.compilerArgs += ['-Xlint:-processing']
    }
}

// ---- JaCoCo ----
jacocoTestReport {
    dependsOn test
    afterEvaluate {
        classDirectories.setFrom(files(classDirectories.files.collect {
            fileTree(dir: it, exclude: [
                'com/accountabilityatlas/searchservice/web/api/**',
                'com/accountabilityatlas/searchservice/web/model/**',
                'org/openapitools/configuration/**',
            ])
        }))
    }
}

jacocoTestCoverageVerification {
    violationRules {
        rule {
            limit {
                minimum = 0.80
            }
        }
    }
    afterEvaluate {
        classDirectories.setFrom(files(classDirectories.files.collect {
            fileTree(dir: it, exclude: [
                'com/accountabilityatlas/searchservice/web/api/**',
                'com/accountabilityatlas/searchservice/web/model/**',
                'org/openapitools/configuration/**',
            ])
        }))
    }
}

check.dependsOn jacocoTestCoverageVerification

// ---- Jib ----
jib {
    from {
        image = 'eclipse-temurin:21-jre-alpine'
    }
    to {
        image = 'acctatlas/search-service'
        tags = [version, 'latest']
    }
    container {
        mainClass = 'com.accountabilityatlas.searchservice.SearchServiceApplication'
        ports = ['8084']
        jvmFlags = ['-Djava.security.egd=file:/dev/./urandom']
    }
}

// ---- Custom Tasks ----
tasks.register('composeUp', Exec) {
    group = 'docker'
    description = 'Build Docker image and start all services via docker-compose'
    dependsOn 'jibDockerBuild'
    commandLine 'docker-compose', '--profile', 'app', 'up', '-d'
}

tasks.register('composeDown', Exec) {
    group = 'docker'
    description = 'Stop all services via docker-compose'
    commandLine 'docker-compose', '--profile', 'app', 'down'
}

// ---- Test Config ----
tasks.withType(Test).configureEach {
    useJUnitPlatform()
    jvmArgs '-XX:+EnableDynamicAgentLoading'
}

tasks.register('unitTest', Test) {
    description = 'Run unit tests only (no Docker required)'
    group = 'verification'
    testClassesDirs = sourceSets.test.output.classesDirs
    classpath = sourceSets.test.runtimeClasspath
    exclude '**/integration/**'
}

tasks.register('integrationTest', Test) {
    description = 'Run integration tests only (requires Docker)'
    group = 'verification'
    testClassesDirs = sourceSets.test.output.classesDirs
    classpath = sourceSets.test.runtimeClasspath
    include '**/integration/**'
}

// ---- Local Development ----
bootRun {
    args = ['--spring.profiles.active=local']
}
```

**Step 4: Copy Gradle wrapper from video-service**

Run:
```bash
cp -r /c/code/AccountabilityAtlas/AcctAtlas-video-service/gradle /c/code/AccountabilityAtlas/AcctAtlas-search-service/
cp /c/code/AccountabilityAtlas/AcctAtlas-video-service/gradlew /c/code/AccountabilityAtlas/AcctAtlas-search-service/
cp /c/code/AccountabilityAtlas/AcctAtlas-video-service/gradlew.bat /c/code/AccountabilityAtlas/AcctAtlas-search-service/
```

**Step 5: Set gradlew execute permission in git**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service && git update-index --chmod=+x gradlew
```

**Step 6: Verify build compiles**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service && ./gradlew clean build -x test -x openApiGenerate
```

Expected: BUILD SUCCESSFUL

**Step 7: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add settings.gradle gradle.properties build.gradle gradle gradlew gradlew.bat
git commit -m "build: add Gradle build configuration with Spring Cloud Stream"
```

---

### Task 3: Create Docker Compose

**Files:**
- Create: `AcctAtlas-search-service/docker-compose.yml`

**Step 1: Create docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: search
      POSTGRES_PASSWORD: search
      POSTGRES_DB: search
    ports:
      - "5436:5432"
    volumes:
      - search-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U search"]
      interval: 5s
      timeout: 5s
      retries: 5

  localstack:
    image: localstack/localstack:3.0
    ports:
      - "4566:4566"
    environment:
      - SERVICES=sqs
      - DEBUG=0
    volumes:
      - ./docker/localstack:/etc/localstack/init/ready.d:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 10s
      timeout: 5s
      retries: 5

  search-service:
    image: acctatlas/search-service:latest
    profiles: [app]
    ports:
      - "8084:8084"
    environment:
      SPRING_PROFILES_ACTIVE: docker
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/search
      SPRING_DATASOURCE_USERNAME: search
      SPRING_DATASOURCE_PASSWORD: search
      SPRING_CLOUD_AWS_SQS_ENDPOINT: http://localstack:4566
      SPRING_CLOUD_AWS_REGION_STATIC: us-east-1
      VIDEO_SERVICE_URL: http://host.docker.internal:8082
    depends_on:
      postgres:
        condition: service_healthy
      localstack:
        condition: service_healthy

volumes:
  search-postgres-data:
```

**Step 2: Create local LocalStack init script**

Run:
```bash
mkdir -p /c/code/AccountabilityAtlas/AcctAtlas-search-service/docker/localstack
```

Create `docker/localstack/init-queues.sh`:

```bash
#!/bin/bash
set -e
echo "Creating moderation-events queue..."
awslocal sqs create-queue --queue-name moderation-events
awslocal sqs create-queue --queue-name moderation-events-dlq
echo "Queues created:"
awslocal sqs list-queues
```

Run:
```bash
chmod +x /c/code/AccountabilityAtlas/AcctAtlas-search-service/docker/localstack/init-queues.sh
```

**Step 3: Verify docker-compose syntax**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service && docker-compose config
```

Expected: Valid YAML output, no errors

**Step 4: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add docker-compose.yml docker/
git commit -m "build: add docker-compose with LocalStack for local development"
```

---

### Task 4: Create Application Entry Point and Config

**Files:**
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/SearchServiceApplication.java`
- Create: `AcctAtlas-search-service/src/main/resources/application.yml`
- Create: `AcctAtlas-search-service/src/main/resources/application-local.yml`

**Step 1: Create main application class**

```java
package com.accountabilityatlas.searchservice;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class SearchServiceApplication {

  public static void main(String[] args) {
    SpringApplication.run(SearchServiceApplication.class, args);
  }
}
```

**Step 2: Create application.yml**

```yaml
server:
  port: 8084

spring:
  application:
    name: search-service
  jpa:
    open-in-view: false
    hibernate:
      ddl-auto: validate
    properties:
      hibernate:
        default_schema: search
  flyway:
    enabled: true
    schemas:
      - search
    locations:
      - classpath:db/migration
  jackson:
    default-property-inclusion: non_null
    serialization:
      write-dates-as-timestamps: false
  cloud:
    aws:
      region:
        static: ${AWS_REGION:us-east-1}
      credentials:
        access-key: ${AWS_ACCESS_KEY_ID:test}
        secret-key: ${AWS_SECRET_ACCESS_KEY:test}
    stream:
      bindings:
        handleVideoApproved-in-0:
          destination: moderation-events
          group: search-service
        handleVideoRejected-in-0:
          destination: moderation-events
          group: search-service
      function:
        definition: handleVideoApproved;handleVideoRejected

management:
  endpoints:
    web:
      exposure:
        include: health,info
  endpoint:
    health:
      show-details: when-authorized

logging:
  level:
    com.accountabilityatlas: DEBUG

app:
  search:
    default-page-size: 20
    max-page-size: 100
  video-service:
    base-url: ${VIDEO_SERVICE_URL:http://localhost:8082}
```

**Step 3: Create application-local.yml**

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5436/search
    username: search
    password: search
    driver-class-name: org.postgresql.Driver
  cloud:
    aws:
      sqs:
        endpoint: http://localhost:4566

logging:
  level:
    org.hibernate.SQL: DEBUG
    io.awspring.cloud: DEBUG
```

**Step 4: Start postgres for later tasks**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service && docker-compose up -d postgres
```

**Step 5: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/java/com/accountabilityatlas/searchservice/SearchServiceApplication.java
git add src/main/resources/application.yml src/main/resources/application-local.yml
git commit -m "feat: add application entry point and configuration"
```

---

### Task 5: Create Domain Entities

**Files:**
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/domain/Amendment.java`
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/domain/Participant.java`
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/domain/SearchVideo.java`

**Step 1: Create Amendment enum**

```java
package com.accountabilityatlas.searchservice.domain;

public enum Amendment {
  FIRST,
  SECOND,
  FOURTH,
  FIFTH
}
```

**Step 2: Create Participant enum**

```java
package com.accountabilityatlas.searchservice.domain;

public enum Participant {
  POLICE,
  GOVERNMENT,
  BUSINESS,
  CITIZEN
}
```

**Step 3: Create SearchVideo entity**

```java
package com.accountabilityatlas.searchservice.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "search_videos", schema = "search")
@Getter
@Setter
@NoArgsConstructor
public class SearchVideo {

  @Id
  private UUID id;

  @Column(name = "youtube_id", nullable = false, length = 11)
  private String youtubeId;

  @Column(nullable = false, length = 500)
  private String title;

  @Column(columnDefinition = "TEXT")
  private String description;

  @Column(name = "thumbnail_url", length = 500)
  private String thumbnailUrl;

  @Column(name = "duration_seconds")
  private Integer durationSeconds;

  @Column(name = "channel_id", length = 50)
  private String channelId;

  @Column(name = "channel_name")
  private String channelName;

  @Column(name = "video_date")
  private LocalDate videoDate;

  @Column(name = "amendments", columnDefinition = "VARCHAR(20)[]")
  private String[] amendments;

  @Column(name = "participants", columnDefinition = "VARCHAR(20)[]")
  private String[] participants;

  @Column(name = "primary_location_id")
  private UUID primaryLocationId;

  @Column(name = "primary_location_name")
  private String primaryLocationName;

  @Column(name = "primary_location_city")
  private String primaryLocationCity;

  @Column(name = "primary_location_state")
  private String primaryLocationState;

  @Column(name = "primary_location_lat")
  private Double primaryLocationLat;

  @Column(name = "primary_location_lng")
  private Double primaryLocationLng;

  @Column(name = "indexed_at", nullable = false)
  private Instant indexedAt;

  @Column(name = "search_vector", insertable = false, updatable = false)
  private String searchVector;
}
```

**Step 4: Verify compilation**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service && ./gradlew compileJava -x openApiGenerate
```

Expected: BUILD SUCCESSFUL

**Step 5: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/java/com/accountabilityatlas/searchservice/domain/
git commit -m "feat: add domain entities"
```

---

### Task 6: Create Database Migration

**Files:**
- Create: `AcctAtlas-search-service/src/main/resources/db/migration/V1__create_search_schema.sql`

**Step 1: Create V1 migration**

```sql
-- Create search schema
CREATE SCHEMA IF NOT EXISTS search;

-- Denormalized search_videos table
CREATE TABLE search.search_videos (
    id UUID PRIMARY KEY,
    youtube_id VARCHAR(11) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    thumbnail_url VARCHAR(500),
    duration_seconds INTEGER,
    channel_id VARCHAR(50),
    channel_name VARCHAR(255),
    video_date DATE,
    amendments VARCHAR(20)[] NOT NULL DEFAULT '{}',
    participants VARCHAR(20)[] NOT NULL DEFAULT '{}',
    primary_location_id UUID,
    primary_location_name VARCHAR(200),
    primary_location_city VARCHAR(100),
    primary_location_state VARCHAR(50),
    primary_location_lat DOUBLE PRECISION,
    primary_location_lng DOUBLE PRECISION,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_vector TSVECTOR
);

-- Trigger to maintain search_vector with weighted ranking
-- Weights: title (A), channel_name (B), description (C)
CREATE OR REPLACE FUNCTION search.update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.channel_name, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER search_videos_vector_trigger
    BEFORE INSERT OR UPDATE OF title, channel_name, description ON search.search_videos
    FOR EACH ROW EXECUTE FUNCTION search.update_search_vector();

-- Indexes
CREATE INDEX idx_search_videos_youtube_id ON search.search_videos(youtube_id);
CREATE INDEX idx_search_videos_channel_id ON search.search_videos(channel_id);
CREATE INDEX idx_search_videos_video_date ON search.search_videos(video_date);
CREATE INDEX idx_search_videos_amendments ON search.search_videos USING GIN(amendments);
CREATE INDEX idx_search_videos_participants ON search.search_videos USING GIN(participants);
CREATE INDEX idx_search_videos_state ON search.search_videos(primary_location_state);
CREATE INDEX idx_search_videos_search_vector ON search.search_videos USING GIN(search_vector);
```

**Step 2: Run migration**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service && ./gradlew flywayMigrate -Pflyway.url=jdbc:postgresql://localhost:5436/search -Pflyway.user=search -Pflyway.password=search -Pflyway.schemas=search
```

Expected: Successfully applied 1 migration

**Step 3: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/resources/db/migration/
git commit -m "feat: add database migration for search schema"
```

---

## Phase 2: Event Handling with Spring Cloud Stream

### Task 7: Create Event DTOs

**Files:**
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/event/VideoApprovedEvent.java`
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/event/VideoRejectedEvent.java`

**Step 1: Create VideoApprovedEvent**

```java
package com.accountabilityatlas.searchservice.event;

import java.time.Instant;
import java.util.UUID;

public record VideoApprovedEvent(
    String eventType,
    UUID videoId,
    UUID reviewerId,
    Instant timestamp
) {}
```

**Step 2: Create VideoRejectedEvent**

```java
package com.accountabilityatlas.searchservice.event;

import java.time.Instant;
import java.util.UUID;

public record VideoRejectedEvent(
    String eventType,
    UUID videoId,
    UUID reviewerId,
    String reason,
    String comment,
    Instant timestamp
) {}
```

**Step 3: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/java/com/accountabilityatlas/searchservice/event/
git commit -m "feat: add event DTOs for moderation events"
```

---

### Task 8: Create Video Service Client

**Files:**
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/client/VideoServiceClient.java`
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/client/VideoDetail.java`

**Step 1: Create VideoDetail DTO**

```java
package com.accountabilityatlas.searchservice.client;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

public record VideoDetail(
    UUID id,
    String youtubeId,
    String title,
    String description,
    String thumbnailUrl,
    Integer durationSeconds,
    String channelId,
    String channelName,
    LocalDate videoDate,
    List<String> amendments,
    List<String> participants,
    String status,
    OffsetDateTime createdAt,
    List<VideoLocationDetail> locations) {

  public record VideoLocationDetail(
      UUID id,
      UUID locationId,
      boolean isPrimary,
      LocationSummary location) {}

  public record LocationSummary(
      UUID id,
      String displayName,
      String city,
      String state,
      Coordinates coordinates) {}

  public record Coordinates(double latitude, double longitude) {}
}
```

**Step 2: Create VideoServiceClient**

```java
package com.accountabilityatlas.searchservice.client;

import java.util.Optional;
import java.util.UUID;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

@Component
@Slf4j
public class VideoServiceClient {

  private final WebClient webClient;

  public VideoServiceClient(
      WebClient.Builder webClientBuilder,
      @Value("${app.video-service.base-url}") String baseUrl) {
    this.webClient = webClientBuilder.baseUrl(baseUrl).build();
  }

  public Optional<VideoDetail> getVideo(UUID videoId) {
    try {
      VideoDetail video =
          webClient
              .get()
              .uri("/videos/{id}", videoId)
              .retrieve()
              .bodyToMono(VideoDetail.class)
              .block();
      return Optional.ofNullable(video);
    } catch (WebClientResponseException.NotFound e) {
      log.warn("Video not found: {}", videoId);
      return Optional.empty();
    } catch (Exception e) {
      log.error("Error fetching video {}: {}", videoId, e.getMessage());
      throw new RuntimeException("Failed to fetch video from video-service", e);
    }
  }
}
```

**Step 3: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/java/com/accountabilityatlas/searchservice/client/
git commit -m "feat: add VideoServiceClient for fetching video details"
```

---

### Task 9: Create SearchVideoRepository

**Files:**
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/repository/SearchVideoRepository.java`

**Step 1: Create repository interface**

```java
package com.accountabilityatlas.searchservice.repository;

import com.accountabilityatlas.searchservice.domain.SearchVideo;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

@Repository
public interface SearchVideoRepository extends JpaRepository<SearchVideo, UUID> {

  @Query(
      value =
          """
          SELECT v.*, ts_rank_cd(v.search_vector, plainto_tsquery('english', :query)) AS rank
          FROM search.search_videos v
          WHERE v.search_vector @@ plainto_tsquery('english', :query)
          ORDER BY rank DESC
          """,
      countQuery =
          """
          SELECT COUNT(*)
          FROM search.search_videos v
          WHERE v.search_vector @@ plainto_tsquery('english', :query)
          """,
      nativeQuery = true)
  Page<SearchVideo> searchByQuery(String query, Pageable pageable);

  @Query(
      value =
          """
          SELECT v.*, ts_rank_cd(v.search_vector, plainto_tsquery('english', :query)) AS rank
          FROM search.search_videos v
          WHERE (:query IS NULL OR :query = '' OR v.search_vector @@ plainto_tsquery('english', :query))
            AND (:amendments IS NULL OR v.amendments && CAST(:amendments AS VARCHAR[]))
            AND (:participants IS NULL OR v.participants && CAST(:participants AS VARCHAR[]))
            AND (:state IS NULL OR v.primary_location_state = :state)
          ORDER BY CASE WHEN :query IS NULL OR :query = '' THEN 0 ELSE ts_rank_cd(v.search_vector, plainto_tsquery('english', :query)) END DESC,
                   v.indexed_at DESC
          """,
      countQuery =
          """
          SELECT COUNT(*)
          FROM search.search_videos v
          WHERE (:query IS NULL OR :query = '' OR v.search_vector @@ plainto_tsquery('english', :query))
            AND (:amendments IS NULL OR v.amendments && CAST(:amendments AS VARCHAR[]))
            AND (:participants IS NULL OR v.participants && CAST(:participants AS VARCHAR[]))
            AND (:state IS NULL OR v.primary_location_state = :state)
          """,
      nativeQuery = true)
  Page<SearchVideo> searchWithFilters(
      String query, String amendments, String participants, String state, Pageable pageable);
}
```

**Step 2: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/java/com/accountabilityatlas/searchservice/repository/
git commit -m "feat: add SearchVideoRepository with FTS queries"
```

---

### Task 10: Create IndexingService

**Files:**
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/service/IndexingService.java`

**Step 1: Create IndexingService**

```java
package com.accountabilityatlas.searchservice.service;

import com.accountabilityatlas.searchservice.client.VideoDetail;
import com.accountabilityatlas.searchservice.client.VideoServiceClient;
import com.accountabilityatlas.searchservice.domain.SearchVideo;
import com.accountabilityatlas.searchservice.repository.SearchVideoRepository;
import java.time.Instant;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Slf4j
public class IndexingService {

  private final SearchVideoRepository searchVideoRepository;
  private final VideoServiceClient videoServiceClient;

  @Transactional
  public void indexVideo(UUID videoId) {
    log.info("Indexing video {}", videoId);

    var videoOpt = videoServiceClient.getVideo(videoId);
    if (videoOpt.isEmpty()) {
      log.warn("Video {} not found, skipping indexing", videoId);
      return;
    }

    VideoDetail video = videoOpt.get();
    if (!"APPROVED".equals(video.status())) {
      log.warn("Video {} is not approved (status={}), skipping indexing", videoId, video.status());
      return;
    }

    SearchVideo searchVideo =
        searchVideoRepository.findById(videoId).orElseGet(SearchVideo::new);

    mapVideoToSearchVideo(video, searchVideo);
    searchVideoRepository.save(searchVideo);

    log.info("Successfully indexed video {}", videoId);
  }

  @Transactional
  public void removeVideo(UUID videoId) {
    if (searchVideoRepository.existsById(videoId)) {
      searchVideoRepository.deleteById(videoId);
      log.info("Removed video {} from index", videoId);
    } else {
      log.debug("Video {} not found in index, nothing to remove", videoId);
    }
  }

  private void mapVideoToSearchVideo(VideoDetail video, SearchVideo searchVideo) {
    searchVideo.setId(video.id());
    searchVideo.setYoutubeId(video.youtubeId());
    searchVideo.setTitle(video.title());
    searchVideo.setDescription(video.description());
    searchVideo.setThumbnailUrl(video.thumbnailUrl());
    searchVideo.setDurationSeconds(video.durationSeconds());
    searchVideo.setChannelId(video.channelId());
    searchVideo.setChannelName(video.channelName());
    searchVideo.setVideoDate(video.videoDate());
    searchVideo.setAmendments(
        video.amendments() != null ? video.amendments().toArray(new String[0]) : new String[0]);
    searchVideo.setParticipants(
        video.participants() != null ? video.participants().toArray(new String[0]) : new String[0]);
    searchVideo.setIndexedAt(Instant.now());

    // Find primary location
    if (video.locations() != null) {
      video.locations().stream()
          .filter(VideoDetail.VideoLocationDetail::isPrimary)
          .findFirst()
          .ifPresent(
              loc -> {
                if (loc.location() != null) {
                  searchVideo.setPrimaryLocationId(loc.location().id());
                  searchVideo.setPrimaryLocationName(loc.location().displayName());
                  searchVideo.setPrimaryLocationCity(loc.location().city());
                  searchVideo.setPrimaryLocationState(loc.location().state());
                  if (loc.location().coordinates() != null) {
                    searchVideo.setPrimaryLocationLat(loc.location().coordinates().latitude());
                    searchVideo.setPrimaryLocationLng(loc.location().coordinates().longitude());
                  }
                }
              });
    }
  }
}
```

**Step 2: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/java/com/accountabilityatlas/searchservice/service/IndexingService.java
git commit -m "feat: add IndexingService for video indexing"
```

---

### Task 11: Create Spring Cloud Stream Event Handlers

**Files:**
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/event/ModerationEventHandlers.java`
- Create: `AcctAtlas-search-service/src/test/java/com/accountabilityatlas/searchservice/event/ModerationEventHandlersTest.java`

**Step 1: Write the test**

```java
package com.accountabilityatlas.searchservice.event;

import static org.mockito.Mockito.*;

import com.accountabilityatlas.searchservice.service.IndexingService;
import java.time.Instant;
import java.util.UUID;
import java.util.function.Consumer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ModerationEventHandlersTest {

  @Mock private IndexingService indexingService;
  @InjectMocks private ModerationEventHandlers handlers;

  @Test
  void handleVideoApproved_callsIndexVideo() {
    UUID videoId = UUID.randomUUID();
    VideoApprovedEvent event = new VideoApprovedEvent(
        "VideoApproved", videoId, UUID.randomUUID(), Instant.now());

    Consumer<VideoApprovedEvent> handler = handlers.handleVideoApproved();
    handler.accept(event);

    verify(indexingService).indexVideo(videoId);
  }

  @Test
  void handleVideoRejected_callsRemoveVideo() {
    UUID videoId = UUID.randomUUID();
    VideoRejectedEvent event = new VideoRejectedEvent(
        "VideoRejected", videoId, UUID.randomUUID(), "OFF_TOPIC", null, Instant.now());

    Consumer<VideoRejectedEvent> handler = handlers.handleVideoRejected();
    handler.accept(event);

    verify(indexingService).removeVideo(videoId);
  }
}
```

**Step 2: Create ModerationEventHandlers**

```java
package com.accountabilityatlas.searchservice.event;

import com.accountabilityatlas.searchservice.service.IndexingService;
import java.util.function.Consumer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@RequiredArgsConstructor
@Slf4j
public class ModerationEventHandlers {

  private final IndexingService indexingService;

  @Bean
  public Consumer<VideoApprovedEvent> handleVideoApproved() {
    return event -> {
      log.info("Received VideoApproved event for video {}", event.videoId());
      try {
        indexingService.indexVideo(event.videoId());
      } catch (Exception e) {
        log.error("Failed to index video {}: {}", event.videoId(), e.getMessage());
        throw e; // Re-throw to trigger retry/DLQ
      }
    };
  }

  @Bean
  public Consumer<VideoRejectedEvent> handleVideoRejected() {
    return event -> {
      log.info("Received VideoRejected event for video {}", event.videoId());
      try {
        indexingService.removeVideo(event.videoId());
      } catch (Exception e) {
        log.error("Failed to remove video {}: {}", event.videoId(), e.getMessage());
        throw e;
      }
    };
  }
}
```

**Step 3: Run tests**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service && ./gradlew test --tests ModerationEventHandlersTest -x openApiGenerate
```

Expected: Tests pass

**Step 4: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/java/com/accountabilityatlas/searchservice/event/ModerationEventHandlers.java
git add src/test/java/com/accountabilityatlas/searchservice/event/ModerationEventHandlersTest.java
git commit -m "feat: add Spring Cloud Stream event handlers"
```

---

## Phase 3: Search API

### Task 12: Create SearchService

**Files:**
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/service/SearchService.java`
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/service/SearchResult.java`

**Step 1: Create SearchResult record**

```java
package com.accountabilityatlas.searchservice.service;

import com.accountabilityatlas.searchservice.domain.SearchVideo;
import java.util.List;

public record SearchResult(
    List<SearchVideo> videos,
    long totalElements,
    int totalPages,
    int page,
    int size,
    long queryTimeMs) {}
```

**Step 2: Create SearchService**

```java
package com.accountabilityatlas.searchservice.service;

import com.accountabilityatlas.searchservice.domain.SearchVideo;
import com.accountabilityatlas.searchservice.repository.SearchVideoRepository;
import java.util.Set;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class SearchService {

  private final SearchVideoRepository searchVideoRepository;

  @Transactional(readOnly = true)
  public SearchResult search(
      String query,
      Set<String> amendments,
      Set<String> participants,
      String state,
      Pageable pageable) {

    long startTime = System.currentTimeMillis();

    String amendmentsArray = amendments != null && !amendments.isEmpty()
        ? toPostgresArray(amendments) : null;
    String participantsArray = participants != null && !participants.isEmpty()
        ? toPostgresArray(participants) : null;
    String searchQuery = query != null && !query.isBlank() ? query.trim() : null;

    Page<SearchVideo> page =
        searchVideoRepository.searchWithFilters(
            searchQuery, amendmentsArray, participantsArray, state, pageable);

    long queryTime = System.currentTimeMillis() - startTime;

    return new SearchResult(
        page.getContent(),
        page.getTotalElements(),
        page.getTotalPages(),
        page.getNumber(),
        page.getSize(),
        queryTime);
  }

  private String toPostgresArray(Set<String> values) {
    return "{" + String.join(",", values) + "}";
  }
}
```

**Step 3: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/java/com/accountabilityatlas/searchservice/service/SearchResult.java
git add src/main/java/com/accountabilityatlas/searchservice/service/SearchService.java
git commit -m "feat: add SearchService"
```

---

### Task 13: Create SearchController

**Files:**
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/web/SearchController.java`

**Step 1: Create SearchController**

```java
package com.accountabilityatlas.searchservice.web;

import com.accountabilityatlas.searchservice.domain.SearchVideo;
import com.accountabilityatlas.searchservice.service.SearchResult;
import com.accountabilityatlas.searchservice.service.SearchService;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/search")
@RequiredArgsConstructor
public class SearchController {

  private final SearchService searchService;

  @GetMapping
  public ResponseEntity<SearchResponse> search(
      @RequestParam(required = false) String q,
      @RequestParam(required = false) Set<String> amendments,
      @RequestParam(required = false) Set<String> participants,
      @RequestParam(required = false) String state,
      @RequestParam(defaultValue = "0") int page,
      @RequestParam(defaultValue = "20") int size) {

    if (size > 100) {
      size = 100;
    }
    Pageable pageable = PageRequest.of(page, size);

    SearchResult result = searchService.search(q, amendments, participants, state, pageable);

    SearchResponse response =
        new SearchResponse(
            result.videos().stream().map(this::toVideoResult).collect(Collectors.toList()),
            new Pagination(
                result.page(), result.size(), result.totalElements(), result.totalPages()),
            result.queryTimeMs(),
            q);

    return ResponseEntity.ok(response);
  }

  private VideoSearchResult toVideoResult(SearchVideo video) {
    LocationSummary location = null;
    if (video.getPrimaryLocationId() != null) {
      location =
          new LocationSummary(
              video.getPrimaryLocationId(),
              video.getPrimaryLocationName(),
              video.getPrimaryLocationCity(),
              video.getPrimaryLocationState(),
              video.getPrimaryLocationLat() != null && video.getPrimaryLocationLng() != null
                  ? new Coordinates(video.getPrimaryLocationLat(), video.getPrimaryLocationLng())
                  : null);
    }

    return new VideoSearchResult(
        video.getId(),
        video.getYoutubeId(),
        video.getTitle(),
        video.getDescription(),
        video.getThumbnailUrl(),
        video.getDurationSeconds(),
        video.getChannelId(),
        video.getChannelName(),
        video.getVideoDate(),
        video.getAmendments() != null ? Set.of(video.getAmendments()) : Set.of(),
        video.getParticipants() != null ? Set.of(video.getParticipants()) : Set.of(),
        location != null ? List.of(location) : List.of());
  }

  // Response DTOs
  public record SearchResponse(
      List<VideoSearchResult> results, Pagination pagination, long queryTime, String query) {}

  public record VideoSearchResult(
      UUID id,
      String youtubeId,
      String title,
      String description,
      String thumbnailUrl,
      Integer durationSeconds,
      String channelId,
      String channelName,
      java.time.LocalDate videoDate,
      Set<String> amendments,
      Set<String> participants,
      List<LocationSummary> locations) {}

  public record LocationSummary(
      UUID id, String displayName, String city, String state, Coordinates coordinates) {}

  public record Coordinates(double latitude, double longitude) {}

  public record Pagination(int page, int size, long totalElements, int totalPages) {}
}
```

**Step 2: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/java/com/accountabilityatlas/searchservice/web/SearchController.java
git commit -m "feat: add SearchController REST endpoint"
```

---

### Task 14: Create SecurityConfig

**Files:**
- Create: `AcctAtlas-search-service/src/main/java/com/accountabilityatlas/searchservice/config/SecurityConfig.java`

**Step 1: Create SecurityConfig**

```java
package com.accountabilityatlas.searchservice.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

  @Bean
  public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http.csrf(csrf -> csrf.disable())
        .sessionManagement(
            session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .authorizeHttpRequests(
            auth ->
                auth
                    // All search endpoints are public
                    .requestMatchers("/search/**")
                    .permitAll()
                    // Actuator endpoints
                    .requestMatchers("/actuator/**")
                    .permitAll()
                    .anyRequest()
                    .denyAll());

    return http.build();
  }
}
```

**Step 2: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/java/com/accountabilityatlas/searchservice/config/SecurityConfig.java
git commit -m "feat: add SecurityConfig (all search endpoints public)"
```

---

## Phase 4: Integration

### Task 15: Update Parent docker-compose

**Files:**
- Modify: `AccountabilityAtlas/docker-compose.yml`
- Modify: `AccountabilityAtlas/docker/postgres/init-databases.sql`

**Step 1: Add search-service database to init-databases.sql**

Append:
```sql
-- Search Service database
CREATE USER search_service WITH PASSWORD 'local_dev';  -- dev-only password
CREATE DATABASE search_service OWNER search_service;
GRANT ALL PRIVILEGES ON DATABASE search_service TO search_service;

\c search_service
GRANT ALL ON SCHEMA public TO search_service;
```

**Step 2: Add search-service to docker-compose.yml**

Add after existing services:

```yaml
  search-service:
    image: acctatlas/search-service:latest
    ports:
      - "8084:8084"
    environment:
      SPRING_PROFILES_ACTIVE: docker
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/search_service
      SPRING_DATASOURCE_USERNAME: search_service
      SPRING_DATASOURCE_PASSWORD: local_dev  # dev-only
      SPRING_FLYWAY_URL: jdbc:postgresql://postgres:5432/search_service
      SPRING_FLYWAY_USER: search_service
      SPRING_FLYWAY_PASSWORD: local_dev  # dev-only
      SPRING_CLOUD_AWS_SQS_ENDPOINT: http://localstack:4566
      SPRING_CLOUD_AWS_REGION_STATIC: us-east-1
      VIDEO_SERVICE_URL: http://video-service:8082
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8084/actuator/health"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    depends_on:
      postgres:
        condition: service_healthy
      localstack:
        condition: service_healthy
    profiles:
      - backend
```

**Step 3: Create application-docker.yml**

Create `AcctAtlas-search-service/src/main/resources/application-docker.yml`:

```yaml
spring:
  datasource:
    url: ${SPRING_DATASOURCE_URL}
    username: ${SPRING_DATASOURCE_USERNAME}
    password: ${SPRING_DATASOURCE_PASSWORD}
  flyway:
    url: ${SPRING_FLYWAY_URL:${SPRING_DATASOURCE_URL}}
    user: ${SPRING_FLYWAY_USER:${SPRING_DATASOURCE_USERNAME}}
    password: ${SPRING_FLYWAY_PASSWORD:${SPRING_DATASOURCE_PASSWORD}}
  cloud:
    aws:
      sqs:
        endpoint: ${SPRING_CLOUD_AWS_SQS_ENDPOINT}
```

**Step 4: Commit (parent repo)**

```bash
cd /c/code/AccountabilityAtlas
git add docker-compose.yml docker/postgres/init-databases.sql
git commit -m "feat: add search-service to docker-compose"
```

**Step 5: Commit (search-service repo)**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add src/main/resources/application-docker.yml
git commit -m "feat: add docker profile configuration"
```

---

### Task 16: Update api-gateway Routes

**Files:**
- Modify: `AcctAtlas-api-gateway/src/main/resources/application.yml`

**Step 1: Add search-service route**

Add to routes:
```yaml
        - id: search-service
          uri: ${SEARCH_SERVICE_URL:http://localhost:8084}
          predicates:
            - Path=/api/v1/search/**
          filters:
            - RewritePath=/api/v1/(?<segment>.*), /${segment}
```

**Step 2: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-api-gateway
git add src/main/resources/application.yml
git commit -m "feat: add search-service routes"
```

---

### Task 17: Run Tests and Verify

**Step 1: Run unit tests**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service && ./gradlew unitTest -x openApiGenerate
```

**Step 2: Apply spotless**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service && ./gradlew spotlessApply -x openApiGenerate
```

**Step 3: Commit any fixes**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-search-service
git add -A
git commit -m "style: apply spotless formatting" --allow-empty
```

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1-6 | Project foundation (git, gradle, docker, config, entities, migration) |
| 2 | 7-11 | Event handling (DTOs, video client, repository, indexing, Stream handlers) |
| 3 | 12-14 | Search API (service, controller, security) |
| 4 | 15-17 | Integration (docker-compose, gateway, testing) |

**Total Tasks:** 17

---

## Testing Checklist

- [ ] GET /search returns empty results when no videos indexed
- [ ] GET /search?q=test returns videos matching query
- [ ] GET /search?amendments=FIRST filters by amendment
- [ ] Spring Cloud Stream consumer receives VideoApproved event
- [ ] VideoApproved triggers fetch from video-service and indexing
- [ ] VideoRejected removes video from index
- [ ] All unit tests pass
- [ ] Application starts with `./gradlew bootRun`

---

## Dependencies

This plan requires:
1. **LocalStack SQS** - from [localstack-sqs-infrastructure plan](2026-02-10-localstack-sqs-infrastructure.md)
2. **moderation-service publishing events** - from [spring-cloud-stream-sqs plan](2026-02-10-spring-cloud-stream-sqs.md)
3. **video-service GET /videos/{id}** - already exists and works
