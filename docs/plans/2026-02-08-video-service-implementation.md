# Video Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the video-service from scratch with YouTube integration, video CRUD, location associations, and internal APIs for moderation.

**Architecture:** Spring Boot 3.4 service with PostgreSQL, OpenAPI-generated interfaces, JWT security for public endpoints, IP-based security for internal endpoints. YouTube metadata cached in Redis.

**Tech Stack:** Java 21, Spring Boot 3.4, PostgreSQL 17, Redis, Flyway, OpenAPI Generator, TestContainers, JUnit 5

**Closes:** AcctAtlas-video-service#1

---

## Task 1: Copy Gradle Build Files from location-service

**Purpose:** Set up the Gradle build configuration by copying from location-service and modifying for video-service.

**Files:**
- Create: `settings.gradle`
- Create: `gradle.properties`
- Create: `build.gradle`
- Create: `.gitignore`

**Step 1: Create settings.gradle**

Create `settings.gradle`:

```groovy
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

rootProject.name = 'acctatlas-video-service'
```

**Step 2: Create gradle.properties**

Create `gradle.properties`:

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

# Resilience4j
resilience4jVersion=2.2.0
```

**Step 3: Create build.gradle**

Create `build.gradle`:

```groovy
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

dependencies {
    // Spring Boot starters
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-actuator'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation 'org.springframework.boot:spring-boot-starter-validation'
    implementation 'org.springframework.boot:spring-boot-starter-webflux'
    implementation 'org.springframework.boot:spring-boot-starter-data-redis'
    implementation 'org.springframework.boot:spring-boot-starter-cache'
    implementation 'org.springframework.boot:spring-boot-starter-oauth2-resource-server'

    // Database
    runtimeOnly 'org.postgresql:postgresql'
    implementation 'org.flywaydb:flyway-core'
    implementation 'org.flywaydb:flyway-database-postgresql'

    // Resilience4j
    implementation "io.github.resilience4j:resilience4j-spring-boot3:${resilience4jVersion}"
    implementation "io.github.resilience4j:resilience4j-reactor:${resilience4jVersion}"

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
    testImplementation "org.testcontainers:testcontainers:${testcontainersVersion}"
    testImplementation "org.testcontainers:junit-jupiter:${testcontainersVersion}"
    testImplementation "org.testcontainers:postgresql:${testcontainersVersion}"
    testImplementation 'com.squareup.okhttp3:mockwebserver'
}

// ---- OpenAPI Generator ----
openApiGenerate {
    generatorName = 'spring'
    inputSpec = "${projectDir}/docs/api-specification.yaml"
    outputDir = layout.buildDirectory.dir('generated').get().asFile.path
    apiPackage = 'com.accountabilityatlas.videoservice.web.api'
    modelPackage = 'com.accountabilityatlas.videoservice.web.model'
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
                'com/accountabilityatlas/videoservice/web/api/**',
                'com/accountabilityatlas/videoservice/web/model/**',
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
                'com/accountabilityatlas/videoservice/web/api/**',
                'com/accountabilityatlas/videoservice/web/model/**',
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
        image = 'acctatlas/video-service'
        tags = [version, 'latest']
    }
    container {
        mainClass = 'com.accountabilityatlas.videoservice.VideoServiceApplication'
        ports = ['8082']
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

**Step 4: Update .gitignore**

Update `.gitignore`:

```
# Gradle
.gradle/
build/
!gradle/wrapper/gradle-wrapper.jar

# IDE
.idea/
*.iml
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Environment
.env
.env.local
```

**Step 5: Copy Gradle wrapper from location-service**

Run:
```bash
cp -r ../AcctAtlas-location-service/gradle ./
cp ../AcctAtlas-location-service/gradlew ./
cp ../AcctAtlas-location-service/gradlew.bat ./
git update-index --chmod=+x gradlew
```

**Step 6: Verify build compiles**

Run:
```bash
./gradlew openApiGenerate
```

Expected: OpenAPI generates interfaces and models in `build/generated/`.

**Step 7: Commit**

Run:
```bash
git add settings.gradle gradle.properties build.gradle .gitignore gradle gradlew gradlew.bat
git commit -m "chore: add Gradle build configuration

- Copy build setup from location-service
- Add Resilience4j and Redis dependencies
- Configure OpenAPI generator for video-service

Refs: #1"
```

---

## Task 2: Create docker-compose and Application Config

**Purpose:** Set up local development infrastructure and Spring Boot configuration.

**Files:**
- Create: `docker-compose.yml`
- Create: `src/main/resources/application.yml`
- Create: `src/main/resources/application-local.yml`

**Step 1: Create docker-compose.yml**

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:17-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: video_service
      POSTGRES_USER: video_service
      POSTGRES_PASSWORD: local_dev
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U video_service"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  video-service:
    image: acctatlas/video-service
    ports:
      - "8082:8082"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      SPRING_PROFILES_ACTIVE: local
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/video_service
      SPRING_DATASOURCE_USERNAME: video_service
      SPRING_DATASOURCE_PASSWORD: local_dev
      SPRING_DATA_REDIS_HOST: redis
      YOUTUBE_API_KEY: ${YOUTUBE_API_KEY:-}
    profiles:
      - app

volumes:
  pgdata:
```

**Step 2: Create application.yml**

Create `src/main/resources/application.yml`:

```yaml
server:
  port: 8082

spring:
  application:
    name: video-service
  jpa:
    open-in-view: false
    hibernate:
      ddl-auto: validate
    properties:
      hibernate:
        default_schema: videos
  flyway:
    enabled: true
    schemas:
      - videos
    locations:
      - classpath:db/migration
  jackson:
    default-property-inclusion: non_null
    serialization:
      write-dates-as-timestamps: false
  cache:
    type: redis
  data:
    redis:
      host: ${SPRING_DATA_REDIS_HOST:localhost}
      port: ${SPRING_DATA_REDIS_PORT:6379}

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
  youtube:
    api-key: ${YOUTUBE_API_KEY:}
    base-url: https://www.googleapis.com/youtube/v3
    cache-ttl: 24h
    timeout: 5s
  location-service:
    base-url: ${LOCATION_SERVICE_URL:http://localhost:8083}
  internal:
    allowed-cidrs:
      - 10.0.0.0/8
      - 172.16.0.0/12
      - 127.0.0.1/32

resilience4j:
  circuitbreaker:
    instances:
      youtube:
        slidingWindowSize: 5
        failureRateThreshold: 50
        waitDurationInOpenState: 30s
  retry:
    instances:
      youtube:
        maxAttempts: 3
        waitDuration: 1s
        exponentialBackoffMultiplier: 2
  timelimiter:
    instances:
      youtube:
        timeoutDuration: 5s
```

**Step 3: Create application-local.yml**

Create `src/main/resources/application-local.yml`:

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/video_service
    username: video_service
    password: local_dev

logging:
  level:
    org.springframework.web: DEBUG
    org.hibernate.SQL: DEBUG
```

**Step 4: Create directory structure**

Run:
```bash
mkdir -p src/main/java/com/accountabilityatlas/videoservice
mkdir -p src/main/resources/db/migration
mkdir -p src/test/java/com/accountabilityatlas/videoservice
```

**Step 5: Create main application class**

Create `src/main/java/com/accountabilityatlas/videoservice/VideoServiceApplication.java`:

```java
package com.accountabilityatlas.videoservice;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;

@SpringBootApplication
@EnableCaching
public class VideoServiceApplication {

  public static void main(String[] args) {
    SpringApplication.run(VideoServiceApplication.class, args);
  }
}
```

**Step 6: Commit**

Run:
```bash
git add docker-compose.yml src/
git commit -m "chore: add docker-compose and application config

- PostgreSQL and Redis for local development
- Spring Boot configuration with Flyway, Redis caching
- YouTube and location-service client settings
- Resilience4j circuit breaker config

Refs: #1"
```

---

## Task 3: Create Database Migrations

**Purpose:** Set up the videos schema with tables for videos and video_locations.

**Files:**
- Create: `src/main/resources/db/migration/V1__create_videos_schema.sql`
- Create: `src/main/resources/db/migration/V2__create_videos_table.sql`
- Create: `src/main/resources/db/migration/V3__create_video_locations_table.sql`

**Step 1: Create schema migration**

Create `src/main/resources/db/migration/V1__create_videos_schema.sql`:

```sql
CREATE SCHEMA IF NOT EXISTS videos;
```

**Step 2: Create videos table migration**

Create `src/main/resources/db/migration/V2__create_videos_table.sql`:

```sql
CREATE TABLE videos.videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    youtube_id VARCHAR(11) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    thumbnail_url VARCHAR(500),
    duration_seconds INTEGER,
    channel_id VARCHAR(50),
    channel_name VARCHAR(255),
    published_at TIMESTAMPTZ,
    video_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    submitted_by UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sys_period tstzrange NOT NULL DEFAULT tstzrange(NOW(), NULL),

    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'DELETED'))
);

-- Amendments (element collection)
CREATE TABLE videos.video_amendments (
    video_id UUID NOT NULL REFERENCES videos.videos(id) ON DELETE CASCADE,
    amendment VARCHAR(20) NOT NULL,
    PRIMARY KEY (video_id, amendment),
    CONSTRAINT valid_amendment CHECK (amendment IN ('FIRST', 'SECOND', 'FOURTH', 'FIFTH'))
);

-- Participants (element collection)
CREATE TABLE videos.video_participants (
    video_id UUID NOT NULL REFERENCES videos.videos(id) ON DELETE CASCADE,
    participant VARCHAR(20) NOT NULL,
    PRIMARY KEY (video_id, participant),
    CONSTRAINT valid_participant CHECK (participant IN ('POLICE', 'GOVERNMENT', 'BUSINESS', 'CITIZEN'))
);

-- Indexes
CREATE INDEX idx_videos_youtube_id ON videos.videos(youtube_id);
CREATE INDEX idx_videos_status ON videos.videos(status);
CREATE INDEX idx_videos_submitted_by ON videos.videos(submitted_by);
CREATE INDEX idx_videos_created_at ON videos.videos(created_at);
```

**Step 3: Create video_locations table migration**

Create `src/main/resources/db/migration/V3__create_video_locations_table.sql`:

```sql
CREATE TABLE videos.video_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos.videos(id) ON DELETE CASCADE,
    location_id UUID NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    display_name VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sys_period tstzrange NOT NULL DEFAULT tstzrange(NOW(), NULL),

    CONSTRAINT unique_video_location UNIQUE (video_id, location_id)
);

-- Indexes
CREATE INDEX idx_video_locations_video_id ON videos.video_locations(video_id);
CREATE INDEX idx_video_locations_location_id ON videos.video_locations(location_id);
```

**Step 4: Start postgres and verify migrations**

Run:
```bash
docker-compose up -d postgres
sleep 5
./gradlew flywayMigrate -i
```

Expected: Migrations run successfully, schema created.

**Step 5: Commit**

Run:
```bash
git add src/main/resources/db/migration/
git commit -m "feat: add database migrations for videos schema

- V1: Create videos schema
- V2: Create videos table with amendments/participants
- V3: Create video_locations table with cached location data

Refs: #1"
```

---

## Task 4: Create Domain Entities

**Purpose:** Create JPA entities for Video and VideoLocation, plus enums.

**Files:**
- Create: `src/main/java/com/accountabilityatlas/videoservice/domain/Amendment.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/domain/Participant.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/domain/VideoStatus.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/domain/Video.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/domain/VideoLocation.java`

**Step 1: Create Amendment enum**

Create `src/main/java/com/accountabilityatlas/videoservice/domain/Amendment.java`:

```java
package com.accountabilityatlas.videoservice.domain;

public enum Amendment {
  FIRST,
  SECOND,
  FOURTH,
  FIFTH
}
```

**Step 2: Create Participant enum**

Create `src/main/java/com/accountabilityatlas/videoservice/domain/Participant.java`:

```java
package com.accountabilityatlas.videoservice.domain;

public enum Participant {
  POLICE,
  GOVERNMENT,
  BUSINESS,
  CITIZEN
}
```

**Step 3: Create VideoStatus enum**

Create `src/main/java/com/accountabilityatlas/videoservice/domain/VideoStatus.java`:

```java
package com.accountabilityatlas.videoservice.domain;

public enum VideoStatus {
  PENDING,
  APPROVED,
  REJECTED,
  DELETED
}
```

**Step 4: Create Video entity**

Create `src/main/java/com/accountabilityatlas/videoservice/domain/Video.java`:

```java
package com.accountabilityatlas.videoservice.domain;

import jakarta.persistence.*;
import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.Setter;

@Entity
@Table(name = "videos", schema = "videos")
@Getter
@Setter
public class Video {

  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;

  @Column(name = "youtube_id", nullable = false, unique = true, length = 11)
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

  @Column(name = "channel_name", length = 255)
  private String channelName;

  @Column(name = "published_at")
  private Instant publishedAt;

  @Column(name = "video_date")
  private LocalDate videoDate;

  @ElementCollection(fetch = FetchType.EAGER)
  @CollectionTable(
      name = "video_amendments",
      schema = "videos",
      joinColumns = @JoinColumn(name = "video_id"))
  @Column(name = "amendment")
  @Enumerated(EnumType.STRING)
  private Set<Amendment> amendments = new HashSet<>();

  @ElementCollection(fetch = FetchType.EAGER)
  @CollectionTable(
      name = "video_participants",
      schema = "videos",
      joinColumns = @JoinColumn(name = "video_id"))
  @Column(name = "participant")
  @Enumerated(EnumType.STRING)
  private Set<Participant> participants = new HashSet<>();

  @Enumerated(EnumType.STRING)
  @Column(nullable = false, length = 20)
  private VideoStatus status = VideoStatus.PENDING;

  @Column(name = "submitted_by", nullable = false)
  private UUID submittedBy;

  @OneToMany(mappedBy = "video", cascade = CascadeType.ALL, orphanRemoval = true)
  private List<VideoLocation> locations = new ArrayList<>();

  @Column(name = "created_at", nullable = false, updatable = false)
  private Instant createdAt = Instant.now();

  @Setter(AccessLevel.NONE)
  @Column(name = "sys_period", insertable = false, updatable = false)
  private String sysPeriod;

  public void addLocation(VideoLocation location) {
    locations.add(location);
    location.setVideo(this);
  }

  public void removeLocation(VideoLocation location) {
    locations.remove(location);
    location.setVideo(null);
  }
}
```

**Step 5: Create VideoLocation entity**

Create `src/main/java/com/accountabilityatlas/videoservice/domain/VideoLocation.java`:

```java
package com.accountabilityatlas.videoservice.domain;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.Setter;

@Entity
@Table(name = "video_locations", schema = "videos")
@Getter
@Setter
public class VideoLocation {

  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "video_id", nullable = false)
  private Video video;

  @Column(name = "location_id", nullable = false)
  private UUID locationId;

  @Column(name = "is_primary", nullable = false)
  private boolean primary;

  @Column(name = "display_name", length = 255)
  private String displayName;

  @Column(length = 100)
  private String city;

  @Column(length = 100)
  private String state;

  private Double latitude;

  private Double longitude;

  @Column(name = "created_at", nullable = false, updatable = false)
  private Instant createdAt = Instant.now();

  @Setter(AccessLevel.NONE)
  @Column(name = "sys_period", insertable = false, updatable = false)
  private String sysPeriod;
}
```

**Step 6: Verify build compiles**

Run:
```bash
./gradlew compileJava
```

Expected: BUILD SUCCESSFUL

**Step 7: Commit**

Run:
```bash
git add src/main/java/com/accountabilityatlas/videoservice/domain/
git commit -m "feat: add domain entities

- Video entity with amendments, participants, status
- VideoLocation entity with cached location data
- Amendment, Participant, VideoStatus enums

Refs: #1"
```

---

## Task 5: Create Repositories

**Purpose:** Create Spring Data JPA repositories for Video and VideoLocation.

**Files:**
- Create: `src/main/java/com/accountabilityatlas/videoservice/repository/VideoRepository.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/repository/VideoLocationRepository.java`

**Step 1: Create VideoRepository**

Create `src/main/java/com/accountabilityatlas/videoservice/repository/VideoRepository.java`:

```java
package com.accountabilityatlas.videoservice.repository;

import com.accountabilityatlas.videoservice.domain.Video;
import com.accountabilityatlas.videoservice.domain.VideoStatus;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

@Repository
public interface VideoRepository extends JpaRepository<Video, UUID> {

  Optional<Video> findByYoutubeId(String youtubeId);

  boolean existsByYoutubeId(String youtubeId);

  Page<Video> findByStatus(VideoStatus status, Pageable pageable);

  Page<Video> findBySubmittedBy(UUID submittedBy, Pageable pageable);

  Page<Video> findBySubmittedByAndStatus(UUID submittedBy, VideoStatus status, Pageable pageable);

  @Query(
      """
      SELECT v FROM Video v
      WHERE v.status = :status
      ORDER BY v.createdAt DESC
      """)
  Page<Video> findByStatusOrderByCreatedAtDesc(VideoStatus status, Pageable pageable);
}
```

**Step 2: Create VideoLocationRepository**

Create `src/main/java/com/accountabilityatlas/videoservice/repository/VideoLocationRepository.java`:

```java
package com.accountabilityatlas.videoservice.repository;

import com.accountabilityatlas.videoservice.domain.VideoLocation;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

@Repository
public interface VideoLocationRepository extends JpaRepository<VideoLocation, UUID> {

  List<VideoLocation> findByVideoId(UUID videoId);

  Optional<VideoLocation> findByVideoIdAndLocationId(UUID videoId, UUID locationId);

  boolean existsByVideoIdAndLocationId(UUID videoId, UUID locationId);

  @Modifying
  @Query("UPDATE VideoLocation vl SET vl.primary = false WHERE vl.video.id = :videoId")
  void clearPrimaryForVideo(UUID videoId);

  Optional<VideoLocation> findByVideoIdAndPrimaryTrue(UUID videoId);
}
```

**Step 3: Verify build compiles**

Run:
```bash
./gradlew compileJava
```

Expected: BUILD SUCCESSFUL

**Step 4: Commit**

Run:
```bash
git add src/main/java/com/accountabilityatlas/videoservice/repository/
git commit -m "feat: add JPA repositories

- VideoRepository with status and submitter queries
- VideoLocationRepository with video-location lookups

Refs: #1"
```

---

## Task 6: Create YouTube Service

**Purpose:** Create the YouTube API client with URL parsing and metadata fetching.

**Files:**
- Create: `src/main/java/com/accountabilityatlas/videoservice/config/YouTubeProperties.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/service/YouTubeService.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/exception/InvalidYouTubeUrlException.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/exception/YouTubeVideoNotFoundException.java`
- Create: `src/test/java/com/accountabilityatlas/videoservice/service/YouTubeServiceTest.java`

**Step 1: Create YouTubeProperties**

Create `src/main/java/com/accountabilityatlas/videoservice/config/YouTubeProperties.java`:

```java
package com.accountabilityatlas.videoservice.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;
import lombok.Getter;
import lombok.Setter;

@Component
@ConfigurationProperties(prefix = "app.youtube")
@Getter
@Setter
public class YouTubeProperties {

  private String apiKey;
  private String baseUrl = "https://www.googleapis.com/youtube/v3";
  private Duration cacheTtl = Duration.ofHours(24);
  private Duration timeout = Duration.ofSeconds(5);
}
```

**Step 2: Create exceptions**

Create `src/main/java/com/accountabilityatlas/videoservice/exception/InvalidYouTubeUrlException.java`:

```java
package com.accountabilityatlas.videoservice.exception;

public class InvalidYouTubeUrlException extends RuntimeException {

  public InvalidYouTubeUrlException(String url) {
    super("Invalid YouTube URL: " + url);
  }
}
```

Create `src/main/java/com/accountabilityatlas/videoservice/exception/YouTubeVideoNotFoundException.java`:

```java
package com.accountabilityatlas.videoservice.exception;

public class YouTubeVideoNotFoundException extends RuntimeException {

  public YouTubeVideoNotFoundException(String videoId) {
    super("YouTube video not found: " + videoId);
  }
}
```

**Step 3: Create YouTubeService**

Create `src/main/java/com/accountabilityatlas/videoservice/service/YouTubeService.java`:

```java
package com.accountabilityatlas.videoservice.service;

import com.accountabilityatlas.videoservice.config.YouTubeProperties;
import com.accountabilityatlas.videoservice.exception.InvalidYouTubeUrlException;
import com.accountabilityatlas.videoservice.exception.YouTubeVideoNotFoundException;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

@Service
public class YouTubeService {

  private static final List<Pattern> YOUTUBE_PATTERNS =
      List.of(
          Pattern.compile("youtube\\.com/watch\\?v=([\\w-]{11})"),
          Pattern.compile("youtu\\.be/([\\w-]{11})"),
          Pattern.compile("youtube\\.com/embed/([\\w-]{11})"));

  private final WebClient webClient;
  private final YouTubeProperties properties;

  public YouTubeService(WebClient.Builder webClientBuilder, YouTubeProperties properties) {
    this.properties = properties;
    this.webClient =
        webClientBuilder
            .baseUrl(properties.getBaseUrl())
            .build();
  }

  public record YouTubeMetadata(
      String videoId,
      String title,
      String description,
      String thumbnailUrl,
      Integer durationSeconds,
      String channelId,
      String channelName,
      Instant publishedAt) {}

  public String extractVideoId(String url) {
    if (url == null || url.isBlank()) {
      throw new InvalidYouTubeUrlException(url);
    }

    for (Pattern pattern : YOUTUBE_PATTERNS) {
      Matcher matcher = pattern.matcher(url);
      if (matcher.find()) {
        return matcher.group(1);
      }
    }

    throw new InvalidYouTubeUrlException(url);
  }

  @Cacheable(value = "youtube-metadata", key = "#videoId")
  @CircuitBreaker(name = "youtube")
  @Retry(name = "youtube")
  public YouTubeMetadata fetchMetadata(String videoId) {
    try {
      var response =
          webClient
              .get()
              .uri(
                  uriBuilder ->
                      uriBuilder
                          .path("/videos")
                          .queryParam("id", videoId)
                          .queryParam("key", properties.getApiKey())
                          .queryParam("part", "snippet,contentDetails")
                          .build())
              .retrieve()
              .bodyToMono(YouTubeApiResponse.class)
              .block(properties.getTimeout());

      if (response == null || response.items() == null || response.items().isEmpty()) {
        throw new YouTubeVideoNotFoundException(videoId);
      }

      var item = response.items().get(0);
      var snippet = item.snippet();
      var contentDetails = item.contentDetails();

      return new YouTubeMetadata(
          videoId,
          snippet.title(),
          snippet.description(),
          selectBestThumbnail(snippet.thumbnails()),
          parseDuration(contentDetails.duration()),
          snippet.channelId(),
          snippet.channelTitle(),
          Instant.parse(snippet.publishedAt()));

    } catch (WebClientResponseException.NotFound e) {
      throw new YouTubeVideoNotFoundException(videoId);
    }
  }

  private String selectBestThumbnail(Thumbnails thumbnails) {
    if (thumbnails.maxres() != null) return thumbnails.maxres().url();
    if (thumbnails.high() != null) return thumbnails.high().url();
    if (thumbnails.medium() != null) return thumbnails.medium().url();
    if (thumbnails.standard() != null) return thumbnails.standard().url();
    return thumbnails.defaultThumb() != null ? thumbnails.defaultThumb().url() : null;
  }

  private Integer parseDuration(String isoDuration) {
    if (isoDuration == null) return null;
    try {
      return (int) Duration.parse(isoDuration).toSeconds();
    } catch (Exception e) {
      return null;
    }
  }

  // DTOs for YouTube API response
  record YouTubeApiResponse(List<VideoItem> items) {}

  record VideoItem(Snippet snippet, ContentDetails contentDetails) {}

  record Snippet(
      String title,
      String description,
      String channelId,
      String channelTitle,
      String publishedAt,
      Thumbnails thumbnails) {}

  record ContentDetails(String duration) {}

  record Thumbnails(
      Thumbnail defaultThumb,
      Thumbnail medium,
      Thumbnail high,
      Thumbnail standard,
      Thumbnail maxres) {}

  record Thumbnail(String url, int width, int height) {}
}
```

**Step 4: Create unit test for URL parsing**

Create `src/test/java/com/accountabilityatlas/videoservice/service/YouTubeServiceTest.java`:

```java
package com.accountabilityatlas.videoservice.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.accountabilityatlas.videoservice.config.YouTubeProperties;
import com.accountabilityatlas.videoservice.exception.InvalidYouTubeUrlException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

class YouTubeServiceTest {

  private YouTubeService youTubeService;

  @BeforeEach
  void setUp() {
    YouTubeProperties properties = new YouTubeProperties();
    properties.setApiKey("test-key");
    youTubeService = new YouTubeService(WebClient.builder(), properties);
  }

  @Test
  void extractVideoId_standardUrl() {
    String url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";
    assertThat(youTubeService.extractVideoId(url)).isEqualTo("dQw4w9WgXcQ");
  }

  @Test
  void extractVideoId_shortUrl() {
    String url = "https://youtu.be/dQw4w9WgXcQ";
    assertThat(youTubeService.extractVideoId(url)).isEqualTo("dQw4w9WgXcQ");
  }

  @Test
  void extractVideoId_embedUrl() {
    String url = "https://www.youtube.com/embed/dQw4w9WgXcQ";
    assertThat(youTubeService.extractVideoId(url)).isEqualTo("dQw4w9WgXcQ");
  }

  @Test
  void extractVideoId_withQueryParams() {
    String url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120";
    assertThat(youTubeService.extractVideoId(url)).isEqualTo("dQw4w9WgXcQ");
  }

  @Test
  void extractVideoId_invalidUrl_throws() {
    String url = "https://vimeo.com/123456";
    assertThatThrownBy(() -> youTubeService.extractVideoId(url))
        .isInstanceOf(InvalidYouTubeUrlException.class)
        .hasMessageContaining("Invalid YouTube URL");
  }

  @Test
  void extractVideoId_nullUrl_throws() {
    assertThatThrownBy(() -> youTubeService.extractVideoId(null))
        .isInstanceOf(InvalidYouTubeUrlException.class);
  }

  @Test
  void extractVideoId_blankUrl_throws() {
    assertThatThrownBy(() -> youTubeService.extractVideoId("  "))
        .isInstanceOf(InvalidYouTubeUrlException.class);
  }
}
```

**Step 5: Run tests**

Run:
```bash
./gradlew test --tests YouTubeServiceTest
```

Expected: All tests pass.

**Step 6: Commit**

Run:
```bash
git add src/main/java/com/accountabilityatlas/videoservice/config/YouTubeProperties.java \
  src/main/java/com/accountabilityatlas/videoservice/service/YouTubeService.java \
  src/main/java/com/accountabilityatlas/videoservice/exception/ \
  src/test/java/com/accountabilityatlas/videoservice/service/YouTubeServiceTest.java
git commit -m "feat: add YouTube service with URL parsing

- YouTubeService with extractVideoId and fetchMetadata
- Circuit breaker and retry via Resilience4j
- Redis caching for metadata
- Unit tests for URL pattern matching

Refs: #1"
```

---

## Task 7: Create Video Service

**Purpose:** Create the business logic layer for video CRUD operations.

**Files:**
- Create: `src/main/java/com/accountabilityatlas/videoservice/service/VideoService.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/exception/VideoNotFoundException.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/exception/VideoAlreadyExistsException.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/exception/UnauthorizedException.java`

**Step 1: Create exceptions**

Create `src/main/java/com/accountabilityatlas/videoservice/exception/VideoNotFoundException.java`:

```java
package com.accountabilityatlas.videoservice.exception;

import java.util.UUID;

public class VideoNotFoundException extends RuntimeException {

  public VideoNotFoundException(UUID id) {
    super("Video not found: " + id);
  }
}
```

Create `src/main/java/com/accountabilityatlas/videoservice/exception/VideoAlreadyExistsException.java`:

```java
package com.accountabilityatlas.videoservice.exception;

public class VideoAlreadyExistsException extends RuntimeException {

  public VideoAlreadyExistsException(String youtubeId) {
    super("Video already exists with YouTube ID: " + youtubeId);
  }
}
```

Create `src/main/java/com/accountabilityatlas/videoservice/exception/UnauthorizedException.java`:

```java
package com.accountabilityatlas.videoservice.exception;

public class UnauthorizedException extends RuntimeException {

  public UnauthorizedException(String message) {
    super(message);
  }
}
```

**Step 2: Create VideoService**

Create `src/main/java/com/accountabilityatlas/videoservice/service/VideoService.java`:

```java
package com.accountabilityatlas.videoservice.service;

import com.accountabilityatlas.videoservice.domain.Amendment;
import com.accountabilityatlas.videoservice.domain.Participant;
import com.accountabilityatlas.videoservice.domain.Video;
import com.accountabilityatlas.videoservice.domain.VideoStatus;
import com.accountabilityatlas.videoservice.exception.UnauthorizedException;
import com.accountabilityatlas.videoservice.exception.VideoAlreadyExistsException;
import com.accountabilityatlas.videoservice.exception.VideoNotFoundException;
import com.accountabilityatlas.videoservice.repository.VideoRepository;
import com.accountabilityatlas.videoservice.service.YouTubeService.YouTubeMetadata;
import java.time.LocalDate;
import java.util.Set;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class VideoService {

  private final VideoRepository videoRepository;
  private final YouTubeService youTubeService;

  @Transactional(readOnly = true)
  public Video getVideo(UUID id) {
    return videoRepository.findById(id).orElseThrow(() -> new VideoNotFoundException(id));
  }

  @Transactional(readOnly = true)
  public Page<Video> listVideos(VideoStatus status, Pageable pageable) {
    if (status == null) {
      status = VideoStatus.APPROVED;
    }
    return videoRepository.findByStatusOrderByCreatedAtDesc(status, pageable);
  }

  @Transactional(readOnly = true)
  public Page<Video> listVideosByUser(UUID userId, VideoStatus status, Pageable pageable) {
    if (status != null) {
      return videoRepository.findBySubmittedByAndStatus(userId, status, pageable);
    }
    return videoRepository.findBySubmittedBy(userId, pageable);
  }

  @Transactional
  public Video createVideo(
      String youtubeUrl,
      Set<Amendment> amendments,
      Set<Participant> participants,
      LocalDate videoDate,
      UUID submittedBy) {

    String videoId = youTubeService.extractVideoId(youtubeUrl);

    if (videoRepository.existsByYoutubeId(videoId)) {
      throw new VideoAlreadyExistsException(videoId);
    }

    YouTubeMetadata metadata = youTubeService.fetchMetadata(videoId);

    Video video = new Video();
    video.setYoutubeId(videoId);
    video.setTitle(metadata.title());
    video.setDescription(metadata.description());
    video.setThumbnailUrl(metadata.thumbnailUrl());
    video.setDurationSeconds(metadata.durationSeconds());
    video.setChannelId(metadata.channelId());
    video.setChannelName(metadata.channelName());
    video.setPublishedAt(metadata.publishedAt());
    video.setVideoDate(videoDate);
    video.setAmendments(amendments);
    video.setParticipants(participants);
    video.setStatus(VideoStatus.PENDING);
    video.setSubmittedBy(submittedBy);

    return videoRepository.save(video);
  }

  @Transactional
  public Video updateVideo(
      UUID id,
      Set<Amendment> amendments,
      Set<Participant> participants,
      LocalDate videoDate,
      UUID currentUserId) {

    Video video = getVideo(id);

    if (!canModify(video, currentUserId)) {
      throw new UnauthorizedException("You do not have permission to modify this video");
    }

    if (amendments != null && !amendments.isEmpty()) {
      video.setAmendments(amendments);
    }
    if (participants != null && !participants.isEmpty()) {
      video.setParticipants(participants);
    }
    if (videoDate != null) {
      video.setVideoDate(videoDate);
    }

    return videoRepository.save(video);
  }

  @Transactional
  public void deleteVideo(UUID id, UUID currentUserId) {
    Video video = getVideo(id);

    if (!canModify(video, currentUserId)) {
      throw new UnauthorizedException("You do not have permission to delete this video");
    }

    video.setStatus(VideoStatus.DELETED);
    videoRepository.save(video);
  }

  @Transactional
  public Video updateVideoInternal(
      UUID id, Set<Amendment> amendments, Set<Participant> participants, LocalDate videoDate) {

    Video video = getVideo(id);

    if (amendments != null && !amendments.isEmpty()) {
      video.setAmendments(amendments);
    }
    if (participants != null && !participants.isEmpty()) {
      video.setParticipants(participants);
    }
    if (videoDate != null) {
      video.setVideoDate(videoDate);
    }

    return videoRepository.save(video);
  }

  @Transactional
  public Video updateVideoStatus(UUID id, VideoStatus status) {
    Video video = getVideo(id);
    video.setStatus(status);
    return videoRepository.save(video);
  }

  private boolean canModify(Video video, UUID currentUserId) {
    if (!video.getSubmittedBy().equals(currentUserId)) {
      return false;
    }
    return video.getStatus() != VideoStatus.APPROVED;
  }

  public boolean canView(Video video, UUID currentUserId, String trustTier) {
    return switch (video.getStatus()) {
      case APPROVED -> true;
      case PENDING, REJECTED -> isOwnerOrModerator(video, currentUserId, trustTier);
      case DELETED -> "ADMIN".equals(trustTier);
    };
  }

  private boolean isOwnerOrModerator(Video video, UUID currentUserId, String trustTier) {
    if (currentUserId != null && video.getSubmittedBy().equals(currentUserId)) {
      return true;
    }
    return Set.of("MODERATOR", "ADMIN").contains(trustTier);
  }
}
```

**Step 3: Commit**

Run:
```bash
git add src/main/java/com/accountabilityatlas/videoservice/service/VideoService.java \
  src/main/java/com/accountabilityatlas/videoservice/exception/VideoNotFoundException.java \
  src/main/java/com/accountabilityatlas/videoservice/exception/VideoAlreadyExistsException.java \
  src/main/java/com/accountabilityatlas/videoservice/exception/UnauthorizedException.java
git commit -m "feat: add VideoService with CRUD operations

- Create, update, delete videos
- Visibility rules (APPROVED public, others restricted)
- Internal update methods for moderation-service
- Authorization checks for owner operations

Refs: #1"
```

---

## Task 8: Create Location Client and VideoLocation Service

**Purpose:** Create REST client for location-service and service for managing video-location associations.

**Files:**
- Create: `src/main/java/com/accountabilityatlas/videoservice/service/LocationClient.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/service/VideoLocationService.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/exception/LocationNotFoundException.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/exception/LocationAlreadyLinkedException.java`

**Step 1: Create LocationClient**

Create `src/main/java/com/accountabilityatlas/videoservice/service/LocationClient.java`:

```java
package com.accountabilityatlas.videoservice.service;

import java.util.Optional;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

@Component
public class LocationClient {

  private final WebClient webClient;

  public LocationClient(
      WebClient.Builder builder,
      @Value("${app.location-service.base-url}") String baseUrl) {
    this.webClient = builder.baseUrl(baseUrl).build();
  }

  public record LocationSummary(
      UUID id, String displayName, String city, String state, Coordinates coordinates) {}

  public record Coordinates(double latitude, double longitude) {}

  public Optional<LocationSummary> getLocation(UUID locationId) {
    try {
      return Optional.ofNullable(
          webClient
              .get()
              .uri("/locations/{id}", locationId)
              .retrieve()
              .bodyToMono(LocationSummary.class)
              .block());
    } catch (WebClientResponseException.NotFound e) {
      return Optional.empty();
    }
  }
}
```

**Step 2: Create exceptions**

Create `src/main/java/com/accountabilityatlas/videoservice/exception/LocationNotFoundException.java`:

```java
package com.accountabilityatlas.videoservice.exception;

import java.util.UUID;

public class LocationNotFoundException extends RuntimeException {

  public LocationNotFoundException(UUID locationId) {
    super("Location not found: " + locationId);
  }
}
```

Create `src/main/java/com/accountabilityatlas/videoservice/exception/LocationAlreadyLinkedException.java`:

```java
package com.accountabilityatlas.videoservice.exception;

import java.util.UUID;

public class LocationAlreadyLinkedException extends RuntimeException {

  public LocationAlreadyLinkedException(UUID videoId, UUID locationId) {
    super("Location " + locationId + " is already linked to video " + videoId);
  }
}
```

**Step 3: Create VideoLocationService**

Create `src/main/java/com/accountabilityatlas/videoservice/service/VideoLocationService.java`:

```java
package com.accountabilityatlas.videoservice.service;

import com.accountabilityatlas.videoservice.domain.Video;
import com.accountabilityatlas.videoservice.domain.VideoLocation;
import com.accountabilityatlas.videoservice.domain.VideoStatus;
import com.accountabilityatlas.videoservice.exception.LocationAlreadyLinkedException;
import com.accountabilityatlas.videoservice.exception.LocationNotFoundException;
import com.accountabilityatlas.videoservice.exception.UnauthorizedException;
import com.accountabilityatlas.videoservice.exception.VideoNotFoundException;
import com.accountabilityatlas.videoservice.repository.VideoLocationRepository;
import com.accountabilityatlas.videoservice.repository.VideoRepository;
import com.accountabilityatlas.videoservice.service.LocationClient.LocationSummary;
import java.util.List;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class VideoLocationService {

  private final VideoRepository videoRepository;
  private final VideoLocationRepository videoLocationRepository;
  private final LocationClient locationClient;

  @Transactional(readOnly = true)
  public List<VideoLocation> getVideoLocations(UUID videoId) {
    if (!videoRepository.existsById(videoId)) {
      throw new VideoNotFoundException(videoId);
    }
    return videoLocationRepository.findByVideoId(videoId);
  }

  @Transactional
  public VideoLocation addLocation(
      UUID videoId, UUID locationId, boolean isPrimary, UUID currentUserId) {

    Video video =
        videoRepository.findById(videoId).orElseThrow(() -> new VideoNotFoundException(videoId));

    if (!canModify(video, currentUserId)) {
      throw new UnauthorizedException("You do not have permission to modify this video");
    }

    return addLocationInternal(video, locationId, isPrimary);
  }

  @Transactional
  public VideoLocation addLocationInternal(UUID videoId, UUID locationId, boolean isPrimary) {
    Video video =
        videoRepository.findById(videoId).orElseThrow(() -> new VideoNotFoundException(videoId));
    return addLocationInternal(video, locationId, isPrimary);
  }

  private VideoLocation addLocationInternal(Video video, UUID locationId, boolean isPrimary) {
    if (videoLocationRepository.existsByVideoIdAndLocationId(video.getId(), locationId)) {
      throw new LocationAlreadyLinkedException(video.getId(), locationId);
    }

    LocationSummary location =
        locationClient.getLocation(locationId).orElseThrow(() -> new LocationNotFoundException(locationId));

    if (isPrimary) {
      videoLocationRepository.clearPrimaryForVideo(video.getId());
    }

    VideoLocation videoLocation = new VideoLocation();
    videoLocation.setVideo(video);
    videoLocation.setLocationId(locationId);
    videoLocation.setPrimary(isPrimary);
    videoLocation.setDisplayName(location.displayName());
    videoLocation.setCity(location.city());
    videoLocation.setState(location.state());
    if (location.coordinates() != null) {
      videoLocation.setLatitude(location.coordinates().latitude());
      videoLocation.setLongitude(location.coordinates().longitude());
    }

    return videoLocationRepository.save(videoLocation);
  }

  @Transactional
  public void removeLocation(UUID videoId, UUID locationId, UUID currentUserId) {
    Video video =
        videoRepository.findById(videoId).orElseThrow(() -> new VideoNotFoundException(videoId));

    if (!canModify(video, currentUserId)) {
      throw new UnauthorizedException("You do not have permission to modify this video");
    }

    removeLocationInternal(videoId, locationId);
  }

  @Transactional
  public void removeLocationInternal(UUID videoId, UUID locationId) {
    VideoLocation location =
        videoLocationRepository
            .findByVideoIdAndLocationId(videoId, locationId)
            .orElseThrow(() -> new LocationNotFoundException(locationId));

    videoLocationRepository.delete(location);
  }

  private boolean canModify(Video video, UUID currentUserId) {
    if (!video.getSubmittedBy().equals(currentUserId)) {
      return false;
    }
    return video.getStatus() != VideoStatus.APPROVED;
  }
}
```

**Step 4: Commit**

Run:
```bash
git add src/main/java/com/accountabilityatlas/videoservice/service/LocationClient.java \
  src/main/java/com/accountabilityatlas/videoservice/service/VideoLocationService.java \
  src/main/java/com/accountabilityatlas/videoservice/exception/LocationNotFoundException.java \
  src/main/java/com/accountabilityatlas/videoservice/exception/LocationAlreadyLinkedException.java
git commit -m "feat: add LocationClient and VideoLocationService

- REST client for location-service
- Add/remove locations with validation
- Cache location data in VideoLocation
- Internal methods for moderation-service

Refs: #1"
```

---

## Task 9: Create Security Configuration

**Purpose:** Configure JWT security for public endpoints and IP-based security for internal endpoints.

**Files:**
- Create: `src/main/java/com/accountabilityatlas/videoservice/config/SecurityConfig.java`

**Step 1: Create SecurityConfig**

Create `src/main/java/com/accountabilityatlas/videoservice/config/SecurityConfig.java`:

```java
package com.accountabilityatlas.videoservice.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

  @Bean
  @Order(1)
  public SecurityFilterChain internalSecurityFilterChain(HttpSecurity http) throws Exception {
    http.securityMatcher("/internal/**")
        .csrf(csrf -> csrf.disable())
        .sessionManagement(
            session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .authorizeHttpRequests(auth -> auth.anyRequest().permitAll());
    return http.build();
  }

  @Bean
  @Order(2)
  public SecurityFilterChain publicSecurityFilterChain(HttpSecurity http) throws Exception {
    http.csrf(csrf -> csrf.disable())
        .sessionManagement(
            session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
        .authorizeHttpRequests(
            auth ->
                auth.requestMatchers("/actuator/**")
                    .permitAll()
                    .requestMatchers("GET", "/videos/**")
                    .permitAll()
                    .anyRequest()
                    .authenticated())
        .oauth2ResourceServer(oauth2 -> oauth2.jwt(jwt -> {}));
    return http.build();
  }
}
```

**Step 2: Commit**

Run:
```bash
git add src/main/java/com/accountabilityatlas/videoservice/config/SecurityConfig.java
git commit -m "feat: add security configuration

- JWT authentication for public endpoints
- Permit internal endpoints without auth
- Public GET endpoints for videos

Refs: #1"
```

---

## Task 10: Create Global Exception Handler

**Purpose:** Create centralized exception handling for consistent error responses.

**Files:**
- Create: `src/main/java/com/accountabilityatlas/videoservice/exception/GlobalExceptionHandler.java`

**Step 1: Create GlobalExceptionHandler**

Create `src/main/java/com/accountabilityatlas/videoservice/exception/GlobalExceptionHandler.java`:

```java
package com.accountabilityatlas.videoservice.exception;

import java.util.List;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

  public record ErrorResponse(String code, String message, List<FieldError> details, String traceId) {}

  public record FieldError(String field, String message) {}

  @ExceptionHandler(VideoNotFoundException.class)
  public ResponseEntity<ErrorResponse> handleVideoNotFound(VideoNotFoundException ex) {
    return ResponseEntity.status(HttpStatus.NOT_FOUND)
        .body(new ErrorResponse("NOT_FOUND", ex.getMessage(), null, UUID.randomUUID().toString()));
  }

  @ExceptionHandler(VideoAlreadyExistsException.class)
  public ResponseEntity<ErrorResponse> handleVideoAlreadyExists(VideoAlreadyExistsException ex) {
    return ResponseEntity.status(HttpStatus.CONFLICT)
        .body(new ErrorResponse("VIDEO_EXISTS", ex.getMessage(), null, UUID.randomUUID().toString()));
  }

  @ExceptionHandler(InvalidYouTubeUrlException.class)
  public ResponseEntity<ErrorResponse> handleInvalidYouTubeUrl(InvalidYouTubeUrlException ex) {
    return ResponseEntity.status(HttpStatus.BAD_REQUEST)
        .body(new ErrorResponse("INVALID_YOUTUBE_URL", ex.getMessage(), null, UUID.randomUUID().toString()));
  }

  @ExceptionHandler(YouTubeVideoNotFoundException.class)
  public ResponseEntity<ErrorResponse> handleYouTubeVideoNotFound(YouTubeVideoNotFoundException ex) {
    return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY)
        .body(new ErrorResponse("YOUTUBE_VIDEO_UNAVAILABLE", ex.getMessage(), null, UUID.randomUUID().toString()));
  }

  @ExceptionHandler(LocationNotFoundException.class)
  public ResponseEntity<ErrorResponse> handleLocationNotFound(LocationNotFoundException ex) {
    return ResponseEntity.status(HttpStatus.NOT_FOUND)
        .body(new ErrorResponse("LOCATION_NOT_FOUND", ex.getMessage(), null, UUID.randomUUID().toString()));
  }

  @ExceptionHandler(LocationAlreadyLinkedException.class)
  public ResponseEntity<ErrorResponse> handleLocationAlreadyLinked(LocationAlreadyLinkedException ex) {
    return ResponseEntity.status(HttpStatus.CONFLICT)
        .body(new ErrorResponse("LOCATION_ALREADY_LINKED", ex.getMessage(), null, UUID.randomUUID().toString()));
  }

  @ExceptionHandler(UnauthorizedException.class)
  public ResponseEntity<ErrorResponse> handleUnauthorized(UnauthorizedException ex) {
    return ResponseEntity.status(HttpStatus.FORBIDDEN)
        .body(new ErrorResponse("FORBIDDEN", ex.getMessage(), null, UUID.randomUUID().toString()));
  }

  @ExceptionHandler(MethodArgumentNotValidException.class)
  public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
    List<FieldError> details =
        ex.getBindingResult().getFieldErrors().stream()
            .map(e -> new FieldError(e.getField(), e.getDefaultMessage()))
            .toList();
    return ResponseEntity.status(HttpStatus.BAD_REQUEST)
        .body(new ErrorResponse("VALIDATION_ERROR", "Request validation failed", details, UUID.randomUUID().toString()));
  }
}
```

**Step 2: Commit**

Run:
```bash
git add src/main/java/com/accountabilityatlas/videoservice/exception/GlobalExceptionHandler.java
git commit -m "feat: add global exception handler

- Consistent error responses with code, message, traceId
- Handle all custom exceptions
- Validation error details

Refs: #1"
```

---

## Task 11: Create Controllers

**Purpose:** Create REST controllers implementing the OpenAPI-generated interfaces.

**Files:**
- Create: `src/main/java/com/accountabilityatlas/videoservice/web/VideoController.java`
- Create: `src/main/java/com/accountabilityatlas/videoservice/web/InternalVideoController.java`

**Step 1: Create VideoController**

Create `src/main/java/com/accountabilityatlas/videoservice/web/VideoController.java`:

```java
package com.accountabilityatlas.videoservice.web;

import com.accountabilityatlas.videoservice.domain.Amendment;
import com.accountabilityatlas.videoservice.domain.Participant;
import com.accountabilityatlas.videoservice.domain.Video;
import com.accountabilityatlas.videoservice.domain.VideoLocation;
import com.accountabilityatlas.videoservice.domain.VideoStatus;
import com.accountabilityatlas.videoservice.exception.VideoNotFoundException;
import com.accountabilityatlas.videoservice.service.VideoLocationService;
import com.accountabilityatlas.videoservice.service.VideoService;
import com.accountabilityatlas.videoservice.web.api.VideosApi;
import com.accountabilityatlas.videoservice.web.model.*;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
public class VideoController implements VideosApi {

  private final VideoService videoService;
  private final VideoLocationService videoLocationService;

  @Override
  public ResponseEntity<VideoDetail> getVideo(UUID id) {
    Video video = videoService.getVideo(id);
    return ResponseEntity.ok(toVideoDetail(video));
  }

  @Override
  public ResponseEntity<VideoListResponse> listVideos(
      com.accountabilityatlas.videoservice.web.model.VideoStatus status,
      List<com.accountabilityatlas.videoservice.web.model.Amendment> amendments,
      List<com.accountabilityatlas.videoservice.web.model.Participant> participants,
      UUID submittedBy,
      Integer page,
      Integer size,
      String sort,
      String direction) {

    PageRequest pageable =
        PageRequest.of(
            page != null ? page : 0,
            size != null ? size : 20,
            Sort.by(
                "desc".equalsIgnoreCase(direction) ? Sort.Direction.DESC : Sort.Direction.ASC,
                sort != null ? sort : "createdAt"));

    VideoStatus domainStatus = status != null ? VideoStatus.valueOf(status.name()) : null;
    Page<Video> videos = videoService.listVideos(domainStatus, pageable);

    return ResponseEntity.ok(toVideoListResponse(videos));
  }

  @Override
  public ResponseEntity<VideoDetail> createVideo(
      CreateVideoRequest request, @AuthenticationPrincipal Jwt jwt) {
    UUID userId = UUID.fromString(jwt.getSubject());

    Video video =
        videoService.createVideo(
            request.getYoutubeUrl(),
            request.getAmendments().stream()
                .map(a -> Amendment.valueOf(a.name()))
                .collect(Collectors.toSet()),
            request.getParticipants().stream()
                .map(p -> Participant.valueOf(p.name()))
                .collect(Collectors.toSet()),
            request.getVideoDate(),
            userId);

    if (request.getLocationId() != null) {
      videoLocationService.addLocationInternal(video.getId(), request.getLocationId(), true);
    }

    return ResponseEntity.status(HttpStatus.CREATED).body(toVideoDetail(video));
  }

  @Override
  public ResponseEntity<VideoDetail> updateVideo(
      UUID id, UpdateVideoRequest request, @AuthenticationPrincipal Jwt jwt) {
    UUID userId = UUID.fromString(jwt.getSubject());

    Video video =
        videoService.updateVideo(
            id,
            request.getAmendments() != null
                ? request.getAmendments().stream()
                    .map(a -> Amendment.valueOf(a.name()))
                    .collect(Collectors.toSet())
                : null,
            request.getParticipants() != null
                ? request.getParticipants().stream()
                    .map(p -> Participant.valueOf(p.name()))
                    .collect(Collectors.toSet())
                : null,
            request.getVideoDate(),
            userId);

    return ResponseEntity.ok(toVideoDetail(video));
  }

  @Override
  public ResponseEntity<Void> deleteVideo(UUID id, @AuthenticationPrincipal Jwt jwt) {
    UUID userId = UUID.fromString(jwt.getSubject());
    videoService.deleteVideo(id, userId);
    return ResponseEntity.noContent().build();
  }

  @Override
  public ResponseEntity<VideoLocationsResponse> getVideoLocations(UUID id) {
    List<VideoLocation> locations = videoLocationService.getVideoLocations(id);
    return ResponseEntity.ok(toVideoLocationsResponse(locations));
  }

  @Override
  public ResponseEntity<com.accountabilityatlas.videoservice.web.model.VideoLocation> addVideoLocation(
      UUID id, AddVideoLocationRequest request, @AuthenticationPrincipal Jwt jwt) {
    UUID userId = UUID.fromString(jwt.getSubject());

    VideoLocation location =
        videoLocationService.addLocation(
            id,
            request.getLocationId(),
            Boolean.TRUE.equals(request.getIsPrimary()),
            userId);

    return ResponseEntity.status(HttpStatus.CREATED).body(toVideoLocationModel(location));
  }

  @Override
  public ResponseEntity<Void> removeVideoLocation(
      UUID id, UUID locationId, @AuthenticationPrincipal Jwt jwt) {
    UUID userId = UUID.fromString(jwt.getSubject());
    videoLocationService.removeLocation(id, locationId, userId);
    return ResponseEntity.noContent().build();
  }

  // Mapping methods
  private VideoDetail toVideoDetail(Video video) {
    VideoDetail detail = new VideoDetail();
    detail.setId(video.getId());
    detail.setYoutubeId(video.getYoutubeId());
    detail.setTitle(video.getTitle());
    detail.setDescription(video.getDescription());
    detail.setThumbnailUrl(video.getThumbnailUrl());
    detail.setDurationSeconds(video.getDurationSeconds());
    detail.setChannelId(video.getChannelId());
    detail.setChannelName(video.getChannelName());
    detail.setPublishedAt(video.getPublishedAt() != null ? video.getPublishedAt().atOffset(java.time.ZoneOffset.UTC) : null);
    detail.setVideoDate(video.getVideoDate());
    detail.setAmendments(
        video.getAmendments().stream()
            .map(a -> com.accountabilityatlas.videoservice.web.model.Amendment.valueOf(a.name()))
            .toList());
    detail.setParticipants(
        video.getParticipants().stream()
            .map(p -> com.accountabilityatlas.videoservice.web.model.Participant.valueOf(p.name()))
            .toList());
    detail.setStatus(
        com.accountabilityatlas.videoservice.web.model.VideoStatus.valueOf(video.getStatus().name()));
    detail.setSubmittedBy(video.getSubmittedBy());
    detail.setCreatedAt(video.getCreatedAt().atOffset(java.time.ZoneOffset.UTC));
    detail.setLocations(video.getLocations().stream().map(this::toVideoLocationModel).toList());
    return detail;
  }

  private VideoListResponse toVideoListResponse(Page<Video> page) {
    VideoListResponse response = new VideoListResponse();
    response.setContent(page.getContent().stream().map(this::toVideoSummary).toList());
    response.setPage(page.getNumber());
    response.setSize(page.getSize());
    response.setTotalElements((int) page.getTotalElements());
    response.setTotalPages(page.getTotalPages());
    return response;
  }

  private VideoSummary toVideoSummary(Video video) {
    VideoSummary summary = new VideoSummary();
    summary.setId(video.getId());
    summary.setYoutubeId(video.getYoutubeId());
    summary.setTitle(video.getTitle());
    summary.setThumbnailUrl(video.getThumbnailUrl());
    summary.setDurationSeconds(video.getDurationSeconds());
    summary.setAmendments(
        video.getAmendments().stream()
            .map(a -> com.accountabilityatlas.videoservice.web.model.Amendment.valueOf(a.name()))
            .toList());
    summary.setParticipants(
        video.getParticipants().stream()
            .map(p -> com.accountabilityatlas.videoservice.web.model.Participant.valueOf(p.name()))
            .toList());
    summary.setStatus(
        com.accountabilityatlas.videoservice.web.model.VideoStatus.valueOf(video.getStatus().name()));
    summary.setCreatedAt(video.getCreatedAt().atOffset(java.time.ZoneOffset.UTC));
    return summary;
  }

  private com.accountabilityatlas.videoservice.web.model.VideoLocation toVideoLocationModel(
      VideoLocation location) {
    var model = new com.accountabilityatlas.videoservice.web.model.VideoLocation();
    model.setId(location.getId());
    model.setVideoId(location.getVideo().getId());
    model.setLocationId(location.getLocationId());
    model.setIsPrimary(location.isPrimary());

    if (location.getDisplayName() != null) {
      LocationSummary locSummary = new LocationSummary();
      locSummary.setId(location.getLocationId());
      locSummary.setDisplayName(location.getDisplayName());
      locSummary.setCity(location.getCity());
      locSummary.setState(location.getState());
      if (location.getLatitude() != null && location.getLongitude() != null) {
        Coordinates coords = new Coordinates();
        coords.setLatitude(location.getLatitude());
        coords.setLongitude(location.getLongitude());
        locSummary.setCoordinates(coords);
      }
      model.setLocation(locSummary);
    }

    return model;
  }

  private VideoLocationsResponse toVideoLocationsResponse(List<VideoLocation> locations) {
    VideoLocationsResponse response = new VideoLocationsResponse();
    response.setLocations(locations.stream().map(this::toVideoLocationModel).toList());
    return response;
  }
}
```

**Step 2: Create InternalVideoController**

Create `src/main/java/com/accountabilityatlas/videoservice/web/InternalVideoController.java`:

```java
package com.accountabilityatlas.videoservice.web;

import com.accountabilityatlas.videoservice.domain.Amendment;
import com.accountabilityatlas.videoservice.domain.Participant;
import com.accountabilityatlas.videoservice.domain.Video;
import com.accountabilityatlas.videoservice.domain.VideoLocation;
import com.accountabilityatlas.videoservice.domain.VideoStatus;
import com.accountabilityatlas.videoservice.service.VideoLocationService;
import com.accountabilityatlas.videoservice.service.VideoService;
import java.time.LocalDate;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/internal/videos")
@RequiredArgsConstructor
public class InternalVideoController {

  private final VideoService videoService;
  private final VideoLocationService videoLocationService;

  public record UpdateVideoRequest(
      Set<String> amendments, Set<String> participants, LocalDate videoDate) {}

  public record UpdateStatusRequest(String status) {}

  public record AddLocationRequest(UUID locationId, boolean isPrimary) {}

  @PutMapping("/{id}")
  public ResponseEntity<Video> updateVideo(@PathVariable UUID id, @RequestBody UpdateVideoRequest request) {
    Set<Amendment> amendments =
        request.amendments() != null
            ? request.amendments().stream().map(Amendment::valueOf).collect(Collectors.toSet())
            : null;
    Set<Participant> participants =
        request.participants() != null
            ? request.participants().stream().map(Participant::valueOf).collect(Collectors.toSet())
            : null;

    Video video = videoService.updateVideoInternal(id, amendments, participants, request.videoDate());
    return ResponseEntity.ok(video);
  }

  @PutMapping("/{id}/status")
  public ResponseEntity<Video> updateStatus(@PathVariable UUID id, @RequestBody UpdateStatusRequest request) {
    VideoStatus status = VideoStatus.valueOf(request.status());
    Video video = videoService.updateVideoStatus(id, status);
    return ResponseEntity.ok(video);
  }

  @PostMapping("/{id}/locations")
  public ResponseEntity<VideoLocation> addLocation(
      @PathVariable UUID id, @RequestBody AddLocationRequest request) {
    VideoLocation location =
        videoLocationService.addLocationInternal(id, request.locationId(), request.isPrimary());
    return ResponseEntity.status(HttpStatus.CREATED).body(location);
  }

  @DeleteMapping("/{id}/locations/{locationId}")
  public ResponseEntity<Void> removeLocation(@PathVariable UUID id, @PathVariable UUID locationId) {
    videoLocationService.removeLocationInternal(id, locationId);
    return ResponseEntity.noContent().build();
  }
}
```

**Step 3: Verify build compiles**

Run:
```bash
./gradlew compileJava
```

Expected: BUILD SUCCESSFUL

**Step 4: Commit**

Run:
```bash
git add src/main/java/com/accountabilityatlas/videoservice/web/
git commit -m "feat: add REST controllers

- VideoController implementing OpenAPI interface
- InternalVideoController for moderation-service
- Request/response mapping

Refs: #1"
```

---

## Task 12: Create README and Documentation

**Purpose:** Create README.md following the location-service template.

**Files:**
- Create: `README.md`
- Update: `docs/database-schema.md`

**Step 1: Create README.md**

Create `README.md`:

```markdown
# AcctAtlas Video Service

Core content management service for AccountabilityAtlas. Manages video records, YouTube API integration, amendment categorization, and video-location associations.

## Prerequisites

- **Docker Desktop** (for PostgreSQL + Redis)
- **Git**
- **YouTube Data API Key** (for metadata fetching)

JDK 21 is managed automatically by the Gradle wrapper via [Foojay Toolchain](https://github.com/gradle/foojay-toolchain) -- no manual JDK installation required.

## Clone and Build

```bash
git clone <repo-url>
cd AcctAtlas-video-service
```

Build the project (downloads JDK 21 automatically on first run):

```bash
# Linux/macOS
./gradlew build

# Windows
gradlew.bat build
```

## Local Development

### Start dependencies

```bash
docker-compose up -d
```

This starts PostgreSQL 17 and Redis 7. Flyway migrations run automatically when the service starts.

### Set environment variables

```bash
# Required for YouTube metadata fetching
export YOUTUBE_API_KEY=your_key_here
```

### Run the service

```bash
# Linux/macOS
./gradlew bootRun

# Windows
gradlew.bat bootRun
```

The service starts on **http://localhost:8082**.

### Quick API test

```bash
# Health check
curl http://localhost:8082/actuator/health

# List approved videos
curl http://localhost:8082/videos

# Get video by ID
curl http://localhost:8082/videos/{id}
```

### Run tests

```bash
./gradlew test
```

Integration tests use [TestContainers](https://testcontainers.com/) to spin up PostgreSQL automatically -- Docker must be running.

### Code formatting

Formatting is enforced by [Spotless](https://github.com/diffplug/spotless) using Google Java Format.

```bash
# Check formatting
./gradlew spotlessCheck

# Auto-fix formatting
./gradlew spotlessApply
```

### Full quality check

Runs Spotless, Error Prone, tests, and JaCoCo coverage verification (80% minimum):

```bash
./gradlew check
```

## Docker Image

Build a Docker image locally using [Jib](https://github.com/GoogleContainerTools/jib) (no Dockerfile needed):

```bash
./gradlew jibDockerBuild
```

Build and start the full stack (service + Postgres + Redis) in Docker:

```bash
./gradlew composeUp
```

## Project Structure

```
src/main/java/com/accountabilityatlas/videoservice/
  config/        Spring configuration (Security, YouTube, WebClient)
  domain/        JPA entities (Video, VideoLocation, enums)
  repository/    Spring Data JPA repositories
  service/       Business logic (VideoService, YouTubeService, LocationClient)
  web/           Controller implementations
  exception/     Custom exceptions and global handler

src/main/resources/
  application.yml          Shared config
  application-local.yml    Local dev overrides
  db/migration/            Flyway SQL migrations

src/test/java/.../
  service/       Service unit tests (Mockito)
  web/           Controller tests (@WebMvcTest)
  integration/   Integration tests (TestContainers)
```

API interfaces and DTOs are generated from `docs/api-specification.yaml` by the OpenAPI Generator plugin into `build/generated/`.

## Key Gradle Tasks

| Task | Description |
|------|-------------|
| `bootRun` | Run the service locally (uses `local` profile) |
| `test` | Run all tests |
| `unitTest` | Run unit tests only (no Docker required) |
| `integrationTest` | Run integration tests only (requires Docker) |
| `check` | Full quality gate (format + analysis + tests + coverage) |
| `spotlessApply` | Auto-fix code formatting |
| `jibDockerBuild` | Build Docker image |
| `composeUp` | Build image + docker-compose up |
| `composeDown` | Stop docker-compose services |

## Documentation

- [Technical Overview](docs/technical.md)
- [API Specification](docs/api-specification.yaml) (OpenAPI 3.1)
- [Database Schema](docs/database-schema.md)
```

**Step 2: Create database-schema.md**

Create `docs/database-schema.md`:

```markdown
# Video Service - Database Schema

## Overview

This document describes the database schema for the Video Service, focusing on JPA entity mappings and service-specific implementation details.

### Tables Owned by Video Service

| Table | Temporal | Description |
|-------|----------|-------------|
| `videos.videos` | Yes | Core video metadata, YouTube info, status |
| `videos.video_amendments` | No | Element collection for amendments |
| `videos.video_participants` | No | Element collection for participants |
| `videos.video_locations` | Yes | Video-to-location associations with cached location data |

---

## JPA Entity Mappings

### Video Entity

```java
@Entity
@Table(name = "videos", schema = "videos")
public class Video {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "youtube_id", nullable = false, unique = true, length = 11)
    private String youtubeId;

    private String title;
    private String description;
    private String thumbnailUrl;
    private Integer durationSeconds;
    private String channelId;
    private String channelName;
    private Instant publishedAt;
    private LocalDate videoDate;

    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "video_amendments", schema = "videos")
    @Enumerated(EnumType.STRING)
    private Set<Amendment> amendments;

    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "video_participants", schema = "videos")
    @Enumerated(EnumType.STRING)
    private Set<Participant> participants;

    @Enumerated(EnumType.STRING)
    private VideoStatus status;

    private UUID submittedBy;

    @OneToMany(mappedBy = "video", cascade = CascadeType.ALL)
    private List<VideoLocation> locations;

    private Instant createdAt;
    private String sysPeriod;  // Read-only
}
```

### VideoLocation Entity

```java
@Entity
@Table(name = "video_locations", schema = "videos")
public class VideoLocation {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "video_id")
    private Video video;

    private UUID locationId;
    private boolean primary;

    // Cached location data
    private String displayName;
    private String city;
    private String state;
    private Double latitude;
    private Double longitude;

    private Instant createdAt;
    private String sysPeriod;  // Read-only
}
```

---

## Temporal vs Non-Temporal Decisions

| Table | Temporal | Rationale |
|-------|----------|-----------|
| `videos` | Yes | Audit trail for video edits, status changes |
| `video_amendments` | No | Element collection, recreated on update |
| `video_participants` | No | Element collection, recreated on update |
| `video_locations` | Yes | Track when locations added/removed |

---

## Index Strategy

| Index | Column(s) | Purpose |
|-------|-----------|---------|
| `idx_videos_youtube_id` | `youtube_id` | Duplicate detection |
| `idx_videos_status` | `status` | Filter by approval status |
| `idx_videos_submitted_by` | `submitted_by` | User's submissions |
| `idx_videos_created_at` | `created_at` | Sort by creation time |
| `idx_video_locations_video_id` | `video_id` | Join queries |
| `idx_video_locations_location_id` | `location_id` | Reverse lookup |

---

## Common Query Patterns

### Find video by YouTube ID

```java
Optional<Video> findByYoutubeId(String youtubeId);
```

### List approved videos

```java
Page<Video> findByStatusOrderByCreatedAtDesc(VideoStatus status, Pageable pageable);
```

### Get user's submissions

```java
Page<Video> findBySubmittedBy(UUID submittedBy, Pageable pageable);
```

### Check video-location exists

```java
boolean existsByVideoIdAndLocationId(UUID videoId, UUID locationId);
```
```

**Step 3: Commit**

Run:
```bash
git add README.md docs/database-schema.md
git commit -m "docs: add README and database schema documentation

- README following location-service template
- Database schema with JPA mappings
- Common query patterns

Refs: #1"
```

---

## Task 13: Run Full Build and Verify

**Purpose:** Verify the complete build compiles and tests pass.

**Step 1: Start dependencies**

Run:
```bash
docker-compose up -d
```

**Step 2: Run full build**

Run:
```bash
./gradlew clean build
```

Expected: BUILD SUCCESSFUL

**Step 3: Fix any issues**

If there are compilation errors, fix them and re-run the build.

**Step 4: Run the service**

Run:
```bash
./gradlew bootRun
```

Expected: Service starts on port 8082.

**Step 5: Test health endpoint**

Run:
```bash
curl http://localhost:8082/actuator/health
```

Expected: `{"status":"UP"}`

**Step 6: Final commit if any fixes needed**

Run:
```bash
git add -A
git commit -m "fix: address build issues

Refs: #1"
```

---

## Summary

After completing all tasks, you will have:

1. **Complete video-service** with:
   - Gradle build with OpenAPI generator
   - PostgreSQL schema with videos and video_locations
   - YouTube integration with resilience patterns
   - Video CRUD with authorization
   - Location integration with caching
   - Internal APIs for moderation-service
   - Security configuration
   - Exception handling
   - Full documentation

2. **Ready for integration** with:
   - moderation-service (via internal APIs)
   - location-service (via REST client)
   - api-gateway (via public endpoints)

3. **GitHub issue #1** ready to close after PR merge.
