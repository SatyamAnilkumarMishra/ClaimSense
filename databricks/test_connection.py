"""Test script for Databricks SQL Warehouse connectivity.

Runs a simple `SELECT 1` query using databricks-sql-connector.
Provides human-friendly diagnostic messages for auth, warehouse state, or missing variables.
"""

import sys
from claimsense.config import get_settings


def test_sql_connection() -> bool:
    settings = get_settings()

    print("=" * 60)
    print("ClaimSense: Databricks SQL Warehouse Connectivity Test")
    print("=" * 60)

    if not settings.is_databricks_configured:
        print("[INFO] Databricks credentials are not configured in your .env file.")
        print("Required variables: DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_HTTP_PATH")
        print("Offline snapshot mode is currently ACTIVE. The project runs seamlessly without live Databricks.")
        print("When you create your Databricks workspace, add your credentials to .env and rerun this script.")
        print("=" * 60)
        return False

    print(f"Connecting to host: {settings.DATABRICKS_HOST}")
    print(f"HTTP Path:          {settings.DATABRICKS_HTTP_PATH}")
    print("Initiating handshake...")

    try:
        from databricks import sql

        with sql.connect(
            server_hostname=settings.DATABRICKS_HOST.replace("https://", "").replace("http://", "").strip("/"),
            http_path=settings.DATABRICKS_HTTP_PATH,
            access_token=settings.DATABRICKS_TOKEN,
        ) as connection:
            with connection.cursor() as cursor:
                print("Running 'SELECT 1 AS status, current_timestamp() AS ts, current_user() AS user'...")
                cursor.execute("SELECT 1 AS status, current_timestamp() AS ts, current_user() AS user")
                result = cursor.fetchall()
                print("\n[SUCCESS] Databricks SQL Warehouse is connected and healthy!")
                print(f"Query Result: {result}")
                return True

    except Exception as exc:
        print("\n[ERROR] Connection failed!")
        error_msg = str(exc)
        if "401" in error_msg or "Invalid access token" in error_msg:
            print("Diagnosis: Authentication failed. Please check that DATABRICKS_TOKEN is valid and has not expired.")
        elif "Starting" in error_msg or "Warehouse is stopped" in error_msg:
            print("Diagnosis: SQL Warehouse is currently starting up from cold sleep. Wait 60 seconds and retry.")
        else:
            print(f"Error details: {error_msg}")
        return False


if __name__ == "__main__":
    success = test_sql_connection()
    sys.exit(0 if success else 1)
