-- ============================================================================
-- ClaimSense Snowflake Script 03: Streams, Tasks & Mart Refresh
-- ============================================================================

USE WAREHOUSE CLAIMSENSE_WH;
USE DATABASE CLAIMSENSE_DB;

-- 1. Create Curated Mart Table
CREATE OR REPLACE TABLE MART.CLAIMS_SUMMARY_MART (
    claim_type VARCHAR(32),
    total_claims NUMBER,
    total_claimed_amount NUMBER(14,2),
    avg_claimed_amount NUMBER(12,2),
    avg_reporting_delay_days NUMBER(6,1),
    high_risk_claim_count NUMBER,
    last_refreshed_at TIMESTAMP_NTZ
);

-- Initial Population of Mart
INSERT INTO MART.CLAIMS_SUMMARY_MART
SELECT
    t.claim_type,
    COUNT(f.claim_sk),
    ROUND(SUM(f.claimed_amount), 2),
    ROUND(AVG(f.claimed_amount), 2),
    ROUND(AVG(f.reporting_delay_days), 1),
    SUM(f.flag_high_risk_customer),
    CURRENT_TIMESTAMP()
FROM STAGING.STG_FACT_CLAIMS f
JOIN STAGING.STG_DIM_CLAIM_TYPE t ON f.claim_type_sk = t.claim_type_sk
GROUP BY t.claim_type;

-- 2. Create Snowflake Stream on Staging Table for CDC Change Tracking
CREATE OR REPLACE STREAM STAGING.FACT_CLAIMS_STREAM
    ON TABLE STAGING.STG_FACT_CLAIMS
    APPEND_ONLY = FALSE
    COMMENT = 'CDC stream capturing incoming claims changes for downstream mart refresh';

-- 3. Create Incremental Refresh Task (Or Modern Snowflake Dynamic Table)
-- Option A: Incremental Task triggered when stream has new data
CREATE OR REPLACE TASK MART.REFRESH_CLAIMS_MART_TASK
    WAREHOUSE = CLAIMSENSE_WH
    SCHEDULE = '5 MINUTE'
    WHEN SYSTEM$STREAM_HAS_DATA('STAGING.FACT_CLAIMS_STREAM')
AS
MERGE INTO MART.CLAIMS_SUMMARY_MART target
USING (
    SELECT
        t.claim_type,
        COUNT(f.claim_sk) AS total_claims,
        ROUND(SUM(f.claimed_amount), 2) AS total_claimed_amount,
        ROUND(AVG(f.claimed_amount), 2) AS avg_claimed_amount,
        ROUND(AVG(f.reporting_delay_days), 1) AS avg_reporting_delay_days,
        SUM(f.flag_high_risk_customer) AS high_risk_claim_count,
        CURRENT_TIMESTAMP() AS last_refreshed_at
    FROM STAGING.STG_FACT_CLAIMS f
    JOIN STAGING.STG_DIM_CLAIM_TYPE t ON f.claim_type_sk = t.claim_type_sk
    GROUP BY t.claim_type
) source
ON target.claim_type = source.claim_type
WHEN MATCHED THEN UPDATE SET
    target.total_claims = source.total_claims,
    target.total_claimed_amount = source.total_claimed_amount,
    target.avg_claimed_amount = source.avg_claimed_amount,
    target.avg_reporting_delay_days = source.avg_reporting_delay_days,
    target.high_risk_claim_count = source.high_risk_claim_count,
    target.last_refreshed_at = source.last_refreshed_at
WHEN NOT MATCHED THEN INSERT (
    claim_type, total_claims, total_claimed_amount, avg_claimed_amount,
    avg_reporting_delay_days, high_risk_claim_count, last_refreshed_at
) VALUES (
    source.claim_type, source.total_claims, source.total_claimed_amount, source.avg_claimed_amount,
    source.avg_reporting_delay_days, source.high_risk_claim_count, source.last_refreshed_at
);

-- Note: Tasks are created suspended by default. Enable when running in live trial:
-- ALTER TASK MART.REFRESH_CLAIMS_MART_TASK RESUME;
