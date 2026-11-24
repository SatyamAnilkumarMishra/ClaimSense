# ClaimSense 🛡️
> **Enterprise Insurance Claims Lakehouse & Anti-Hallucinating AI Triage Agent**

ClaimSense is a production-grade, zero-cost reference platform addressing one of the most critical challenges in the insurance industry: **processing unstructured, messy claims rapidly and reliably without sacrificing data integrity or compliance.**

---

## 🏛️ Architecture Overview

```text
[ Messy Synthetic Claims & Policies ]
                  │
                  ▼
[ Databricks Unity Catalog Volume (Landing Zone) ]
                  │
                  ▼ (Auto Loader / cloudFiles)
    ┌───────────────────────────┐
    │     Bronze Delta Lake     │  (Append-only, Schema Evolution, Ingestion Metadata)
    └─────────────┬─────────────┘
                  │ (PySpark: Normalization, Deduplication, FK Checks)
    ┌─────────────┴─────────────┐
    │     Silver Delta Lake     │ ──▶ [ Quarantine Table (Rejection Reason) ]
    └─────────────┬─────────────┘
                  │ (Star Schema Modeling, CTE / Window Function Aggregations)
    ┌─────────────┴─────────────┐
    │      Gold Delta Lake      │ ──▶ [ pipeline_audit (Reconciliation) ]
    └─────────────┬─────────────┘
                  │
     ┌────────────┴─────────────┐
     ▼                          ▼
[ Databricks SQL ]     [ LangGraph Agent + Groq ] ──▶ [ Human Review UI ]
     │                          │
     └────────────┬─────────────┘
                  │
                  ▼
  [ Shared Python Service Layer ]
        │                  │
        ▼                  ▼
[ Streamlit UI ]    [ FastAPI REST ]
(Community Cloud)   (X-API-Key Auth)
```

---

## ⚡ Tech Stack

* **Lakehouse Engine**: Databricks (Serverless / Free Edition), Delta Lake, PySpark, Auto Loader, Unity Catalog
* **AI Agent & LLMs**: LangGraph StateGraph, Groq (`llama-3.1-8b-instant`, `llama-3.3-70b-versatile`), Anti-hallucination Grounding Engine
* **Service & REST**: FastAPI, Pydantic v2, SlowAPI rate-limiting, `databricks-sql-connector`, `databricks-sdk`
* **Data Visualization**: Streamlit (Dark Theme), Plotly
* **Serving (Optional)**: Snowflake (Stages, Streams, Tasks / Dynamic Tables, RBAC)
* **DevOps & QA**: Pytest, Ruff, GitHub Actions CI

---

## 🚀 Quickstart

1. **Clone and activate environment**:
   ```bash
   git clone <repo-url>
   cd ClaimSense
   python -m venv .venv
   .\.venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials (or leave blank to use automatic Offline Snapshot mode)
   ```

3. **Run local verification**:
   ```bash
   python databricks/test_connection.py
   python claimsense/agent/test_groq.py
   pytest tests/
   ```

---

## 📋 Project Stages

* **Stage 0: Connectivity & Environment Gate** *(Current)*
* **Stage 1: Synthetic Data & Schemas**
* **Stage 2: Databricks Pipeline (Medallion: Bronze $\rightarrow$ Silver $\rightarrow$ Gold)**
* **Stage 3: Service Layer, Offline Snapshot & FastAPI**
* **Stage 4: LangGraph Triage Agent & Hallucination Guardrails**
* **Stage 5: Streamlit Multi-Page Frontend**
* **Stage 6: Deployment, CI & Documentation**
* **Stage 7: Snowflake Serving Layer**
* **Stage 8: Interview Readiness & Walkthrough Defense**
