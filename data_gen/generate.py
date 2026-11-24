"""ClaimSense Synthetic Data Generator.

Generates realistic, dirty insurance datasets (customers, policies, claims, updates, adjuster notes)
with precise dirty data proportions for testing Data Engineering pipelines, Delta Lake Medallion
architecture, and LangGraph triage agent rules.

Pure Python standard library implementation with zero external dependencies.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

# Deterministic Seed
DEFAULT_SEED = 42

# Anchor Date for Time Calculations (Relative "Present")
ANCHOR_DATE = date(2026, 6, 1)

CITIES_BY_STATE = [
    ("Columbus", "OH"),
    ("Cleveland", "OH"),
    ("Cincinnati", "OH"),
    ("Indianapolis", "IN"),
    ("Chicago", "IL"),
    ("Detroit", "MI"),
    ("Pittsburgh", "PA"),
    ("Louisville", "KY"),
    ("Milwaukee", "WI"),
    ("Des Moines", "IA"),
]

FIRST_NAMES = [
    "James",
    "Mary",
    "Robert",
    "Patricia",
    "John",
    "Jennifer",
    "Michael",
    "Linda",
    "David",
    "Elizabeth",
    "William",
    "Barbara",
    "Richard",
    "Susan",
    "Joseph",
    "Jessica",
    "Thomas",
    "Sarah",
    "Charles",
    "Karen",
    "Christopher",
    "Nancy",
    "Daniel",
    "Lisa",
    "Matthew",
    "Betty",
    "Anthony",
    "Margaret",
    "Mark",
    "Sandra",
    "Donald",
    "Ashley",
    "Steven",
    "Kimberly",
    "Paul",
    "Emily",
    "Andrew",
    "Donna",
    "Joshua",
    "Michelle",
]

LAST_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
    "Lee",
    "Perez",
    "Thompson",
    "White",
    "Harris",
    "Sanchez",
    "Clark",
    "Ramirez",
    "Lewis",
    "Robinson",
    "Walker",
]

CLAIM_DESCRIPTIONS = {
    "AUTO": [
        "Rear-ended at traffic signal during morning rush hour.",
        "Vehicle side-swiped while legally parked on curbside overnight.",
        "Struck deer on state highway causing heavy front bumper and radiator damage.",
        "Vehicle windshield cracked by loose gravel thrown by commercial truck.",
        "Vehicle broken into overnight; dashboard audio electronics stolen and window broken.",
        "Single-car collision with guardrail after unexpected black ice spin.",
    ],
    "HEALTH": [
        "Emergency appendectomy performed following severe abdominal symptoms.",
        "Inpatient hospitalization for acute pneumonia treatment over 4 days.",
        "Day care surgical procedure for knee meniscus repair after sports injury.",
        "Cardiac stent insertion and 3-day post-operative ICU monitoring.",
        "Treatment for fractured clavicle and overnight observation following bicycle fall.",
        "Emergency medical admission for acute kidney stone removal.",
    ],
    "HOME": [
        "Severe tree branch collapse through residential roof during thunder windstorm.",
        "Burst kitchen plumbing pipe during freeze causing drywall and floor water damage.",
        "Basement furnace fire with heavy smoke damage throughout main living level.",
        "Residential forced entry burglary; jewelry and electronics removed from master bedroom.",
        "Hail storm impact damage to roof asphalt shingles and window vinyl siding.",
        "Lightning strike causing electrical surge and scorched exterior chimney brick.",
    ],
}


def generate_customers(
    num_customers: int = 100, rng: random.Random | None = None
) -> list[dict[str, Any]]:
    """Generates synthetic customer dimension records."""
    if rng is None:
        rng = random.Random(DEFAULT_SEED)

    customers = []
    for i in range(1, num_customers + 1):
        cust_id = f"CUST-{10000 + i}"
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        email = f"{first_name.lower()}.{last_name.lower()}{rng.randint(10, 99)}@example.com"
        phone = f"+1-{rng.randint(200, 999)}-{rng.randint(200, 999)}-{rng.randint(1000, 9999)}"
        city, state = rng.choice(CITIES_BY_STATE)

        # 90% normal risk (0.05 - 0.40), 10% elevated risk (0.60 - 0.95)
        if rng.random() < 0.10:
            risk_score = round(rng.uniform(0.60, 0.95), 2)
        else:
            risk_score = round(rng.uniform(0.05, 0.40), 2)

        created_days_ago = rng.randint(200, 900)
        created_at = (ANCHOR_DATE - timedelta(days=created_days_ago)).isoformat()

        customers.append(
            {
                "customer_id": cust_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "city": city,
                "state": state,
                "risk_score": risk_score,
                "created_at": created_at,
            }
        )
    return customers


def generate_policies(
    customers: list[dict[str, Any]],
    num_policies: int = 150,
    rng: random.Random | None = None,
) -> list[dict[str, Any]]:
    """Generates synthetic policy records mapped to customers."""
    if rng is None:
        rng = random.Random(DEFAULT_SEED)

    policies = []
    policy_types = ["AUTO", "HEALTH", "HOME"]

    for i in range(1, num_policies + 1):
        pol_id = f"POL-{20000 + i}"
        customer = rng.choice(customers)
        p_type = rng.choice(policy_types)

        # Policy period
        start_offset = rng.randint(100, 450)
        start_date = ANCHOR_DATE - timedelta(days=start_offset)
        duration_days = rng.choice([180, 365, 730])
        end_date = start_date + timedelta(days=duration_days)

        if p_type == "AUTO":
            sum_insured = rng.choice([15000, 25000, 35000, 50000, 65000])
            deductible = rng.choice([500, 750, 1000])
        elif p_type == "HEALTH":
            sum_insured = rng.choice([25000, 50000, 75000, 100000, 150000])
            deductible = rng.choice([250, 500, 1000])
        else:  # HOME
            sum_insured = rng.choice([150000, 250000, 350000, 500000])
            deductible = rng.choice([1000, 1500, 2500])

        status_roll = rng.random()
        if status_roll < 0.85:
            status = "ACTIVE"
        elif status_roll < 0.95:
            status = "LAPSED"
        else:
            status = "CANCELLED"

        policies.append(
            {
                "policy_id": pol_id,
                "customer_id": customer["customer_id"],
                "policy_type": p_type,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "sum_insured": float(sum_insured),
                "deductible": float(deductible),
                "status": status,
            }
        )
    return policies


def generate_claims_and_notes(
    policies: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    total_claims: int = 600,
    rng: random.Random | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Generates synthetic raw claims, updates, and adjuster notes with injected dirty data."""
    if rng is None:
        rng = random.Random(DEFAULT_SEED)

    policy_map = {p["policy_id"]: p for p in policies}
    raw_claims: list[dict[str, Any]] = []
    adjuster_notes: list[dict[str, Any]] = []

    # Identify a high-risk customer for fraud clustering (~4 claims in a short window)
    cluster_customer = next(c for c in customers if c["risk_score"] > 0.80)
    cluster_policies = [p for p in policies if p["customer_id"] == cluster_customer["customer_id"]]
    cluster_policy = cluster_policies[0] if cluster_policies else policies[0]

    for i in range(1, total_claims + 1):
        claim_id = f"CLM-{30000 + i}"

        # Fraud cluster injection: claims 10-13 belong to cluster customer in 10-day span
        if 10 <= i <= 13:
            policy = cluster_policy
            p_type = policy["policy_type"]
            incident_dt = ANCHOR_DATE - timedelta(days=20 + (i - 10) * 2)
            reported_dt = incident_dt + timedelta(days=1)
        else:
            policy = rng.choice(policies)
            p_type = policy["policy_type"]
            # Pick incident date within active period or slightly outside
            incident_offset = rng.randint(5, 300)
            incident_dt = ANCHOR_DATE - timedelta(days=incident_offset)

            # Normal reporting delay: 1 to 25 days
            reporting_delay = rng.randint(1, 20)
            reported_dt = incident_dt + timedelta(days=reporting_delay)

        # Baseline amount calculation
        sum_insured = policy["sum_insured"]
        claimed_amt = round(rng.uniform(0.05, 0.70) * sum_insured, 2)
        doc_count = rng.randint(1, 4)
        city = rng.choice(CITIES_BY_STATE)[0]
        desc = rng.choice(CLAIM_DESCRIPTIONS[p_type])

        # Status distribution
        status_raw = rng.choice(["SUBMITTED", "IN_REVIEW", "PENDING_DOCS", "APPROVED", "SETTLED"])

        # Create record
        claim_rec = {
            "claim_id": claim_id,
            "policy_id": policy["policy_id"],
            "claim_type": p_type,
            "incident_date": incident_dt.isoformat(),
            "reported_date": reported_dt.isoformat(),
            "claimed_amount": str(claimed_amt),
            "status": status_raw,
            "description": desc,
            "documents_count": doc_count,
            "city": city,
        }

        # Create corresponding adjuster note
        notes_entry = {
            "claim_id": claim_id,
            "notes": [
                {
                    "note_id": 1,
                    "author": f"Adjuster {rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                    "timestamp": f"{reported_dt.isoformat()}T14:30:00Z",
                    "severity_tag": "SUSPICIOUS"
                    if (10 <= i <= 13 or rng.random() < 0.05)
                    else "NORMAL",
                    "text": f"Intake record logged for {p_type} incident in {city}. Documents attached: {doc_count}.",
                }
            ],
        }
        adjuster_notes.append(notes_entry)
        raw_claims.append(claim_rec)

    # -------------------------------------------------------------
    # Inject Specified Dirty Data Proportions
    # -------------------------------------------------------------
    # 1. Duplicate claim rows (~3% = ~18 rows)
    num_dups = int(total_claims * 0.03)
    dup_indices = rng.sample(range(len(raw_claims)), num_dups)
    for idx in dup_indices:
        dup_row = dict(raw_claims[idx])
        # Insert duplicate directly into raw claims
        raw_claims.append(dup_row)

    # 2. Null incident_date (~2% = ~12 rows)
    num_null_dates = int(total_claims * 0.02)
    null_date_indices = rng.sample(range(total_claims), num_null_dates)
    for idx in null_date_indices:
        raw_claims[idx]["incident_date"] = ""

    # 3. Negative or zero claimed_amount (~1% = ~6 rows)
    num_invalid_amounts = int(total_claims * 0.01)
    invalid_amount_indices = rng.sample(range(total_claims), num_invalid_amounts)
    for idx in invalid_amount_indices:
        raw_claims[idx]["claimed_amount"] = str(rng.choice([-500.0, 0.0, -1250.75]))

    # 4. Orphan policy_id (~2% = ~12 rows)
    num_orphans = int(total_claims * 0.02)
    orphan_indices = rng.sample(range(total_claims), num_orphans)
    for idx in orphan_indices:
        raw_claims[idx]["policy_id"] = f"POL-999{rng.randint(10, 99)}"

    # 5. Inconsistent casing and whitespace (~10% of rows)
    casing_indices = rng.sample(range(total_claims), int(total_claims * 0.10))
    for idx in casing_indices:
        orig_status = raw_claims[idx]["status"]
        cased = rng.choice(
            [
                f" {orig_status.lower()} ",
                orig_status.capitalize(),
                f"  {orig_status}  ",
                orig_status.lower(),
            ]
        )
        raw_claims[idx]["status"] = cased

    # 6. Future incident_date (~1% = ~6 rows)
    num_future = int(total_claims * 0.01)
    future_indices = rng.sample(range(total_claims), num_future)
    for idx in future_indices:
        future_dt = ANCHOR_DATE + timedelta(days=rng.randint(15, 60))
        raw_claims[idx]["incident_date"] = future_dt.isoformat()

    # 7. Some claims exceeding sum_insured (~1% = ~6 rows)
    exceed_indices = rng.sample(range(total_claims), int(total_claims * 0.01))
    for idx in exceed_indices:
        pol_id = raw_claims[idx]["policy_id"]
        if pol_id in policy_map:
            pol_sum = policy_map[pol_id]["sum_insured"]
            raw_claims[idx]["claimed_amount"] = str(round(pol_sum + rng.uniform(2000, 15000), 2))

    # 8. Some claims outside policy active period (~2% = ~12 rows)
    inactive_indices = rng.sample(range(total_claims), int(total_claims * 0.02))
    for idx in inactive_indices:
        pol_id = raw_claims[idx]["policy_id"]
        if pol_id in policy_map:
            pol_start = date.fromisoformat(policy_map[pol_id]["start_date"])
            # Set incident 60 days before policy started
            raw_claims[idx]["incident_date"] = (pol_start - timedelta(days=60)).isoformat()

    # Generate incremental updates batch (for Delta MERGE verification in Stage 2)
    # Pick ~40 existing claims from early records and advance their statuses
    claims_updates = []
    for c in raw_claims[:40]:
        if c["claim_id"].startswith("CLM-"):
            new_status = (
                "APPROVED"
                if c["status"].strip().upper() in ["SUBMITTED", "IN_REVIEW"]
                else "SETTLED"
            )
            claims_updates.append(
                {
                    "claim_id": c["claim_id"],
                    "policy_id": c["policy_id"],
                    "claim_type": c["claim_type"],
                    "incident_date": c["incident_date"],
                    "reported_date": c["reported_date"],
                    "claimed_amount": c["claimed_amount"],
                    "status": new_status,
                    "description": c["description"],
                    "documents_count": c["documents_count"],
                    "city": c["city"],
                }
            )

    return raw_claims, claims_updates, adjuster_notes


def save_csv(data: list[dict[str, Any]], filepath: Path) -> None:
    """Writes list of dicts to CSV file."""
    if not data:
        return
    import csv

    fieldnames = list(data[0].keys())
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


def run_generator(output_dir: Path, seed: int = DEFAULT_SEED) -> dict[str, int]:
    """Generates all synthetic artifacts deterministically and writes to disk."""
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating ClaimSense synthetic dataset (Seed: {seed}, Output: {output_dir})...")

    # 1. Customers
    customers = generate_customers(num_customers=100, rng=rng)
    save_csv(customers, output_dir / "customers.csv")
    print(f" -> Created customers.csv ({len(customers)} rows)")

    # 2. Policies
    policies = generate_policies(customers, num_policies=150, rng=rng)
    save_csv(policies, output_dir / "policies.csv")
    print(f" -> Created policies.csv ({len(policies)} rows)")

    # 3. Claims & Notes
    raw_claims, claims_updates, adjuster_notes = generate_claims_and_notes(
        policies, customers, total_claims=600, rng=rng
    )

    # Split raw claims into 3 batches
    batch_size = len(raw_claims) // 3
    batch_1 = raw_claims[:batch_size]
    batch_2 = raw_claims[batch_size : 2 * batch_size]
    batch_3 = raw_claims[2 * batch_size :]

    save_csv(batch_1, output_dir / "claims_batch_1.csv")
    save_csv(batch_2, output_dir / "claims_batch_2.csv")
    save_csv(batch_3, output_dir / "claims_batch_3.csv")
    print(f" -> Created claims_batch_1.csv ({len(batch_1)} rows)")
    print(f" -> Created claims_batch_2.csv ({len(batch_2)} rows)")
    print(f" -> Created claims_batch_3.csv ({len(batch_3)} rows)")

    # Incremental updates
    save_csv(claims_updates, output_dir / "claims_updates.csv")
    print(f" -> Created claims_updates.csv ({len(claims_updates)} rows)")

    # Adjuster Notes (JSON)
    notes_path = output_dir / "adjuster_notes.json"
    with open(notes_path, "w", encoding="utf-8") as f:
        json.dump(adjuster_notes, f, indent=2)
    print(f" -> Created adjuster_notes.json ({len(adjuster_notes)} claims)")

    counts = {
        "customers": len(customers),
        "policies": len(policies),
        "claims_batch_1": len(batch_1),
        "claims_batch_2": len(batch_2),
        "claims_batch_3": len(batch_3),
        "claims_updates": len(claims_updates),
        "adjuster_notes": len(adjuster_notes),
        "total_raw_claims": len(raw_claims),
    }
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ClaimSense synthetic insurance data.")
    parser.add_argument(
        "--output-dir", type=Path, default=Path(__file__).parent, help="Target output folder"
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Random generator seed")
    args = parser.parse_args()

    results = run_generator(output_dir=args.output_dir, seed=args.seed)
    print("\nGeneration summary:")
    for k, v in results.items():
        print(f"  {k:20s}: {v}")
