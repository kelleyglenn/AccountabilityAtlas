# Design: Add SECURITY Participant Type

**Date:** 2026-02-19
**Issue:** [#46](https://github.com/kelleyglenn/AccountabilityAtlas/issues/46)

## Summary

Add `SECURITY` as a new participant type to capture interactions with private security guards, bouncers, and non-law-enforcement security personnel. The current enum is `POLICE, GOVERNMENT, BUSINESS, CITIZEN`.

## Scope

**6 repos** need changes:

| Repo | Changes |
|------|---------|
| video-service | Java enum, API spec, DB migration, dev seed data, technical.md |
| search-service | Java enum, API spec, technical.md |
| moderation-service | API spec (generated enum updates automatically) |
| web-app | `PARTICIPANT_TYPE_OPTIONS`, remove dead `Participant` interface, map-integration.md |
| integration-tests | Seed data fixtures, filter test for SECURITY |
| top-level docs | 04-ServiceCatalog.md, 05-DataArchitecture.md |

**No changes** to: api-gateway, location-service, user-service.

**Note:** The original issue said moderation-service needs no changes, but it has the participant enum in its API spec and generated models. Including it here to avoid drift.

## Detailed Changes

### video-service

**`Participant.java`** — Add `SECURITY` to enum:
```java
public enum Participant {
  POLICE, GOVERNMENT, BUSINESS, CITIZEN, SECURITY
}
```

**`api-specification.yaml`** — Update `Participant` schema enum to include `SECURITY`.

**New Flyway migration `V3__add_security_participant.sql`**:
```sql
ALTER TABLE videos.video_participants
    DROP CONSTRAINT valid_participant,
    ADD CONSTRAINT valid_participant CHECK (
        participant IN ('POLICE', 'GOVERNMENT', 'BUSINESS', 'CITIZEN', 'SECURITY')
    );
```

**Dev seed data `R__dev_seed_videos.sql`** — Add `SECURITY` and `CITIZEN` to some seed videos (both are currently unrepresented in seed data).

**`docs/technical.md`** — Update enum reference.

### search-service

**`Participant.java`** — Add `SECURITY` to enum.

**`api-specification.yaml`** — Update enum in query parameter and response schemas.

**`docs/technical.md`** — Update enum references and examples.

**No database migration needed** — participants are stored as `VARCHAR(20)[]` with no CHECK constraint.

### moderation-service

**`api-specification.yaml`** — Add `SECURITY` to participants enum. Generated `UpdateVideoRequest.ParticipantsEnum` updates automatically on build.

### web-app

**`src/types/map.ts`**:
- Add `{ id: "SECURITY", label: "Security" }` to `PARTICIPANT_TYPE_OPTIONS`
- Remove dead `Participant` interface (id/name/role/organizationType) — unused, confusing name collision

**`docs/map-integration.md`** — Add SECURITY to filter values table.

No component changes — `ParticipantFilter` and `VideoSubmitForm` render dynamically from `PARTICIPANT_TYPE_OPTIONS`.

### integration-tests

**`e2e/fixtures/seed-data.ts`** — Add SECURITY and CITIZEN to some seed video fixtures.

**API tests** — Add test filtering by `participants=SECURITY`.

### Top-level docs

**`docs/04-ServiceCatalog.md`** — Update all participant enum references.

**`docs/05-DataArchitecture.md`** — Update CHECK constraint example.

## Design Decisions

- **Migration approach**: Drop and re-add CHECK constraint (Approach A). Simpler than switching to PostgreSQL ENUM type, maintains existing patterns.
- **Seed data**: Add both SECURITY and CITIZEN to dev seed data since neither is currently represented.
- **Dead code cleanup**: Remove unused `Participant` interface in web-app `map.ts` to avoid confusion with the participant type enum.
