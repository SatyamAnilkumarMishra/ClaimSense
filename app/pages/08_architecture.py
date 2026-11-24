"""ClaimSense: Architecture, Decisions & Design Specs Page."""

import streamlit as st


def render():
    st.title("🏛️ Architecture, Trade-offs & Design Decisions")
    st.markdown(
        "Detailed reference documentation covering Lakehouse data flow, architectural decision records (ADRs), PySpark optimizations, and ValueMomentum syllabus alignment."
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "System Architecture",
            "Design Decision Records",
            "Spark Optimization",
            "ValueMomentum Alignment",
        ]
    )

    with tab1:
        st.markdown("### 📐 End-to-End Lakehouse & Agent Data Flow")
        st.code(
            """
        [ Landing Zone: Unity Catalog Volume ]
                         │
                         ▼ (Auto Loader: cloudFiles, schema evolution, .trigger(availableNow=True))
        ┌─────────────────────────────────────────────────────────┐
        │ Bronze Delta Tables (Append-Only)                       │
        │ - bronze_customers, bronze_policies, bronze_claims       │
        │ - Metadata: _ingest_timestamp, _source_file             │
        └────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼ (PySpark Cleaning, Dedup Window Functions, Referential Checks)
        ┌─────────────────────────────────────────────────────────┐
        │ Silver Delta Tables (Cleaned & Quarantined)             │
        │ - silver_customers, silver_policies, silver_claims      │ ──▶ [ quarantine_claims ]
        │ - Delta MERGE (Upsert by claim_id for CDC updates)      │ ──▶ [ dq_results ]
        └────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼ (Star Schema Modeling, Surrogate Keys, Window CTEs)
        ┌─────────────────────────────────────────────────────────┐
        │ Gold Delta Tables (Star Schema & KPIs)                  │
        │ - dim_customer, dim_policy, dim_claim_type, dim_date    │
        │ - fact_claims, kpi_claims_by_type_month                 │ ──▶ [ pipeline_audit ]
        └────────────────────────────┬────────────────────────────┘
                                     │
             ┌───────────────────────┴───────────────────────┐
             ▼                                               ▼
        [ Databricks SQL Warehouse ]           [ LangGraph AI Triage Agent ]
        (Fixed Parameterised Queries)          (Prompt Delimiters + Grounded Citations)
             │                                               │
             └───────────────────────┬───────────────────────┘
                                     ▼
                     [ Shared Python Service Layer ]
                     (claimsense.services.claims_service)
                             │               │
             ┌───────────────┘               └───────────────┐
             ▼                                               ▼
    [ Streamlit Cloud UI ]                          [ FastAPI REST API ]
    (BACKEND_MODE=inprocess)                        (BACKEND_MODE=http, X-API-Key)
        """,
            language="text",
        )

    with tab2:
        st.markdown("### 📋 Key Architectural Decision Records (ADRs)")
        st.markdown("""
        | Decision Area | Architectural Choice | Rationale | Trade-off / Mitigation |
        | :--- | :--- | :--- | :--- |
        | **Lakehouse Storage** | Delta Lake (Medallion) | ACID transactions, schema enforcement, time travel, and native `MERGE`. | Slightly more complex metadata management vs raw Parquet. |
        | **Ingestion Engine** | Databricks Auto Loader (`cloudFiles`) | Handles schema evolution, file discovery, and incremental ingestion automatically. | Bound to Spark runtime; simulated locally using python for zero-cost testability. |
        | **Database Fallback** | Dual-Mode Resilient DB Client | Guarantees zero crashes on Free Edition cold starts, suspension, or quota expiration. | Requires maintaining local snapshot tables in `snapshots/`. |
        | **AI Agent Engine** | LangGraph StateGraph | Typed explicit state, checkpointing, and native human-in-the-loop review. | State schemas must be strictly defined with Pydantic/TypedDict. |
        | **Deployment Architecture** | In-Process Shared Service Layer | Streamlit Community Cloud hosts only a single repo container without background microservices. | FastAPI runs as an alternative REST showcase rather than a hard runtime dependency. |
        """)

    with tab3:
        st.markdown("### ⚡ PySpark & Spark SQL Query Optimization")
        st.markdown("""
        #### 1. Space-Filling Z-ORDER / Liquid Clustering
        Traditional physical partitioning by date creates the small-file problem when claims arrive in small hourly or daily batches.
        ClaimSense utilizes **Z-ORDER clustering** on `(incident_date, claim_type_sk)`:
        ```sql
        OPTIMIZE claimsense.fact_claims
        ZORDER BY (incident_date, claim_type_sk);
        ```
        * **Benefit**: Collocates multi-dimensional records along a Hilbert curve, allowing Catalyst file readers to skip 80%+ of Parquet row groups using column min/max statistics.

        #### 2. Broadcast Hash Join Elimination of Shuffles
        Because dimension tables (`dim_claim_type`, `dim_date`) are small (<10 MB), Spark Catalyst performs **BroadcastHashJoins**:
        ```sql
        -- Broadcast join eliminates network shuffle exchanges
        SELECT /*+ BROADCAST(t) */ f.claim_id, t.claim_type
        FROM fact_claims f
        JOIN dim_claim_type t ON f.claim_type_sk = t.claim_type_sk;
        ```
        """)

    with tab4:
        st.markdown("### 🎯 ValueMomentum Evaluator Mapping")
        st.markdown("""
        | Evaluator Skill Expected | Where Demonstrated in ClaimSense |
        | :--- | :--- |
        | **PySpark & Delta Lake** | Medallion notebooks, Delta `MERGE` upserts, Auto Loader, `pipeline_audit` arithmetic reconciliation. |
        | **Data Modeling** | Kimball Star Schema (`fact_claims`, `dim_customer`, `dim_policy`, `dim_claim_type`, `dim_date`). |
        | **Data Quality & Governance**| Quarantine tables, rule hierarchy (`ERR_*`), lineage comparison, zero raw data drops. |
        | **AI Agent & LLMs** | LangGraph StateGraph, Groq model routing, anti-hallucination citation verifier, human review checkpoints. |
        | **Enterprise API Design** | FastAPI with constant-time `X-API-Key` auth, SlowAPI rate-limiting, CORS, Pydantic v2 schemas. |
        | **Resilience & Production Readiness**| Resilient DB client, offline snapshot mode, zero hardcoded credentials, CI/CD pipeline. |
        """)


if __name__ == "__main__":
    render()
