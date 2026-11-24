# Databricks notebook source
# COMMAND ----------
# DBTITLE 1,ClaimSense: 02 - Silver Cleaning, Quarantine & Delta MERGE
# MAGIC %md
# MAGIC ### Pipeline Stage: Silver Transformations & Quality Guardrails
# MAGIC Transforms raw Bronze data into trusted, analytics-ready Silver tables.
# MAGIC 
# MAGIC Steps:
# MAGIC 1. **Deduplication**: Window functions pick latest record by `(reported_date, _ingest_timestamp)`.
# MAGIC 2. **Type Casting & Normalization**: Standardizes status casing, trims whitespace, casts dates and currencies.
# MAGIC 3. **Referential Checks**: Validates `policy_id` exists in policies dimension.
# MAGIC 4. **Quarantine Routing**: Moves defective records to `quarantine_claims` with explicit `reject_reason`.
# MAGIC 5. **Delta MERGE (CDC Upsert)**: Incremental updates advance claim status without duplicating rows.
# MAGIC 6. **Data Quality Audit**: Records failure metrics in `dq_results`.

# COMMAND ----------
import uuid
from pyspark.sql.functions import (
    col, trim, upper, current_timestamp, current_date, row_number, when, lit, coalesce
)
from pyspark.sql.window import Window
from delta.tables import DeltaTable

dbutils.widgets.text("catalog", "workspace", "Unity Catalog Name")
dbutils.widgets.text("schema", "claimsense", "Database / Schema Name")
dbutils.widgets.text("run_id", "", "Pipeline Run ID (optional)")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
run_id = dbutils.widgets.get("run_id") or f"RUN-{uuid.uuid4().hex[:8].upper()}"

print(f"Target Schema: {catalog}.{schema}")
print(f"Pipeline Run ID: {run_id}")

# COMMAND ----------
# DBTITLE 1,Step 1: Silver Customers (Clean & Deduplicate)
print("Transforming Silver Customers...")
bronze_cust = spark.table(f"{catalog}.{schema}.bronze_customers")

cust_window = Window.partitionBy("customer_id").orderBy(col("_ingest_timestamp").desc())
silver_cust = (
    bronze_cust
    .withColumn("row_num", row_number().over(cust_window))
    .filter(col("row_num") == 1)
    .drop("row_num")
    .withColumn("first_name", trim(col("first_name")))
    .withColumn("last_name", trim(col("last_name")))
    .withColumn("email", trim(col("email")))
    .withColumn("city", trim(col("city")))
    .withColumn("state", trim(col("state")))
    .withColumn("risk_score", col("risk_score").cast("decimal(3,2)"))
    .withColumn("created_at", col("created_at").cast("timestamp"))
    .withColumn("_silver_timestamp", current_timestamp())
)

(
    silver_cust.write
    .format("delta")
    .mode("overwrite")
    .saveAsTable(f"{catalog}.{schema}.silver_customers")
)
print(f"Silver Customers count: {spark.table(f'{catalog}.{schema}.silver_customers').count()}")

# COMMAND ----------
# DBTITLE 1,Step 2: Silver Policies (Clean & Deduplicate)
print("Transforming Silver Policies...")
bronze_pol = spark.table(f"{catalog}.{schema}.bronze_policies")

pol_window = Window.partitionBy("policy_id").orderBy(col("_ingest_timestamp").desc())
silver_pol = (
    bronze_pol
    .withColumn("row_num", row_number().over(pol_window))
    .filter(col("row_num") == 1)
    .drop("row_num")
    .withColumn("policy_type", upper(trim(col("policy_type"))))
    .withColumn("status", upper(trim(col("status"))))
    .withColumn("start_date", col("start_date").cast("date"))
    .withColumn("end_date", col("end_date").cast("date"))
    .withColumn("sum_insured", col("sum_insured").cast("decimal(12,2)"))
    .withColumn("deductible", col("deductible").cast("decimal(10,2)"))
    .withColumn("_silver_timestamp", current_timestamp())
)

(
    silver_pol.write
    .format("delta")
    .mode("overwrite")
    .saveAsTable(f"{catalog}.{schema}.silver_policies")
)
print(f"Silver Policies count: {spark.table(f'{catalog}.{schema}.silver_policies').count()}")

# COMMAND ----------
# DBTITLE 1,Step 3: Quality Rules & Deduplication on Bronze Claims
print("Processing Bronze Claims...")
bronze_claims = spark.table(f"{catalog}.{schema}.bronze_claims")

# Window to detect duplicates within Bronze
claim_window = Window.partitionBy("claim_id").orderBy(col("reported_date").desc(), col("_ingest_timestamp").desc())

claims_staged = (
    bronze_claims
    .withColumn("row_num", row_number().over(claim_window))
    .withColumn("clean_status", upper(trim(col("status"))))
    .withColumn("clean_amount", col("claimed_amount").cast("decimal(12,2)"))
    .withColumn("clean_incident_date", col("incident_date").cast("date"))
    .withColumn("clean_reported_date", col("reported_date").cast("date"))
    .withColumn("clean_docs_count", col("documents_count").cast("int"))
)

# Join with Policies for foreign key check
valid_policies = spark.table(f"{catalog}.{schema}.silver_policies").select("policy_id", "sum_insured", "start_date", "end_date")
claims_with_policy = claims_staged.join(valid_policies, on="policy_id", how="left")

# Assign rejection reason hierarchy
claims_evaluated = claims_with_policy.withColumn(
    "reject_reason",
    when(col("row_num") > 1, lit("ERR_DUP_CLAIM"))
    .when(col("clean_incident_date").isNull(), lit("ERR_NULL_INCIDENT_DATE"))
    .when((col("clean_amount").isNull()) | (col("clean_amount") <= 0), lit("ERR_INVALID_AMOUNT"))
    .when(valid_policies.policy_id.isNull(), lit("ERR_ORPHAN_POLICY"))
    .when(col("clean_incident_date") > current_date(), lit("ERR_FUTURE_INCIDENT_DATE"))
    .otherwise(lit(None))
)

# Split into Quarantined vs Valid
quarantine_df = (
    claims_evaluated
    .filter(col("reject_reason").isNotNull())
    .select(
        col("claim_id"),
        col("policy_id"),
        col("claim_type"),
        col("incident_date").alias("raw_incident_date"),
        col("reported_date").alias("raw_reported_date"),
        col("claimed_amount").alias("raw_claimed_amount"),
        col("status").alias("raw_status"),
        col("description"),
        col("reject_reason"),
        col("_source_file"),
        lit(run_id).alias("run_id"),
        current_timestamp().alias("quarantined_at")
    )
)

valid_claims_df = (
    claims_evaluated
    .filter(col("reject_reason").isNull())
    .select(
        col("claim_id"),
        col("policy_id"),
        upper(trim(col("claim_type"))).alias("claim_type"),
        col("clean_incident_date").alias("incident_date"),
        col("clean_reported_date").alias("reported_date"),
        col("clean_amount").alias("claimed_amount"),
        col("clean_status").alias("status"),
        trim(col("description")).alias("description"),
        coalesce(col("clean_docs_count"), lit(0)).alias("documents_count"),
        trim(col("city")).alias("city"),
        col("_source_file"),
        current_timestamp().alias("_silver_timestamp")
    )
)

# COMMAND ----------
# DBTITLE 1,Step 4: Write to Quarantine Table
(
    quarantine_df.write
    .format("delta")
    .mode("append")
    .saveAsTable(f"{catalog}.{schema}.quarantine_claims")
)
quarantine_count = quarantine_df.count()
print(f"Quarantined claims in this run: {quarantine_count}")

# COMMAND ----------
# DBTITLE 1,Step 5: Delta MERGE into silver_claims (CDC Upsert)
silver_table_name = f"{catalog}.{schema}.silver_claims"

if not spark.catalog.tableExists(silver_table_name):
    print("Initializing silver_claims table...")
    (
        valid_claims_df.write
        .format("delta")
        .mode("overwrite")
        .saveAsTable(silver_table_name)
    )
else:
    print("Performing Delta MERGE (Upsert) on silver_claims...")
    silver_delta = DeltaTable.forName(spark, silver_table_name)
    (
        silver_delta.alias("target")
        .merge(
            valid_claims_df.alias("source"),
            "target.claim_id = source.claim_id"
        )
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )

silver_claims_count = spark.table(silver_table_name).count()
print(f"Total Silver Claims count: {silver_claims_count}")

# COMMAND ----------
# DBTITLE 1,Step 6: Record Data Quality Metrics (dq_results)
dq_metrics = (
    quarantine_df
    .groupBy("reject_reason")
    .count()
    .withColumnRenamed("count", "failed_count")
    .withColumn("run_id", lit(run_id))
    .withColumn("checked_at", current_timestamp())
)

(
    dq_metrics.write
    .format("delta")
    .mode("append")
    .saveAsTable(f"{catalog}.{schema}.dq_results")
)
print("Data Quality metrics successfully recorded in dq_results.")
