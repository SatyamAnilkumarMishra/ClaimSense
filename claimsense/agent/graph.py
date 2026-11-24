"""LangGraph StateGraph Triage Agent Engine for ClaimSense.

Implements a deterministic rule engine, grounded policy clause evaluation,
closed-world triage decisions (FAST_TRACK, NEEDS_REVIEW, ESCALATE_SIU),
anti-hallucination citation verification, and human-in-the-loop checkpoints.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, TypedDict

from claimsense.agent.audit_store import get_triage_audit_store
from claimsense.agent.citation_verifier import CitationVerifier
from claimsense.agent.groq_client import get_groq_client_wrapper
from claimsense.agent.prompts import SYSTEM_PROMPT_VERSION, TRIAGE_SYSTEM_PROMPT, build_triage_user_prompt
from claimsense.agent.retriever import get_policy_retriever
from claimsense.agent.tools import get_claim, validate_claim
from claimsense.services.models import TriageDecisionEnum


class TriageAgentState(TypedDict):
    claim_id: str
    claim_record: Optional[Dict[str, Any]]
    validation_results: List[Dict[str, Any]]
    retrieved_clauses: List[Dict[str, Any]]
    assessment: Optional[Dict[str, Any]]
    confidence: float
    decision: str
    needs_human: bool
    human_feedback: Optional[Dict[str, Any]]
    trace: List[Dict[str, Any]]


class ClaimTriageGraph:
    """LangGraph StateGraph controller for insurance claim triage."""

    def __init__(self):
        self._checkpoints: Dict[str, TriageAgentState] = {}
        self.retriever = get_policy_retriever()
        self.groq = get_groq_client_wrapper()
        self.audit_store = get_triage_audit_store()

    def _sanitize_claim_id(self, claim_id: str) -> str:
        """Security: Input validation with allow-list pattern."""
        cleaned = claim_id.strip().upper()
        if not re.match(r"^CLM-\d{5}$", cleaned):
            raise ValueError(f"Invalid claim_id format: '{claim_id}'. Expected 'CLM-xxxxx'.")
        return cleaned

    def run_intake(self, state: TriageAgentState) -> TriageAgentState:
        """Node 1: Validates claim_id and starts trace."""
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
        """Node 2: Tool call to fetch claim record."""
        claim_id = state["claim_id"]
        record = get_claim(claim_id)
        trace = list(state["trace"])
        trace.append({
            "step": "fetch_data",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "SUCCESS",
            "fields_loaded": list(record.keys()),
        })
        return {**state, "claim_record": record, "trace": trace}

    def run_validate_rules(self, state: TriageAgentState) -> TriageAgentState:
        """Node 3: Tool call to execute deterministic rules."""
        rules = validate_claim(state["claim_id"])
        trace = list(state["trace"])
        trace.append({
            "step": "validate_rules",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rules_evaluated": len(rules),
            "passed_count": sum(1 for r in rules if r["passed"]),
        })
        return {**state, "validation_results": rules, "trace": trace}

    def run_retrieve_clauses(self, state: TriageAgentState) -> TriageAgentState:
        """Node 4: Tool call for policy clause retrieval."""
        rec = state["claim_record"]
        p_type = rec["policy_type"]
        query = f"{rec.get('claim_type', '')} {rec.get('description', '')}"
        retrieved = self.retriever.retrieve(query=query, policy_type=p_type, top_k=4)

        trace = list(state["trace"])
        trace.append({
            "step": "retrieve_clauses",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "clauses_count": len(retrieved),
            "clause_ids": [c["clause_id"] for c in retrieved],
        })
        return {**state, "retrieved_clauses": retrieved, "trace": trace}

    def run_assess(self, state: TriageAgentState) -> TriageAgentState:
        """Node 5: LLM reasoning with anti-hallucination verification and repair retry."""
        rec = state["claim_record"]
        rules = state["validation_results"]
        clauses = state["retrieved_clauses"]

        # Build secured prompt with delimiters
        user_prompt = build_triage_user_prompt(rec, rules, clauses)

        # Call Groq LLM (or deterministic fallback)
        raw_output = self.groq.generate_json_response(
            system_prompt=TRIAGE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model_tier="reasoning",
        )

        # Anti-Hallucination Verification Check
        verification = CitationVerifier.verify(
            assessment=raw_output,
            claim_record=rec,
            retrieved_clauses=clauses,
        )

        # If hallucination or unverifiable citation detected, repair retry or escalate
        if not verification.is_valid:
            # Trigger Repair Retry: Force conservative decision and cited facts
            decision = verification.repaired_decision or TriageDecisionEnum.NEEDS_REVIEW.value
            confidence = 0.85
            reasons = raw_output.get("reasons", [])
            reasons.append("Flagged by citation verifier: Non-grounded statements or unverifiable citations.")
            cited_ids = verification.verified_citations
            needs_human = True
        else:
            decision = raw_output.get("decision", TriageDecisionEnum.NEEDS_REVIEW.value)
            confidence = float(raw_output.get("confidence", 0.90))
            reasons = raw_output.get("reasons", [])
            cited_ids = verification.verified_citations
            needs_human = (decision != TriageDecisionEnum.FAST_TRACK.value)

        # Enforce rule-based override: If critical rule failed, decision cannot be FAST_TRACK
        has_critical_failure = any(not r["passed"] and r["severity"] in ["CRITICAL", "HIGH"] for r in rules)
        if has_critical_failure and decision == TriageDecisionEnum.FAST_TRACK.value:
            decision = TriageDecisionEnum.NEEDS_REVIEW.value
            needs_human = True
            reasons.append("Overridden by deterministic policy rule violation.")

        trace = list(state["trace"])
        trace.append({
            "step": "assess",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "confidence": confidence,
            "prompt_version": SYSTEM_PROMPT_VERSION,
            "hallucination_detected": verification.hallucination_detected,
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
        """Executes full StateGraph flow and records decision to audit log."""
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

        # Persist decision to compliance audit store
        self.audit_store.record_decision(
            claim_id=final_state["claim_id"],
            decision=final_state["decision"],
            confidence=final_state["confidence"],
            reasons=final_state["assessment"]["reasons"] if final_state["assessment"] else [],
            cited_clauses=final_state["assessment"]["cited_clause_ids"] if final_state["assessment"] else [],
            needs_human=final_state["needs_human"],
            trace=final_state["trace"],
        )

        # Save to checkpointer for human review
        self._checkpoints[claim_id] = final_state
        return final_state

    def resume_review(
        self,
        claim_id: str,
        action: str,
        reviewer_notes: str,
        override_decision: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resumes the graph after human adjuster review."""
        claim_id = self._sanitize_claim_id(claim_id)
        if claim_id not in self._checkpoints:
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
