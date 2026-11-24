"""Local Medallion Lakehouse Pipeline Engine for ClaimSense.

Simulates the exact Databricks PySpark Medallion execution locally using SQLite:
1. Bronze: Appends raw batches with _ingest_timestamp and _source_file metadata.
2. Silver: Deduplicates, casts types, performs referential checks, routes to quarantine, and executes Delta MERGE upserts.
3. Gold: Builds Star Schema (dim_customer, dim_policy, dim_claim_type, dim_date, fact_claims) and KPI views.
4. Audit: Evaluates mathematical reconciliation and asserts:
   Bronze Count == Duplicates Quarantined + Defects Quarantined + Silver Count.
5. Snapshot Export: Saves offline Parquet/SQLite tables in snapshots/ for zero-cost operation.
"""

from __future__ import annotations

import csv
import sqlite3
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from claimsense.config import get_settings


class LocalMedallionPipeline:
    """Executes the Medallion pipeline locally, mirroring PySpark Delta operations."""

    def __init__(self, db_path: Path | None = None, data_dir: Path | None = None):
        settings = get_settings()
        self.data_dir = data_dir or settings.DATA_GEN_PATH
        self.snapshots_dir = settings.SNAPSHOTS_PATH
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or (self.snapshots_dir / "claimsense_local.db")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        """Creates DDL schemas matching the Lakehouse tables."""
        cur = self.conn.cursor()
        # Bronze Tables (Raw, Append-only)
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS bronze_customers (
            customer_id TEXT,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            phone TEXT,
            city TEXT,
            state TEXT,
            risk_score REAL,
            created_at TEXT,
            _ingest_timestamp TEXT,
            _source_file TEXT
        );

        CREATE TABLE IF NOT EXISTS bronze_policies (
            policy_id TEXT,
            customer_id TEXT,
            policy_type TEXT,
            start_date TEXT,
            end_date TEXT,
            sum_insured REAL,
            deductible REAL,
            status TEXT,
            _ingest_timestamp TEXT,
            _source_file TEXT
        );

        CREATE TABLE IF NOT EXISTS bronze_claims (
            claim_id TEXT,
            policy_id TEXT,
            claim_type TEXT,
            incident_date TEXT,
            reported_date TEXT,
            claimed_amount TEXT,
            status TEXT,
            description TEXT,
            documents_count INTEGER,
            city TEXT,
            _ingest_timestamp TEXT,
            _source_file TEXT
        );

        -- Silver Tables
        CREATE TABLE IF NOT EXISTS silver_customers (
            customer_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            phone TEXT,
            city TEXT,
            state TEXT,
            risk_score REAL,
            created_at TEXT,
            _silver_timestamp TEXT
        );

        CREATE TABLE IF NOT EXISTS silver_policies (
            policy_id TEXT PRIMARY KEY,
            customer_id TEXT,
            policy_type TEXT,
            start_date TEXT,
            end_date TEXT,
            sum_insured REAL,
            deductible REAL,
            status TEXT,
            _silver_timestamp TEXT
        );

        CREATE TABLE IF NOT EXISTS silver_claims (
            claim_id TEXT PRIMARY KEY,
            policy_id TEXT,
            claim_type TEXT,
            incident_date TEXT,
            reported_date TEXT,
            claimed_amount REAL,
            status TEXT,
            description TEXT,
            documents_count INTEGER,
            city TEXT,
            _source_file TEXT,
            _silver_timestamp TEXT
        );

        CREATE TABLE IF NOT EXISTS quarantine_claims (
            quarantine_id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id TEXT,
            policy_id TEXT,
            claim_type TEXT,
            raw_incident_date TEXT,
            raw_reported_date TEXT,
            raw_claimed_amount TEXT,
            raw_status TEXT,
            description TEXT,
            reject_reason TEXT,
            _source_file TEXT,
            run_id TEXT,
            quarantined_at TEXT
        );

        CREATE TABLE IF NOT EXISTS dq_results (
            rule_id TEXT,
            description TEXT,
            severity TEXT,
            failed_count INTEGER,
            run_id TEXT,
            checked_at TEXT
        );

        -- Gold Star Schema
        CREATE TABLE IF NOT EXISTS dim_customer (
            customer_sk TEXT PRIMARY KEY,
            customer_id TEXT,
            first_name TEXT,
            last_name TEXT,
            full_name TEXT,
            email TEXT,
            phone TEXT,
            city TEXT,
            state TEXT,
            risk_score REAL,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS dim_policy (
            policy_sk TEXT PRIMARY KEY,
            policy_id TEXT,
            customer_id TEXT,
            customer_sk TEXT,
            policy_type TEXT,
            start_date TEXT,
            end_date TEXT,
            sum_insured REAL,
            deductible REAL,
            policy_status TEXT
        );

        CREATE TABLE IF NOT EXISTS dim_claim_type (
            claim_type_sk TEXT PRIMARY KEY,
            claim_type TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS dim_date (
            date_key INTEGER PRIMARY KEY,
            full_date TEXT,
            year INTEGER,
            quarter INTEGER,
            month INTEGER,
            month_name TEXT,
            day_of_month INTEGER,
            day_of_week INTEGER,
            day_name TEXT,
            is_weekend INTEGER
        );

        CREATE TABLE IF NOT EXISTS fact_claims (
            claim_sk TEXT PRIMARY KEY,
            claim_id TEXT,
            policy_sk TEXT,
            customer_sk TEXT,
            claim_type_sk TEXT,
            incident_date_key INTEGER,
            reported_date_key INTEGER,
            incident_date TEXT,
            reported_date TEXT,
            reporting_delay_days INTEGER,
            claimed_amount REAL,
            claim_status TEXT,
            documents_count INTEGER,
            description TEXT,
            city TEXT,
            is_settled INTEGER,
            flag_high_risk_customer INTEGER,
            _gold_timestamp TEXT
        );

        -- Pipeline Audit / Reconciliation
        CREATE TABLE IF NOT EXISTS pipeline_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            run_timestamp TEXT,
            bronze_count INTEGER,
            duplicates_count INTEGER,
            defects_count INTEGER,
            quarantined_total INTEGER,
            silver_count INTEGER,
            gold_fact_count INTEGER,
            discrepancy_count INTEGER,
            reconciliation_status TEXT,
            audit_notes TEXT
        );
        """)
        self.conn.commit()

    def run_bronze(self, batches: list[str] | None = None) -> dict[str, int]:
        """Ingests raw CSV batches into Bronze tables with metadata."""
        if batches is None:
            batches = ["claims_batch_1.csv", "claims_batch_2.csv", "claims_batch_3.csv"]
        cur = self.conn.cursor()
        now_ts = datetime.now(UTC).isoformat()

        # Ingest Customers
        cust_path = self.data_dir / "customers.csv"
        if cust_path.exists():
            with open(cust_path, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                for r in rows:
                    cur.execute(
                        """
                        INSERT INTO bronze_customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            r["customer_id"],
                            r["first_name"],
                            r["last_name"],
                            r["email"],
                            r["phone"],
                            r["city"],
                            r["state"],
                            float(r["risk_score"]),
                            r["created_at"],
                            now_ts,
                            "customers.csv",
                        ),
                    )

        # Ingest Policies
        pol_path = self.data_dir / "policies.csv"
        if pol_path.exists():
            with open(pol_path, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                for r in rows:
                    cur.execute(
                        """
                        INSERT INTO bronze_policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            r["policy_id"],
                            r["customer_id"],
                            r["policy_type"],
                            r["start_date"],
                            r["end_date"],
                            float(r["sum_insured"]),
                            float(r["deductible"]),
                            r["status"],
                            now_ts,
                            "policies.csv",
                        ),
                    )

        # Ingest Claims Batches
        claims_ingested = 0
        for batch_name in batches:
            p = self.data_dir / batch_name
            if p.exists():
                with open(p, encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
                    claims_ingested += len(rows)
                    for r in rows:
                        cur.execute(
                            """
                            INSERT INTO bronze_claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                r["claim_id"],
                                r["policy_id"],
                                r["claim_type"],
                                r["incident_date"],
                                r["reported_date"],
                                r["claimed_amount"],
                                r["status"],
                                r["description"],
                                int(r.get("documents_count", 0)),
                                r["city"],
                                now_ts,
                                batch_name,
                            ),
                        )

        self.conn.commit()
        return {"claims_ingested": claims_ingested}

    def run_silver(self, run_id: str | None = None) -> dict[str, int]:
        """Performs deduplication, quarantine routing, and Delta MERGE into Silver."""
        run_id = run_id or f"RUN-{uuid.uuid4().hex[:8].upper()}"
        cur = self.conn.cursor()
        now_ts = datetime.now(UTC).isoformat()
        today_str = date.today().isoformat()

        # 1. Populate Silver Customers (Dedup by latest ingest)
        cur.execute(
            """
            INSERT OR REPLACE INTO silver_customers
            SELECT customer_id, TRIM(first_name), TRIM(last_name), TRIM(email), phone,
                   TRIM(city), TRIM(state), risk_score, created_at, ?
            FROM bronze_customers
        """,
            (now_ts,),
        )

        # 2. Populate Silver Policies (Dedup by latest ingest)
        cur.execute(
            """
            INSERT OR REPLACE INTO silver_policies
            SELECT policy_id, customer_id, UPPER(TRIM(policy_type)), start_date, end_date,
                   sum_insured, deductible, UPPER(TRIM(status)), ?
            FROM bronze_policies
        """,
            (now_ts,),
        )

        # 3. Fetch valid policy IDs
        cur.execute("SELECT policy_id FROM silver_policies")
        valid_policies = {r[0] for r in cur.fetchall()}

        # 4. Fetch all Bronze claims
        cur.execute(
            "SELECT * FROM bronze_claims ORDER BY reported_date DESC, _ingest_timestamp DESC"
        )
        bronze_rows = [dict(r) for r in cur.fetchall()]

        seen_claim_ids = set()
        duplicates_count = 0
        defects_count = 0
        merged_count = 0

        rule_counts = {
            "ERR_DUP_CLAIM": 0,
            "ERR_NULL_INCIDENT_DATE": 0,
            "ERR_INVALID_AMOUNT": 0,
            "ERR_ORPHAN_POLICY": 0,
            "ERR_FUTURE_INCIDENT_DATE": 0,
        }

        for row in bronze_rows:
            cid = row["claim_id"]
            reject_reason = None

            # Rule 1: Duplicate check
            if cid in seen_claim_ids:
                reject_reason = "ERR_DUP_CLAIM"
                duplicates_count += 1
            else:
                seen_claim_ids.add(cid)

                # Rule 2: Null or empty incident date
                inc_date_raw = (row["incident_date"] or "").strip()
                if not inc_date_raw:
                    reject_reason = "ERR_NULL_INCIDENT_DATE"
                    defects_count += 1

                # Rule 3: Invalid amount
                else:
                    try:
                        amt = float(row["claimed_amount"])
                        if amt <= 0:
                            reject_reason = "ERR_INVALID_AMOUNT"
                            defects_count += 1
                    except (ValueError, TypeError):
                        reject_reason = "ERR_INVALID_AMOUNT"
                        defects_count += 1

                # Rule 4: Orphan policy
                if not reject_reason and row["policy_id"] not in valid_policies:
                    reject_reason = "ERR_ORPHAN_POLICY"
                    defects_count += 1

                # Rule 5: Future incident date
                if not reject_reason and inc_date_raw > today_str:
                    reject_reason = "ERR_FUTURE_INCIDENT_DATE"
                    defects_count += 1

            if reject_reason:
                rule_counts[reject_reason] += 1
                cur.execute(
                    """
                    INSERT INTO quarantine_claims (
                        claim_id, policy_id, claim_type, raw_incident_date, raw_reported_date,
                        raw_claimed_amount, raw_status, description, reject_reason, _source_file,
                        run_id, quarantined_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        row["claim_id"],
                        row["policy_id"],
                        row["claim_type"],
                        row["incident_date"],
                        row["reported_date"],
                        row["claimed_amount"],
                        row["status"],
                        row["description"],
                        reject_reason,
                        row["_source_file"],
                        run_id,
                        now_ts,
                    ),
                )
            else:
                # Valid -> Perform Delta MERGE (Upsert)
                clean_status = (row["status"] or "SUBMITTED").strip().upper()
                clean_amount = float(row["claimed_amount"])
                cur.execute(
                    """
                    INSERT INTO silver_claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(claim_id) DO UPDATE SET
                        status = excluded.status,
                        claimed_amount = excluded.claimed_amount,
                        _silver_timestamp = excluded._silver_timestamp
                """,
                    (
                        row["claim_id"],
                        row["policy_id"],
                        row["claim_type"].strip().upper(),
                        inc_date_raw,
                        row["reported_date"],
                        clean_amount,
                        clean_status,
                        (row["description"] or "").strip(),
                        int(row.get("documents_count") or 0),
                        (row["city"] or "").strip(),
                        row["_source_file"],
                        now_ts,
                    ),
                )
                merged_count += 1

        # Record Data Quality Results
        for rule_id, count in rule_counts.items():
            if count > 0:
                cur.execute(
                    """
                    INSERT INTO dq_results VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (rule_id, f"Rule violation count for {rule_id}", "HIGH", count, run_id, now_ts),
                )

        self.conn.commit()
        return {
            "run_id": run_id,
            "duplicates_quarantined": duplicates_count,
            "defects_quarantined": defects_count,
            "silver_valid": merged_count,
        }

    def run_gold(self) -> dict[str, int]:
        """Builds Gold Star Schema (dimensions, fact, and views)."""
        cur = self.conn.cursor()
        now_ts = datetime.now(UTC).isoformat()

        # 1. dim_customer
        cur.execute("""
            INSERT OR REPLACE INTO dim_customer
            SELECT
                'SK-CUST-' || customer_id, customer_id, first_name, last_name,
                first_name || ' ' || last_name, email, phone, city, state, risk_score, created_at
            FROM silver_customers
        """)

        # 2. dim_policy
        cur.execute("""
            INSERT OR REPLACE INTO dim_policy
            SELECT
                'SK-POL-' || policy_id, policy_id, customer_id, 'SK-CUST-' || customer_id,
                policy_type, start_date, end_date, sum_insured, deductible, status
            FROM silver_policies
        """)

        # 3. dim_claim_type
        cur.execute("""
            INSERT OR REPLACE INTO dim_claim_type
            SELECT DISTINCT
                'SK-TYPE-' || claim_type, claim_type
            FROM silver_claims
        """)

        # 4. dim_date (Generate dates for 2024 to 2027)
        cur.execute("SELECT COUNT(*) FROM dim_date")
        if cur.fetchone()[0] == 0:
            start_dt = date(2024, 1, 1)
            end_dt = date(2027, 12, 31)
            curr = start_dt
            date_records = []
            while curr <= end_dt:
                date_key = int(curr.strftime("%Y%m%d"))
                full_dt = curr.isoformat()
                is_wknd = 1 if curr.weekday() in (5, 6) else 0
                date_records.append(
                    (
                        date_key,
                        full_dt,
                        curr.year,
                        (curr.month - 1) // 3 + 1,
                        curr.month,
                        curr.strftime("%B"),
                        curr.day,
                        curr.weekday() + 1,
                        curr.strftime("%A"),
                        is_wknd,
                    )
                )
                curr += timedelta(days=1)

            cur.executemany(
                "INSERT INTO dim_date VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", date_records
            )

        # 5. fact_claims
        cur.execute(
            """
            INSERT OR REPLACE INTO fact_claims
            SELECT
                'SK-CLM-' || c.claim_id,
                c.claim_id,
                p.policy_sk,
                u.customer_sk,
                t.claim_type_sk,
                CAST(strftime('%Y%m%d', c.incident_date) AS INTEGER),
                CAST(strftime('%Y%m%d', c.reported_date) AS INTEGER),
                c.incident_date,
                c.reported_date,
                CAST(julianday(c.reported_date) - julianday(c.incident_date) AS INTEGER),
                c.claimed_amount,
                c.status,
                c.documents_count,
                c.description,
                c.city,
                CASE WHEN c.status IN ('APPROVED', 'SETTLED') THEN 1 ELSE 0 END,
                CASE WHEN u.risk_score >= 0.70 THEN 1 ELSE 0 END,
                ?
            FROM silver_claims c
            JOIN dim_policy p ON c.policy_id = p.policy_id
            JOIN dim_customer u ON p.customer_id = u.customer_id
            JOIN dim_claim_type t ON c.claim_type = t.claim_type
        """,
            (now_ts,),
        )

        self.conn.commit()

        cur.execute("SELECT COUNT(*) FROM fact_claims")
        fact_count = cur.fetchone()[0]
        return {"fact_claims_count": fact_count}

    def run_reconciliation(self, run_id: str) -> dict[str, Any]:
        """Calculates and logs mathematical reconciliation metrics to pipeline_audit."""
        cur = self.conn.cursor()
        now_ts = datetime.now(UTC).isoformat()

        cur.execute("SELECT COUNT(*) FROM bronze_claims")
        bronze_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM quarantine_claims WHERE reject_reason = 'ERR_DUP_CLAIM'")
        dups_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM quarantine_claims WHERE reject_reason != 'ERR_DUP_CLAIM'")
        defects_count = cur.fetchone()[0]

        quarantine_total = dups_count + defects_count

        cur.execute("SELECT COUNT(*) FROM silver_claims")
        silver_count = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM fact_claims")
        gold_fact_count = cur.fetchone()[0]

        # Invariant check
        expected_bronze = dups_count + defects_count + silver_count
        discrepancy = abs(bronze_count - expected_bronze)

        if discrepancy == 0 and silver_count == gold_fact_count:
            status = "PASS"
            notes = "Full mathematical reconciliation achieved. Zero data leakage across Bronze, Silver, and Gold."
        else:
            status = "PASS_WITH_WARNING" if discrepancy == 0 else "FAIL"
            notes = f"Discrepancy count: {discrepancy}. Bronze ({bronze_count}) vs (Quarantine {quarantine_total} + Silver {silver_count} = {expected_bronze})."

        cur.execute(
            """
            INSERT INTO pipeline_audit (
                run_id, run_timestamp, bronze_count, duplicates_count, defects_count,
                quarantined_total, silver_count, gold_fact_count, discrepancy_count,
                reconciliation_status, audit_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                run_id,
                now_ts,
                bronze_count,
                dups_count,
                defects_count,
                quarantine_total,
                silver_count,
                gold_fact_count,
                discrepancy,
                status,
                notes,
            ),
        )
        self.conn.commit()

        return {
            "run_id": run_id,
            "bronze_count": bronze_count,
            "duplicates_count": dups_count,
            "defects_count": defects_count,
            "quarantined_total": quarantine_total,
            "silver_count": silver_count,
            "gold_fact_count": gold_fact_count,
            "discrepancy": discrepancy,
            "status": status,
            "notes": notes,
        }

    def apply_incremental_updates(self, updates_file: str = "claims_updates.csv") -> dict[str, int]:
        """Applies status updates batch via Delta MERGE simulation without creating duplicate rows."""
        cur = self.conn.cursor()
        p = self.data_dir / updates_file
        if not p.exists():
            return {"updated_rows": 0}

        cur.execute("SELECT COUNT(*) FROM silver_claims")
        initial_silver_count = cur.fetchone()[0]

        updated_count = 0
        now_ts = datetime.now(UTC).isoformat()
        with open(p, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                cur.execute(
                    """
                    UPDATE silver_claims
                    SET status = ?, _silver_timestamp = ?
                    WHERE claim_id = ?
                """,
                    (r["status"].strip().upper(), now_ts, r["claim_id"]),
                )
                if cur.rowcount > 0:
                    updated_count += 1

        self.conn.commit()

        # Re-sync Gold fact_claims
        cur.execute(
            """
            UPDATE fact_claims
            SET claim_status = (SELECT status FROM silver_claims WHERE silver_claims.claim_id = fact_claims.claim_id),
                is_settled = (CASE WHEN (SELECT status FROM silver_claims WHERE silver_claims.claim_id = fact_claims.claim_id) IN ('APPROVED', 'SETTLED') THEN 1 ELSE 0 END),
                _gold_timestamp = ?
            WHERE claim_id IN (SELECT claim_id FROM silver_claims)
        """,
            (now_ts,),
        )
        self.conn.commit()

        cur.execute("SELECT COUNT(*) FROM silver_claims")
        final_silver_count = cur.fetchone()[0]

        return {
            "updated_rows": updated_count,
            "initial_silver_count": initial_silver_count,
            "final_silver_count": final_silver_count,
            "delta_count": final_silver_count - initial_silver_count,
        }


def run_full_pipeline(clean: bool = True) -> dict[str, Any]:
    """Convenience runner for full pipeline test execution."""
    pipeline = LocalMedallionPipeline()
    if clean:
        # Clear tables
        for tbl in [
            "bronze_customers",
            "bronze_policies",
            "bronze_claims",
            "quarantine_claims",
            "silver_claims",
            "fact_claims",
        ]:
            pipeline.conn.execute(f"DELETE FROM {tbl}")
        pipeline.conn.commit()

    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    print(f"Executing Full Pipeline for Run ID: {run_id}...")

    # Stage 1: Bronze
    bronze_res = pipeline.run_bronze()
    print(f" [1/4] Bronze Ingestion completed: {bronze_res}")

    # Stage 2: Silver
    silver_res = pipeline.run_silver(run_id=run_id)
    print(f" [2/4] Silver Transformations & Quarantine completed: {silver_res}")

    # Stage 3: Gold
    gold_res = pipeline.run_gold()
    print(f" [3/4] Gold Star Schema completed: {gold_res}")

    # Stage 4: Reconciliation Audit
    audit_res = pipeline.run_reconciliation(run_id=run_id)
    print(f" [4/4] Reconciliation Audit: {audit_res['status']} | {audit_res['notes']}")

    return audit_res


if __name__ == "__main__":
    audit = run_full_pipeline(clean=True)
    print("\nReconciliation Summary:")
    for k, v in audit.items():
        print(f"  {k:22s}: {v}")
