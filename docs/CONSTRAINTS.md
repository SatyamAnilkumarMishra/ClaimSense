# ClaimSense: Platform Limits & Free-Tier Constraints

This document records the exact operational constraints, quotas, and architectural safeguards implemented across all external services in ClaimSense. All choices ensure **100% zero-cost operation** with honest, un-faked fallback modes.

---

## 1. Databricks Free Edition (Serverless)

| Dimension | Quota / Restriction | Architecture Safeguard |
| :--- | :--- | :--- |
| **Compute Type** | Serverless SQL Warehouses & Serverless Notebooks only | No custom cluster configurations; all code is written in serverless-compatible standard Spark/Delta syntax. |
| **Catalog** | Dynamic discovery (cannot assume `main` or `hive_metastore`) | Catalog name is discovered and parameterized via `DATABRICKS_CATALOG` environment variable. |
| **Auto-Suspension** | SQL Warehouse suspends when idle (spins up in ~60-120s) | The UI displays cold-start loading indicators and connection timeouts with graceful retry logic. |
| **Daily Compute Quota** | Strict daily quota limit (account shuts down when exceeded) | Queries are cached (`st.cache_data`); `OFFLINE_MODE` allows full application functionality using local Parquet/SQLite snapshots. |
| **Landing Zone** | External S3/ADLS storage configuration restricted | Uses Unity Catalog Volumes (`landing_zone`) for source file ingestion. |
| **Account Retention** | Inactive accounts can be pruned | All notebooks and workflow configurations are version-controlled in Git (`databricks/` folder). |

---

## 2. Groq Free Tier (LLM Provider)

| Dimension | Free Limit | Architecture Safeguard |
| :--- | :--- | :--- |
| **Rate Limits (RPM / TPM)** | Varies by model (typically 30 RPM, 6,000-20,000 TPM) | Two-tier model routing: low-latency 8B model (`llama-3.1-8b-instant`) for parsing, 70B model (`llama-3.3-70b-versatile`) only for complex claim triage. |
| **Quota Protection** | Daily token budget ceiling | Exponential backoff retries, local response caching for identical inputs, and `GROQ_DAILY_TOKEN_LIMIT` tracker. |
| **Security** | Prompts transmitted over HTTPS | API keys are kept server-side only; untrusted inputs (claim descriptions, notes) are delimited and sanitized against prompt injections. |

---

## 3. Streamlit Community Cloud

| Dimension | Restriction | Architecture Safeguard |
| :--- | :--- | :--- |
| **Compute & Memory** | ~1 GB RAM per app, CPU-only container | In-process execution (`BACKEND_MODE=inprocess`) eliminates the need for hosting a secondary container. |
| **Container Idle Sleep** | Apps go to sleep when inactive | Fast startup design, light dependencies, state restoration from persistent snapshots. |
| **Secrets Management** | No local `.env` file in the cloud | Integrated reading from `st.secrets` falling back cleanly to environment variables. |

---

## 4. Snowflake (Stage 7 - 30-Day Trial)

| Dimension | Restriction | Architecture Safeguard |
| :--- | :--- | :--- |
| **Trial Duration** | 30 days / \$400 credit allowance | Trial is initiated only when starting Stage 7; warehouse is sized `X-SMALL` with `AUTO_SUSPEND = 60` seconds. |
| **Reproducibility** | Trial will expire | All DDL/DML, stages, tasks, and RBAC policies are preserved in versioned SQL scripts (`snowflake/` folder). Application gracefully falls back to cached exports if Snowflake is disconnected. |
