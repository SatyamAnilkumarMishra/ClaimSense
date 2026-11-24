# ClaimSense: Databricks Free Edition Setup Guide

Follow these steps when you are ready to create your Databricks Free Edition / Community workspace and connect it to ClaimSense.

---

## 1. Create Databricks Free Edition Workspace
1. Visit **[databricks.com/try-databricks](https://www.databricks.com/try-databricks)**.
2. Select **Community Edition** (or Free Serverless Trial if offered without requiring a credit card).
3. Complete the signup and verify your email.

---

## 2. Obtain Credentials & Connection Details

### A. Serverless SQL Warehouse Connection
1. In the left navigation bar, open **SQL Warehouses** (or **Compute** $\rightarrow$ **SQL Warehouses**).
2. Click on the default warehouse (e.g., `Serverless Starter Warehouse`).
3. Click on the **Connection Details** tab.
4. Copy the following values:
   * **Server Hostname**: e.g., `dbc-xxxxxx.cloud.databricks.com`
   * **HTTP Path**: e.g., `/sql/1.0/warehouses/a1b2c3d4e5f6`
   * **Port**: `443`

### B. Personal Access Token (PAT)
1. In the upper-right corner, click on your profile icon $\rightarrow$ **Settings**.
2. Under **User**, click on **Developer** $\rightarrow$ **Access Tokens**.
3. Click **Generate New Token**.
   * *Comment*: `ClaimSense-Local-App`
   * *Lifetime*: `30` or `90` days (choose narrowest practical window)
4. Copy the token string immediately (format: `dapi...`).

### C. Discover Catalog & Schema
1. In the left sidebar, click **Catalog**.
2. Notice the top-level catalog name (usually `workspace` or `main`).
3. Ensure or create a database/schema called `claimsense`:
   ```sql
   CREATE SCHEMA IF NOT EXISTS workspace.claimsense;
   ```
4. Create a Volume for landing messy claim files:
   ```sql
   CREATE VOLUME IF NOT EXISTS workspace.claimsense.landing_zone;
   ```

---

## 3. Update Your `.env` File
Create a `.env` file in `D:\ClaimSense\` by copying `.env.example`:
```ini
BACKEND_MODE=inprocess
OFFLINE_MODE=false

DATABRICKS_HOST=https://dbc-xxxxxx.cloud.databricks.com
DATABRICKS_TOKEN=dapi_your_actual_token_here
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/xxxxxx
DATABRICKS_CATALOG=workspace
DATABRICKS_SCHEMA=claimsense
DATABRICKS_VOLUME=landing_zone
```

---

## 4. Verify Connectivity
Run the check scripts:
```powershell
.\.venv\Scripts\python.exe databricks/check_connection.py
.\.venv\Scripts\python.exe databricks/check_jobs_api.py
```
If successful, you will see `[SUCCESS] Databricks SQL Warehouse is connected and healthy!`.
