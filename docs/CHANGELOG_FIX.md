# ClaimSense Fix-Up Changelog & Issue Resolution Audit (v1.0)

This changelog records the complete resolution of all audited issues (ISS-01 through ISS-08) and LangGraph strictness requirements (LG-01 through LG-11).

---

## Issue Resolution Matrix

| Issue ID | Severity | Description | Resolution Implemented | Supporting Evidence File |
| :--- | :---: | :--- | :--- | :--- |
| **ISS-01** | **Critical** | Escalation recall claim was false (all 10 SIU cases routed to `NEEDS_REVIEW`). | Implemented explicit 4-tier escalation precedence in `claimsense/agent/graph.py` (LG-04) and fixed regex check in `claimsense/agent/groq_client.py`. All 10 SIU claims now correctly route to `ESCALATE_SIU`. | [docs/evidence/escalation_trace.md](evidence/escalation_trace.md)<br>[claimsense/evaluation/eval_results.json](../claimsense/evaluation/eval_results.json) |
| **ISS-02** | **Critical** | Evaluation reports disagreed between README, EVALUATION.md, and code output. | Created `claimsense/evaluation/render_report.py` to establish `eval_results.json` as the single source of truth. Automated unit test prevents regressions. | [tests/test_evaluation_consistency.py](../tests/test_evaluation_consistency.py)<br>[claimsense/evaluation/render_report.py](../claimsense/evaluation/render_report.py) |
| **ISS-03** | **High** | Unclear whether evaluation exercised live Groq LLM or fallback. | Runner now tracks `llm_mode` per case and logs the dominant mode (`deterministic_fallback`) in documentation tables. | [claimsense/evaluation/eval_results.json](../claimsense/evaluation/eval_results.json) |
| **ISS-04** | **High** | Hallucination claims overstated ("Zero Hallucinations"). | Renamed metric to "Unverifiable Citation Rate" and documented exact structural checks and semantic limitations in `docs/EVALUATION.md`. Grep returns 0 matches for prohibited terms. | [docs/EVALUATION.md](EVALUATION.md) |
| **ISS-05** | **Medium** | Test count and CI status not verified. | Pytest suite expanded to 51 passing tests (covering all LG-01 to LG-11 criteria). README updated with verified test count and execution date (`2026-11-24`). | [docs/evidence/pytest_baseline.txt](evidence/pytest_baseline.txt) |
| **ISS-06** | **Medium** | Placeholder and machine-specific `file:///` links. | Replaced all `file:///d:/ClaimSense/` paths with clean repository-relative links and updated GitHub URLs from `placeholder` to `claimsense-lakehouse`. Verified zero broken links. | [README.md](../README.md)<br>[docs/ARCHITECTURE.md](ARCHITECTURE.md) |
| **ISS-07** | **Medium** | Databricks and Snowflake runs not evidenced. | Added `docs/evidence/pipeline_audit_run.md` with raw execution logs from `local_pipeline.py`. Staged Snowflake SQL and Parquet files documented with remote execution transparently labelled as "not yet executed". | [docs/evidence/pipeline_audit_run.md](evidence/pipeline_audit_run.md)<br>[docs/evidence/snowflake_queries.md](evidence/snowflake_queries.md) |
| **ISS-08** | **Low** | Latency and token claims lacked measurement method. | Annotated latency with measurement method: `Windows x64 Python 3.13 / high_resolution_timer / offline heuristic fallback`. | [README.md](../README.md)<br>[docs/EVALUATION.md](EVALUATION.md) |

---

## LangGraph Strictness Verification (LG-01 to LG-11)

All 11 strictness requirements are tested and enforced in `tests/test_langgraph_strictness.py`:
- **LG-01 (Typed State)**: `TriageStateModel` enforces Pydantic validation across all fields.
- **LG-02 (Explicit Topology)**: Compiled `StateGraph` builder registers explicit nodes, entry point, fixed edges, and conditional edge path maps.
- **LG-03 (Deterministic Routing)**: `route_after_precedence` is pure Python over state fields with a safe `human_review` fallback.
- **LG-04 (Escalation Precedence)**: 4-tier precedence explicitly tested (SIU fraud > citation failure > low confidence > LLM accepted).
- **LG-05 (Gated LLM Step)**: Output validated against `LLMOutputSchema` with bounded 1-attempt repair contract.
- **LG-06 (Tool Allow-List)**: Tools invoked only by named nodes; SQL parameterisation prevents injection.
- **LG-07 (Bounded Execution)**: Step count bounded at 15 steps; recursion limit set to 25.
- **LG-08 (HITL Checkpointer)**: Checkpointed with `MemorySaver` using `thread_id = {claim_id}_{run_id}`; resume requires action and notes; rejects duplicate resumes.
- **LG-09 (Full Structured Trace)**: Every node appends timestamped records with input IDs, summary, route, and `llm_mode`.
- **LG-10 (Exported Graph Matches Code)**: Programmatic `export_mermaid_diagram()` verified against `docs/ARCHITECTURE.md`.
- **LG-11 (Stateless Execution)**: Multi-claim execution order verified to produce identical results regardless of invocation sequence.
