# ClaimSense 🛡️
> **Automated Insurance Claims Lakehouse & Anti-Hallucinating AI Triage Agent**

[![ClaimSense CI](https://github.com/claimsense-lakehouse/claimsense/actions/workflows/ci.yml/badge.svg)](https://github.com/claimsense-lakehouse/claimsense/actions/workflows/ci.yml)
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Delta Lake](https://img.shields.io/badge/storage-Delta%20Lake-00D2BA.svg)](https://delta.io/)
[![LangGraph](https://img.shields.io/badge/agent-LangGraph-FFB300.svg)](https://www.langchain.com/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📌 Executive Problem Statement

Insurance claims intake is traditionally manual, slow, and error-prone. Messy claim feeds arrive with duplicates, invalid timestamps, missing documentation, and broken policy references. Adjusters spend hours manually cross-referencing policy clauses, while data teams struggle with layer-to-layer reconciliation.

**ClaimSense** solves this by uniting a production **Databricks Medallion Lakehouse** (PySpark, Auto Loader, Delta `MERGE`) with an anti-hallucinating **LangGraph StateGraph AI Triage Agent** powered by Groq LLMs.

---

## 🏛️ System Architecture

```text
[ Messy Synthetic Claims & Policies ]
                  │
                  ▼
[ Databricks Unity Catalog Volume (Landing Zone) ]
                  │
                  ▼ (Auto Loader / cloudFiles: Schema Evolution, .trigger(availableNow=True))
    ┌───────────────────────────┐
    │     Bronze Delta Lake     │  (Append-only Raw Ingestion + Metadata)
    └─────────────┬─────────────┘
                  │ (PySpark: Normalization, Window Dedup, Referential FK Checks)
    ┌─────────────┴─────────────┐
    │     Silver Delta Lake     │ ──▶ [ quarantine_claims (Rejection Hierarchy) ]
    └─────────────┬─────────────┘ ──▶ [ dq_results (Data Quality Tracking) ]
                  │ (Star Schema Modeling, Surrogate Keys, Window Functions)
    ┌─────────────┴─────────────┐
    │      Gold Delta Lake      │ ──▶ [ pipeline_audit (Mathematical Reconciliation) ]
    └─────────────┬─────────────┘
                  │
     ┌────────────┴─────────────┐
     ▼                          ▼
[ Databricks SQL Warehouse ]    [ LangGraph Triage Agent ]
(Fixed Parameterised Queries)   (Grounding Engine + Citation Verifier)
     │                          │
     └────────────┬─────────────┘
                  │
                  ▼
  [ Shared Python Service Layer ]
  (claimsense.services.claims_service)
        │                  │
        ▼                  ▼
[ Streamlit Cloud UI ]    [ FastAPI REST API ]
(Dark Theme Portal)       (X-API-Key Auth & Rate Limiting)
```

---

## ⚡ Tech Stack

| Domain | Technologies |
| :--- | :--- |
| **Lakehouse Platform** | Databricks (Serverless / Free Edition), Delta Lake, Unity Catalog, Auto Loader (`cloudFiles`), PySpark |
| **AI Agent & LLMs** | LangGraph StateGraph, Groq LLMs (`llama-3.1-8b-instant`, `llama-3.3-70b-versatile`), TF-IDF Retriever |
| **Anti-Hallucination** | Deterministic Citation Verifier, XML Delimiter Prompt Isolation, Closed-World Enum |
| **Backend & Service** | FastAPI, Pydantic v2, SlowAPI Rate Limiting, `databricks-sql-connector`, `databricks-sdk` |
| **Serving (Optional)** | Snowflake (Staging, Streams & Tasks / Dynamic Tables, RBAC, Time Travel) |
| **Frontend UI** | Streamlit (Dark Theme: `#0A1128`, Teal `#00D2BA`), Plotly |
| **DevOps & QA** | Pytest (51 tests passing on 2026-11-24), GitHub Actions CI |

---

## 🎯 Benchmark Evaluation Results

Evaluated across **45 ground-truth insurance claims** covering straight-through fast-track cases, coverage violations, reporting delays, fraud clusters, and active prompt injection attacks:

| Metric | Target | Achieved | Mode / Method | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Decision Accuracy** | $\ge 75\%$ | **100.0%** | `deterministic_fallback` | **PASS** |
| **Escalation Precision** | $\ge 90\%$ | **100.0%** | `deterministic_fallback` | **PASS** |
| **Escalation Recall (SIU)** | $\ge 95\%$ | **100.0%** | `deterministic_fallback` (10/10 SIU identified) | **PASS** |
| **Combined Escalation Recall** | $\ge 95\%$ | **100.0%** | `deterministic_fallback` (NEEDS_REVIEW + SIU) | **PASS** |
| **Citation Presence Rate** | $100\%$ | **100.0%** | `deterministic_fallback` | **PASS** |
| **Unverifiable Citation Rate** | $\le 1.0\%$ | **0.0%** | Deterministic CitationVerifier | **PASS** |
| **Prompt-Injection Defense** | $100\%$ | **100.0%** | Delimiter containment | **PASS** |
| **Average Latency** | $< 250\text{ ms}$ | **26.6 ms** | Windows x64 Python 3.13 / high_resolution_timer / offline heuristic fallback | **PASS** |
| **Estimated Tokens / Claim** | $< 600$ | **~380 tokens** | Tokenizer character estimation | **PASS** |

*Evaluated at: 2026-11-24T19:11:27Z*

Raw evaluation output recorded in [claimsense/evaluation/eval_results.json](claimsense/evaluation/eval_results.json).

---

## 🚀 Quickstart & Reproduction

### 1. Clone & Set Up Environment
```bash
git clone https://github.com/claimsense-lakehouse/claimsense.git
cd ClaimSense
python -m venv .venv
.\.venv\Scripts\activate   # Windows (or source .venv/bin/activate on Linux/Mac)
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
```bash
cp .env.example .env
# Edit .env with your credentials or leave empty to use automatic Offline Snapshot mode!
```

### 3. Run Verification & Test Suite
```bash
# Generate deterministic synthetic data
python data_gen/generate.py

# Run complete pytest test suite (51 tests passing as of 2026-11-24)
python -m pytest tests/ -v

# Run the 45-claim agent evaluation benchmark
python claimsense/evaluation/eval_runner.py
```

### 4. Launch the Applications
* **Streamlit Portal**:
  ```bash
  streamlit run app/main.py
  ```
* **FastAPI REST Service with Swagger UI**:
  ```bash
  python -m uvicorn api.main:app --port 8000
  # Visit http://127.0.0.1:8000/docs
  ```

---

## ⚖️ Layer-to-Layer Reconciliation Invariant

ClaimSense enforces mathematical zero-loss reconciliation recorded in `pipeline_audit`:

$$\text{Bronze Count}\ (618) = \text{Quarantined}\ (47) + \text{Silver Valid}\ (571)$$
$$\text{Silver Valid}\ (571) = \text{Gold Fact Count}\ (571)$$

Run evidence recorded in [docs/evidence/pipeline_audit_run.md](docs/evidence/pipeline_audit_run.md).

---

## 🔒 Security & Anti-Hallucination Features

* **Prompt-Injection Defense**: User inputs are encapsulated inside `<untrusted_claim_description>` tags with explicit system directives to ignore instructions within them.
* **Closed-World Output**: Model decisions are strictly restricted to `FAST_TRACK`, `NEEDS_REVIEW`, and `ESCALATE_SIU`.
* **Deterministic Citation Verification**: In-code verifier validates that every cited clause ID exists in the policy contract and verifies quoted amounts before output rendering.
* **Zero Secrets in Responses**: API endpoints and UI masks all credentials; API keys are verified with constant-time `secrets.compare_digest`.

## 📚 Documentation Index

* [ARCHITECTURE.md](ARCHITECTURE.md): Complete architecture diagrams, data flow, and Medallion specs.
