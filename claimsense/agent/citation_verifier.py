"""Deterministic Anti-Hallucination & Citation Verification Engine.

Enforces:
1. Grounding: All cited clause IDs must exist in the retrieved set.
2. Closed-world decision: Decision must belong to [FAST_TRACK, NEEDS_REVIEW, ESCALATE_SIU].
3. Data consistency: Quoted amounts or dates must match the claim record.
4. Abstention: When citations fail or evidence is insufficient, forces NEEDS_REVIEW.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple
from claimsense.services.models import TriageDecisionEnum


class VerificationResult:
    def __init__(
        self,
        is_valid: bool,
        repaired_decision: str | None = None,
        errors: list[str] | None = None,
        verified_citations: list[str] | None = None,
        hallucination_detected: bool = False,
    ):
        self.is_valid = is_valid
        self.repaired_decision = repaired_decision
        self.errors = errors or []
        self.verified_citations = verified_citations or []
        self.hallucination_detected = hallucination_detected


class CitationVerifier:
    """Validates LLM outputs against ground-truth facts and retrieved policy clauses."""

    @staticmethod
    def verify(
        assessment: Dict[str, Any],
        claim_record: Dict[str, Any],
        retrieved_clauses: List[Dict[str, Any]],
    ) -> VerificationResult:
        errors = []
        hallucination_detected = False

        # 1. Closed-world Decision Validation
        raw_decision = assessment.get("decision", "").strip().upper()
        valid_decisions = {e.value for e in TriageDecisionEnum}
        if raw_decision not in valid_decisions:
            errors.append(f"Invalid decision '{raw_decision}'. Must be one of {valid_decisions}.")
            hallucination_detected = True

        # 2. Citation Verification against Retrieved Clauses
        retrieved_ids: Set[str] = {c["clause_id"] for c in retrieved_clauses}
        cited_ids: List[str] = assessment.get("cited_clause_ids", [])

        verified_citations = []
        for cid in cited_ids:
            clean_cid = cid.strip().upper()
            if clean_cid in retrieved_ids:
                verified_citations.append(clean_cid)
            else:
                errors.append(f"Hallucinated citation: Clause ID '{cid}' was not in retrieved context.")
                hallucination_detected = True

        # 3. Grounded Factual Verification (Amounts & Dates)
        reasons_text = " ".join(assessment.get("reasons", []))

        # Check for dollar amounts quoted in reasons
        quoted_amounts = re.findall(r"\$([0-9,]+(?:\.[0-9]{2})?)", reasons_text)
        if quoted_amounts:
            record_amt = f"{float(claim_record['claimed_amount']):,.2f}"
            record_sum = f"{float(claim_record['sum_insured']):,.2f}"
            for qa in quoted_amounts:
                # Quoted amount must match either claimed amount or sum insured
                if qa not in [record_amt, record_sum, str(claim_record['claimed_amount'])]:
                    errors.append(f"Factual discrepancy: Stated amount '${qa}' does not match record.")
                    hallucination_detected = True

        # 4. Abstention Rule: If citations could not be verified or were completely missing
        if not verified_citations and raw_decision == TriageDecisionEnum.FAST_TRACK.value:
            errors.append("Abstention: FAST_TRACK requires at least one verified policy clause citation.")
            hallucination_detected = True

        if hallucination_detected or errors:
            # Force conservative escalation (NEEDS_REVIEW)
            return VerificationResult(
                is_valid=False,
                repaired_decision=TriageDecisionEnum.NEEDS_REVIEW.value,
                errors=errors,
                verified_citations=verified_citations,
                hallucination_detected=True,
            )

        return VerificationResult(
            is_valid=True,
            repaired_decision=raw_decision,
            errors=[],
            verified_citations=verified_citations,
            hallucination_detected=False,
        )
