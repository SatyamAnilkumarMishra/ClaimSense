"""Databricks SQL Warehouse client with retries, parameterisation, and error classification."""

import logging
import time
from typing import Any

from claimsense.config import Settings, get_settings
from claimsense.db.errors import (
    DatabricksAuthError,
    DatabricksConnectionError,
    DatabricksQuotaExceededError,
    DatabricksWarehouseStartingError,
)

logger = logging.getLogger(__name__)


class DatabricksClient:
    """Client for executing parameterised queries against Databricks SQL Warehouses."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _classify_error(self, exc: Exception) -> Exception:
        """Classifies raw Databricks driver exceptions into domain-typed errors."""
        msg = str(exc)
        if "401" in msg or "Invalid access token" in msg or "authentication failed" in msg.lower():
            return DatabricksAuthError(f"Authentication failed: {msg}")
        if (
            "starting" in msg.lower()
            or "warehouse is stopped" in msg.lower()
            or "429" in msg
            and "cold" in msg.lower()
        ):
            return DatabricksWarehouseStartingError(
                "Databricks SQL Warehouse is currently starting up from cold sleep."
            )
        if "quota exceeded" in msg.lower() or "limit reached" in msg.lower():
            return DatabricksQuotaExceededError(
                "Databricks Free Edition daily compute quota exceeded."
            )
        return DatabricksConnectionError(f"Databricks connection error: {msg}")

    def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | tuple[Any, ...] | None = None,
        max_retries: int = 3,
        backoff_sec: float = 1.5,
    ) -> list[dict[str, Any]]:
        """Executes a parameterised read query with exponential backoff retries."""
        if not self.settings.is_databricks_configured:
            raise DatabricksConnectionError("Databricks is not configured in settings.")

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                from databricks import sql

                server_host = (
                    self.settings.DATABRICKS_HOST.replace("https://", "")
                    .replace("http://", "")
                    .strip("/")
                )

                with sql.connect(
                    server_hostname=server_host,
                    http_path=self.settings.DATABRICKS_HTTP_PATH,
                    access_token=self.settings.DATABRICKS_TOKEN,
                ) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(query, parameters or ())
                        if cursor.description:
                            columns = [col[0] for col in cursor.description]
                            rows = cursor.fetchall()
                            return [dict(zip(columns, row, strict=True)) for row in rows]
                        return []

            except Exception as exc:
                last_error = self._classify_error(exc)
                logger.warning(
                    f"Databricks query attempt {attempt}/{max_retries} failed: {last_error}"
                )
                if isinstance(last_error, (DatabricksAuthError, DatabricksQuotaExceededError)):
                    # Non-retryable
                    raise last_error from exc
                if attempt < max_retries:
                    time.sleep(backoff_sec * (2 ** (attempt - 1)))

        raise last_error or DatabricksConnectionError("Query execution failed after retries.")
