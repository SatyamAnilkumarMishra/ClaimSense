-- ============================================================================
-- ClaimSense Snowflake Script 02: Staging Tables & COPY INTO Ingestion
-- ============================================================================

USE WAREHOUSE CLAIMSENSE_WH;
USE DATABASE CLAIMSENSE_DB;
USE SCHEMA STAGING;

-- 1. Create Staging Tables matching exported Parquet schemas
CREATE OR REPLACE TABLE STAGING.STG_FACT_CLAIMS (
    claim_sk VARCHAR(64),
    claim_id VARCHAR(32),
    policy_sk VARCHAR(64),
    customer_sk VARCHAR(64),
    claim_type_sk VARCHAR(64),
    incident_date_key INTEGER,
    reported_date_key INTEGER,
    incident_date DATE,
    reported_date DATE,
    reporting_delay_days INTEGER,
    claimed_amount NUMBER(12,2),
    claim_status VARCHAR(32),
    documents_count INTEGER,
    description VARCHAR,
    city VARCHAR(64),
    is_settled INTEGER,
    flag_high_risk_customer INTEGER,
    _gold_timestamp TIMESTAMP_NTZ
);

CREATE OR REPLACE TABLE STAGING.STG_DIM_CUSTOMER (
    customer_sk VARCHAR(64),
    customer_id VARCHAR(32),
    first_name VARCHAR(64),
    last_name VARCHAR(64),
    full_name VARCHAR(128),
    email VARCHAR(128),
    phone VARCHAR(32),
    city VARCHAR(64),
    state VARCHAR(32),
    risk_score NUMBER(3,2),
    created_at TIMESTAMP_NTZ
);

CREATE OR REPLACE TABLE STAGING.STG_DIM_POLICY (
    policy_sk VARCHAR(64),
    policy_id VARCHAR(32),
    customer_id VARCHAR(32),
    customer_sk VARCHAR(64),
    policy_type VARCHAR(16),
    start_date DATE,
    end_date DATE,
    sum_insured NUMBER(12,2),
    deductible NUMBER(10,2),
    policy_status VARCHAR(16)
);

CREATE OR REPLACE TABLE STAGING.STG_DIM_CLAIM_TYPE (
    claim_type_sk VARCHAR(64),
    claim_type VARCHAR(32)
);

-- 2. COPY INTO Commands (Executed after SnowSQL PUT @CLAIMSENSE_STAGE)
-- Example upload command via SnowSQL CLI:
-- PUT file:///d:/ClaimSense/snowflake/staged_data/*.parquet @CLAIMSENSE_STAGE;

COPY INTO STAGING.STG_FACT_CLAIMS
FROM (
    SELECT
        $1:claim_sk::VARCHAR,
        $1:claim_id::VARCHAR,
        $1:policy_sk::VARCHAR,
        $1:customer_sk::VARCHAR,
        $1:claim_type_sk::VARCHAR,
        $1:incident_date_key::INTEGER,
        $1:reported_date_key::INTEGER,
        $1:incident_date::DATE,
        $1:reported_date::DATE,
        $1:reporting_delay_days::INTEGER,
        $1:claimed_amount::NUMBER(12,2),
        $1:claim_status::VARCHAR,
        $1:documents_count::INTEGER,
        $1:description::VARCHAR,
        $1:city::VARCHAR,
        $1:is_settled::INTEGER,
        $1:flag_high_risk_customer::INTEGER,
        $1:_gold_timestamp::TIMESTAMP_NTZ
    FROM @CLAIMSENSE_STAGE/fact_claims.parquet
)
FILE_FORMAT = (FORMAT_NAME = 'PARQUET_FORMAT')
ON_ERROR = 'CONTINUE';

COPY INTO STAGING.STG_DIM_CUSTOMER
FROM @CLAIMSENSE_STAGE/dim_customer.parquet
FILE_FORMAT = (FORMAT_NAME = 'PARQUET_FORMAT')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
ON_ERROR = 'CONTINUE';

COPY INTO STAGING.STG_DIM_POLICY
FROM @CLAIMSENSE_STAGE/dim_policy.parquet
FILE_FORMAT = (FORMAT_NAME = 'PARQUET_FORMAT')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
ON_ERROR = 'CONTINUE';

COPY INTO STAGING.STG_DIM_CLAIM_TYPE
FROM @CLAIMSENSE_STAGE/dim_claim_type.parquet
FILE_FORMAT = (FORMAT_NAME = 'PARQUET_FORMAT')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
ON_ERROR = 'CONTINUE';
