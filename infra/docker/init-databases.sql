-- RDS Database Initialization Script
-- Run once on first deployment to create per-service databases and users.
--
-- Usage (from EC2 instance):
--   psql -h <RDS_ENDPOINT> -U postgres -d accountabilityatlas -f init-databases.sql
--
-- Replace CHANGE_ME_DB_PASSWORD with the actual service database password before running.

-- Create user_service database and user
CREATE USER user_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
CREATE DATABASE user_service OWNER user_service;
GRANT ALL PRIVILEGES ON DATABASE user_service TO user_service;

-- Connect to user_service database to set up schema permissions
\c user_service
GRANT ALL ON SCHEMA public TO user_service;

-- Location Service database
\c accountabilityatlas
CREATE USER location_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
CREATE DATABASE location_service OWNER location_service;
GRANT ALL PRIVILEGES ON DATABASE location_service TO location_service;

-- Connect to location_service database; create PostGIS extension (requires rds_superuser role)
\c location_service
CREATE EXTENSION IF NOT EXISTS postgis;
GRANT ALL ON SCHEMA public TO location_service;

-- Search Service database
\c accountabilityatlas
CREATE USER search_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
CREATE DATABASE search_service OWNER search_service;
GRANT ALL PRIVILEGES ON DATABASE search_service TO search_service;

\c search_service
GRANT ALL ON SCHEMA public TO search_service;

-- Video Service database
\c accountabilityatlas
CREATE USER video_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
CREATE DATABASE video_service OWNER video_service;
GRANT ALL PRIVILEGES ON DATABASE video_service TO video_service;

\c video_service
GRANT ALL ON SCHEMA public TO video_service;

-- Moderation Service database
\c accountabilityatlas
CREATE USER moderation_service WITH PASSWORD 'CHANGE_ME_DB_PASSWORD';
CREATE DATABASE moderation_service OWNER moderation_service;
GRANT ALL PRIVILEGES ON DATABASE moderation_service TO moderation_service;

\c moderation_service
GRANT ALL ON SCHEMA public TO moderation_service;
