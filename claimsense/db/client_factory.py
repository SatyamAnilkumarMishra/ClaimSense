"""Database client factory with automatic, transparent fallback to offline snapshots."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from claimsense.config import Settings, get_settings
from claimsense.db.databricks_client import DatabricksClient
from claimsense.db.errors import ClaimSenseDBError
from claimsense.db.snapshot_client import SnapshotClient

logger = logging.getLogger(__name__)


class ResilientDBClient:
    """Unified client that routes to Databricks when healthy, with instant snapshot fallback."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.databricks_client = DatabricksClient(self.settings)
        self.snapshot_client = SnapshotClient(self.settings)
        self.active_mode = "LIVE" if self.settings.is_databricks_configured else "OFFLINE_SNAPSHOT"

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any] | Tuple[Any, ...] | List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Executes query on Databricks if configured, degrading gracefully to Snapshot on error."""
        if self.settings.is_databricks_configured:
            try:
                results = self.databricks_client.execute_query(query, parameters)
                self.active_mode = "LIVE"
                return results
            except ClaimSenseDBError as exc:
                logger.warning(
                    f"Live Databricks query failed ({exc}). Falling back to Offline Snapshot mode."
                )
                self.active_mode = "OFFLINE_SNAPSHOT"

        # Offline snapshot fallback
        return self.snapshot_client.execute_query(query, parameters)


_resilient_client_instance: Optional[ResilientDBClient] = None


def get_db_client(settings: Optional[Settings] = None) -> ResilientDBClient:
    """Singleton getter for the resilient database client."""
    global _resilient_client_instance
    if _resilient_client_instance is None:
        _resilient_client_instance = ResilientDBClient(settings or get_settings())
    return _resilient_client_instance
