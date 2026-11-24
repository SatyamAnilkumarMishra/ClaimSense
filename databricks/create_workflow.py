"""Programmatically deploys the ClaimSense Medallion Workflow Job on Databricks.

Uses Databricks SDK to create an idempotent, restartable 5-task Workflow:
setup_volume -> bronze_ingestion -> silver_transformation -> gold_star_schema -> reconciliation_audit
"""

import sys
from claimsense.config import get_settings


def deploy_workflow() -> bool:
    settings = get_settings()

    print("=" * 60)
    print("ClaimSense: Databricks Workflow Job Deployment")
    print("=" * 60)

    if not settings.is_databricks_configured:
        print("[INFO] Databricks credentials not configured in .env.")
        print("Workflow definition script is ready. When your workspace is created, run:")
        print("  python databricks/create_workflow.py")
        print("=" * 60)
        return False

    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.service import jobs

        w = WorkspaceClient(
            host=settings.DATABRICKS_HOST,
            token=settings.DATABRICKS_TOKEN,
        )

        job_name = "ClaimSense-Medallion-Pipeline"
        print(f"Checking for existing job named '{job_name}'...")

        existing_jobs = list(w.jobs.list(name=job_name))
        existing_job_id = existing_jobs[0].job_id if existing_jobs else None

        # Base task parameters
        base_params = {
            "catalog": settings.DATABRICKS_CATALOG,
            "schema": settings.DATABRICKS_SCHEMA,
            "volume": settings.DATABRICKS_VOLUME,
        }

        # Notebook path prefix in Databricks workspace
        ws_user = w.current_user.me().user_name
        base_nb_path = f"/Users/{ws_user}/ClaimSense/notebooks"

        task_setup = jobs.Task(
            task_key="setup_volume",
            description="Initializes Unity Catalog schema and landing Volume",
            notebook_task=jobs.NotebookTask(
                notebook_path=f"{base_nb_path}/00_setup_volume",
                base_parameters=base_params,
            ),
        )

        task_bronze = jobs.Task(
            task_key="bronze_ingestion",
            description="Auto Loader ingestion from landing Volume into Bronze Delta",
            depends_on=[jobs.TaskDependency(task_key="setup_volume")],
            notebook_task=jobs.NotebookTask(
                notebook_path=f"{base_nb_path}/01_bronze_autoloader",
                base_parameters=base_params,
            ),
        )

        task_silver = jobs.Task(
            task_key="silver_transformation",
            description="Deduplication, cleaning, quarantine routing and Delta MERGE",
            depends_on=[jobs.TaskDependency(task_key="bronze_ingestion")],
            notebook_task=jobs.NotebookTask(
                notebook_path=f"{base_nb_path}/02_silver_transformation",
                base_parameters=base_params,
            ),
        )

        task_gold = jobs.Task(
            task_key="gold_star_schema",
            description="Builds Star Schema dimensions, fact_claims, and KPI views",
            depends_on=[jobs.TaskDependency(task_key="silver_transformation")],
            notebook_task=jobs.NotebookTask(
                notebook_path=f"{base_nb_path}/03_gold_star_schema",
                base_parameters=base_params,
            ),
        )

        task_audit = jobs.Task(
            task_key="reconciliation_audit",
            description="Reconciles row counts across layers and logs to pipeline_audit",
            depends_on=[jobs.TaskDependency(task_key="gold_star_schema")],
            notebook_task=jobs.NotebookTask(
                notebook_path=f"{base_nb_path}/04_reconciliation_audit",
                base_parameters=base_params,
            ),
        )

        tasks = [task_setup, task_bronze, task_silver, task_gold, task_audit]

        if existing_job_id:
            print(f"Updating existing Workflow Job (ID: {existing_job_id})...")
            w.jobs.reset(
                job_id=existing_job_id,
                new_settings=jobs.JobSettings(
                    name=job_name,
                    tasks=tasks,
                ),
            )
            job_id = existing_job_id
        else:
            print(f"Creating new Workflow Job '{job_name}'...")
            created = w.jobs.create(
                name=job_name,
                tasks=tasks,
            )
            job_id = created.job_id

        print(f"\n[SUCCESS] Databricks Workflow deployed successfully! Job ID: {job_id}")
        print(f"View in UI: {settings.DATABRICKS_HOST}/#job/{job_id}")
        return True

    except Exception as exc:
        print(f"\n[ERROR] Failed to deploy Workflow: {exc}")
        return False


if __name__ == "__main__":
    success = deploy_workflow()
    sys.exit(0 if success else 1)
