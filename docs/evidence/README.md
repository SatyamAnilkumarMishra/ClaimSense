# ClaimSense Verification & Evidence Index (ISS-07)

This directory contains real run outputs, audit traces, and baseline snapshots demonstrating reproducible system behavior:

1. [pytest_baseline.txt](pytest_baseline.txt): Raw initial pytest execution output on branch checkout.
2. [eval_baseline.txt](eval_baseline.txt): Raw initial 45-claim evaluation runner output on branch checkout.
3. [escalation_trace.md](escalation_trace.md): Step-by-step trace of the 10 `ESCALATE_SIU` cases diagnosing the ISS-01 defect.
4. [langgraph_gap_table.md](langgraph_gap_table.md): Requirement gap analysis for LangGraph strictness items LG-01 through LG-11.
5. [pipeline_audit_run.md](pipeline_audit_run.md): Output from `local_pipeline.py` confirming the 618 = 47 + 571 reconciliation invariant.
6. [snowflake_queries.md](snowflake_queries.md): Summary of staged Parquet files and SQL DDL/DML scripts (noted as *Local Staging Prepared / Live Remote Execution Not Yet Executed*).
