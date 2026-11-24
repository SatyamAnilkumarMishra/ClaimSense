# Snowflake Staging & SQL Query Evidence (ISS-07)

## Execution Status
* **Status**: **Local Staging Prepared / Live Remote Execution Not Yet Executed**
* **Staged Files**: `snowflake/staged_data/` contains Parquet exports of `fact_claims.parquet` (571 rows), `dim_customer.parquet` (100 rows), `dim_policy.parquet` (150 rows), and `pipeline_audit.parquet` (1 row).
* **SQL Scripts Prepared**:
  - `01_setup_database_and_warehouse.sql`: Database, schema, and compute warehouse DDL.
  - `02_staging_tables_and_copy_into.sql`: Staging tables, file formats, and `COPY INTO` commands.
  - `03_silver_gold_serving_views.sql`: Dynamic Tables and Kimball serving views.
  - `04_rbac_security_roles.sql`: Granular RBAC (`ANALYST`, `AUDITOR`, `DATA_ENGINEER`).
  - `05_time_travel_and_cloning.sql`: Time travel queries and zero-copy cloning.

## Local Parquet Verification

```text
fact_claims.parquet:    571 rows (matches Gold Fact count)
dim_customer.parquet:   100 rows
dim_policy.parquet:     150 rows
pipeline_audit.parquet: 1 row
```

*Note: Per ISS-07 guidelines, remote warehouse execution has not yet been executed on a cloud Snowflake instance and is transparently recorded as such.*
