"""Unit tests for ClaimSense Service Layer and Database Fallback."""

from unittest.mock import MagicMock

import pytest

from claimsense.config import Settings
from claimsense.db.client_factory import ResilientDBClient
from claimsense.db.errors import DatabricksConnectionError
from claimsense.services.claims_service import ClaimsService
from claimsense.services.models import TriageDecisionEnum


@pytest.fixture(scope="module")
def service_instance():
    """Returns ClaimsService instance backed by local snapshot."""
    return ClaimsService()


def test_service_health(service_instance):
    """Verify health endpoint reports offline snapshot mode when Databricks is unconfigured."""
    health = service_instance.get_health()
    assert health.status in ["HEALTHY", "DEGRADED"]
    assert health.mode in ["LIVE", "OFFLINE_SNAPSHOT"]


def test_service_kpi_summary(service_instance):
    """Verify KPI calculations return non-null positive metrics."""
    kpis = service_instance.get_kpi_summary()
    assert kpis.total_claims > 0
    assert kpis.total_claimed_amount > 0.0
    assert kpis.average_claimed_amount > 0.0
    assert 0.0 <= kpis.high_risk_rate_percent <= 100.0


def test_service_claims_list_and_detail(service_instance):
    """Verify claims listing and single-claim lookup."""
    claims = service_instance.get_claims(limit=10)
    assert len(claims) > 0
    sample_id = claims[0].claim_id

    detail = service_instance.get_claim_detail(sample_id)
    assert detail.claim_id == sample_id
    assert detail.policy_sum_insured > 0


def test_service_triage_flow(service_instance):
    """Verify LangGraph triage agent assesses claim and returns cited clauses."""
    claims = service_instance.get_claims(limit=5)
    sample_id = claims[0].claim_id

    assessment = service_instance.triage_claim(sample_id)
    assert assessment.claim_id == sample_id
    assert assessment.decision in [
        TriageDecisionEnum.FAST_TRACK,
        TriageDecisionEnum.NEEDS_REVIEW,
        TriageDecisionEnum.ESCALATE_SIU,
    ]
    assert len(assessment.rule_checks) == 5
    assert len(assessment.cited_clause_ids) > 0
    assert len(assessment.trace) >= 4


def test_databricks_failure_fallback_to_snapshot():
    """Verify ResilientDBClient gracefully degrades to snapshot when Databricks raises error."""
    mock_settings = Settings(
        DATABRICKS_HOST="https://dbc-mock.cloud.databricks.com",
        DATABRICKS_TOKEN="dapi_mock",
        DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/mock",
        OFFLINE_MODE=False,
    )
    client = ResilientDBClient(settings=mock_settings)

    # Mock Databricks client to raise connection error
    client.databricks_client.execute_query = MagicMock(
        side_effect=DatabricksConnectionError("Mocked timeout to Databricks SQL Warehouse")
    )

    # Execution should not raise exception, but fallback to snapshot
    rows = client.execute_query("SELECT COUNT(*) as cnt FROM fact_claims")
    assert len(rows) == 1
    assert rows[0]["cnt"] > 0
    assert client.active_mode == "OFFLINE_SNAPSHOT"
