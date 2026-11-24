"""Tool allow-list for ClaimSense LangGraph agent.

Hard rule: LLM never writes or executes arbitrary SQL. All data access goes through
these 4 fixed, parameterised functions with typed, validated arguments.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from claimsense.db.client_factory import get_db_client


def _validate_claim_id(claim_id: str) -> str:
    """Input validation on claim_id with allow-list pattern."""
    cleaned = claim_id.strip().upper()
    if not re.match(r"^CLM-\d{5}$", cleaned):
        raise ValueError(f"Invalid claim_id format: '{claim_id}'. Expected 'CLM-xxxxx'.")
    return cleaned


def _validate_customer_id(customer_id: str) -> str:
    """Input validation on customer_id with allow-list pattern."""
    cleaned = customer_id.strip().upper()
    if not re.match(r"^CUST-\d{5}$", cleaned):
        raise ValueError(f"Invalid customer_id format: '{customer_id}'. Expected 'CUST-xxxxx'.")
    return cleaned


def get_claim(claim_id: str) -> Dict[str, Any]:
    """Tool 1: Fetches complete claim, policy, and customer record from Gold/Silver tables."""
    cid = _validate_claim_id(claim_id)
    db = get_db_client()
    query = """
        SELECT
            f.claim_id, f.incident_date, f.reported_date, f.reporting_delay_days,
            f.claimed_amount, f.claim_status, f.documents_count, f.description, f.city,
            f.flag_high_risk_customer,
            p.policy_id, p.policy_type, p.start_date, p.end_date, p.sum_insured,
            p.deductible, p.policy_status,
            u.customer_id, u.full_name, u.email, u.risk_score
        FROM fact_claims f
        JOIN dim_policy p ON f.policy_sk = p.policy_sk
        JOIN dim_customer u ON f.customer_sk = u.customer_sk
        WHERE f.claim_id = ?
    """
    rows = db.execute_query(query, (cid,))
    if not rows:
        raise ValueError(f"Claim '{cid}' does not exist.")
    return dict(rows[0])


def validate_claim(claim_id: str) -> List[Dict[str, Any]]:
    """Tool 2: Executes deterministic policy and coverage rules against the claim record."""
    rec = get_claim(claim_id)
    rules: List[Dict[str, Any]] = []

    # 1. Policy Active on Incident Date
    inc_date = rec["incident_date"]
    p_start = rec["start_date"]
    p_end = rec["end_date"]
    active = (p_start <= inc_date <= p_end) and (rec["policy_status"] == "ACTIVE")
    rules.append({
        "rule_id": "RULE-01-ACTIVE-PERIOD",
        "description": "Policy was active and within coverage dates during incident",
        "passed": active,
        "severity": "CRITICAL",
        "details": f"Incident: {inc_date} | Term: {p_start} to {p_end} (Status: {rec['policy_status']})",
    })

    # 2. Within Sum Insured
    amt = float(rec["claimed_amount"])
    sum_ins = float(rec["sum_insured"])
    within_limit = amt <= sum_ins
    rules.append({
        "rule_id": "RULE-02-SUM-INSURED",
        "description": "Claimed amount does not exceed policy declared sum insured",
        "passed": within_limit,
        "severity": "HIGH",
        "details": f"Claimed: ${amt:,.2f} | Limit: ${sum_ins:,.2f}",
    })

    # 3. Minimum Documents
    docs = int(rec.get("documents_count", 0))
    min_docs = 2
    rules.append({
        "rule_id": "RULE-03-MANDATORY-DOCS",
        "description": "Minimum supporting documentation supplied",
        "passed": docs >= min_docs,
        "severity": "MEDIUM",
        "details": f"Attached documents: {docs} (Required: >= {min_docs})",
    })

    # 4. Reporting Window
    delay = int(rec.get("reporting_delay_days", 0))
    rules.append({
        "rule_id": "RULE-04-TIMELY-REPORTING",
        "description": "Incident reported within allowable notification window (14 days)",
        "passed": delay <= 14,
        "severity": "MEDIUM",
        "details": f"Reporting delay: {delay} calendar days",
    })

    # 5. Customer Fraud Risk
    risk = float(rec.get("risk_score", 0.20))
    rules.append({
        "rule_id": "RULE-05-FRAUD-RISK",
        "description": "Customer behavioral risk score is within acceptable limits",
        "passed": risk < 0.60,
        "severity": "HIGH",
        "details": f"Risk score: {risk:.2f} (Threshold: 0.60)",
    })

    return rules


def search_policy_clauses(query: str, policy_type: str) -> List[Dict[str, str]]:
    """Tool 3: Retrieves top matching policy clauses from policy documents."""
    from claimsense.agent.retriever import get_policy_retriever
    retriever = get_policy_retriever()
    return retriever.retrieve(query=query, policy_type=policy_type, top_k=4)


def get_customer_claim_history(customer_id: str) -> List[Dict[str, Any]]:
    """Tool 4: Fetches past claims submitted by the same customer (detects rapid filing clusters)."""
    cust_id = _validate_customer_id(customer_id)
    db = get_db_client()
    query = """
        SELECT
            f.claim_id, f.incident_date, f.reported_date, f.claimed_amount,
            f.claim_status, t.claim_type
        FROM fact_claims f
        JOIN dim_customer u ON f.customer_sk = u.customer_sk
        JOIN dim_claim_type t ON f.claim_type_sk = t.claim_type_sk
        WHERE u.customer_id = ?
        ORDER BY f.incident_date DESC
    """
    rows = db.execute_query(query, (cust_id,))
    return [dict(r) for r in rows]
