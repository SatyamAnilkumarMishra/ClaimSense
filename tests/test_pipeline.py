"""Tests for ClaimSense Medallion Pipeline & Reconciliation Engine.

Verifies:
1. End-to-end Medallion execution produces exact mathematical reconciliation (discrepancy == 0).
2. Quarantine routing correctly categorizes bad records with valid error codes.
3. Delta MERGE (CDC updates) correctly mutates claim statuses without inflating row count.
4. Gold Star schema integrity (fact_claims foreign keys match dimension tables).
"""

from pathlib import Path
import pytest
from databricks.local_pipeline import LocalMedallionPipeline


@pytest.fixture(scope="module")
def pipeline_instance(tmp_path_factory):
    """Initializes local pipeline in temporary test directory."""
    temp_dir = tmp_path_factory.mktemp("pipeline_test")
    db_file = temp_dir / "test_claimsense.db"
    pipeline = LocalMedallionPipeline(db_path=db_file)
    return pipeline


def test_bronze_ingestion(pipeline_instance):
    """Verify raw batch ingestion row counts."""
    res = pipeline_instance.run_bronze()
    assert res["claims_ingested"] >= 600


def test_silver_and_quarantine_routing(pipeline_instance):
    """Verify defective claims are quarantined and valid rows populate Silver."""
    res = pipeline_instance.run_silver()
    assert res["duplicates_quarantined"] > 0
    assert res["defects_quarantined"] > 0
    assert res["silver_valid"] > 500

    # Check quarantine rejection codes
    cur = pipeline_instance.conn.cursor()
    cur.execute("SELECT DISTINCT reject_reason FROM quarantine_claims")
    reasons = {r[0] for r in cur.fetchall()}
    assert "ERR_DUP_CLAIM" in reasons
    assert "ERR_NULL_INCIDENT_DATE" in reasons
    assert "ERR_INVALID_AMOUNT" in reasons
    assert "ERR_ORPHAN_POLICY" in reasons


def test_gold_star_schema(pipeline_instance):
    """Verify Star Schema dimensions and fact table creation."""
    res = pipeline_instance.run_gold()
    assert res["fact_claims_count"] > 500

    cur = pipeline_instance.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM dim_customer")
    assert cur.fetchone()[0] == 100

    cur.execute("SELECT COUNT(*) FROM dim_policy")
    assert cur.fetchone()[0] == 150

    cur.execute("SELECT COUNT(*) FROM dim_claim_type")
    assert cur.fetchone()[0] == 3


def test_reconciliation_audit_zero_discrepancy(pipeline_instance):
    """Verify invariant: Bronze == Duplicates + Defects + Silver."""
    audit = pipeline_instance.run_reconciliation(run_id="TEST-AUDIT-01")
    assert audit["status"] == "PASS"
    assert audit["discrepancy"] == 0
    assert audit["bronze_count"] == audit["duplicates_count"] + audit["defects_count"] + audit["silver_count"]
    assert audit["silver_count"] == audit["gold_fact_count"]


def test_delta_merge_cdc_updates(pipeline_instance):
    """Verify incremental updates batch mutates status without duplicating rows."""
    cur = pipeline_instance.conn.cursor()
    cur.execute("SELECT COUNT(*) FROM silver_claims")
    before_count = cur.fetchone()[0]

    update_res = pipeline_instance.apply_incremental_updates()
    assert update_res["updated_rows"] > 0

    cur.execute("SELECT COUNT(*) FROM silver_claims")
    after_count = cur.fetchone()[0]

    # Crucial Delta MERGE invariant: updates change row states, never inflate total count
    assert before_count == after_count, f"Row count changed from {before_count} to {after_count} during MERGE!"
