"""Audit Trail Storage for Agent Triage Decisions and Traces."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from claimsense.config import get_settings


class TriageAuditStore:
    """Persists every triage assessment, citation, and human review trace for compliance."""

    def __init__(self, db_path: Optional[Path] = None):
        settings = get_settings()
        self.db_path = db_path or (settings.SNAPSHOTS_PATH / "claimsense_local.db")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS triage_audit (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id TEXT,
                decision TEXT,
                confidence REAL,
                reasons TEXT,
                cited_clauses TEXT,
                needs_human INTEGER,
                full_trace TEXT,
                created_at TEXT
            )
            """)
            conn.commit()

    def record_decision(
        self,
        claim_id: str,
        decision: str,
        confidence: float,
        reasons: List[str],
        cited_clauses: List[str],
        needs_human: bool,
        trace: List[Dict[str, Any]],
    ) -> int:
        now_ts = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO triage_audit (
                    claim_id, decision, confidence, reasons, cited_clauses,
                    needs_human, full_trace, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                claim_id,
                decision,
                confidence,
                json.dumps(reasons),
                json.dumps(cited_clauses),
                1 if needs_human else 0,
                json.dumps(trace),
                now_ts,
            ))
            conn.commit()
            return cur.lastrowid or 1

    def list_audit_records(self, limit: int = 50, decision: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM triage_audit"
        params = []
        if decision:
            query += " WHERE decision = ?"
            params.append(decision.upper())
        query += " ORDER BY audit_id DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["reasons"] = json.loads(d["reasons"])
                d["cited_clauses"] = json.loads(d["cited_clauses"])
                d["full_trace"] = json.loads(d["full_trace"])
                results.append(d)
            return results


_audit_store_instance: Optional[TriageAuditStore] = None


def get_triage_audit_store() -> TriageAuditStore:
    global _audit_store_instance
    if _audit_store_instance is None:
        _audit_store_instance = TriageAuditStore()
    return _audit_store_instance
