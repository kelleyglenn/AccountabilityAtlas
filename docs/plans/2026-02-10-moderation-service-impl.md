# Moderation Service Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the moderation-service that manages content approval/rejection, abuse reports, and trust tier progression.

**Architecture:** Spring Boot 3.4.x service with PostgreSQL temporal tables. Consumes VideoSubmitted events, publishes VideoApproved/VideoRejected. Integrates with video-service (internal APIs) and user-service (trust tier management).

**Tech Stack:** Java 21, Spring Boot 3.4.x, PostgreSQL 15, Flyway, JUnit 5, TestContainers, OpenAPI Generator

**Design Doc:** [moderation-service-design.md](2026-02-09-moderation-service-design.md)

---

## Phase 1: Project Foundation

### Task 1: Create Gradle Build Files

**Files:**
- Create: `AcctAtlas-moderation-service/settings.gradle`
- Create: `AcctAtlas-moderation-service/gradle.properties`
- Create: `AcctAtlas-moderation-service/build.gradle`

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

rootProject.name = 'acctatlas-moderation-service'
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

dependencies {
    // Spring Boot starters
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-actuator'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation 'org.springframework.boot:spring-boot-starter-validation'
    implementation 'org.springframework.boot:spring-boot-starter-webflux'
    implementation 'org.springframework.boot:spring-boot-starter-oauth2-resource-server'

    // Database
    runtimeOnly 'org.postgresql:postgresql'
    implementation 'org.flywaydb:flyway-core'
    implementation 'org.flywaydb:flyway-database-postgresql'

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
}

// ---- OpenAPI Generator ----
openApiGenerate {
    generatorName = 'spring'
    inputSpec = "${projectDir}/docs/api-specification.yaml"
    outputDir = layout.buildDirectory.dir('generated').get().asFile.path
    apiPackage = 'com.accountabilityatlas.moderationservice.web.api'
    modelPackage = 'com.accountabilityatlas.moderationservice.web.model'
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
                'com/accountabilityatlas/moderationservice/web/api/**',
                'com/accountabilityatlas/moderationservice/web/model/**',
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
                'com/accountabilityatlas/moderationservice/web/api/**',
                'com/accountabilityatlas/moderationservice/web/model/**',
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
        image = 'acctatlas/moderation-service'
        tags = [version, 'latest']
    }
    container {
        mainClass = 'com.accountabilityatlas.moderationservice.ModerationServiceApplication'
        ports = ['8085']
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
cp -r /c/code/AccountabilityAtlas/AcctAtlas-video-service/gradle /c/code/AccountabilityAtlas/AcctAtlas-moderation-service/
cp /c/code/AccountabilityAtlas/AcctAtlas-video-service/gradlew /c/code/AccountabilityAtlas/AcctAtlas-moderation-service/
cp /c/code/AccountabilityAtlas/AcctAtlas-video-service/gradlew.bat /c/code/AccountabilityAtlas/AcctAtlas-moderation-service/
```

**Step 5: Set gradlew execute permission in git**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && git update-index --chmod=+x gradlew
```

**Step 6: Verify build compiles**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew clean build -x test
```

Expected: BUILD SUCCESSFUL

**Step 7: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add settings.gradle gradle.properties build.gradle gradle gradlew gradlew.bat
git commit -m "build: add Gradle build configuration"
```

---

### Task 2: Create Docker Compose

**Files:**
- Create: `AcctAtlas-moderation-service/docker-compose.yml`

**Step 1: Create docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: moderation
      POSTGRES_PASSWORD: moderation
      POSTGRES_DB: moderation
    ports:
      - "5435:5432"
    volumes:
      - moderation-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U moderation"]
      interval: 5s
      timeout: 5s
      retries: 5

  moderation-service:
    image: acctatlas/moderation-service:latest
    profiles: [app]
    ports:
      - "8085:8085"
    environment:
      SPRING_PROFILES_ACTIVE: local
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/moderation
      SPRING_DATASOURCE_USERNAME: moderation
      SPRING_DATASOURCE_PASSWORD: moderation
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  moderation-postgres-data:
```

**Step 2: Verify docker-compose syntax**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && docker-compose config
```

Expected: Valid YAML output, no errors

**Step 3: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add docker-compose.yml
git commit -m "build: add docker-compose for local development"
```

---

### Task 3: Create Application Entry Point and Config

**Files:**
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/ModerationServiceApplication.java`
- Create: `AcctAtlas-moderation-service/src/main/resources/application.yml`
- Create: `AcctAtlas-moderation-service/src/main/resources/application-local.yml`

**Step 1: Create main application class**

```java
package com.accountabilityatlas.moderationservice;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class ModerationServiceApplication {

  public static void main(String[] args) {
    SpringApplication.run(ModerationServiceApplication.class, args);
  }
}
```

**Step 2: Create application.yml**

```yaml
spring:
  application:
    name: moderation-service

  datasource:
    url: jdbc:postgresql://localhost:5435/moderation
    username: moderation
    password: moderation
    driver-class-name: org.postgresql.Driver

  jpa:
    hibernate:
      ddl-auto: validate
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        default_schema: moderation
    open-in-view: false

  flyway:
    enabled: true
    schemas:
      - moderation
    default-schema: moderation

server:
  port: 8085

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics
  endpoint:
    health:
      show-details: when_authorized

app:
  video-service:
    base-url: http://localhost:8082
  user-service:
    base-url: http://localhost:8080
```

**Step 3: Create application-local.yml**

```yaml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: http://localhost:8080

logging:
  level:
    com.accountabilityatlas: DEBUG
    org.springframework.security: DEBUG
```

**Step 4: Verify application starts (will fail on missing schema, that's expected)**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && docker-compose up -d postgres
```

Wait 5 seconds for postgres to start.

**Step 5: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/main/java/com/accountabilityatlas/moderationservice/ModerationServiceApplication.java
git add src/main/resources/application.yml src/main/resources/application-local.yml
git commit -m "feat: add application entry point and configuration"
```

---

### Task 4: Create Domain Enums

**Files:**
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/domain/ContentType.java`
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/domain/ModerationStatus.java`
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/domain/ReportStatus.java`
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/domain/AbuseReason.java`

**Step 1: Create ContentType enum**

```java
package com.accountabilityatlas.moderationservice.domain;

public enum ContentType {
  VIDEO
}
```

**Step 2: Create ModerationStatus enum**

```java
package com.accountabilityatlas.moderationservice.domain;

public enum ModerationStatus {
  PENDING,
  APPROVED,
  REJECTED
}
```

**Step 3: Create ReportStatus enum**

```java
package com.accountabilityatlas.moderationservice.domain;

public enum ReportStatus {
  OPEN,
  RESOLVED,
  DISMISSED
}
```

**Step 4: Create AbuseReason enum**

```java
package com.accountabilityatlas.moderationservice.domain;

public enum AbuseReason {
  SPAM,
  INAPPROPRIATE,
  COPYRIGHT,
  MISINFORMATION,
  OTHER
}
```

**Step 5: Verify compilation**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew compileJava
```

Expected: BUILD SUCCESSFUL

**Step 6: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/main/java/com/accountabilityatlas/moderationservice/domain/
git commit -m "feat: add domain enums"
```

---

### Task 5: Create ModerationItem Entity

**Files:**
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/domain/ModerationItem.java`

**Step 1: Create ModerationItem entity**

```java
package com.accountabilityatlas.moderationservice.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "moderation_items", schema = "moderation")
@Getter
@Setter
@NoArgsConstructor
public class ModerationItem {

  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;

  @Enumerated(EnumType.STRING)
  @Column(nullable = false)
  private ContentType contentType;

  @Column(nullable = false)
  private UUID contentId;

  @Column(nullable = false)
  private UUID submitterId;

  @Enumerated(EnumType.STRING)
  @Column(nullable = false)
  private ModerationStatus status;

  @Column(nullable = false)
  private int priority;

  private UUID reviewerId;

  private Instant reviewedAt;

  @Column(length = 1000)
  private String rejectionReason;

  @Column(nullable = false, updatable = false)
  private Instant createdAt;

  @PrePersist
  protected void onCreate() {
    if (createdAt == null) {
      createdAt = Instant.now();
    }
    if (status == null) {
      status = ModerationStatus.PENDING;
    }
  }
}
```

**Step 2: Verify compilation**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew compileJava
```

Expected: BUILD SUCCESSFUL

**Step 3: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/main/java/com/accountabilityatlas/moderationservice/domain/ModerationItem.java
git commit -m "feat: add ModerationItem entity"
```

---

### Task 6: Create AbuseReport Entity

**Files:**
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/domain/AbuseReport.java`

**Step 1: Create AbuseReport entity**

```java
package com.accountabilityatlas.moderationservice.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "abuse_reports", schema = "moderation")
@Getter
@Setter
@NoArgsConstructor
public class AbuseReport {

  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;

  @Enumerated(EnumType.STRING)
  @Column(nullable = false)
  private ContentType contentType;

  @Column(nullable = false)
  private UUID contentId;

  @Column(nullable = false)
  private UUID reporterId;

  @Enumerated(EnumType.STRING)
  @Column(nullable = false)
  private AbuseReason reason;

  @Column(length = 2000)
  private String description;

  @Enumerated(EnumType.STRING)
  @Column(nullable = false)
  private ReportStatus status;

  private UUID resolvedBy;

  @Column(length = 1000)
  private String resolution;

  @Column(nullable = false, updatable = false)
  private Instant createdAt;

  @PrePersist
  protected void onCreate() {
    if (createdAt == null) {
      createdAt = Instant.now();
    }
    if (status == null) {
      status = ReportStatus.OPEN;
    }
  }
}
```

**Step 2: Verify compilation**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew compileJava
```

Expected: BUILD SUCCESSFUL

**Step 3: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/main/java/com/accountabilityatlas/moderationservice/domain/AbuseReport.java
git commit -m "feat: add AbuseReport entity"
```

---

### Task 7: Create AuditLogEntry Entity

**Files:**
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/domain/AuditLogEntry.java`

**Step 1: Create AuditLogEntry entity**

```java
package com.accountabilityatlas.moderationservice.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "audit_log", schema = "moderation")
@Getter
@Setter
@NoArgsConstructor
public class AuditLogEntry {

  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;

  @Column(nullable = false)
  private UUID actorId;

  @Column(nullable = false)
  private String action;

  @Column(nullable = false)
  private String targetType;

  @Column(nullable = false)
  private UUID targetId;

  @Column(columnDefinition = "jsonb")
  private String details;

  @Column(nullable = false, updatable = false)
  private Instant createdAt;

  @PrePersist
  protected void onCreate() {
    if (createdAt == null) {
      createdAt = Instant.now();
    }
  }
}
```

**Step 2: Verify compilation**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew compileJava
```

Expected: BUILD SUCCESSFUL

**Step 3: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/main/java/com/accountabilityatlas/moderationservice/domain/AuditLogEntry.java
git commit -m "feat: add AuditLogEntry entity"
```

---

### Task 8: Create Database Migrations

**Files:**
- Create: `AcctAtlas-moderation-service/src/main/resources/db/migration/V1__create_moderation_items.sql`
- Create: `AcctAtlas-moderation-service/src/main/resources/db/migration/V2__create_abuse_reports.sql`
- Create: `AcctAtlas-moderation-service/src/main/resources/db/migration/V3__create_audit_log.sql`

**Step 1: Create V1 migration for moderation_items**

```sql
-- Create moderation schema
CREATE SCHEMA IF NOT EXISTS moderation;

-- Enable btree_gist for exclusion constraints with temporal tables
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Create moderation_items table
CREATE TABLE moderation.moderation_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type VARCHAR(50) NOT NULL,
    content_id UUID NOT NULL,
    submitter_id UUID NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    priority INTEGER NOT NULL DEFAULT 0,
    reviewer_id UUID,
    reviewed_at TIMESTAMPTZ,
    rejection_reason VARCHAR(1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sys_period TSTZRANGE NOT NULL DEFAULT tstzrange(NOW(), NULL)
);

-- Create history table for temporal data
CREATE TABLE moderation.moderation_items_history (
    LIKE moderation.moderation_items
);

-- Create trigger function for temporal versioning
CREATE OR REPLACE FUNCTION moderation.versioning_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        INSERT INTO moderation.moderation_items_history
        SELECT OLD.id, OLD.content_type, OLD.content_id, OLD.submitter_id,
               OLD.status, OLD.priority, OLD.reviewer_id, OLD.reviewed_at,
               OLD.rejection_reason, OLD.created_at,
               tstzrange(lower(OLD.sys_period), NOW());
        NEW.sys_period = tstzrange(NOW(), NULL);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO moderation.moderation_items_history
        SELECT OLD.id, OLD.content_type, OLD.content_id, OLD.submitter_id,
               OLD.status, OLD.priority, OLD.reviewer_id, OLD.reviewed_at,
               OLD.rejection_reason, OLD.created_at,
               tstzrange(lower(OLD.sys_period), NOW());
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger
CREATE TRIGGER moderation_items_versioning
    BEFORE UPDATE OR DELETE ON moderation.moderation_items
    FOR EACH ROW EXECUTE FUNCTION moderation.versioning_trigger();

-- Indexes
CREATE INDEX idx_moderation_items_status ON moderation.moderation_items(status);
CREATE INDEX idx_moderation_items_content_id ON moderation.moderation_items(content_id);
CREATE INDEX idx_moderation_items_submitter_id ON moderation.moderation_items(submitter_id);
CREATE INDEX idx_moderation_items_created_at ON moderation.moderation_items(created_at);
```

**Step 2: Create V2 migration for abuse_reports**

```sql
-- Create abuse_reports table
CREATE TABLE moderation.abuse_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type VARCHAR(50) NOT NULL,
    content_id UUID NOT NULL,
    reporter_id UUID NOT NULL,
    reason VARCHAR(50) NOT NULL,
    description VARCHAR(2000),
    status VARCHAR(50) NOT NULL DEFAULT 'OPEN',
    resolved_by UUID,
    resolution VARCHAR(1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sys_period TSTZRANGE NOT NULL DEFAULT tstzrange(NOW(), NULL)
);

-- Create history table for temporal data
CREATE TABLE moderation.abuse_reports_history (
    LIKE moderation.abuse_reports
);

-- Create trigger function for abuse_reports versioning
CREATE OR REPLACE FUNCTION moderation.abuse_reports_versioning_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        INSERT INTO moderation.abuse_reports_history
        SELECT OLD.id, OLD.content_type, OLD.content_id, OLD.reporter_id,
               OLD.reason, OLD.description, OLD.status, OLD.resolved_by,
               OLD.resolution, OLD.created_at,
               tstzrange(lower(OLD.sys_period), NOW());
        NEW.sys_period = tstzrange(NOW(), NULL);
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO moderation.abuse_reports_history
        SELECT OLD.id, OLD.content_type, OLD.content_id, OLD.reporter_id,
               OLD.reason, OLD.description, OLD.status, OLD.resolved_by,
               OLD.resolution, OLD.created_at,
               tstzrange(lower(OLD.sys_period), NOW());
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger
CREATE TRIGGER abuse_reports_versioning
    BEFORE UPDATE OR DELETE ON moderation.abuse_reports
    FOR EACH ROW EXECUTE FUNCTION moderation.abuse_reports_versioning_trigger();

-- Indexes
CREATE INDEX idx_abuse_reports_status ON moderation.abuse_reports(status);
CREATE INDEX idx_abuse_reports_content_id ON moderation.abuse_reports(content_id);
CREATE INDEX idx_abuse_reports_reporter_id ON moderation.abuse_reports(reporter_id);
```

**Step 3: Create V3 migration for audit_log**

```sql
-- Create audit_log table (append-only, no temporal versioning needed)
CREATE TABLE moderation.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(100) NOT NULL,
    target_id UUID NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_audit_log_actor_id ON moderation.audit_log(actor_id);
CREATE INDEX idx_audit_log_target ON moderation.audit_log(target_type, target_id);
CREATE INDEX idx_audit_log_created_at ON moderation.audit_log(created_at);
```

**Step 4: Run migrations**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew flywayMigrate
```

Expected: Successfully applied 3 migrations

**Step 5: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/main/resources/db/migration/
git commit -m "feat: add database migrations for moderation schema"
```

---

### Task 9: Create Repositories

**Files:**
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/repository/ModerationItemRepository.java`
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/repository/AbuseReportRepository.java`
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/repository/AuditLogRepository.java`

**Step 1: Create ModerationItemRepository**

```java
package com.accountabilityatlas.moderationservice.repository;

import com.accountabilityatlas.moderationservice.domain.ModerationItem;
import com.accountabilityatlas.moderationservice.domain.ModerationStatus;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

@Repository
public interface ModerationItemRepository extends JpaRepository<ModerationItem, UUID> {

  Page<ModerationItem> findByStatus(ModerationStatus status, Pageable pageable);

  Optional<ModerationItem> findByContentId(UUID contentId);

  @Query("SELECT COUNT(m) FROM ModerationItem m WHERE m.submitterId = :submitterId "
      + "AND m.status = 'REJECTED' AND m.reviewedAt >= :since")
  int countRejectionsSince(UUID submitterId, Instant since);

  long countByStatus(ModerationStatus status);
}
```

**Step 2: Create AbuseReportRepository**

```java
package com.accountabilityatlas.moderationservice.repository;

import com.accountabilityatlas.moderationservice.domain.AbuseReport;
import com.accountabilityatlas.moderationservice.domain.ReportStatus;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;

@Repository
public interface AbuseReportRepository extends JpaRepository<AbuseReport, UUID> {

  Page<AbuseReport> findByStatus(ReportStatus status, Pageable pageable);

  @Query("SELECT COUNT(a) FROM AbuseReport a WHERE a.contentId IN "
      + "(SELECT m.contentId FROM ModerationItem m WHERE m.submitterId = :userId) "
      + "AND a.status = 'OPEN'")
  int countActiveReportsAgainst(UUID userId);

  long countByStatus(ReportStatus status);
}
```

**Step 3: Create AuditLogRepository**

```java
package com.accountabilityatlas.moderationservice.repository;

import com.accountabilityatlas.moderationservice.domain.AuditLogEntry;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface AuditLogRepository extends JpaRepository<AuditLogEntry, UUID> {

  Page<AuditLogEntry> findByActorId(UUID actorId, Pageable pageable);

  Page<AuditLogEntry> findByTargetTypeAndTargetId(
      String targetType, UUID targetId, Pageable pageable);
}
```

**Step 4: Verify compilation**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew compileJava
```

Expected: BUILD SUCCESSFUL

**Step 5: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/main/java/com/accountabilityatlas/moderationservice/repository/
git commit -m "feat: add repositories for moderation entities"
```

---

## Phase 2: Moderation Queue (Tasks 10-16)

### Task 10: Create Custom Exceptions

**Files:**
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/exception/ModerationItemNotFoundException.java`
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/exception/ItemAlreadyReviewedException.java`
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/exception/AbuseReportNotFoundException.java`

**Step 1: Create ModerationItemNotFoundException**

```java
package com.accountabilityatlas.moderationservice.exception;

import java.util.UUID;

public class ModerationItemNotFoundException extends RuntimeException {

  public ModerationItemNotFoundException(UUID id) {
    super("Moderation item not found: " + id);
  }
}
```

**Step 2: Create ItemAlreadyReviewedException**

```java
package com.accountabilityatlas.moderationservice.exception;

import java.util.UUID;

public class ItemAlreadyReviewedException extends RuntimeException {

  public ItemAlreadyReviewedException(UUID id) {
    super("Moderation item already reviewed: " + id);
  }
}
```

**Step 3: Create AbuseReportNotFoundException**

```java
package com.accountabilityatlas.moderationservice.exception;

import java.util.UUID;

public class AbuseReportNotFoundException extends RuntimeException {

  public AbuseReportNotFoundException(UUID id) {
    super("Abuse report not found: " + id);
  }
}
```

**Step 4: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/main/java/com/accountabilityatlas/moderationservice/exception/
git commit -m "feat: add custom exceptions"
```

---

### Task 11: Write ModerationService Tests

**Files:**
- Create: `AcctAtlas-moderation-service/src/test/java/com/accountabilityatlas/moderationservice/service/ModerationServiceTest.java`

**Step 1: Write the failing tests**

```java
package com.accountabilityatlas.moderationservice.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.accountabilityatlas.moderationservice.domain.ContentType;
import com.accountabilityatlas.moderationservice.domain.ModerationItem;
import com.accountabilityatlas.moderationservice.domain.ModerationStatus;
import com.accountabilityatlas.moderationservice.exception.ItemAlreadyReviewedException;
import com.accountabilityatlas.moderationservice.exception.ModerationItemNotFoundException;
import com.accountabilityatlas.moderationservice.repository.ModerationItemRepository;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ModerationServiceTest {

  @Mock private ModerationItemRepository moderationItemRepository;
  @Mock private AuditLogService auditLogService;

  private ModerationService moderationService;

  @BeforeEach
  void setUp() {
    moderationService = new ModerationService(moderationItemRepository, auditLogService);
  }

  @Test
  void createItem_validInput_createsItemWithPendingStatus() {
    // Arrange
    UUID contentId = UUID.randomUUID();
    UUID submitterId = UUID.randomUUID();
    when(moderationItemRepository.save(any(ModerationItem.class)))
        .thenAnswer(inv -> inv.getArgument(0));

    // Act
    ModerationItem result = moderationService.createItem(ContentType.VIDEO, contentId, submitterId);

    // Assert
    assertThat(result.getContentType()).isEqualTo(ContentType.VIDEO);
    assertThat(result.getContentId()).isEqualTo(contentId);
    assertThat(result.getSubmitterId()).isEqualTo(submitterId);
    assertThat(result.getStatus()).isEqualTo(ModerationStatus.PENDING);
  }

  @Test
  void getItem_existingId_returnsItem() {
    // Arrange
    UUID id = UUID.randomUUID();
    ModerationItem item = new ModerationItem();
    item.setId(id);
    when(moderationItemRepository.findById(id)).thenReturn(Optional.of(item));

    // Act
    ModerationItem result = moderationService.getItem(id);

    // Assert
    assertThat(result.getId()).isEqualTo(id);
  }

  @Test
  void getItem_nonExistingId_throwsException() {
    // Arrange
    UUID id = UUID.randomUUID();
    when(moderationItemRepository.findById(id)).thenReturn(Optional.empty());

    // Act
    Throwable thrown = catchThrowable(() -> moderationService.getItem(id));

    // Assert
    assertThat(thrown).isInstanceOf(ModerationItemNotFoundException.class);
  }

  @Test
  void approve_pendingItem_setsApprovedStatus() {
    // Arrange
    UUID id = UUID.randomUUID();
    UUID reviewerId = UUID.randomUUID();
    ModerationItem item = new ModerationItem();
    item.setId(id);
    item.setStatus(ModerationStatus.PENDING);
    when(moderationItemRepository.findById(id)).thenReturn(Optional.of(item));
    when(moderationItemRepository.save(any(ModerationItem.class)))
        .thenAnswer(inv -> inv.getArgument(0));

    // Act
    ModerationItem result = moderationService.approve(id, reviewerId);

    // Assert
    assertThat(result.getStatus()).isEqualTo(ModerationStatus.APPROVED);
    assertThat(result.getReviewerId()).isEqualTo(reviewerId);
    assertThat(result.getReviewedAt()).isNotNull();
    verify(auditLogService).logAction(reviewerId, "APPROVE", "MODERATION_ITEM", id, null);
  }

  @Test
  void approve_alreadyReviewedItem_throwsException() {
    // Arrange
    UUID id = UUID.randomUUID();
    UUID reviewerId = UUID.randomUUID();
    ModerationItem item = new ModerationItem();
    item.setId(id);
    item.setStatus(ModerationStatus.APPROVED);
    when(moderationItemRepository.findById(id)).thenReturn(Optional.of(item));

    // Act
    Throwable thrown = catchThrowable(() -> moderationService.approve(id, reviewerId));

    // Assert
    assertThat(thrown).isInstanceOf(ItemAlreadyReviewedException.class);
  }

  @Test
  void reject_pendingItem_setsRejectedStatusWithReason() {
    // Arrange
    UUID id = UUID.randomUUID();
    UUID reviewerId = UUID.randomUUID();
    String reason = "Off-topic content";
    ModerationItem item = new ModerationItem();
    item.setId(id);
    item.setStatus(ModerationStatus.PENDING);
    when(moderationItemRepository.findById(id)).thenReturn(Optional.of(item));
    when(moderationItemRepository.save(any(ModerationItem.class)))
        .thenAnswer(inv -> inv.getArgument(0));

    // Act
    ModerationItem result = moderationService.reject(id, reviewerId, reason);

    // Assert
    assertThat(result.getStatus()).isEqualTo(ModerationStatus.REJECTED);
    assertThat(result.getReviewerId()).isEqualTo(reviewerId);
    assertThat(result.getRejectionReason()).isEqualTo(reason);
    verify(auditLogService).logAction(reviewerId, "REJECT", "MODERATION_ITEM", id, reason);
  }
}
```

**Step 2: Run tests to verify they fail**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew test --tests ModerationServiceTest
```

Expected: FAIL - ModerationService class not found

**Step 3: Commit test file**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/test/java/com/accountabilityatlas/moderationservice/service/ModerationServiceTest.java
git commit -m "test: add ModerationService unit tests (red)"
```

---

### Task 12: Implement AuditLogService

**Files:**
- Create: `AcctAtlas-moderation-service/src/test/java/com/accountabilityatlas/moderationservice/service/AuditLogServiceTest.java`
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/service/AuditLogService.java`

**Step 1: Write the failing test**

```java
package com.accountabilityatlas.moderationservice.service;

import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.verify;

import com.accountabilityatlas.moderationservice.repository.AuditLogRepository;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class AuditLogServiceTest {

  @Mock private AuditLogRepository auditLogRepository;

  private AuditLogService auditLogService;

  @BeforeEach
  void setUp() {
    auditLogService = new AuditLogService(auditLogRepository);
  }

  @Test
  void logAction_validInput_savesAuditLogEntry() {
    // Arrange
    UUID actorId = UUID.randomUUID();
    String action = "APPROVE";
    String targetType = "MODERATION_ITEM";
    UUID targetId = UUID.randomUUID();
    String details = "test details";

    // Act
    auditLogService.logAction(actorId, action, targetType, targetId, details);

    // Assert
    verify(auditLogRepository).save(argThat(entry ->
        entry.getActorId().equals(actorId)
        && entry.getAction().equals(action)
        && entry.getTargetType().equals(targetType)
        && entry.getTargetId().equals(targetId)
    ));
  }
}
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew test --tests AuditLogServiceTest
```

Expected: FAIL - AuditLogService class not found

**Step 3: Implement AuditLogService**

```java
package com.accountabilityatlas.moderationservice.service;

import com.accountabilityatlas.moderationservice.domain.AuditLogEntry;
import com.accountabilityatlas.moderationservice.repository.AuditLogRepository;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class AuditLogService {

  private final AuditLogRepository auditLogRepository;

  @Transactional
  public void logAction(
      UUID actorId, String action, String targetType, UUID targetId, String details) {
    AuditLogEntry entry = new AuditLogEntry();
    entry.setActorId(actorId);
    entry.setAction(action);
    entry.setTargetType(targetType);
    entry.setTargetId(targetId);
    entry.setDetails(details);
    auditLogRepository.save(entry);
  }
}
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew test --tests AuditLogServiceTest
```

Expected: PASS

**Step 5: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/test/java/com/accountabilityatlas/moderationservice/service/AuditLogServiceTest.java
git add src/main/java/com/accountabilityatlas/moderationservice/service/AuditLogService.java
git commit -m "feat: add AuditLogService with tests"
```

---

### Task 13: Implement ModerationService

**Files:**
- Create: `AcctAtlas-moderation-service/src/main/java/com/accountabilityatlas/moderationservice/service/ModerationService.java`

**Step 1: Implement ModerationService**

```java
package com.accountabilityatlas.moderationservice.service;

import com.accountabilityatlas.moderationservice.domain.ContentType;
import com.accountabilityatlas.moderationservice.domain.ModerationItem;
import com.accountabilityatlas.moderationservice.domain.ModerationStatus;
import com.accountabilityatlas.moderationservice.exception.ItemAlreadyReviewedException;
import com.accountabilityatlas.moderationservice.exception.ModerationItemNotFoundException;
import com.accountabilityatlas.moderationservice.repository.ModerationItemRepository;
import java.time.Instant;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class ModerationService {

  private final ModerationItemRepository moderationItemRepository;
  private final AuditLogService auditLogService;

  @Transactional
  public ModerationItem createItem(ContentType contentType, UUID contentId, UUID submitterId) {
    ModerationItem item = new ModerationItem();
    item.setContentType(contentType);
    item.setContentId(contentId);
    item.setSubmitterId(submitterId);
    item.setStatus(ModerationStatus.PENDING);
    item.setPriority(0);
    return moderationItemRepository.save(item);
  }

  @Transactional(readOnly = true)
  public ModerationItem getItem(UUID id) {
    return moderationItemRepository
        .findById(id)
        .orElseThrow(() -> new ModerationItemNotFoundException(id));
  }

  @Transactional(readOnly = true)
  public Page<ModerationItem> getQueue(ModerationStatus status, Pageable pageable) {
    return moderationItemRepository.findByStatus(status, pageable);
  }

  @Transactional
  public ModerationItem approve(UUID id, UUID reviewerId) {
    ModerationItem item = getItem(id);
    if (item.getStatus() != ModerationStatus.PENDING) {
      throw new ItemAlreadyReviewedException(id);
    }
    item.setStatus(ModerationStatus.APPROVED);
    item.setReviewerId(reviewerId);
    item.setReviewedAt(Instant.now());
    auditLogService.logAction(reviewerId, "APPROVE", "MODERATION_ITEM", id, null);
    return moderationItemRepository.save(item);
  }

  @Transactional
  public ModerationItem reject(UUID id, UUID reviewerId, String reason) {
    ModerationItem item = getItem(id);
    if (item.getStatus() != ModerationStatus.PENDING) {
      throw new ItemAlreadyReviewedException(id);
    }
    item.setStatus(ModerationStatus.REJECTED);
    item.setReviewerId(reviewerId);
    item.setReviewedAt(Instant.now());
    item.setRejectionReason(reason);
    auditLogService.logAction(reviewerId, "REJECT", "MODERATION_ITEM", id, reason);
    return moderationItemRepository.save(item);
  }
}
```

**Step 2: Run tests to verify they pass**

Run:
```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service && ./gradlew test --tests ModerationServiceTest
```

Expected: PASS (all 6 tests)

**Step 3: Commit**

```bash
cd /c/code/AccountabilityAtlas/AcctAtlas-moderation-service
git add src/main/java/com/accountabilityatlas/moderationservice/service/ModerationService.java
git commit -m "feat: implement ModerationService (green)"
```

---

## Remaining Tasks (Summary)

The implementation plan continues with:

### Phase 2 (continued):
- **Task 14-16:** SecurityConfig, Queue controller, Queue stats endpoint

### Phase 3: Abuse Reports
- **Task 17-19:** AbuseReportService tests, implementation, controller

### Phase 4: Service Integration
- **Task 20-23:** VideoServiceClient, UserServiceClient, video tweak endpoints

### Phase 5: Trust Tier Logic
- **Task 24-26:** TrustPromotionService, TrustDemotionService with tests

### Phase 6: Event Handling
- **Task 27-29:** Event publisher, VideoSubmitted listener, UserTrustTierChanged listener

### Phase 7: Documentation & Final Tests
- **Task 30-32:** README, database-schema.md, integration tests

---

**Plan complete and saved to `docs/plans/2026-02-10-moderation-service-impl.md`.**

---

## Execution Options

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
