"""Unit tests for ClaimSense synthetic data generator.

Verifies:
1. Deterministic generation with fixed random seed.
2. File existence and schema conformity.
3. Accurate dirty data injection proportions (duplicates, nulls, negative amounts, orphans).
"""

import csv
import json

import pytest

from data_gen.generate import (
    DEFAULT_SEED,
    generate_customers,
    run_generator,
)


@pytest.fixture(scope="module")
def generated_data(tmp_path_factory):
    """Generates synthetic dataset in temporary test directory."""
    temp_dir = tmp_path_factory.mktemp("data_gen_test")
    counts = run_generator(output_dir=temp_dir, seed=DEFAULT_SEED)
    return temp_dir, counts


def test_generator_determinism():
    """Verify identical random seed produces bit-for-bit identical customer lists."""
    c1 = generate_customers(num_customers=20)
    c2 = generate_customers(num_customers=20)
    assert c1 == c2


def test_generated_files_exist(generated_data):
    """Verify all required CSV and JSON output files are generated."""
    temp_dir, _ = generated_data
    expected_files = [
        "customers.csv",
        "policies.csv",
        "claims_batch_1.csv",
        "claims_batch_2.csv",
        "claims_batch_3.csv",
        "claims_updates.csv",
        "adjuster_notes.json",
    ]
    for filename in expected_files:
        p = temp_dir / filename
        assert p.exists(), f"File {filename} was not created."
        assert p.stat().st_size > 0, f"File {filename} is unexpectedly empty."


def test_customer_count_and_schema(generated_data):
    """Verify customer dataset dimensions and required fields."""
    temp_dir, counts = generated_data
    assert counts["customers"] == 100

    with open(temp_dir / "customers.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 100
        for r in rows:
            assert r["customer_id"].startswith("CUST-")
            assert float(r["risk_score"]) >= 0.0


def test_policy_count_and_types(generated_data):
    """Verify policy dataset dimensions and enum types."""
    temp_dir, counts = generated_data
    assert counts["policies"] == 150

    with open(temp_dir / "policies.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 150
        for r in rows:
            assert r["policy_type"] in ["AUTO", "HEALTH", "HOME"]
            assert float(r["sum_insured"]) > 0
            assert float(r["deductible"]) >= 0


def test_dirty_data_proportions(generated_data):
    """Verify injected dirty data matches expected statistical tolerances."""
    temp_dir, _ = generated_data

    # Load all 3 raw claims batches
    all_claims = []
    for b in [1, 2, 3]:
        with open(temp_dir / f"claims_batch_{b}.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            all_claims.extend(list(reader))

    total = len(all_claims)
    assert total > 600, "Expected at least 600 raw records."

    # 1. Duplicates check (~3% duplicates)
    claim_ids = [c["claim_id"] for c in all_claims]
    unique_ids = set(claim_ids)
    num_dups = total - len(unique_ids)
    dup_rate = num_dups / total
    assert 0.015 <= dup_rate <= 0.05, f"Duplicate rate {dup_rate:.3f} outside expected tolerance."

    # 2. Null incident_date check (~2%)
    null_dates = sum(1 for c in all_claims if not c["incident_date"].strip())
    null_date_rate = null_dates / total
    assert 0.01 <= null_date_rate <= 0.035, (
        f"Null date rate {null_date_rate:.3f} outside expected tolerance."
    )

    # 3. Invalid claimed amount (<= 0) check (~1%)
    invalid_amounts = sum(1 for c in all_claims if float(c["claimed_amount"]) <= 0)
    invalid_amt_rate = invalid_amounts / total
    assert 0.005 <= invalid_amt_rate <= 0.025, (
        f"Invalid amount rate {invalid_amt_rate:.3f} outside tolerance."
    )

    # 4. Orphan policy IDs check (~2%)
    with open(temp_dir / "policies.csv", encoding="utf-8") as f:
        valid_policy_ids = {r["policy_id"] for r in csv.DictReader(f)}
    orphan_claims = sum(1 for c in all_claims if c["policy_id"] not in valid_policy_ids)
    orphan_rate = orphan_claims / total
    assert 0.01 <= orphan_rate <= 0.035, f"Orphan rate {orphan_rate:.3f} outside tolerance."

    # 5. Inconsistent casing / whitespace check
    has_inconsistent_casing = any(
        c["status"] != c["status"].strip() or c["status"] != c["status"].upper() for c in all_claims
    )
    assert has_inconsistent_casing, "Expected inconsistent status casing and whitespace."


def test_adjuster_notes_json(generated_data):
    """Verify semi-structured notes JSON structure."""
    temp_dir, _ = generated_data
    with open(temp_dir / "adjuster_notes.json", encoding="utf-8") as f:
        notes_data = json.load(f)
        assert len(notes_data) == 600
        for entry in notes_data[:20]:
            assert "claim_id" in entry
            assert "notes" in entry
            assert len(entry["notes"]) >= 1
            assert "severity_tag" in entry["notes"][0]
