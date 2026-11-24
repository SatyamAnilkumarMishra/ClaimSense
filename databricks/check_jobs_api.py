"""Manual check: verifies the Databricks Jobs (Workflows) API connectivity.

Uses databricks-sdk WorkspaceClient to verify API connectivity and list available jobs.
"""

import sys

from claimsense.config import get_settings


def check_jobs_api() -> bool:
    settings = get_settings()

    print("=" * 60)
    print("ClaimSense: Databricks Jobs / Workflows API Test")
    print("=" * 60)

    if not settings.is_databricks_configured:
        print("[INFO] Databricks credentials are not configured in your .env file.")
        print("Required variables: DATABRICKS_HOST, DATABRICKS_TOKEN")
        print(
            "Offline pipeline simulation is ACTIVE. The project functions seamlessly without live Databricks."
        )
        print(
            "When you create your Databricks workspace, add credentials to .env and rerun this script."
        )
        print("=" * 60)
        return False

    try:
        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient(
            host=settings.DATABRICKS_HOST,
            token=settings.DATABRICKS_TOKEN,
        )

        print(f"Connecting to Databricks Workspace at: {settings.DATABRICKS_HOST}")
        print("Querying current user identity and jobs...")

        current_user = w.current_user.me()
        print(f"Authenticated User: {current_user.user_name}")

        jobs = list(w.jobs.list(limit=10))
        print(f"[SUCCESS] Databricks SDK connected! Found {len(jobs)} existing jobs.")
        for job in jobs:
            print(
                f" - Job ID: {job.job_id} | Name: {job.settings.name if job.settings else 'Unnamed'}"
            )

        return True

    except Exception as exc:
        print(f"\n[ERROR] Databricks SDK Jobs API test failed: {exc}")
        return False


if __name__ == "__main__":
    success = check_jobs_api()
    sys.exit(0 if success else 1)
