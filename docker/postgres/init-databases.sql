-- Initialize databases and users for local development
-- This script runs once when the postgres container is first created
--
-- WARNING: These are dev-only credentials. Do not use in production.

-- Create user_service database and user
CREATE USER user_service WITH PASSWORD 'local_dev';  -- dev-only password
CREATE DATABASE user_service OWNER user_service;
GRANT ALL PRIVILEGES ON DATABASE user_service TO user_service;

-- Connect to user_service database to set up schema permissions
\c user_service
GRANT ALL ON SCHEMA public TO user_service;

-- Location Service database
CREATE USER location_service WITH PASSWORD 'local_dev';  -- dev-only password
CREATE DATABASE location_service OWNER location_service;
GRANT ALL PRIVILEGES ON DATABASE location_service TO location_service;

\c location_service
CREATE EXTENSION IF NOT EXISTS postgis;
GRANT ALL ON SCHEMA public TO location_service;

-- Search Service database
CREATE USER search_service WITH PASSWORD 'local_dev';  -- dev-only password
CREATE DATABASE search_service OWNER search_service;
GRANT ALL PRIVILEGES ON DATABASE search_service TO search_service;

\c search_service
GRANT ALL ON SCHEMA public TO search_service;
