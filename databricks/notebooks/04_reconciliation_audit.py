# Databricks notebook source
# COMMAND ----------
# DBTITLE 1,ClaimSense: 04 - Pipeline Reconciliation Audit
# MAGIC %md
# MAGIC ### Pipeline Stage: Automated Reconciliation Audit
# MAGIC Verifies zero data loss and data integrity across all Medallion Lakehouse layers.
# MAGIC 
# MAGIC Invariant Assertion:
# MAGIC $$\text{Bronze Count} = \text{Duplicates Quarantined} + \text{Defects Quarantined} + \text{Silver Count}$$
# MAGIC $$\text{Silver Count} = \text{Gold Fact Count}$$

# COMMAND ----------
import uuid
from pyspark.sql.functions import current_timestamp, lit

dbutils.widgets.text("catalog", "workspace", "Unity Catalog Name")
dbutils.widgets.text("schema", "claimsense", "Database / Schema Name")
dbutils.widgets.text("run_id", "", "Pipeline Run ID (optional)")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
run_id = dbutils.widgets.get("run_id") or f"RUN-{uuid.uuid4().hex[:8].upper()}"

print(f"Executing Reconciliation Audit for Run ID: {run_id}")

# COMMAND ----------
# DBTITLE 1,Query Layer Row Counts
bronze_claims = spark.table(f"{catalog}.{schema}.bronze_claims")
quarantine = spark.table(f"{catalog}.{schema}.quarantine_claims")
silver_claims = spark.table(f"{catalog}.{schema}.silver_claims")
fact_claims = spark.table(f"{catalog}.{schema}.fact_claims")

bronze_count = bronze_claims.count()
quarantine_total = quarantine.count()
duplicates_count = quarantine.filter("reject_reason = 'ERR_DUP_CLAIM'").count()
defects_count = quarantine.filter("reject_reason != 'ERR_DUP_CLAIM'").count()
silver_count = silver_claims.count()
gold_fact_count = fact_claims.count()

print("=" * 60)
print("PIPELINE AUDIT METRICS:")
print(f"  Bronze Raw Claims:       {bronze_count}")
print(f"  Quarantine Duplicates:   {duplicates_count}")
print(f"  Quarantine Defects:      {defects_count}")
print(f"  Total Quarantined:       {quarantine_total}")
print(f"  Silver Valid Claims:     {silver_count}")
print(f"  Gold Fact Claims:        {gold_fact_count}")
print("=" * 60)

# COMMAND ----------
# DBTITLE 1,Evaluate Mathematical Invariant
# In single batch or initial load: bronze == duplicates + defects + silver
expected_bronze = duplicates_count + defects_count + silver_count
discrepancy = abs(bronze_count - expected_bronze)

if discrepancy == 0 and silver_count == gold_fact_count:
    status = "PASS"
    notes = "Full mathematical reconciliation achieved. Zero data leakage across Bronze, Silver, and Gold."
    print(f"\n[RECONCILIATION PASS] {notes}")
else:
    status = "FAIL" if discrepancy > 0 else "PASS_WITH_WARNING"
    notes = f"Variance detected: Bronze ({bronze_count}) vs (Quarantine {quarantine_total} + Silver {silver_count} = {expected_bronze}). Discrepancy: {discrepancy}."
    print(f"\n[{status}] {notes}")

# COMMAND ----------
# DBTITLE 1,Persist Audit Record in pipeline_audit Delta Table
audit_df = spark.createDataFrame([
    (
        run_id,
        bronze_count,
        duplicates_count,
        defects_count,
        quarantine_total,
        silver_count,
        gold_fact_count,
        discrepancy,
        status,
        notes
    )
], [
    "run_id",
    "bronze_count",
    "duplicates_count",
    "defects_count",
    "quarantined_total",
    "silver_count",
    "gold_fact_count",
    "discrepancy_count",
    "reconciliation_status",
    "audit_notes"
]).withColumn("run_timestamp", current_timestamp())

(
    audit_df.write
    .format("delta")
    .mode("append")
    .saveAsTable(f"{catalog}.{schema}.pipeline_audit")
)

print(f"Audit log saved to {catalog}.{schema}.pipeline_audit.")
