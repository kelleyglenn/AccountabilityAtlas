-- RDS Database Initialization Script
-- Run once on first deployment to create per-service databases and users.
--
-- RDS notes:
--   - CREATE DATABASE cannot run inside a transaction, so this script must be
--     run as individual statements (psql -c per command), not with psql -f.
--   - The postgres user must be granted each role before creating a database
--     owned by that role (RDS restriction — postgres is not a true superuser).
--
-- Usage (from EC2 instance):
--   export PGHOST=<RDS_ENDPOINT_HOST>
--   export PGUSER=postgres
--   export PGPASSWORD='<master_password>'
--
--   # Replace CHANGE_ME_DB_PASSWORD below, then run each statement:
--   psql -d accountabilityatlas -c "CREATE USER user_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';"
--   psql -d accountabilityatlas -c "GRANT user_service TO postgres;"
--   psql -d accountabilityatlas -c "CREATE DATABASE user_service OWNER user_service;"
--   psql -d user_service -c "GRANT ALL ON SCHEMA public TO user_service;"
--   # ... repeat for each service below ...
--
-- Services and their databases:

-- user_service
CREATE USER user_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
GRANT user_service TO postgres;
CREATE DATABASE user_service OWNER user_service;
-- then: psql -d user_service -c "GRANT ALL ON SCHEMA public TO user_service;"

-- video_service
CREATE USER video_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
GRANT video_service TO postgres;
CREATE DATABASE video_service OWNER video_service;
-- then: psql -d video_service -c "GRANT ALL ON SCHEMA public TO video_service;"

-- location_service
CREATE USER location_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
GRANT location_service TO postgres;
CREATE DATABASE location_service OWNER location_service;
-- then: psql -d location_service -c "CREATE EXTENSION IF NOT EXISTS postgis; GRANT ALL ON SCHEMA public TO location_service;"

-- search_service
CREATE USER search_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
GRANT search_service TO postgres;
CREATE DATABASE search_service OWNER search_service;
-- then: psql -d search_service -c "GRANT ALL ON SCHEMA public TO search_service;"

-- moderation_service
CREATE USER moderation_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
GRANT moderation_service TO postgres;
CREATE DATABASE moderation_service OWNER moderation_service;
-- then: psql -d moderation_service -c "GRANT ALL ON SCHEMA public TO moderation_service;"
