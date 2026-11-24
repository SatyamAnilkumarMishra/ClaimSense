# ClaimSense Data Schemas & Medallion Mapping

This document details the data contract, schema definitions, and evolution path across the ClaimSense Lakehouse platform from raw files to Gold analytics tables.

---

## 1. Landing Source Schemas

### `customers.csv` (~100 records)
| Column Name | Data Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `customer_id` | `VARCHAR(32)` | No | Unique customer identifier (`CUST-xxxxx`) |
| `first_name` | `VARCHAR(64)` | No | Customer given name |
| `last_name` | `VARCHAR(64)` | No | Customer family name |
| `email` | `VARCHAR(128)` | No | Contact email address |
| `phone` | `VARCHAR(32)` | Yes | Contact phone number |
| `city` | `VARCHAR(64)` | No | Residential city |
| `state` | `VARCHAR(32)` | No | State or province |
| `risk_score` | `DECIMAL(3,2)` | No | Baseline fraud risk score (0.00 to 1.00) |
| `created_at` | `TIMESTAMP` | No | Account registration timestamp |

---

### `policies.csv` (~150 records)
| Column Name | Data Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `policy_id` | `VARCHAR(32)` | No | Unique policy identifier (`POL-xxxxx`) |
| `customer_id` | `VARCHAR(32)` | No | Foreign key referencing `customers.customer_id` |
| `policy_type` | `VARCHAR(16)` | No | `AUTO`, `HEALTH`, or `HOME` |
| `start_date` | `DATE` | No | Policy inception date |
| `end_date` | `DATE` | No | Policy expiration date |
| `sum_insured` | `DECIMAL(12,2)` | No | Maximum policy indemnity limit |
| `deductible` | `DECIMAL(10,2)` | No | Out-of-pocket customer liability |
| `status` | `VARCHAR(16)` | No | `ACTIVE`, `LAPSED`, or `CANCELLED` |

---

### `claims_batch_{1,2,3}.csv` (~600 records total)
Raw claims arrive with messy values, inconsistent whitespace, casing issues, and intentional edge cases.

| Column Name | Data Type (Raw) | Description & Dirty Rules |
| :--- | :--- | :--- |
| `claim_id` | `VARCHAR(32)` | Primary key (`CLM-xxxxx`). ~3% duplicate rows. |
| `policy_id` | `VARCHAR(32)` | Foreign key. ~2% orphan IDs not in `policies.csv`. |
| `claim_type` | `VARCHAR(32)` | E.g. Collision, Theft, Hospitalization, Storm Damage. |
| `incident_date` | `VARCHAR(32)` | Date string. ~2% null; ~1% future dates. |
| `reported_date` | `VARCHAR(32)` | Date string when claim was submitted. |
| `claimed_amount` | `VARCHAR(32)` | Monetary amount. ~1% negative or zero; some exceeding `sum_insured`. |
| `status` | `VARCHAR(32)` | Inconsistent casing (`" submitted "`, `"IN_REVIEW"`, `"approved"`). |
| `description` | `TEXT` | Incident details written by customer or agent. |
| `documents_count`| `INTEGER` | Number of supporting documents uploaded. |
| `city` | `VARCHAR(64)` | Incident location city. |

---

### `claims_updates.csv` (Incremental Updates)
Used in Stage 2 to verify incremental CDC processing and Delta Lake `MERGE` (upsert) without creating duplicate records.
* Contains updated statuses (`APPROVED`, `SETTLED`, `REJECTED`) for existing claims.

---

### `adjuster_notes.json` (Semi-Structured Data)
Demonstrates handling nested JSON with PySpark in the Medallion lakehouse.
```json
[
  {
    "claim_id": "CLM-10023",
    "notes": [
      {
        "note_id": 1,
        "author": "Adjuster Jane Doe",
        "timestamp": "2026-03-12T10:15:00Z",
        "severity_tag": "LOW",
        "text": "Initial damage assessment matches standard collision photos."
      }
    ]
  }
]
```

---

## 2. Medallion Layer Architecture

```text
[Landing Zone Volume]
        │
        ▼ (Auto Loader / cloudFiles)
┌────────────────────────────────────────────────────────┐
│ Bronze Layer (Append-only Delta)                       │
│ - bronze_customers, bronze_policies, bronze_claims     │
│ - Extra columns: _ingest_timestamp, _source_file      │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼ (PySpark Cleaning, Dedup, FK Checks)
┌────────────────────────────────────────────────────────┐
│ Silver Layer (Cleaned & Quarantined Delta)             │
│ - silver_customers, silver_policies, silver_claims     │
│ - Delta MERGE (Upsert by claim_id)                     │
│ - quarantine_claims (Invalid rows + reject_reason)     │
│ - dq_results (Per-rule check counts)                   │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼ (Star Schema Modeling, Window Functions)
┌────────────────────────────────────────────────────────┐
│ Gold Layer (Analytics & Serving)                       │
│ - dim_customer, dim_policy, dim_claim_type, dim_date   │
│ - fact_claims                                          │
│ - Views: kpi_claims_by_type_month, top_risk_customers  │
│ - pipeline_audit (Reconciliation: Bronze = Silver + Q) │
└────────────────────────────────────────────────────────┘
```

---

## 3. Data Quality Rejection Reason Codes

| Code | Condition | Severity | Action |
| :--- | :--- | :--- | :--- |
| `ERR_DUP_CLAIM` | Duplicate `claim_id` within batch | HIGH | Quarantine later occurrences |
| `ERR_NULL_INCIDENT_DATE` | `incident_date IS NULL` or empty string | HIGH | Quarantine to `quarantine_claims` |
| `ERR_INVALID_AMOUNT` | `claimed_amount <= 0` or NaN | HIGH | Quarantine to `quarantine_claims` |
| `ERR_ORPHAN_POLICY` | `policy_id` does not exist in `silver_policies` | CRITICAL | Quarantine to `quarantine_claims` |
| `ERR_FUTURE_INCIDENT_DATE`| `incident_date > CURRENT_DATE()` | HIGH | Quarantine to `quarantine_claims` |
| `WARN_EXCEEDS_SUM_INSURED`| `claimed_amount > sum_insured` | MEDIUM | Kept in Silver with `flag_exceeds_sum=1` |
| `WARN_INACTIVE_POLICY` | `incident_date` outside `[start_date, end_date]` | MEDIUM | Kept in Silver with `flag_inactive_period=1` |
