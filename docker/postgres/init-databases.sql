-- Initialize databases and users for local development
-- This script runs once when the postgres container is first created

-- Create user_service database and user
CREATE USER user_service WITH PASSWORD 'local_dev';
CREATE DATABASE user_service OWNER user_service;
GRANT ALL PRIVILEGES ON DATABASE user_service TO user_service;

-- Connect to user_service database to set up schema permissions
\c user_service
GRANT ALL ON SCHEMA public TO user_service;
