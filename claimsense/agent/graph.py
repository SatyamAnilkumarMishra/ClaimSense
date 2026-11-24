"""LangGraph StateGraph Triage Agent Engine for ClaimSense.

Implements a deterministic rule engine, grounded policy clause evaluation,
closed-world triage decisions (FAST_TRACK, NEEDS_REVIEW, ESCALATE_SIU),
anti-hallucination guardrails, and human-in-the-loop checkpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, TypedDict
from claimsense.services.models import RuleCheckResult, TriageDecisionEnum


class TriageAgentState(TypedDict):
    claim_id: str
    claim_record: Optional[Dict[str, Any]]
    validation_results: List[Dict[str, Any]]
    retrieved_clauses: List[Dict[str, str]]
    assessment: Optional[Dict[str, Any]]
    confidence: float
    decision: str
    needs_human: bool
    human_feedback: Optional[Dict[str, Any]]
    trace: List[Dict[str, Any]]


class ClaimTriageGraph:
    """LangGraph StateGraph controller for insurance claim triage."""

    def __init__(self):
        # We maintain an in-memory checkpointer for active and pending human reviews
        self._checkpoints: Dict[str, TriageAgentState] = {}

    def _sanitize_claim_id(self, claim_id: str) -> str:
        """Security: Input validation with allow-list pattern."""
        cleaned = claim_id.strip().upper()
        if not re.match(r"^CLM-\d{5}$", cleaned):
            raise ValueError(f"Invalid claim_id format: '{claim_id}'. Expected format 'CLM-xxxxx'.")
        return cleaned

    def run_intake(self, state: TriageAgentState) -> TriageAgentState:
        """Node 1: Validates claim_id and initializes trace."""
        claim_id = self._sanitize_claim_id(state["claim_id"])
        trace = list(state.get("trace", []))
        trace.append({
            "step": "intake",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "VALIDATED",
            "claim_id": claim_id,
        })
        return {**state, "claim_id": claim_id, "trace": trace}

    def run_fetch_data(self, state: TriageAgentState, db_client: Any) -> TriageAgentState:
        """Node 2: Fetches claim, policy, and customer record from Lakehouse."""
        claim_id = state["claim_id"]
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
        rows = db_client.execute_query(query, (claim_id,))
        if not rows:
            raise ValueError(f"Claim '{claim_id}' not found in Lakehouse.")

        record = rows[0]
        trace = list(state["trace"])
        trace.append({
            "step": "fetch_data",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "SUCCESS",
            "fields_loaded": list(record.keys()),
        })
        return {**state, "claim_record": record, "trace": trace}

    def run_validate_rules(self, state: TriageAgentState) -> TriageAgentState:
        """Node 3: Deterministic Rule Engine checks."""
        rec = state["claim_record"]
        rules = []

        # Rule 1: Policy Active on Incident Date
        inc_date = rec["incident_date"]
        p_start = rec["start_date"]
        p_end = rec["end_date"]
        active_during_incident = (p_start <= inc_date <= p_end) and (rec["policy_status"] == "ACTIVE")
        rules.append({
            "rule_id": "RULE-01-ACTIVE-PERIOD",
            "description": "Policy was active and within coverage dates during incident",
            "passed": active_during_incident,
            "severity": "CRITICAL",
            "details": f"Incident: {inc_date} | Coverage: {p_start} to {p_end} (Status: {rec['policy_status']})"
        })

        # Rule 2: Amount within Sum Insured
        claimed_amt = float(rec["claimed_amount"])
        sum_insured = float(rec["sum_insured"])
        within_limit = claimed_amt <= sum_insured
        rules.append({
            "rule_id": "RULE-02-SUM-INSURED",
            "description": "Claimed amount does not exceed policy declared sum insured",
            "passed": within_limit,
            "severity": "HIGH",
            "details": f"Claimed: ${claimed_amt:,.2f} | Max Limit: ${sum_insured:,.2f}"
        })

        # Rule 3: Required Minimum Documentation Present
        docs_count = int(rec.get("documents_count", 0))
        min_docs_req = 2
        docs_sufficient = docs_count >= min_docs_req
        rules.append({
            "rule_id": "RULE-03-MANDATORY-DOCS",
            "description": "Minimum supporting documentation supplied",
            "passed": docs_sufficient,
            "severity": "MEDIUM",
            "details": f"Attached documents: {docs_count} (Required: at least {min_docs_req})"
        })

        # Rule 4: Timely Notification Window (Within 14 days)
        delay = int(rec.get("reporting_delay_days", 0))
        timely_notification = delay <= 14
        rules.append({
            "rule_id": "RULE-04-TIMELY-REPORTING",
            "description": "Incident reported within allowable notification window (14 days)",
            "passed": timely_notification,
            "severity": "MEDIUM",
            "details": f"Reporting delay: {delay} calendar days"
        })

        # Rule 5: Low Customer Fraud Risk Score
        risk_score = float(rec.get("risk_score", 0.20))
        low_risk = risk_score < 0.60
        rules.append({
            "rule_id": "RULE-05-FRAUD-RISK",
            "description": "Customer behavioral risk score is within acceptable limits",
            "passed": low_risk,
            "severity": "HIGH",
            "details": f"Customer risk score: {risk_score:.2f} (Threshold: 0.60)"
        })

        trace = list(state["trace"])
        trace.append({
            "step": "validate_rules",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rules_evaluated": len(rules),
            "passed_count": sum(1 for r in rules if r["passed"]),
        })
        return {**state, "validation_results": rules, "trace": trace}

    def run_retrieve_clauses(self, state: TriageAgentState) -> TriageAgentState:
        """Node 4: Retrieves matching policy clauses based on policy type and claim details."""
        rec = state["claim_record"]
        p_type = rec["policy_type"].upper()

        # Grounded policy clause store
        clauses_pool = {
            "AUTO": [
                {"clause_id": "AUTO-COV-01", "text": "Covers direct physical collision damage up to Sum Insured less deductible."},
                {"clause_id": "AUTO-TIME-01", "text": "All claims must be reported within 14 calendar days from the date of the incident."},
                {"clause_id": "AUTO-DOC-01", "text": "Requires official police report and certified repair estimate."},
            ],
            "HEALTH": [
                {"clause_id": "HLTH-COV-01", "text": "Covers inpatient hospitalization exceeding a minimum of 24 continuous hours."},
                {"clause_id": "HLTH-LIM-01", "text": "Total cumulative reimbursements cannot exceed the declared Sum Insured."},
                {"clause_id": "HLTH-DOC-01", "text": "Requires hospital discharge summary and detailed itemized bills."},
            ],
            "HOME": [
                {"clause_id": "HOME-COV-01", "text": "Covers physical structural loss from fire, storm, or impact damage."},
                {"clause_id": "HOME-TIME-01", "text": "Property damages must be reported within 7 calendar days from occurrence."},
                {"clause_id": "HOME-DOC-01", "text": "Requires local fire or police report and certified contractor estimate."},
            ],
        }

        retrieved = clauses_pool.get(p_type, clauses_pool["AUTO"])
        trace = list(state["trace"])
        trace.append({
            "step": "retrieve_clauses",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "clauses_count": len(retrieved),
            "clause_ids": [c["clause_id"] for c in retrieved],
        })
        return {**state, "retrieved_clauses": retrieved, "trace": trace}

    def run_assess(self, state: TriageAgentState) -> TriageAgentState:
        """Node 5: Computes assessment recommendation using grounded rule facts."""
        rules = state["validation_results"]
        rec = state["claim_record"]
        clauses = state["retrieved_clauses"]

        failed_rules = [r for r in rules if not r["passed"]]
        failed_severities = {r["severity"] for r in failed_rules}

        reasons = []
        cited_ids = []

        # Anti-hallucination decision mapping
        if "CRITICAL" in failed_severities or "HIGH" in failed_severities:
            if any(r["rule_id"] == "RULE-05-FRAUD-RISK" for r in failed_rules):
                decision = TriageDecisionEnum.ESCALATE_SIU.value
                reasons.append("Elevated behavioral fraud risk detected on customer profile.")
            else:
                decision = TriageDecisionEnum.NEEDS_REVIEW.value
                reasons.append("Policy condition or coverage limit violation detected.")
            confidence = 0.95
            needs_human = True
        elif failed_rules:
            decision = TriageDecisionEnum.NEEDS_REVIEW.value
            reasons.append("Minor validation exceptions (e.g. reporting delay or missing documentation).")
            confidence = 0.88
            needs_human = True
        else:
            decision = TriageDecisionEnum.FAST_TRACK.value
            reasons.append("All deterministic policy checks passed. Eligible for automated straight-through processing.")
            confidence = 0.96
            needs_human = False

        # Add citations grounded in retrieved clauses
        for c in clauses:
            cited_ids.append(c["clause_id"])

        trace = list(state["trace"])
        trace.append({
            "step": "assess",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "confidence": confidence,
            "needs_human": needs_human,
        })

        return {
            **state,
            "decision": decision,
            "confidence": confidence,
            "needs_human": needs_human,
            "assessment": {
                "decision": decision,
                "confidence": confidence,
                "reasons": reasons,
                "cited_clause_ids": cited_ids,
            },
            "trace": trace,
        }

    def execute_triage(self, claim_id: str, db_client: Any) -> TriageAgentState:
        """Runs the complete StateGraph flow for a claim."""
        initial_state: TriageAgentState = {
            "claim_id": claim_id,
            "claim_record": None,
            "validation_results": [],
            "retrieved_clauses": [],
            "assessment": None,
            "confidence": 0.0,
            "decision": "NEEDS_REVIEW",
            "needs_human": True,
            "human_feedback": None,
            "trace": [],
        }

        s1 = self.run_intake(initial_state)
        s2 = self.run_fetch_data(s1, db_client)
        s3 = self.run_validate_rules(s2)
        s4 = self.run_retrieve_clauses(s3)
        final_state = self.run_assess(s4)

        # Save to checkpointer for human-in-the-loop review
        self._checkpoints[claim_id] = final_state
        return final_state

    def resume_review(
        self,
        claim_id: str,
        action: str,
        reviewer_notes: str,
        override_decision: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resumes the graph after human review interrupt."""
        claim_id = self._sanitize_claim_id(claim_id)
        if claim_id not in self._checkpoints:
            # Reconstruct or create placeholder state
            self._checkpoints[claim_id] = {
                "claim_id": claim_id,
                "decision": "NEEDS_REVIEW",
                "trace": [],
            }  # type: ignore

        state = self._checkpoints[claim_id]
        final_dec = override_decision or state.get("decision", "NEEDS_REVIEW")
        if action == "REJECT":
            final_dec = "NEEDS_REVIEW"

        feedback = {
            "action": action,
            "reviewer_notes": reviewer_notes,
            "final_decision": final_dec,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        state["human_feedback"] = feedback
        state["decision"] = final_dec
        state["needs_human"] = False

        trace = list(state.get("trace", []))
        trace.append({
            "step": "human_review",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "reviewer_notes": reviewer_notes,
            "final_decision": final_dec,
        })
        state["trace"] = trace

        return {
            "claim_id": claim_id,
            "final_decision": final_dec,
            "reviewer_notes": reviewer_notes,
            "status": "FINALIZED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


_global_triage_graph = ClaimTriageGraph()


def get_triage_graph() -> ClaimTriageGraph:
    """Singleton getter for the Triage StateGraph."""
    return _global_triage_graph
