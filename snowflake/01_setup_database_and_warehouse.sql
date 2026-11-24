-- ============================================================================
-- ClaimSense Snowflake Script 01: Database, Schemas, Warehouse & Staging
-- ============================================================================
-- Cost Optimization: Uses X-SMALL warehouse with 60-second auto-suspend
-- to guarantee zero credit waste on Snowflake trial accounts.

-- 1. Create Dedicated X-Small Virtual Warehouse
CREATE WAREHOUSE IF NOT EXISTS CLAIMSENSE_WH
WITH
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60           -- Auto-suspend after 1 minute of inactivity
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Dedicated warehouse for ClaimSense analytics serving layer';

USE WAREHOUSE CLAIMSENSE_WH;

-- 2. Create Database
CREATE DATABASE IF NOT EXISTS CLAIMSENSE_DB
    COMMENT = 'Insurance Claims Analytics & Serving Database';

USE DATABASE CLAIMSENSE_DB;

-- 3. Create Multi-Tier Schemas
CREATE SCHEMA IF NOT EXISTS CLAIMSENSE_DB.STAGING
    COMMENT = 'Landing and staging tables for ingested Parquet files';

CREATE SCHEMA IF NOT EXISTS CLAIMSENSE_DB.MART
    COMMENT = 'Curated dimensional star schema and aggregated KPI marts';

-- 4. Create Parquet File Format
CREATE OR REPLACE FILE FORMAT CLAIMSENSE_DB.STAGING.PARQUET_FORMAT
    TYPE = 'PARQUET'
    COMPRESSION = 'SNAPPY';

-- 5. Create Internal Named Stage
CREATE OR REPLACE STAGE CLAIMSENSE_DB.STAGING.CLAIMSENSE_STAGE
    FILE_FORMAT = CLAIMSENSE_DB.STAGING.PARQUET_FORMAT
    COMMENT = 'Internal stage for Gold Parquet file uploads';
