# Dev Seed Data Design

**Date:** 2026-02-12
**Status:** Approved
**Purpose:** Populate PostgreSQL with test data for local development

---

## Overview

A Flyway-based dev seed data system that populates PostgreSQL with test users, videos, and locations for local development only. The data loads automatically when running services with the `local` Spring profile.

---

## Approach

**Flyway Repeatable Migrations** with profile gating:

- Files prefixed with `R__` run after all versioned migrations
- Re-run automatically when file content changes (checksum-based)
- Only loaded when `local` profile is active (via `application-local.yml`)

---

## File Structure

```
AcctAtlas-user-service/
└── src/main/resources/
    ├── application-local.yml           # Add devdata location
    ├── application-docker.yml          # Add devdata location
    └── db/devdata/
        └── R__dev_seed_users.sql       # 4 test users

AcctAtlas-video-service/
└── src/main/resources/
    ├── application-local.yml           # Add devdata location
    ├── application-docker.yml          # Add devdata location
    └── db/devdata/
        └── R__dev_seed_videos.sql      # 10 videos + amendments/participants

AcctAtlas-location-service/
└── src/main/resources/
    ├── application-local.yml           # Add devdata location
    ├── application-docker.yml          # Add devdata location
    └── db/devdata/
        └── R__dev_seed_locations.sql   # 10 locations + video_locations links

AcctAtlas-search-service/
└── src/main/resources/
    ├── application-local.yml           # Add devdata location
    ├── application-docker.yml          # Add devdata location
    └── db/devdata/
        └── R__dev_seed_search_videos.sql  # 10 videos (denormalized for search)
```

> **Note:** search-service requires its own seed data because it normally receives
> video data via SQS events. Direct seeding bypasses the event flow.

---

## Profile Gating

Add to each service's `application-local.yml` **AND** `application-docker.yml`:

```yaml
spring:
  flyway:
    locations:
      - classpath:db/migration
      - classpath:db/devdata
```

Both `local` (IDE/bootRun) and `docker` (docker-compose) are development environments, so both should load seed data. This ensures:
- Dev seed data loads when running via `./gradlew bootRun` (local profile)
- Dev seed data loads when running via `docker-compose` (docker profile)
- Dev seed data **never runs in production** (no devdata location configured)

---

## User Seed Data

**4 test users with predictable credentials:**

| Email | Display Name | Trust Tier | Password |
|-------|--------------|------------|----------|
| `admin@example.com` | Admin User | ADMIN | password123 |
| `moderator@example.com` | Moderator User | MODERATOR | password123 |
| `trusted@example.com` | Trusted User | TRUSTED | password123 |
| `newuser@example.com` | New User | NEW | password123 |

**Fixed UUIDs:**

| User | UUID |
|------|------|
| Admin | `00000000-0000-0000-0000-000000000001` |
| Moderator | `00000000-0000-0000-0000-000000000002` |
| Trusted | `00000000-0000-0000-0000-000000000003` |
| New User | `00000000-0000-0000-0000-000000000004` |

**Implementation notes:**
- Pre-hashed bcrypt password for `password123`
- `email_verified = true` for immediate login
- UPSERT pattern (`ON CONFLICT ... DO UPDATE`) for idempotency

---

## Video Seed Data

**10 real YouTube videos:**

| # | UUID | YouTube ID | Title | Channel | Amendments | Participants |
|---|------|------------|-------|---------|------------|--------------|
| 1 | `10000000-...-000000000001` | `RngL8_3k0C0` | NorCal Government Building Audit | Phil | FIRST | POLICE, GOVERNMENT |
| 2 | `10000000-...-000000000002` | `nQRpazbSRf4` | ELPD Audit Analysis | Audit the Audit | FIRST, FOURTH | POLICE |
| 3 | `10000000-...-000000000003` | `ULjtPKeh9Co` | 61st Precinct Brooklyn Arrest | Long Island Audit | FIRST, FOURTH | POLICE |
| 4 | `10000000-...-000000000004` | `AJi0LgnoIJA` | Utica MI Police Confrontation | Fricn Media | FIRST, FOURTH | POLICE |
| 5 | `10000000-...-000000000005` | `OdsTAYnC8Kc` | Pocahontas City Hall | The Random Patriot | FIRST | GOVERNMENT |
| 6 | `10000000-...-000000000006` | `-kNacBPsNxo` | San Antonio Strip Mall | Mexican Padilla | FIRST | POLICE, BUSINESS |
| 7 | `10000000-...-000000000007` | `IX_8Epjcp54` | Leon Valley Police Press Conf | News Now Houston | FIRST | POLICE, GOVERNMENT |
| 8 | `10000000-...-000000000008` | `hkhrXPur4ws` | Silverthorne Post Office | Amagansett Press | FIRST | GOVERNMENT |
| 9 | `10000000-...-000000000009` | `QgkT4epLRcw` | East Lansing PD Incident | Livingston Audits | FIRST | POLICE |
| 10 | `10000000-...-000000000010` | `FwvZCn0uLiw` | Pocahontas Uncut Footage | The Random Patriot | FIRST | GOVERNMENT |

**Implementation notes:**
- All videos set to `status = 'APPROVED'`
- `submitted_by` references Trusted User (`00000000-0000-0000-0000-000000000003`)
- Real YouTube IDs ensure thumbnails load in UI

---

## Location Seed Data

### San Francisco Area (5 locations)

| # | UUID | Video | Location | Lat | Lng |
|---|------|-------|----------|-----|-----|
| 1 | `20000000-...-000000000001` | #1 NorCal Audit | SF City Hall | 37.7793 | -122.4193 |
| 2 | `20000000-...-000000000002` | #2 Audit the Audit | Oakland Federal Building | 37.8044 | -122.2712 |
| 3 | `20000000-...-000000000003` | #3 Brooklyn Arrest | San Jose Police HQ | 37.3382 | -121.8863 |
| 4 | `20000000-...-000000000004` | #4 Utica Confrontation | Fremont City Hall | 37.5485 | -121.9886 |
| 5 | `20000000-...-000000000005` | #5 Pocahontas City Hall | Berkeley Post Office | 37.8716 | -122.2727 |

### Scattered Across USA (5 locations)

| # | UUID | Video | Location | Lat | Lng |
|---|------|-------|----------|-----|-----|
| 6 | `20000000-...-000000000006` | #6 San Antonio | San Antonio, TX | 29.4241 | -98.4936 |
| 7 | `20000000-...-000000000007` | #7 Leon Valley | Leon Valley, TX | 29.4952 | -98.6136 |
| 8 | `20000000-...-000000000008` | #8 Silverthorne | Silverthorne, CO | 39.6336 | -106.0753 |
| 9 | `20000000-...-000000000009` | #9 East Lansing | East Lansing, MI | 42.7370 | -84.4839 |
| 10 | `20000000-...-000000000010` | #10 Pocahontas | Pocahontas, AR | 36.2612 | -90.9712 |

**Implementation notes:**
- Coordinates use PostGIS `GEOMETRY(Point, 4326)` format
- Each location links to its video via `video_locations` junction table
- All locations marked as `is_primary = true`

---

## UUID Convention

Predictable UUIDs for cross-service references:

| Entity | UUID Pattern | Example |
|--------|--------------|---------|
| Users | `00000000-0000-0000-0000-00000000000X` | `...0001` = Admin |
| Videos | `10000000-0000-0000-0000-00000000000X` | `...0001` = Video 1 |
| Locations | `20000000-0000-0000-0000-00000000000X` | `...0001` = Location 1 |

---

## Verification

After running services with local profile:

```sql
-- Check users
SELECT email, trust_tier FROM users.users WHERE email LIKE '%@example.com';

-- Check videos
SELECT youtube_id, title, status FROM videos.videos;

-- Check locations
SELECT display_name, ST_AsText(coordinates) FROM locations.locations;

-- Check video-location links
SELECT v.youtube_id, l.display_name
FROM videos.videos v
JOIN locations.video_locations vl ON v.id = vl.video_id
JOIN locations.locations l ON vl.location_id = l.id;
```

Or open map page at `http://localhost:3000/map` and verify markers appear.

---

## Implementation Checklist

- [x] Create `db/devdata/R__dev_seed_users.sql` in user-service
- [x] Update `application-local.yml` in user-service (add devdata location)
- [x] Update `application-docker.yml` in user-service (add devdata location)
- [x] Create `db/devdata/R__dev_seed_videos.sql` in video-service
- [x] Update `application-local.yml` in video-service (add devdata location)
- [x] Update `application-docker.yml` in video-service (add devdata location)
- [x] Create `db/devdata/R__dev_seed_locations.sql` in location-service
- [x] Update `application-local.yml` in location-service (add devdata location)
- [x] Update `application-docker.yml` in location-service (add devdata location)
- [x] Create `db/devdata/R__dev_seed_search_videos.sql` in search-service
- [x] Update `application-local.yml` in search-service (add devdata location)
- [x] Update `application-docker.yml` in search-service (add devdata location)
- [ ] Merge PRs and test with `docker-compose up`
- [ ] Verify map page shows markers
