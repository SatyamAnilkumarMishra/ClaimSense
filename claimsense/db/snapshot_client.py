"""Local SQLite / Parquet Snapshot client for zero-cost offline resilience."""

import sqlite3
from pathlib import Path
from typing import Any

from claimsense.config import Settings, get_settings


class SnapshotClient:
    """Queries local snapshot database for offline demo and resilient fallback."""

    def __init__(self, settings: Settings | None = None, db_path: Path | None = None):
        self.settings = settings or get_settings()
        self.db_path = db_path or (self.settings.SNAPSHOTS_PATH / "claimsense_local.db")
        self._ensure_snapshot_exists()

    def _ensure_snapshot_exists(self) -> None:
        """Auto-populates local snapshot if not present."""
        if not self.db_path.exists():
            from databricks.local_pipeline import LocalMedallionPipeline

            pipeline = LocalMedallionPipeline(db_path=self.db_path)
            pipeline.run_bronze()
            pipeline.run_silver()
            pipeline.run_gold()
            pipeline.run_reconciliation(run_id="INIT-SNAPSHOT")

    def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | tuple[Any, ...] | list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Executes parameterised read queries against the local snapshot SQLite database."""
        # Convert Databricks catalog/schema qualified names to standard local table names
        cleaned_query = (
            query.replace(
                f"{self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.", ""
            )
            .replace("workspace.claimsense.", "")
            .replace("main.claimsense.", "")
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(cleaned_query, parameters or ())
            rows = cur.fetchall()
            return [dict(r) for r in rows]
