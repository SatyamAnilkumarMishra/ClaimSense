# ClaimSense: Snowflake Serving Layer Guide

This directory contains the complete set of reproducible SQL scripts and Parquet staging utilities for deploying the ClaimSense downstream serving mart on Snowflake.

---

## 📁 File Structure

| Script | Purpose |
| :--- | :--- |
| `export_gold_to_parquet.py` | Extracts Gold Star Schema tables from ClaimSense to Parquet in `staged_data/`. |
| `01_setup_database_and_warehouse.sql` | DDL for `CLAIMSENSE_WH` (X-Small, auto-suspend 60s), `CLAIMSENSE_DB`, schemas, and internal stage. |
| `02_staging_tables_and_copy_into.sql` | DDL for staging tables (`STG_*`) and `COPY INTO` ingestion from internal stage. |
| `03_streams_and_tasks_mart_refresh.sql`| Snowflake `STREAM` on staging table and `TASK` (or Dynamic Table) for CDC mart refreshes. |
| `04_rbac_roles_and_privileges.sql` | Enterprise RBAC implementation (`CLAIMS_ANALYST`, `CLAIMS_DATA_ENGINEER`, `CLAIMS_SIU_INVESTIGATOR`). |
| `05_time_travel_and_cloning.sql` | Demonstration queries for Snowflake Time Travel (`AT(OFFSET)`) and Zero-Copy Cloning (`CLONE`). |

---

## 🚀 Execution Steps on a Snowflake Trial Account

1. **Sign Up for Direct Snowflake Free Trial**:
   * Visit [signup.snowflake.com](https://signup.snowflake.com) (Select direct account, Standard or Enterprise edition, AWS/Azure, **no credit card** required).

2. **Generate Parquet Staging Files**:
   ```powershell
   python snowflake/export_gold_to_parquet.py
   ```

3. **Execute SQL Scripts in Order**:
   In Snowflake Snowsight Web UI, run:
   * Run `01_setup_database_and_warehouse.sql`
   * Run `02_staging_tables_and_copy_into.sql`
   * Run `03_streams_and_tasks_mart_refresh.sql`
   * Run `04_rbac_roles_and_privileges.sql`
   * Run `05_time_travel_and_cloning.sql`

4. **Connect to ClaimSense (Optional)**:
   Add credentials to `.env`:
   ```ini
   SNOWFLAKE_ACCOUNT=xy12345.us-east-1
   SNOWFLAKE_USER=YOUR_USERNAME
   SNOWFLAKE_PASSWORD=YOUR_PASSWORD
   SNOWFLAKE_WAREHOUSE=CLAIMSENSE_WH
   SNOWFLAKE_DATABASE=CLAIMSENSE_DB
   SNOWFLAKE_SCHEMA=MART
   ```
   The Streamlit app will immediately detect the connection and switch from cached fallback mode to live Snowflake serving!
