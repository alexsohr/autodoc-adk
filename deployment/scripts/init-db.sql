-- init-db.sql: Runs on first PostgreSQL startup
-- The 'autodoc' database is created automatically by POSTGRES_DB env var.

-- Create the 'prefect' database for Prefect Server
SELECT 'CREATE DATABASE prefect'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'prefect')\gexec

-- Enable pgvector extension on autodoc database (already connected to it)
CREATE EXTENSION IF NOT EXISTS vector;
