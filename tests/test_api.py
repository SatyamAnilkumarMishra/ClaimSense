"""Integration and Security tests for ClaimSense FastAPI endpoints."""

from fastapi.testclient import TestClient
import pytest

from api.main import app
from claimsense.config import get_settings


@pytest.fixture(scope="module")
def api_client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers():
    settings = get_settings()
    return {"X-API-Key": settings.FASTAPI_API_KEY}


def test_api_health_endpoint(api_client):
    """Verify GET /health returns 200 and system modes."""
    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["HEALTHY", "DEGRADED"]
    assert data["mode"] in ["LIVE", "OFFLINE_SNAPSHOT"]


def test_api_kpis_endpoint(api_client):
    """Verify GET /kpis returns aggregated numbers."""
    response = api_client.get("/kpis")
    assert response.status_code == 200
    data = response.json()
    assert data["total_claims"] > 0
    assert data["total_claimed_amount"] > 0


def test_api_claims_endpoints(api_client):
    """Verify GET /claims and GET /claims/{claim_id}."""
    response = api_client.get("/claims?limit=5")
    assert response.status_code == 200
    claims = response.json()
    assert len(claims) > 0

    first_claim_id = claims[0]["claim_id"]
    detail_resp = api_client.get(f"/claims/{first_claim_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["claim_id"] == first_claim_id


def test_api_triage_unauthorized(api_client):
    """Security: Verify /triage is rejected with 401 when missing or invalid API key."""
    # 1. Missing header
    res1 = api_client.post("/triage/CLM-30001")
    assert res1.status_code == 401
    assert "Invalid or missing X-API-Key" in res1.json()["detail"]

    # 2. Invalid header
    res2 = api_client.post("/triage/CLM-30001", headers={"X-API-Key": "invalid_wrong_secret"})
    assert res2.status_code == 401


def test_api_triage_authorized(api_client, auth_headers):
    """Verify /triage invokes LangGraph agent with valid API key."""
    # Fetch a valid claim id
    claims_resp = api_client.get("/claims?limit=1")
    claim_id = claims_resp.json()[0]["claim_id"]

    response = api_client.post(f"/triage/{claim_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == claim_id
    assert data["decision"] in ["FAST_TRACK", "NEEDS_REVIEW", "ESCALATE_SIU"]
    assert len(data["cited_clause_ids"]) > 0
    assert len(data["rule_checks"]) == 5


def test_api_human_review_resume(api_client, auth_headers):
    """Verify /triage/{claim_id}/review resumes LangGraph agent checkpoint."""
    claims_resp = api_client.get("/claims?limit=1")
    claim_id = claims_resp.json()[0]["claim_id"]

    # Run triage first
    api_client.post(f"/triage/{claim_id}", headers=auth_headers)

    # Submit human review
    review_payload = {
        "action": "APPROVE",
        "reviewer_notes": "Claim verified with police report and repair invoice.",
    }
    response = api_client.post(
        f"/triage/{claim_id}/review",
        headers=auth_headers,
        json=review_payload,
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["claim_id"] == claim_id
    assert res_data["status"] == "FINALIZED"


def test_no_secrets_in_responses(api_client, auth_headers):
    """Security: Asserts no tokens or keys are ever leaked in API response payloads."""
    settings = get_settings()
    endpoints = ["/health", "/kpis", "/claims?limit=1", "/quality/summary", "/audit/runs"]

    for ep in endpoints:
        resp = api_client.get(ep)
        text = resp.text
        if settings.DATABRICKS_TOKEN:
            assert settings.DATABRICKS_TOKEN not in text
        if settings.GROQ_API_KEY:
            assert settings.GROQ_API_KEY not in text
        assert settings.FASTAPI_API_KEY not in text
