# ClaimSense Interview Defense & Evaluator Walkthrough Guide

This guide is specifically tailored for senior engineering evaluators (e.g. ValueMomentum, healthcare/insurance platform evaluators) who evaluate both **production data engineering competence** and **agentic AI architectural rigor**.

---

## ⏱️ Walkthrough Scripts

### 🎤 The 2-Minute Elevator Pitch
> *"ClaimSense is an enterprise insurance claims intelligence platform that solves the costly problem of ingesting messy claims and validating policy coverage without manual adjuster bottleneck.*
>
> *On the data engineering side, I built a serverless Medallion Lakehouse on Databricks using Auto Loader and Delta Lake. Messy claims flow into Bronze; PySpark cleans, deduplicates via window functions, and isolates defective records into a quarantine table with strict error codes. Incremental status updates are handled via Delta MERGE upserts, feeding a Kimball Star Schema with dimension and fact tables. Crucially, I enforce an automated mathematical reconciliation check where Bronze count equals Quarantined plus Silver valid rows, ensuring zero data leakage.*
>
> *On the AI side, I built an anti-hallucinating LangGraph triage agent. The agent executes deterministic policy checks, retrieves numbered policy clauses via TF-IDF, and produces grounded triage recommendations—Fast Track, Needs Review, or Escalate to SIU. To guarantee safety, I implemented a code-level citation verifier that caught 100% of injected prompt overrides and achieved a 0.0% hallucination rate across our 45-claim benchmark, while keeping human adjusters in the loop for final approval.*
>
> *The entire system is exposed via an authenticated FastAPI REST service and a dark-themed Streamlit portal that degrades gracefully to local snapshots if cloud compute sleeps."*

---

### 🎙️ The 5-Minute Technical Deep Dive
1. **The Business Problem & Ingestion (Minute 1)**: Explain why insurance claims arrive messy (broken FKs, null dates, duplicate transmissions, prompt injections) and how Databricks Auto Loader (`cloudFiles`) with schema evolution and `.trigger(availableNow=True)` ingests them into Bronze.
2. **Medallion Cleaning, Quarantine & Delta MERGE (Minute 2)**: Detail how PySpark deduplicates using `row_number() OVER (PARTITION BY claim_id ORDER BY reported_date DESC)`, checks policy FKs, isolates bad rows into `quarantine_claims`, and applies `claims_updates.csv` via Delta `MERGE INTO` so statuses change without inflating row counts.
3. **Reconciliation Audit & Performance (Minute 3)**: Walk through the equation $\text{Bronze} = \text{Quarantined} + \text{Silver}$, Catalyst BroadcastHashJoins on small dimensions (`dim_claim_type`, `dim_date`), and Space-Filling Z-ORDER clustering on `fact_claims`.
4. **LangGraph Agent & Anti-Hallucination Guardrails (Minute 4)**: Detail why StateGraph was chosen over ReAct, the XML delimiter prompt isolation (`<untrusted_claim_description>`), and the deterministic `CitationVerifier` enforcing closed-world decisions and grounded clause IDs.
5. **Serving Layer & Resilience (Minute 5)**: Explain dual `BACKEND_MODE` (`inprocess` for Streamlit Cloud, `http` for FastAPI), the constant-time `X-API-Key` check, and the Snowflake serving mart with RBAC and Time Travel.

---

## 🎯 Top 10 Technical Interview Questions & Grounded Answers

### 1. "Why choose Delta Lake over standard Parquet files in Amazon S3 or ADLS?"
* **Answer**: *"Raw Parquet is immutable and lacks ACID transaction support. In an insurance claims platform, claims constantly transition statuses (e.g. from SUBMITTED to IN_REVIEW to APPROVED). In raw Parquet, updating a single claim requires rewriting the entire partition. Delta Lake provides native `MERGE INTO` (upsert) support using transaction logs (`_delta_log`), schema enforcement to prevent corrupted feeds from poisoning downstream tables, and Time Travel auditing for regulatory compliance."*

### 2. "How does your pipeline handle dirty data without dropping rows or crashing batches?"
* **Answer**: *"We never call `dropna()` or silently discard records. In our Silver notebook (`02_silver_transformation.py`), incoming rows are evaluated against a documented rule hierarchy (`ERR_DUP_CLAIM`, `ERR_NULL_INCIDENT_DATE`, `ERR_INVALID_AMOUNT`, `ERR_ORPHAN_POLICY`, `ERR_FUTURE_INCIDENT_DATE`). Valid rows merge into `silver_claims`, while defective rows are routed to `quarantine_claims` with an explicit `reject_reason` and ingestion metadata. This keeps Gold clean while preserving 100% auditability for upstream data providers to correct and retransmit."*

### 3. "Explain your reconciliation audit formula. What happens if a discrepancy occurs?"
* **Answer**: *"In `04_reconciliation_audit.py`, we assert that:
$$\text{Bronze Count} = \text{Duplicates Quarantined} + \text{Defects Quarantined} + \text{Silver Count}$$
and $\text{Silver Count} = \text{Gold Fact Count}$. Every run records counts and status in `pipeline_audit`. If a discrepancy occurs, status is marked `FAIL` and alerts are triggered. Because each layer logs `_source_file` and run IDs, we can pinpoint whether the leak was caused by an unhandled join filter, an erroneous window function, or duplicate ingestion."*

### 4. "How does Delta MERGE implement CDC-style incremental updates for `claims_updates.csv`?"
* **Answer**: *"We execute:
```sql
MERGE INTO silver_claims target
USING updates source
ON target.claim_id = source.claim_id
WHEN MATCHED AND source.reported_date >= target.reported_date THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;
```
This guarantees that existing claims have their statuses updated (e.g. to SETTLED) in-place without creating duplicate rows, proven by our invariant test in `tests/test_pipeline.py`."*

### 5. "Why use LangGraph StateGraph instead of a standard LangChain agent with tools?"
* **Answer**: *"Standard ReAct or tool-calling loops in LLMs are non-deterministic: the LLM decides dynamically which tool to call next and can get trapped in loops or hallucinate function calls. For insurance compliance, we require an immutable, auditable state machine. LangGraph `StateGraph` enforces typed state (`TriageAgentState`) and strict directed edges (`intake` $\rightarrow$ `fetch_data` $\rightarrow$ `validate_rules` $\rightarrow$ `retrieve_clauses` $\rightarrow$ `assess` $\rightarrow$ `human_review` $\rightarrow$ `finalize`). Furthermore, it provides native checkpointer persistence so the graph pauses for human adjuster approval before writing the final decision to `triage_audit`."*

### 6. "How did you achieve a 0.0% hallucination rate on your evaluation benchmark?"
* **Answer**: *"Anti-hallucination is enforced in code, not just in prompt instructions. First, the prompt receives only verified facts from deterministic tool calls and numbered retrieved clauses. Second, `CitationVerifier` programmatically validates that every cited `clause_id` exists in the retrieved set and matches numbers against the claim record. If an LLM cites a non-existent clause or hallucinates an amount, the verifier automatically catches it, forces a conservative repair (`NEEDS_REVIEW`), and records the attempt. Across all 45 ground-truth claims, zero unverifiable citations reached the final output."*

### 7. "How do you defend against prompt injection attacks inside customer claim descriptions?"
* **Answer**: *"All claimant text is enclosed inside `<untrusted_claim_description>` XML delimiters. The system prompt directs the LLM that content inside delimiters is untrusted claimant text, NOT system directives. More importantly, we have a hard programmatic rule in Python: **no claim can be fast-tracked if any high-severity deterministic rule has failed**. Even if an LLM is tricked by an injection into recommending `FAST_TRACK`, the Python layer overrides the decision to `NEEDS_REVIEW`."*

### 8. "Why did you use Space-Filling Z-ORDER clustering instead of traditional partitioning?"
* **Answer**: *"Traditional Hive-style partitioning (e.g. `PARTITIONED BY (year, month)`) causes the small file problem when claims volume fluctuates, generating thousands of tiny 5KB files. We use Delta Lake **Z-ORDER clustering** on `(incident_date, claim_type_sk)`. Z-ORDER maps multidimensional data onto a Hilbert curve inside Parquet files, allowing Catalyst readers to skip row groups using column statistics without creating physical subdirectory fragmentation."*

### 9. "Why is BroadcastHashJoin used for dimension tables in Spark?"
* **Answer**: *"Dimension tables like `dim_claim_type` (3 rows) and `dim_date` (1,461 rows) are under the default 10 MB broadcast threshold. Spark Catalyst automatically serializes and broadcasts them to all executor worker nodes. This converts a distributed shuffle join into a local memory lookup, completely eliminating expensive network shuffle I/O."*

### 10. "How does your architecture handle Databricks Free Edition cold starts, suspension, or quota limits?"
* **Answer**: *"We designed a `ResilientDBClient` with transparent circuit breaking. When Databricks SQL Warehouse is suspended and spinning up from cold sleep (~60-90s latency) or daily free quotas are reached, our database wrapper catches `DatabricksWarehouseStartingError` or `DatabricksQuotaExceededError` and instantly degrades to local Parquet/SQLite snapshots in `snapshots/`. The UI displays a clear offline banner and continues operating with zero downtime."*
