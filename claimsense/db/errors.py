"""Custom typed exceptions for ClaimSense Database & Service layers.

Enables precise error classification and clean diagnostic reporting for UI and API clients.
"""


class ClaimSenseDBError(Exception):
    """Base exception for ClaimSense database operations."""

    pass


class DatabricksConnectionError(ClaimSenseDBError):
    """Raised when network connection to Databricks fails or times out."""

    pass


class DatabricksAuthError(ClaimSenseDBError):
    """Raised when Databricks token is invalid, expired, or unauthorized."""

    pass


class DatabricksWarehouseStartingError(ClaimSenseDBError):
    """Raised when Databricks SQL Warehouse is suspended and spinning up from cold sleep."""

    pass


class DatabricksQuotaExceededError(ClaimSenseDBError):
    """Raised when Databricks Free Edition daily compute quota has been exhausted."""

    pass


class ClaimNotFoundError(Exception):
    """Raised when a requested claim_id does not exist."""

    def __init__(self, claim_id: str):
        super().__init__(f"Claim '{claim_id}' not found.")
        self.claim_id = claim_id
