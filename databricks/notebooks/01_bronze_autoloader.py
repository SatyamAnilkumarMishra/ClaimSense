# Databricks notebook source
# COMMAND ----------
# DBTITLE 1,ClaimSense: 01 - Bronze Ingestion with Auto Loader
# MAGIC %md
# MAGIC ### Pipeline Stage: Bronze Ingestion
# MAGIC Ingests messy source files from Unity Catalog Volume using Databricks Auto Loader (`cloudFiles`).
# MAGIC 
# MAGIC Key Principles:
# MAGIC 1. **Append-Only**: Raw data is never modified or filtered at Bronze.
# MAGIC 2. **Metadata Enrichment**: Adds `_ingest_timestamp` and `_source_file`.
# MAGIC 3. **Schema Evolution**: Automatically infers and tracks schema changes via `cloudFiles.schemaLocation`.
# MAGIC 4. **Incremental Execution**: `.trigger(availableNow=True)` for predictable serverless batch costs.

# COMMAND ----------
from pyspark.sql.functions import current_timestamp, col

dbutils.widgets.text("catalog", "workspace", "Unity Catalog Name")
dbutils.widgets.text("schema", "claimsense", "Database / Schema Name")
dbutils.widgets.text("volume", "landing_zone", "Landing Volume Name")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
volume = dbutils.widgets.get("volume")

volume_base = f"/Volumes/{catalog}/{schema}/{volume}"
checkpoint_base = f"/Volumes/{catalog}/{schema}/{volume}/_checkpoints"

# COMMAND ----------
# DBTITLE 1,Ingest Bronze Customers
print("Ingesting Bronze Customers...")
customers_stream = (
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.inferColumnTypes", "true")
    .option("cloudFiles.schemaLocation", f"{checkpoint_base}/bronze_customers_schema")
    .option("header", "true")
    .load(f"{volume_base}/customers*.csv")
    .withColumn("_ingest_timestamp", current_timestamp())
    .withColumn("_source_file", col("_metadata.file_name"))
)

query_customers = (
    customers_stream.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{checkpoint_base}/bronze_customers_chk")
    .trigger(availableNow=True)
    .toTable(f"{catalog}.{schema}.bronze_customers")
)
query_customers.awaitTermination()
print(f"Bronze Customers row count: {spark.table(f'{catalog}.{schema}.bronze_customers').count()}")

# COMMAND ----------
# DBTITLE 1,Ingest Bronze Policies
print("Ingesting Bronze Policies...")
policies_stream = (
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.inferColumnTypes", "true")
    .option("cloudFiles.schemaLocation", f"{checkpoint_base}/bronze_policies_schema")
    .option("header", "true")
    .load(f"{volume_base}/policies*.csv")
    .withColumn("_ingest_timestamp", current_timestamp())
    .withColumn("_source_file", col("_metadata.file_name"))
)

query_policies = (
    policies_stream.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{checkpoint_base}/bronze_policies_chk")
    .trigger(availableNow=True)
    .toTable(f"{catalog}.{schema}.bronze_policies")
)
query_policies.awaitTermination()
print(f"Bronze Policies row count: {spark.table(f'{catalog}.{schema}.bronze_policies').count()}")

# COMMAND ----------
# DBTITLE 1,Ingest Bronze Claims (Raw Batches & Updates)
print("Ingesting Bronze Claims batches...")
claims_stream = (
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.inferColumnTypes", "true")
    .option("cloudFiles.schemaLocation", f"{checkpoint_base}/bronze_claims_schema")
    .option("header", "true")
    .load(f"{volume_base}/claims_*.csv")
    .withColumn("_ingest_timestamp", current_timestamp())
    .withColumn("_source_file", col("_metadata.file_name"))
)

query_claims = (
    claims_stream.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", f"{checkpoint_base}/bronze_claims_chk")
    .trigger(availableNow=True)
    .toTable(f"{catalog}.{schema}.bronze_claims")
)
query_claims.awaitTermination()
print(f"Bronze Claims row count: {spark.table(f'{catalog}.{schema}.bronze_claims').count()}")

# COMMAND ----------
# DBTITLE 1,Ingest Bronze Adjuster Notes (Semi-Structured JSON)
print("Ingesting Bronze Adjuster Notes...")
try:
    notes_df = (
        spark.read
        .option("multiline", "true")
        .json(f"{volume_base}/adjuster_notes.json")
        .withColumn("_ingest_timestamp", current_timestamp())
        .withColumn("_source_file", col("_metadata.file_name"))
    )
    (
        notes_df.write
        .format("delta")
        .mode("overwrite")
        .saveAsTable(f"{catalog}.{schema}.bronze_adjuster_notes")
    )
    print(f"Bronze Adjuster Notes row count: {spark.table(f'{catalog}.{schema}.bronze_adjuster_notes').count()}")
except Exception as e:
    print(f"Adjuster notes ingestion note: {e}")
