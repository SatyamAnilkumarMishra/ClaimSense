# Pipeline Reconciliation Audit Evidence (ISS-07)

Captured from deterministic Lakehouse pipeline run executing `databricks/local_pipeline.py`.

## Execution Log

```text
Executing Full Pipeline for Run ID: RUN-688A9534...
 [1/4] Bronze Ingestion completed: {'claims_ingested': 618}
 [2/4] Silver Transformations & Quarantine completed: {'run_id': 'RUN-688A9534', 'duplicates_quarantined': 18, 'defects_quarantined': 29, 'silver_valid': 571}
 [3/4] Gold Star Schema completed: {'fact_claims_count': 571}
 [4/4] Reconciliation Audit: PASS | Full mathematical reconciliation achieved. Zero data leakage across Bronze, Silver, and Gold.

Reconciliation Summary:
  run_id                : RUN-688A9534
  bronze_count          : 618
  duplicates_count      : 18
  defects_count         : 29
  quarantined_total     : 47
  silver_count          : 571
  gold_fact_count       : 571
  discrepancy           : 0
  status                : PASS
  notes                 : Full mathematical reconciliation achieved. Zero data leakage across Bronze, Silver, and Gold.
```

## Reconciliation Invariant Audit Record

| Metric Name | Value | Invariant Formula Verified |
| :--- | :---: | :--- |
| **Bronze Raw Ingestion** | **618** | $\text{Bronze} = \text{Silver} + \text{Quarantine} = 571 + 47 = 618$ |
| **Duplicates Quarantined** | **18** | Window dedup on `claim_id` ordering by `reported_date DESC` |
| **Defects Quarantined** | **29** | Invalidation hierarchy (null dates, negative amount, orphan policy) |
| **Total Quarantined** | **47** | $18 + 29 = 47$ |
| **Silver Valid Claims** | **571** | Passed all data quality expectations |
| **Gold Fact Records** | **571** | $\text{Silver Valid} = \text{Gold Fact} = 571$ |
| **Discrepancy** | **0** | **Zero Data Leakage** |
