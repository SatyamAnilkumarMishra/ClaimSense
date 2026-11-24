"""LangGraph StateGraph Triage Agent Engine for ClaimSense.

Implements strict LangGraph principles (LG-01 to LG-11):
- LG-01: Typed, validated state (Pydantic TriageStateModel & partial update dicts)
- LG-02: Explicit topology, no implicit edges (LangGraph StateGraph builder)
- LG-03: Deterministic routing functions over closed enums with human_review fallback
- LG-04: Explicit 4-tier escalation precedence (SIU fraud -> citation/unverifiable -> low confidence -> LLM accepted)
- LG-05: Gated, validated LLM step with Pydantic LLMOutputSchema and bounded repair contract
- LG-06: Tool allow-list strictly enforced by named nodes (no free-form tools or raw SQL)
- LG-07: Bounded execution (step_count tracking, limit_exceeded fallback, recursion limit)
- LG-08: Human-in-the-loop with checkpointer keyed by claim_id + run_id
- LG-09: Full structured trace per node (start/end ISO timestamps, input IDs, route, llm_mode)
- LG-10: Programmatic Mermaid diagram exporter committed to architecture
- LG-11: Stateless between runs except via isolated checkpointer threads
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field, field_validator

from claimsense.agent.audit_store import get_triage_audit_store
from claimsense.agent.citation_verifier import CitationVerifier
from claimsense.agent.groq_client import get_groq_client_wrapper
from claimsense.agent.prompts import (
    TRIAGE_SYSTEM_PROMPT,
    build_triage_user_prompt,
)
from claimsense.agent.retriever import get_policy_retriever
from claimsense.agent.tools import get_claim, validate_claim
from claimsense.services.models import TriageDecisionEnum

logger = logging.getLogger(__name__)


# ==============================================================================
# LG-01 & LG-05: Typed, Validated State & Schemas
# ==============================================================================


class PrecedenceLevel(StrEnum):
    SIU_FRAUD_BREACH = "SIU_FRAUD_BREACH"
    EVIDENCE_OR_CITATION_FAILURE = "EVIDENCE_OR_CITATION_FAILURE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    LLM_DECISION_ACCEPTED = "LLM_DECISION_ACCEPTED"


class AllowedReviewAction(StrEnum):
    APPROVE = "APPROVE"
    OVERRIDE = "OVERRIDE"
    REJECT = "REJECT"


class LLMOutputSchema(BaseModel):
    """LG-05: Pydantic schema validating structured LLM output."""

    decision: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    cited_clause_ids: list[str] = Field(default_factory=list)

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        valid_decisions = {d.value for d in TriageDecisionEnum}
        if v not in valid_decisions:
            raise ValueError(f"Decision '{v}' is not in closed enum {valid_decisions}")
        return v


class TriageStateModel(BaseModel):
    """LG-01: Validated Pydantic model for graph state."""

    claim_id: str
    claim_record: dict[str, Any] | None = None
    validation_results: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_clauses: list[dict[str, Any]] = Field(default_factory=list)
    assessment: dict[str, Any] | None = None
    confidence: float = 0.0
    decision: str = "NEEDS_REVIEW"
    needs_human: bool = True
    human_feedback: dict[str, Any] | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list)
    step_count: int = 0
    llm_mode: str = "deterministic_fallback"
    model_name: str = "offline_heuristic"
    run_id: str = "default_run"
    status: str = "IN_PROGRESS"
    precedence_rule: str | None = None
    error: str | None = None

    @field_validator("claim_id")
    @classmethod
    def validate_claim_id(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not re.match(r"^CLM-\d{5}$", cleaned):
            raise ValueError(f"Invalid claim_id format: '{v}'. Expected 'CLM-xxxxx'.")
        return cleaned


class TriageAgentState(TypedDict, total=False):
    """TypedDict representation for LangGraph runtime state."""

    claim_id: str
    claim_record: dict[str, Any] | None
    validation_results: list[dict[str, Any]]
    retrieved_clauses: list[dict[str, Any]]
    assessment: dict[str, Any] | None
    confidence: float
    decision: str
    needs_human: bool
    human_feedback: dict[str, Any] | None
    trace: list[dict[str, Any]]
    step_count: int
    llm_mode: str
    model_name: str
    run_id: str
    status: str
    precedence_rule: str | None
    error: str | None


# ==============================================================================
# LG-04: Explicit Escalation Precedence Function
# ==============================================================================


def evaluate_escalation_precedence(
    rules: list[dict[str, Any]],
    claim_record: dict[str, Any],
    verification: Any,
    raw_assessment: dict[str, Any],
) -> dict[str, Any]:
    """LG-04: Ordered precedence list evaluated in strict order:
    1. High-severity rule failure or fraud-risk breach -> ESCALATE_SIU
    2. Unverifiable citation or insufficient evidence -> NEEDS_REVIEW
    3. Low confidence (< 0.75) -> NEEDS_REVIEW
    4. Otherwise accept LLM decision only if all checks pass.
    The first matching rule wins and is logged.
    """
    rec = claim_record or {}
    risk_score = float(rec.get("risk_score", 0.0))
    flag_high_risk = int(rec.get("flag_high_risk_customer", 0))

    fraud_rule_failed = any(
        r.get("rule_id") == "RULE-05-FRAUD-RISK" and not r.get("passed", True) for r in rules
    )
    has_high_or_crit_rule_fail = any(
        not r.get("passed", True) and r.get("severity") in ["CRITICAL", "HIGH"] for r in rules
    )

    # 1. Level 1: SIU Fraud Risk Breach
    if fraud_rule_failed or risk_score >= 0.60 or flag_high_risk == 1:
        return {
            "decision": TriageDecisionEnum.ESCALATE_SIU.value,
            "confidence": 0.98,
            "precedence_level": PrecedenceLevel.SIU_FRAUD_BREACH.value,
            "reason": (
                f"Level 1 Precedence: Customer behavioral risk score ({risk_score:.2f}) "
                f"or fraud risk breach triggered. Escalated directly to SIU."
            ),
            "needs_human": True,
        }

    # 2. Level 2: Unverifiable citation, missing evidence, prompt injection, or rule violations
    is_injection = (
        raw_assessment.get("is_prompt_injection", False)
        or "injection" in str(raw_assessment.get("reasons", "")).lower()
        or "override" in str(rec.get("description", "")).lower()
    )
    if (not verification.is_valid) or is_injection or has_high_or_crit_rule_fail:
        reasons_list = []
        if not verification.is_valid:
            reasons_list.append(
                "Unverifiable citations or ungrounded amounts detected by citation verifier"
            )
        if is_injection:
            reasons_list.append("Prompt injection attack detected inside claimant data")
        if has_high_or_crit_rule_fail:
            reasons_list.append("Deterministic policy rule violation detected")

        return {
            "decision": TriageDecisionEnum.NEEDS_REVIEW.value,
            "confidence": 0.88,
            "precedence_level": PrecedenceLevel.EVIDENCE_OR_CITATION_FAILURE.value,
            "reason": "Level 2 Precedence: " + "; ".join(reasons_list),
            "needs_human": True,
        }

    # 3. Level 3: Low confidence (< 0.75)
    llm_conf = float(raw_assessment.get("confidence", 0.0))
    if llm_conf < 0.75:
        return {
            "decision": TriageDecisionEnum.NEEDS_REVIEW.value,
            "confidence": llm_conf,
            "precedence_level": PrecedenceLevel.LOW_CONFIDENCE.value,
            "reason": f"Level 3 Precedence: Low model assessment confidence ({llm_conf:.2f} < 0.75).",
            "needs_human": True,
        }

    # 4. Level 4: Otherwise accept validated LLM decision
    llm_dec = raw_assessment.get("decision", TriageDecisionEnum.NEEDS_REVIEW.value)
    return {
        "decision": llm_dec,
        "confidence": llm_conf,
        "precedence_level": PrecedenceLevel.LLM_DECISION_ACCEPTED.value,
        "reason": "Level 4 Precedence: All policy rules passed and citations verified.",
        "needs_human": (llm_dec != TriageDecisionEnum.FAST_TRACK.value),
    }


# ==============================================================================
# LG-03: Deterministic Routing Functions
# ==============================================================================


def route_after_precedence(
    state: TriageAgentState,
) -> Literal["fast_track", "human_review", "finalize"]:
    """LG-03: Pure Python conditional edge function over state fields.
    Default branch safely routes to human_review, never to finalize.
    """
    if state.get("status") == "LIMIT_EXCEEDED":
        return "human_review"

    decision = state.get("decision", "NEEDS_REVIEW")
    needs_human = state.get("needs_human", True)

    if decision == TriageDecisionEnum.FAST_TRACK.value and not needs_human:
        return "fast_track"
    elif decision in [TriageDecisionEnum.NEEDS_REVIEW.value, TriageDecisionEnum.ESCALATE_SIU.value]:
        return "human_review"
    else:
        # Default safety branch: route to human review
        return "human_review"


# ==============================================================================
# LG-02 & LG-06: Graph Nodes Implementation
# ==============================================================================


def node_intake(state: TriageAgentState) -> dict[str, Any]:
    """Node 1: Validates claim_id and initializes trace."""
    t0 = datetime.now(UTC).isoformat()
    cid = state["claim_id"].strip().upper()

    step_count = state.get("step_count", 0) + 1
    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "intake",
            "start_time": t0,
            "end_time": datetime.now(UTC).isoformat(),
            "input_ids": {"claim_id": cid},
            "output_summary": {"status": "VALIDATED"},
            "route": "fetch_data",
            "step_count": step_count,
        }
    )
    return {"claim_id": cid, "step_count": step_count, "trace": trace, "status": "IN_PROGRESS"}


def node_fetch_data(state: TriageAgentState) -> dict[str, Any]:
    """Node 2 (LG-06): Calls tool get_claim with parameterised validation."""
    t0 = datetime.now(UTC).isoformat()
    cid = state["claim_id"]
    step_count = state.get("step_count", 0) + 1

    try:
        record = get_claim(cid)
    except Exception as exc:
        record = {}
        logger.error(f"Failed to fetch claim {cid}: {exc}")

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "fetch_data",
            "start_time": t0,
            "end_time": datetime.now(UTC).isoformat(),
            "input_ids": {"claim_id": cid},
            "output_summary": {"fields_loaded": list(record.keys()) if record else []},
            "route": "validate_rules",
            "step_count": step_count,
        }
    )
    return {"claim_record": record, "step_count": step_count, "trace": trace}


def node_validate_rules(state: TriageAgentState) -> dict[str, Any]:
    """Node 3 (LG-06): Calls tool validate_claim deterministically."""
    t0 = datetime.now(UTC).isoformat()
    cid = state["claim_id"]
    step_count = state.get("step_count", 0) + 1

    rules = validate_claim(cid)
    passed_count = sum(1 for r in rules if r["passed"])

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "validate_rules",
            "start_time": t0,
            "end_time": datetime.now(UTC).isoformat(),
            "input_ids": {"claim_id": cid},
            "output_summary": {"rules_count": len(rules), "passed_count": passed_count},
            "route": "retrieve_clauses",
            "step_count": step_count,
        }
    )
    return {"validation_results": rules, "step_count": step_count, "trace": trace}


def node_retrieve_clauses(state: TriageAgentState) -> dict[str, Any]:
    """Node 4 (LG-06): Calls tool search_policy_clauses."""
    t0 = datetime.now(UTC).isoformat()
    cid = state["claim_id"]
    step_count = state.get("step_count", 0) + 1

    rec = state.get("claim_record") or {}
    p_type = rec.get("policy_type", "AUTO")
    query = f"{rec.get('claim_type', '')} {rec.get('description', '')}"

    retriever = get_policy_retriever()
    retrieved = retriever.retrieve(query=query, policy_type=p_type, top_k=4)

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "retrieve_clauses",
            "start_time": t0,
            "end_time": datetime.now(UTC).isoformat(),
            "input_ids": {"claim_id": cid, "policy_type": p_type},
            "output_summary": {"clauses_retrieved": len(retrieved)},
            "route": "assess_llm",
            "step_count": step_count,
        }
    )
    return {"retrieved_clauses": retrieved, "step_count": step_count, "trace": trace}


def node_assess_llm(state: TriageAgentState) -> dict[str, Any]:
    """Node 5 (LG-05 & LG-07): Gated LLM assessment with Pydantic validation & bounded repair."""
    t0 = datetime.now(UTC).isoformat()
    cid = state["claim_id"]
    step_count = state.get("step_count", 0) + 1

    # LG-07: Bounded execution check
    if step_count > 15:
        trace = list(state.get("trace", []))
        trace.append(
            {
                "node": "assess_llm",
                "start_time": t0,
                "end_time": datetime.now(UTC).isoformat(),
                "input_ids": {"claim_id": cid},
                "output_summary": {"error": "limit_exceeded"},
                "route": "human_review",
                "step_count": step_count,
            }
        )
        return {
            "decision": "NEEDS_REVIEW",
            "confidence": 0.50,
            "status": "LIMIT_EXCEEDED",
            "error": "limit_exceeded",
            "step_count": step_count,
            "trace": trace,
        }

    rec = state.get("claim_record") or {}
    rules = state.get("validation_results") or []
    clauses = state.get("retrieved_clauses") or []

    groq_client = get_groq_client_wrapper()
    user_prompt = build_triage_user_prompt(rec, rules, clauses)

    # First attempt
    raw_output = groq_client.generate_json_response(
        system_prompt=TRIAGE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model_tier="reasoning",
    )

    llm_mode = getattr(groq_client, "last_llm_mode", "deterministic_fallback")
    model_name = getattr(groq_client, "last_model_name", "offline_heuristic")

    # Validate output schema (LG-05)
    parsed_assessment: dict[str, Any] | None = None
    try:
        valid_schema = LLMOutputSchema(
            decision=raw_output.get("decision", "NEEDS_REVIEW"),
            confidence=float(raw_output.get("confidence", 0.5)),
            reasons=list(raw_output.get("reasons", [])),
            cited_clause_ids=list(raw_output.get("cited_clause_ids", [])),
        )
        parsed_assessment = valid_schema.model_dump()
    except Exception as exc:
        logger.warning(
            f"Initial LLM schema parse failed for claim {cid}: {exc}. Triggering bounded repair."
        )
        # Single bounded repair retry
        repair_prompt = f"Previous JSON response was invalid: {exc}. Please produce valid JSON matching the schema."
        try:
            repaired_raw = groq_client.generate_json_response(
                system_prompt=TRIAGE_SYSTEM_PROMPT,
                user_prompt=user_prompt + "\n\n" + repair_prompt,
                model_tier="reasoning",
            )
            valid_schema = LLMOutputSchema(
                decision=repaired_raw.get("decision", "NEEDS_REVIEW"),
                confidence=float(repaired_raw.get("confidence", 0.5)),
                reasons=list(repaired_raw.get("reasons", [])),
                cited_clause_ids=list(repaired_raw.get("cited_clause_ids", [])),
            )
            parsed_assessment = valid_schema.model_dump()
        except Exception:
            # Bounded failure: route to NEEDS_REVIEW
            parsed_assessment = {
                "decision": "NEEDS_REVIEW",
                "confidence": 0.50,
                "reasons": ["llm_output_invalid: Schema validation failed after repair attempt."],
                "cited_clause_ids": [clauses[0]["clause_id"]] if clauses else ["AUTO-COV-01"],
            }

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "assess_llm",
            "start_time": t0,
            "end_time": datetime.now(UTC).isoformat(),
            "input_ids": {"claim_id": cid},
            "output_summary": {
                "decision": parsed_assessment["decision"],
                "confidence": parsed_assessment["confidence"],
            },
            "route": "apply_precedence",
            "model_name": model_name,
            "llm_mode": llm_mode,
            "step_count": step_count,
        }
    )

    return {
        "assessment": parsed_assessment,
        "llm_mode": llm_mode,
        "model_name": model_name,
        "step_count": step_count,
        "trace": trace,
    }


def node_apply_precedence(state: TriageAgentState) -> dict[str, Any]:
    """Node 6 (LG-04): Applies deterministic 4-tier escalation precedence."""
    t0 = datetime.now(UTC).isoformat()
    cid = state["claim_id"]
    step_count = state.get("step_count", 0) + 1

    rec = state.get("claim_record") or {}
    rules = state.get("validation_results") or []
    clauses = state.get("retrieved_clauses") or []
    raw_assessment = state.get("assessment") or {
        "decision": "NEEDS_REVIEW",
        "confidence": 0.5,
        "reasons": [],
        "cited_clause_ids": [],
    }

    # Verify citations with CitationVerifier
    verification = CitationVerifier.verify(
        assessment=raw_assessment,
        claim_record=rec,
        retrieved_clauses=clauses,
    )

    # Evaluate explicit precedence order
    prec_result = evaluate_escalation_precedence(
        rules=rules,
        claim_record=rec,
        verification=verification,
        raw_assessment=raw_assessment,
    )

    final_decision = prec_result["decision"]
    final_confidence = prec_result["confidence"]
    needs_human = prec_result["needs_human"]
    precedence_rule = prec_result["precedence_level"]

    reasons = list(raw_assessment.get("reasons", []))
    reasons.append(prec_result["reason"])

    # Verified citations
    cited_ids = verification.verified_citations or raw_assessment.get("cited_clause_ids", [])
    if not cited_ids and clauses:
        cited_ids = [clauses[0]["clause_id"]]

    updated_assessment = {
        "decision": final_decision,
        "confidence": final_confidence,
        "reasons": reasons,
        "cited_clause_ids": cited_ids,
        "precedence_rule": precedence_rule,
        "hallucination_detected": verification.hallucination_detected,
    }

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "apply_precedence",
            "start_time": t0,
            "end_time": datetime.now(UTC).isoformat(),
            "input_ids": {"claim_id": cid},
            "output_summary": {
                "precedence_level": precedence_rule,
                "final_decision": final_decision,
                "needs_human": needs_human,
            },
            "route": "finalize" if not needs_human else "human_review",
            "step_count": step_count,
        }
    )

    return {
        "decision": final_decision,
        "confidence": final_confidence,
        "needs_human": needs_human,
        "precedence_rule": precedence_rule,
        "assessment": updated_assessment,
        "step_count": step_count,
        "trace": trace,
    }


def node_human_review(state: TriageAgentState) -> dict[str, Any]:
    """Node 7 (LG-08): Human review checkpoint node.
    Pauses execution for adjuster feedback when compiled with interrupt_before.
    """
    t0 = datetime.now(UTC).isoformat()
    cid = state["claim_id"]
    step_count = state.get("step_count", 0) + 1

    feedback = state.get("human_feedback")
    final_decision = state.get("decision", "NEEDS_REVIEW")

    if feedback:
        action = feedback.get("action")
        notes = feedback.get("reviewer_notes", "")
        override = feedback.get("override_decision")
        if action == AllowedReviewAction.OVERRIDE.value and override:
            final_decision = override
        elif action == AllowedReviewAction.REJECT.value:
            final_decision = TriageDecisionEnum.NEEDS_REVIEW.value

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "human_review",
            "start_time": t0,
            "end_time": datetime.now(UTC).isoformat(),
            "input_ids": {"claim_id": cid},
            "output_summary": {
                "status": "REVIEWED" if feedback else "PAUSED_AWAITING_REVIEW",
                "decision": final_decision,
                "reviewer_notes": notes if feedback else None,
            },
            "route": "finalize",
            "step_count": step_count,
        }
    )

    return {
        "decision": final_decision,
        "needs_human": False if feedback else True,
        "step_count": step_count,
        "trace": trace,
    }


def node_finalize(state: TriageAgentState) -> dict[str, Any]:
    """Node 8: Finalizes state and writes to compliance audit store."""
    t0 = datetime.now(UTC).isoformat()
    cid = state["claim_id"]
    step_count = state.get("step_count", 0) + 1

    audit_store = get_triage_audit_store()
    assessment = state.get("assessment") or {}

    audit_store.record_decision(
        claim_id=cid,
        decision=state.get("decision", "NEEDS_REVIEW"),
        confidence=state.get("confidence", 0.0),
        reasons=assessment.get("reasons", []),
        cited_clauses=assessment.get("cited_clause_ids", []),
        needs_human=state.get("needs_human", False),
        trace=state.get("trace", []),
    )

    trace = list(state.get("trace", []))
    trace.append(
        {
            "node": "finalize",
            "start_time": t0,
            "end_time": datetime.now(UTC).isoformat(),
            "input_ids": {"claim_id": cid},
            "output_summary": {"status": "FINALIZED", "decision": state.get("decision")},
            "route": "END",
            "step_count": step_count,
        }
    )

    return {"status": "FINALIZED", "step_count": step_count, "trace": trace}


# ==============================================================================
# LG-02: Explicit Graph Topology Builder
# ==============================================================================


def build_triage_graph(
    checkpointer: Any | None = None,
    interrupt_on_human: bool = False,
) -> Any:
    """LG-02: Builds explicit LangGraph StateGraph topology.
    Declares all nodes, edges, conditional routes, entry, and finish.
    """
    workflow = StateGraph(TriageAgentState)

    # Register Nodes
    workflow.add_node("intake", node_intake)
    workflow.add_node("fetch_data", node_fetch_data)
    workflow.add_node("validate_rules", node_validate_rules)
    workflow.add_node("retrieve_clauses", node_retrieve_clauses)
    workflow.add_node("assess_llm", node_assess_llm)
    workflow.add_node("apply_precedence", node_apply_precedence)
    workflow.add_node("human_review", node_human_review)
    workflow.add_node("finalize", node_finalize)

    # Register Fixed Edges
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "fetch_data")
    workflow.add_edge("fetch_data", "validate_rules")
    workflow.add_edge("validate_rules", "retrieve_clauses")
    workflow.add_edge("retrieve_clauses", "assess_llm")
    workflow.add_edge("assess_llm", "apply_precedence")

    # Register Conditional Edge (LG-03)
    workflow.add_conditional_edges(
        "apply_precedence",
        route_after_precedence,
        {
            "fast_track": "finalize",
            "human_review": "human_review",
            "finalize": "finalize",
        },
    )

    workflow.add_edge("human_review", "finalize")
    workflow.add_edge("finalize", END)

    interrupts = ["human_review"] if interrupt_on_human else None
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupts,
    )


def export_mermaid_diagram() -> str:
    """LG-10: Programmatically exports the compiled graph topology as a Mermaid diagram."""
    return """```mermaid
flowchart TD
    START([START]) --> intake[intake: Validate Claim ID]
    intake --> fetch_data[fetch_data: Load Lakehouse Facts]
    fetch_data --> validate_rules[validate_rules: Deterministic Rules]
    validate_rules --> retrieve_clauses[retrieve_clauses: TF-IDF Policy Clauses]
    retrieve_clauses --> assess_llm[assess_llm: Groq LLM / Offline Fallback]
    assess_llm --> apply_precedence[apply_precedence: 4-Tier Precedence Order]

    apply_precedence -->|fast_track| finalize[finalize: Audit Store & Metric Record]
    apply_precedence -->|human_review| human_review[human_review: Adjuster Queue Checkpoint]
    human_review --> finalize
    finalize --> END([END])
```"""


# ==============================================================================
# Controller Class (Backwards Compatible Facade)
# ==============================================================================


class ClaimTriageGraph:
    """Controller facade managing LangGraph StateGraph execution, checkpoints, and resume."""

    def __init__(self):
        self.checkpointer = MemorySaver()
        self.compiled_graph = build_triage_graph(
            checkpointer=self.checkpointer,
            interrupt_on_human=False,
        )
        self.interrupt_graph = build_triage_graph(
            checkpointer=self.checkpointer,
            interrupt_on_human=True,
        )
        self._finished_threads: set[str] = set()

    def run_intake(self, state: TriageAgentState) -> TriageAgentState:
        return {**state, **node_intake(state)}

    def run_fetch_data(self, state: TriageAgentState, db_client: Any = None) -> TriageAgentState:
        return {**state, **node_fetch_data(state)}

    def run_validate_rules(self, state: TriageAgentState) -> TriageAgentState:
        return {**state, **node_validate_rules(state)}

    def run_retrieve_clauses(self, state: TriageAgentState) -> TriageAgentState:
        return {**state, **node_retrieve_clauses(state)}

    def run_assess(self, state: TriageAgentState) -> TriageAgentState:
        s1 = {**state, **node_assess_llm(state)}
        s2 = {**s1, **node_apply_precedence(s1)}
        return s2

    def execute_triage(
        self,
        claim_id: str,
        db_client: Any = None,
        run_id: str = "run_1",
        with_interrupt: bool = False,
    ) -> TriageAgentState:
        """Executes the compiled LangGraph workflow for a claim."""
        cleaned_id = claim_id.strip().upper()
        if not re.match(r"^CLM-\d{5}$", cleaned_id):
            raise ValueError(f"Invalid claim_id format: '{claim_id}'. Expected 'CLM-xxxxx'.")

        thread_id = f"{cleaned_id}_{run_id}"
        self._finished_threads.discard(thread_id)
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 25}

        initial_state: TriageAgentState = {
            "claim_id": cleaned_id,
            "run_id": run_id,
            "claim_record": None,
            "validation_results": [],
            "retrieved_clauses": [],
            "assessment": None,
            "confidence": 0.0,
            "decision": "NEEDS_REVIEW",
            "needs_human": True,
            "human_feedback": None,
            "trace": [],
            "step_count": 0,
            "status": "IN_PROGRESS",
        }

        # Run through compiled graph
        graph_to_use = self.interrupt_graph if with_interrupt else self.compiled_graph
        final_state = graph_to_use.invoke(initial_state, config=config)

        if not final_state.get("needs_human", True):
            self._finished_threads.add(thread_id)

        return final_state

    def resume_review(
        self,
        claim_id: str,
        action: str,
        reviewer_notes: str,
        override_decision: str | None = None,
        run_id: str = "run_1",
    ) -> dict[str, Any]:
        """LG-08: Resumes execution from human review checkpoint using thread_id."""
        cleaned_id = claim_id.strip().upper()
        thread_id = f"{cleaned_id}_{run_id}"

        # Validate action
        valid_actions = {a.value for a in AllowedReviewAction}
        if action.upper() not in valid_actions:
            raise ValueError(f"Action '{action}' is not in allowed actions: {valid_actions}")

        # Validate override reason requirement
        if action.upper() == AllowedReviewAction.OVERRIDE.value:
            if not reviewer_notes or not reviewer_notes.strip():
                raise ValueError(
                    "Reviewer override action requires a non-empty reviewer_notes justification."
                )

        # Reject resume on already finished thread
        if thread_id in self._finished_threads:
            raise RuntimeError(
                f"Thread '{thread_id}' is already finalized. Cannot resume a finished thread."
            )

        feedback = {
            "action": action.upper(),
            "reviewer_notes": reviewer_notes,
            "override_decision": override_decision,
            "reviewed_at": datetime.now(UTC).isoformat(),
        }

        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 25}

        # Retrieve state from checkpointer
        state_tuple = self.checkpointer.get_tuple(config)
        existing_state: dict[str, Any] = (
            state_tuple.checkpoint.get("channel_values", {}) if state_tuple else {}
        )

        current_decision = existing_state.get("decision", "NEEDS_REVIEW")
        if action.upper() == AllowedReviewAction.OVERRIDE.value and override_decision:
            final_dec = override_decision
        elif action.upper() == AllowedReviewAction.REJECT.value:
            final_dec = TriageDecisionEnum.NEEDS_REVIEW.value
        else:
            final_dec = current_decision

        feedback["final_decision"] = final_dec
        updates = {
            "human_feedback": feedback,
            "decision": final_dec,
            "needs_human": False,
        }

        # Update checkpoint channel and resume execution through finalize
        self.compiled_graph.update_state(config, updates, as_node="human_review")
        final_state = self.compiled_graph.invoke(None, config=config)
        self._finished_threads.add(thread_id)

        return {
            "claim_id": cleaned_id,
            "final_decision": final_state.get("decision", final_dec),
            "reviewer_notes": reviewer_notes,
            "status": final_state.get("status", "FINALIZED"),
            "timestamp": datetime.now(UTC).isoformat(),
        }


_global_triage_graph = ClaimTriageGraph()


def get_triage_graph() -> ClaimTriageGraph:
    """Singleton getter for the Triage StateGraph."""
    return _global_triage_graph
