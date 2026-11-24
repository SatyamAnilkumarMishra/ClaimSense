-- ============================================================================
-- ClaimSense Snowflake Script 05: Time Travel & Zero-Copy Cloning
-- ============================================================================

USE WAREHOUSE CLAIMSENSE_WH;
USE DATABASE CLAIMSENSE_DB;
USE SCHEMA MART;

-- ----------------------------------------------------------------------------
-- DEMO A: Snowflake Time Travel
-- Query historical data before changes or accidental updates occur
-- ----------------------------------------------------------------------------

-- Check current state
SELECT COUNT(*), SUM(total_claimed_amount) FROM MART.CLAIMS_SUMMARY_MART;

-- 1. Query table state from 5 minutes ago using OFFSET (in seconds)
SELECT *
FROM MART.CLAIMS_SUMMARY_MART
AT(OFFSET => -60 * 5);

-- 2. Query table state before a specific Query ID (e.g. before an accidental UPDATE)
-- SELECT * FROM MART.CLAIMS_SUMMARY_MART BEFORE(STATEMENT => '01b2c3d4-0000-xxxx-xxxx-xxxxxxxxxxxx');

-- 3. Undrop demonstration (if an object was accidentally dropped)
-- DROP TABLE MART.CLAIMS_SUMMARY_MART;
-- UNDROP TABLE MART.CLAIMS_SUMMARY_MART;

-- ----------------------------------------------------------------------------
-- DEMO B: Zero-Copy Cloning
-- Instant, zero-storage-cost duplication of tables/schemas for Dev & Testing
-- ----------------------------------------------------------------------------

-- 1. Clone a production mart table for testing
CREATE OR REPLACE TABLE MART.CLAIMS_SUMMARY_MART_DEV
    CLONE MART.CLAIMS_SUMMARY_MART
    COMMENT = 'Zero-copy clone created for developer experimentation with 0 extra storage cost';

-- 2. Verify cloned table contains identical data
SELECT COUNT(*) FROM MART.CLAIMS_SUMMARY_MART_DEV;

-- 3. Modify cloned table without affecting production
UPDATE MART.CLAIMS_SUMMARY_MART_DEV
SET total_claims = total_claims + 100
WHERE claim_type = 'AUTO';

-- Production table remains completely untouched!
SELECT claim_type, total_claims FROM MART.CLAIMS_SUMMARY_MART WHERE claim_type = 'AUTO';
SELECT claim_type, total_claims FROM MART.CLAIMS_SUMMARY_MART_DEV WHERE claim_type = 'AUTO';
