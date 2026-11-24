# Databricks notebook source
# COMMAND ----------
# DBTITLE 1,ClaimSense: 00 - Environment & Unity Catalog Volume Setup
# MAGIC %md
# MAGIC ### Pipeline Stage: Setup Landing Volume & Schema
# MAGIC Initializes the Unity Catalog schema and landing zone Volume where messy incoming claim batch files are stored.
# MAGIC Designed to be fully serverless-compatible on Databricks Free Edition.

# COMMAND ----------
dbutils.widgets.text("catalog", "workspace", "Unity Catalog Name")
dbutils.widgets.text("schema", "claimsense", "Database / Schema Name")
dbutils.widgets.text("volume", "landing_zone", "Landing Volume Name")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
volume = dbutils.widgets.get("volume")

print(f"Target Environment: {catalog}.{schema}")
print(f"Landing Volume:     {catalog}.{schema}.{volume}")

# COMMAND ----------
# DBTITLE 1,Create Unity Catalog Schema & Volume
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{volume}")

volume_path = f"/Volumes/{catalog}/{schema}/{volume}"
print(f"[SUCCESS] Unity Catalog Volume ready at: {volume_path}")

# COMMAND ----------
# DBTITLE 1,Verify Volume Path
try:
    files = dbutils.fs.ls(volume_path)
    print(f"Found {len(files)} files in landing volume:")
    for f in files:
        print(f" - {f.name} ({f.size} bytes)")
except Exception as e:
    print(f"Landing volume empty or initializing: {e}")
