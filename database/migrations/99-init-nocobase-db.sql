-- Create NocoBase database if it doesn't exist
-- This script runs on PostgreSQL container initialization
SELECT 'CREATE DATABASE nocobase'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'nocobase')\gexec
