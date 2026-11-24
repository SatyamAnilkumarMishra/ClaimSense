"""Tests for ClaimSense configuration module."""

import os
from claimsense.config.settings import Settings


def test_default_settings():
    """Verify sensible defaults are active."""
    settings = Settings()
    assert settings.BACKEND_MODE in ["inprocess", "http"]
    assert settings.DATABRICKS_CATALOG == "workspace"
    assert settings.DATABRICKS_SCHEMA == "claimsense"
    assert settings.GROQ_FAST_MODEL == "llama-3.1-8b-instant"
    assert settings.GROQ_REASONING_MODEL == "llama-3.3-70b-versatile"


def test_databricks_not_configured_by_default(monkeypatch):
    """Verify is_databricks_configured returns False when credentials are empty."""
    monkeypatch.delenv("DATABRICKS_HOST", raising=False)
    monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
    monkeypatch.delenv("DATABRICKS_HTTP_PATH", raising=False)

    settings = Settings(
        DATABRICKS_HOST=None,
        DATABRICKS_TOKEN=None,
        DATABRICKS_HTTP_PATH=None,
        OFFLINE_MODE=False,
    )
    assert not settings.is_databricks_configured


def test_databricks_configured_when_all_params_present():
    """Verify is_databricks_configured returns True with valid credentials."""
    settings = Settings(
        DATABRICKS_HOST="https://dbc-test.cloud.databricks.com",
        DATABRICKS_TOKEN="dapi_test_token",
        DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/test",
        OFFLINE_MODE=False,
    )
    assert settings.is_databricks_configured


def test_offline_mode_forces_unconfigured():
    """Verify OFFLINE_MODE=True overrides credential presence for safe fallback."""
    settings = Settings(
        DATABRICKS_HOST="https://dbc-test.cloud.databricks.com",
        DATABRICKS_TOKEN="dapi_test_token",
        DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/test",
        GROQ_API_KEY="gsk_test",
        OFFLINE_MODE=True,
    )
    assert not settings.is_databricks_configured
    assert not settings.is_groq_configured
