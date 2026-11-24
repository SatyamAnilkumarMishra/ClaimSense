"""ClaimSense: Snowflake Analytics Mart Page."""

import pandas as pd
import streamlit as st
from claimsense.config import get_settings
from claimsense.db.client_factory import get_db_client


def render():
    st.title("❄️ Snowflake Serving Layer (Mart)")
    st.markdown("Examine the downstream serving layer designed for enterprise BI tools, role-based access control (RBAC), and Dynamic Tables / Tasks.")

    settings = get_settings()
    db = get_db_client()

    # Snowflake Connectivity Card
    if settings.is_snowflake_configured:
        st.success(f"Connected to Snowflake Warehouse: {settings.SNOWFLAKE_WAREHOUSE} | DB: {settings.SNOWFLAKE_DATABASE}.{settings.SNOWFLAKE_SCHEMA}")
    else:
        st.info("Snowflake Serving Layer: Currently operating in Stage 7 Cached Mode. Full SQL DDL/DML, stages, tasks, and RBAC scripts are preserved in the `snowflake/` repository folder.")

    # Snowflake Mart Summary Metrics
    st.markdown("### 📊 Curated Mart View: `CLAIMS_SUMMARY_MART`")

    # Fetch Gold facts as representation of Snowflake mart data
    rows = db.execute_query("""
        SELECT
            t.claim_type,
            COUNT(f.claim_sk) AS total_claims,
            ROUND(SUM(f.claimed_amount), 2) AS total_claimed,
            ROUND(AVG(f.claimed_amount), 2) AS avg_claimed,
            ROUND(AVG(f.reporting_delay_days), 1) AS avg_delay_days
        FROM fact_claims f
        JOIN dim_claim_type t ON f.claim_type_sk = t.claim_type_sk
        GROUP BY t.claim_type
    """)

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()

    # RBAC and Time Travel Showcase
    st.markdown("### 🔒 Enterprise Governance: Role-Based Access Control (RBAC)")
    st.markdown("""
    | Role | Granted Privileges | Objects Accessible | Business Persona |
    | :--- | :--- | :--- | :--- |
    | `CLAIMS_ANALYST` | `SELECT` only | `CLAIMS_SUMMARY_MART`, `DIM_*` | Actuary & Claims BI Analysts |
    | `CLAIMS_DATA_ENGINEER` | `ALL PRIVILEGES` | `STAGING`, `STREAMS`, `TASKS` | Data Engineering & ETL Pipeline |
    | `CLAIMS_SIU_INVESTIGATOR` | `SELECT` with row-masking | Masked Customer PII + Risk Scores | Fraud & SIU Investigators |
    """)

    with st.expander("⏱️ Snowflake Time Travel & Zero-Copy Clone DDL"):
        st.code("""
        -- Snowflake Time Travel Demonstration
        SELECT * FROM CLAIMSENSE_DB.MART.FACT_CLAIMS
        AT(OFFSET => -60*5); -- Query state exactly 5 minutes ago

        -- Zero-Copy Clone for Dev/Testing
        CREATE TABLE CLAIMSENSE_DB.MART.FACT_CLAIMS_DEV
        CLONE CLAIMSENSE_DB.MART.FACT_CLAIMS;
        """, language="sql")


if __name__ == "__main__":
    render()
