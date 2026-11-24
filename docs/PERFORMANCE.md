# ClaimSense: PySpark & Delta Lake Performance Engineering

This document analyzes query execution plans, partitioning strategies, Liquid Clustering / Z-ORDER, and caching within the ClaimSense Lakehouse.

> [!NOTE]
> **Scale Disclaimer**: At our demonstration dataset size (~600 to 10,000 records), PySpark operations complete in sub-second timeframes regardless of optimization. The techniques documented below illustrate **production data engineering best practices** essential when scaling to millions of insurance claims.

---

## 1. Spark Execution Plan Analysis (`EXPLAIN EXTENDED`)

When computing the `fact_claims` join against dimensions, PySpark generates physical execution plans using the Catalyst Optimizer:

```sql
EXPLAIN EXTENDED
SELECT
    t.claim_type,
    d.year,
    COUNT(f.claim_sk) AS total_claims,
    ROUND(SUM(f.claimed_amount), 2) AS total_claimed
FROM claimsense.fact_claims f
JOIN claimsense.dim_claim_type t ON f.claim_type_sk = t.claim_type_sk
JOIN claimsense.dim_date d ON f.incident_date_key = d.date_key
GROUP BY t.claim_type, d.year;
```

### Physical Plan Walkthrough
1. **FileScan delta**: Reads Parquet files under Delta log protocol, applying **partition pruning** and **data skipping** using min/max stats stored in the `_delta_log`.
2. **BroadcastExchange (BroadcastHashJoin)**:
   * `dim_claim_type` (3 rows) and `dim_date` (1,460 rows) fall well below the `spark.sql.autoBroadcastJoinThreshold` (default 10 MB).
   * Catalyst broadcasts these dimension tables to all executor worker nodes, completely avoiding costly shuffle exchanges across the network.
3. **HashAggregate**: Aggregates `claimed_amount` and counts in two phases (partial aggregation in mapper, final aggregation in reducer) using Spark's tungsten binary memory layout.

---

## 2. Partitioning vs. Liquid Clustering in Delta Lake

### Traditional Hive-Style Partitioning
In legacy Delta Lake architectures, partitioning was applied on high-cardinality date columns:
```sql
-- Legacy partition strategy:
CREATE TABLE claimsense.fact_claims (...)
USING DELTA
PARTITIONED BY (year, month);
```
* **Limitation**: Creates small file problems if partitions contain too few rows (e.g. daily partitions with only 20 claims).

### Databricks Liquid Clustering / Z-ORDER (Recommended)
ClaimSense recommends **Liquid Clustering** or **Z-ORDER clustering** on `(incident_date, policy_type)`:
```sql
-- Modern Delta optimization:
OPTIMIZE claimsense.fact_claims
ZORDER BY (incident_date, claim_type_sk);
```
* **Advantage**: Dynamically clusters multidimensional data along a Space-Filling Curve (Peano / Hilbert curve). Queries filtering by date range or claim type skip non-relevant Parquet row groups automatically using column statistics without creating physical folder fragmentation.

---

## 3. Caching & Persistence Strategies

```python
# Caching frequent lookup tables in PySpark:
silver_policies = spark.table("claimsense.silver_policies").filter("status = 'ACTIVE'").cache()
silver_policies.count() # Materialize in executor memory (StorageLevel.MEMORY_AND_DISK_DESER)
```
* **Use Case**: Used during the Silver transformation where all 3 incoming claim batches must repeatedly validate against the policy dimension.
* **Cleanup**: Always call `silver_policies.unpersist()` at the end of the pipeline run to release Spark executor memory.
