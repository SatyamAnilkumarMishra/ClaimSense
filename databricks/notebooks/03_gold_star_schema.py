# Databricks notebook source
# COMMAND ----------
# DBTITLE 1,ClaimSense: 03 - Gold Star Schema Modeling & KPI Views
# MAGIC %md
# MAGIC ### Pipeline Stage: Gold Star Schema & KPI Views
# MAGIC Models cleaned Silver data into an analytical Star Schema optimized for BI queries, dashboard serving, and the LangGraph triage agent.
# MAGIC
# MAGIC Star Schema Design:
# MAGIC * **Dimensions**: `dim_customer`, `dim_policy`, `dim_claim_type`, `dim_date`
# MAGIC * **Fact**: `fact_claims` with surrogate keys, grain: 1 row per claim
# MAGIC * **KPI Views**: `kpi_claims_by_type_month`, `kpi_top_risk_customers`

# COMMAND ----------
from pyspark.sql.functions import (
    col,
    concat_ws,
    current_timestamp,
    date_format,
    datediff,
    lit,
    sha2,
    when,
)

dbutils.widgets.text("catalog", "workspace", "Unity Catalog Name")
dbutils.widgets.text("schema", "claimsense", "Database / Schema Name")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

print(f"Target Schema: {catalog}.{schema}")

# COMMAND ----------
# DBTITLE 1,Dimension: dim_customer
print("Building dim_customer...")
silver_cust = spark.table(f"{catalog}.{schema}.silver_customers")
dim_customer = silver_cust.select(
    sha2(col("customer_id"), 256).alias("customer_sk"),
    col("customer_id"),
    col("first_name"),
    col("last_name"),
    concat_ws(" ", col("first_name"), col("last_name")).alias("full_name"),
    col("email"),
    col("phone"),
    col("city"),
    col("state"),
    col("risk_score"),
    col("created_at"),
    current_timestamp().alias("_effective_date"),
)
dim_customer.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.dim_customer")
print(f"dim_customer rows: {spark.table(f'{catalog}.{schema}.dim_customer').count()}")

# COMMAND ----------
# DBTITLE 1,Dimension: dim_policy
print("Building dim_policy...")
silver_pol = spark.table(f"{catalog}.{schema}.silver_policies")
dim_policy = silver_pol.select(
    sha2(col("policy_id"), 256).alias("policy_sk"),
    col("policy_id"),
    col("customer_id"),
    sha2(col("customer_id"), 256).alias("customer_sk"),
    col("policy_type"),
    col("start_date"),
    col("end_date"),
    col("sum_insured"),
    col("deductible"),
    col("status").alias("policy_status"),
    current_timestamp().alias("_effective_date"),
)
dim_policy.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.dim_policy")
print(f"dim_policy rows: {spark.table(f'{catalog}.{schema}.dim_policy').count()}")

# COMMAND ----------
# DBTITLE 1,Dimension: dim_claim_type
print("Building dim_claim_type...")
silver_claims = spark.table(f"{catalog}.{schema}.silver_claims")
dim_claim_type = (
    silver_claims.select("claim_type")
    .distinct()
    .select(sha2(col("claim_type"), 256).alias("claim_type_sk"), col("claim_type"))
)
dim_claim_type.write.format("delta").mode("overwrite").saveAsTable(
    f"{catalog}.{schema}.dim_claim_type"
)
print(f"dim_claim_type rows: {spark.table(f'{catalog}.{schema}.dim_claim_type').count()}")

# COMMAND ----------
# DBTITLE 1,Dimension: dim_date
print("Building dim_date...")
spark.sql(f"""
CREATE OR REPLACE TABLE {catalog}.{schema}.dim_date AS
WITH date_range AS (
    SELECT explode(sequence(to_date('2024-01-01'), to_date('2027-12-31'), interval 1 day)) AS calendar_date
)
SELECT
    cast(date_format(calendar_date, 'yyyyMMdd') AS INT) AS date_key,
    calendar_date AS full_date,
    year(calendar_date) AS year,
    quarter(calendar_date) AS quarter,
    month(calendar_date) AS month,
    date_format(calendar_date, 'MMMM') AS month_name,
    day(calendar_date) AS day_of_month,
    dayofweek(calendar_date) AS day_of_week,
    date_format(calendar_date, 'EEEE') AS day_name,
    CASE WHEN dayofweek(calendar_date) IN (1, 7) THEN 1 ELSE 0 END AS is_weekend
FROM date_range
""")
print(f"dim_date rows: {spark.table(f'{catalog}.{schema}.dim_date').count()}")

# COMMAND ----------
# DBTITLE 1,Fact Table: fact_claims
print("Building fact_claims...")
fact_claims = (
    silver_claims.alias("c")
    .join(
        spark.table(f"{catalog}.{schema}.dim_policy").alias("p"),
        col("c.policy_id") == col("p.policy_id"),
        "inner",
    )
    .join(
        spark.table(f"{catalog}.{schema}.dim_customer").alias("u"),
        col("p.customer_id") == col("u.customer_id"),
        "inner",
    )
    .join(
        spark.table(f"{catalog}.{schema}.dim_claim_type").alias("t"),
        col("c.claim_type") == col("t.claim_type"),
        "inner",
    )
    .select(
        sha2(col("c.claim_id"), 256).alias("claim_sk"),
        col("c.claim_id"),
        col("p.policy_sk"),
        col("u.customer_sk"),
        col("t.claim_type_sk"),
        date_format(col("c.incident_date"), "yyyyMMdd").cast("int").alias("incident_date_key"),
        date_format(col("c.reported_date"), "yyyyMMdd").cast("int").alias("reported_date_key"),
        col("c.incident_date"),
        col("c.reported_date"),
        datediff(col("c.reported_date"), col("c.incident_date")).alias("reporting_delay_days"),
        col("c.claimed_amount"),
        col("c.status").alias("claim_status"),
        col("c.documents_count"),
        col("c.description"),
        col("c.city"),
        when(col("c.status").isin("APPROVED", "SETTLED"), lit(1))
        .otherwise(lit(0))
        .alias("is_settled"),
        when(col("u.risk_score") >= 0.70, lit(1))
        .otherwise(lit(0))
        .alias("flag_high_risk_customer"),
        current_timestamp().alias("_gold_timestamp"),
    )
)

fact_claims.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.fact_claims")
print(f"fact_claims row count: {spark.table(f'{catalog}.{schema}.fact_claims').count()}")

# COMMAND ----------
# DBTITLE 1,KPI View: Claims by Type and Month
spark.sql(f"""
CREATE OR REPLACE VIEW {catalog}.{schema}.kpi_claims_by_type_month AS
SELECT
    t.claim_type,
    d.year,
    d.month,
    d.month_name,
    COUNT(f.claim_sk) AS total_claims,
    ROUND(SUM(f.claimed_amount), 2) AS total_claimed_amount,
    ROUND(AVG(f.claimed_amount), 2) AS avg_claimed_amount,
    ROUND(AVG(f.reporting_delay_days), 1) AS avg_reporting_delay_days,
    ROUND(SUM(f.flag_high_risk_customer) / COUNT(f.claim_sk) * 100, 2) AS high_risk_percentage
FROM {catalog}.{schema}.fact_claims f
JOIN {catalog}.{schema}.dim_claim_type t ON f.claim_type_sk = t.claim_type_sk
JOIN {catalog}.{schema}.dim_date d ON f.incident_date_key = d.date_key
GROUP BY t.claim_type, d.year, d.month, d.month_name
ORDER BY d.year DESC, d.month DESC, t.claim_type
""")
print("kpi_claims_by_type_month view created.")

# COMMAND ----------
# DBTITLE 1,KPI View: Top Risk Customers (Window Function / CTE)
spark.sql(f"""
CREATE OR REPLACE VIEW {catalog}.{schema}.kpi_top_risk_customers AS
WITH customer_claim_summary AS (
    SELECT
        u.customer_id,
        u.full_name,
        u.email,
        u.city,
        u.state,
        u.risk_score,
        COUNT(f.claim_sk) AS claim_count,
        ROUND(SUM(f.claimed_amount), 2) AS total_claimed_amount,
        ROUND(AVG(f.claimed_amount), 2) AS avg_claimed_amount,
        MAX(f.incident_date) AS latest_incident_date
    FROM {catalog}.{schema}.fact_claims f
    JOIN {catalog}.{schema}.dim_customer u ON f.customer_sk = u.customer_sk
    GROUP BY u.customer_id, u.full_name, u.email, u.city, u.state, u.risk_score
)
SELECT
    *,
    DENSE_RANK() OVER (ORDER BY claim_count DESC, total_claimed_amount DESC) AS risk_rank
FROM customer_claim_summary
WHERE claim_count >= 2 OR risk_score >= 0.70
ORDER BY risk_rank
""")
print("kpi_top_risk_customers view created.")
