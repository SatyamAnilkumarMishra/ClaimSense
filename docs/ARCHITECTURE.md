# ClaimSense Architectural Blueprint

ClaimSense is an enterprise-grade Insurance Claims Lakehouse & Anti-Hallucinating AI Triage Platform designed for reliable, auditable, and zero-cost operation.

---

## 1. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph DataIngestion ["1. Data Ingestion & Storage"]
        Raw["Messy Claim Batches (CSV/JSON)"] --> Landing["Unity Catalog Volume (landing_zone)"]
        Landing --> AutoLoader["Databricks Auto Loader (cloudFiles)"]
    end

    subgraph MedallionLakehouse ["2. Medallion Lakehouse Engine"]
        AutoLoader --> Bronze["Bronze Delta (Append-only, Schema Evolution)"]
        Bronze --> Silver["Silver Delta (PySpark Dedup, Normalization, Delta MERGE)"]
        Silver -. Defective Records .-> Quarantine["quarantine_claims (Error Hierarchy)"]
        Silver --> Gold["Gold Star Schema (dim_customer, dim_policy, fact_claims)"]
        Gold --> Recon["pipeline_audit (Mathematical Reconciliation)"]
    end

    subgraph ServiceLayer ["3. Resilient Service & API Layer"]
        Gold --> ResilientDB["Resilient DB Client (Databricks SQL Warehouse)"]
        ResilientDB -. Cold Sleep / Quota Fallback .-> LocalSnapshot["Local Parquet/SQLite Snapshot"]
        ResilientDB --> DomainService["Shared ClaimsService (claimsense.services)"]
        DomainService --> FastAPI["FastAPI REST Application (X-API-Key, SlowAPI)"]
    end

    subgraph AIAgent ["4. LangGraph Triage Agent"]
        DomainService --> Agent["LangGraph StateGraph Engine"]
        Agent --> Tools["Parameterised Tools (Allow-List)"]
        Agent --> Retriever["Policy Clause Retriever (TF-IDF)"]
        Agent --> Verifier["Citation Verifier (Anti-Hallucination)"]
        Agent --> Groq["Groq LLM (llama-3.1-8b & llama-3.3-70b)"]
        Agent --> HumanUI["Human Adjuster Review Checkpoint"]
    end

    subgraph Presentation ["5. Presentation & Serving"]
        DomainService --> Streamlit["Streamlit UI (Community Cloud, Dark Theme)"]
        Gold -. Stage 7 .-> Snowflake["Snowflake Serving Mart (RBAC, Time Travel)"]
    end
```

---

## 2. Medallion Layer Specifications

### Bronze Layer
* **Technology**: Databricks Auto Loader (`cloudFiles`), Delta Lake.
* **Characteristics**: Append-only, zero business transformation, automatic schema inference & tracking (`cloudFiles.schemaLocation`).
* **Metadata Enriched**: `_ingest_timestamp` (`TIMESTAMP`), `_source_file` (`STRING`).

### Silver Layer
* **Technology**: PySpark DataFrames, Delta Lake `MERGE INTO`.
* **Transforms**:
  * Window deduplication: `row_number() OVER (PARTITION BY claim_id ORDER BY reported_date DESC, _ingest_timestamp DESC) = 1`.
  * Type casting: Currency to `DECIMAL(12,2)`, dates to `DATE`.
  * Status normalization: String trim, casing standardization (`APPROVED`, `IN_REVIEW`, `SUBMITTED`, etc.).
  * Referential integrity: Left join to `silver_policies` to isolate orphan policy claims.
* **Quarantine**: Bad rows routed to `quarantine_claims` with error codes (`ERR_DUP_CLAIM`, `ERR_NULL_INCIDENT_DATE`, `ERR_INVALID_AMOUNT`, `ERR_ORPHAN_POLICY`, `ERR_FUTURE_INCIDENT_DATE`).
* **CDC Upsert**: Delta `MERGE` ensures incremental status updates from `claims_updates.csv` modify existing records without row duplication.

### Gold Layer
* **Technology**: Kimball Star Schema, Spark SQL Views.
* **Dimensions**: `dim_customer`, `dim_policy`, `dim_claim_type`, `dim_date` (surrogate keys via SHA-256).
* **Fact Table**: `fact_claims` (Grain: 1 row per valid claim, metrics: `claimed_amount`, `reporting_delay_days`, `documents_count`, `flag_high_risk_customer`).
* **KPI Views**: `kpi_claims_by_type_month`, `kpi_top_risk_customers`.

### Reconciliation Audit
* **Mathematical Invariant**:
  $$\text{Bronze Count} = \text{Duplicates Quarantined} + \text{Defects Quarantined} + \text{Silver Count}$$
  $$\text{Silver Count} = \text{Gold Fact Count}$$
* Recorded per run in `pipeline_audit`.

---

## 3. LangGraph AI Triage Agent Architecture

```mermaid
sequenceDiagram
    participant UI as Streamlit / FastAPI
    participant G as LangGraph StateGraph
    participant T as Parameterised Tools
    participant R as Clause Retriever
    participant LLM as Groq LLM
    participant V as Citation Verifier
    participant H as Human Adjuster

    UI->>G: POST /triage/{claim_id}
    G->>T: intake & fetch_data(claim_id)
    T-->>G: claim_record, policy, customer facts
    G->>T: validate_rules(claim_id)
    T-->>G: 5 deterministic rule check outcomes
    G->>R: retrieve_clauses(claim_type, description)
    R-->>G: top-4 relevant policy clauses
    G->>LLM: Delimited prompt with facts, rules, and clauses
    LLM-->>G: JSON recommendation + cited clause IDs
    G->>V: verify(assessment, record, retrieved_clauses)
    alt Unverifiable citation or factual hallucination detected
        V-->>G: Flagged! Repair retry / Force NEEDS_REVIEW
    else Citations verified
        V-->>G: Grounded validation passed
    end
    alt Requires human review (NEEDS_REVIEW / ESCALATE_SIU)
        G->>H: Pause graph at checkpoint
        H->>G: resume_review(approve / override / reject)
    end
    G-->>UI: Finalized triage report with complete trace
```

---

## 4. Multi-Layer Resilience & Fallback

1. **Live Mode (`LIVE`)**: The application queries Databricks SQL Warehouse and Groq LLMs directly over HTTPS.
2. **Cold-Sleep / Quota Degradation (`OFFLINE_SNAPSHOT`)**:
   * If Databricks SQL Warehouse is sleeping, rate-limited, or token credentials are not supplied, `ResilientDBClient` automatically routes to local Parquet/SQLite snapshots in `snapshots/`.
   * If Groq API quota is reached or offline, `GroqClientWrapper` executes deterministic offline reasoning based on verified rule facts.
   * **Result**: Zero crashes, zero blank screens, and 100% full application functionality at zero cost.
