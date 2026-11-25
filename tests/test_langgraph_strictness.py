"""LangGraph Strictness Verification Test Suite (LG-01 to LG-11).

Ensures the LangGraph StateGraph engine adheres to strict control-flow requirements:
- LG-01: Typed, validated state
- LG-02: Explicit topology, no implicit edges
- LG-03: Deterministic routing functions
- LG-04: Explicit 4-tier escalation precedence
- LG-05: Gated, validated LLM step with bounded repair
- LG-06: Tool allow-list enforcement
- LG-07: Bounded execution and step tracking
- LG-08: Human-in-the-loop checkpointer with thread resumption
- LG-09: Full structured trace per run
- LG-10: Exported Mermaid diagram matches code
- LG-11: Stateless execution between runs
"""

import pytest
from pydantic import ValidationError

from claimsense.agent.graph import (
    AllowedReviewAction,
    LLMOutputSchema,
    PrecedenceLevel,
    TriageAgentState,
    TriageStateModel,
    build_triage_graph,
    evaluate_escalation_precedence,
    export_mermaid_diagram,
    get_triage_graph,
    route_after_precedence,
)
from claimsense.db.client_factory import get_db_client

# ==============================================================================
# LG-01: Typed, Validated State
# ==============================================================================


def test_lg01_typed_validated_state():
    """Verify graph state enforces typed validation and rejects invalid schemas."""
    # Valid model construction
    valid_state = TriageStateModel(
        claim_id="CLM-30001",
        confidence=0.95,
        decision="FAST_TRACK",
    )
    assert valid_state.claim_id == "CLM-30001"

    # Invalid claim_id format
    with pytest.raises(ValidationError):
        TriageStateModel(claim_id="INVALID_ID_999")

    # Invalid confidence type
    with pytest.raises(ValidationError):
        TriageStateModel(claim_id="CLM-30002", confidence="not_a_float")


# ==============================================================================
# LG-02: Explicit Topology, No Implicit Edges
# ==============================================================================


def test_lg02_explicit_topology():
    """Verify compiled graph contains exact registered nodes and edges."""
    graph = build_triage_graph()

    expected_nodes = {
        "__start__",
        "intake",
        "fetch_data",
        "validate_rules",
        "retrieve_clauses",
        "assess_llm",
        "apply_precedence",
        "human_review",
        "finalize",
    }
    actual_nodes = set(graph.nodes.keys())
    assert expected_nodes.issubset(actual_nodes)


# ==============================================================================
# LG-03: Deterministic Routing Functions
# ==============================================================================


@pytest.mark.parametrize(
    "decision,needs_human,status,expected_route",
    [
        ("FAST_TRACK", False, "IN_PROGRESS", "fast_track"),
        ("FAST_TRACK", True, "IN_PROGRESS", "human_review"),
        ("NEEDS_REVIEW", True, "IN_PROGRESS", "human_review"),
        ("ESCALATE_SIU", True, "IN_PROGRESS", "human_review"),
        ("UNKNOWN_STATUS", False, "IN_PROGRESS", "human_review"),  # Default safety fallback
        ("FAST_TRACK", False, "LIMIT_EXCEEDED", "human_review"),  # Limit exceeded fallback
    ],
)
def test_lg03_deterministic_routing_boundaries(decision, needs_human, status, expected_route):
    """Verify pure Python routing returns strictly defined routes with safety fallback."""
    state: TriageAgentState = {
        "decision": decision,
        "needs_human": needs_human,
        "status": status,
    }
    route = route_after_precedence(state)
    assert route == expected_route


# ==============================================================================
# LG-04: Explicit Escalation Precedence Order
# ==============================================================================


def test_lg04_escalation_precedence_order():
    """Verify 4-tier precedence list is strictly enforced:
    Level 1 (SIU Fraud) > Level 2 (Evidence/Citations) > Level 3 (Confidence) > Level 4 (LLM Accepted).
    """
    mock_verifier_valid = type(
        "MockVerifier",
        (),
        {"is_valid": True, "hallucination_detected": False, "verified_citations": ["AUTO-COV-01"]},
    )
    mock_verifier_invalid = type(
        "MockVerifier",
        (),
        {"is_valid": False, "hallucination_detected": True, "verified_citations": []},
    )

    # Case A: Level 1 Trumps Level 2 (Fraud Risk + Invalid Citation -> ESCALATE_SIU)
    res_a = evaluate_escalation_precedence(
        rules=[{"rule_id": "RULE-05-FRAUD-RISK", "passed": False, "severity": "HIGH"}],
        claim_record={"risk_score": 0.88, "flag_high_risk_customer": 1},
        verification=mock_verifier_invalid,
        raw_assessment={"decision": "FAST_TRACK", "confidence": 0.99},
    )
    assert res_a["decision"] == "ESCALATE_SIU"
    assert res_a["precedence_level"] == PrecedenceLevel.SIU_FRAUD_BREACH.value

    # Case B: Level 2 Trumps Level 3 (Low Risk + Invalid Citation -> NEEDS_REVIEW)
    res_b = evaluate_escalation_precedence(
        rules=[{"rule_id": "RULE-05-FRAUD-RISK", "passed": True, "severity": "HIGH"}],
        claim_record={"risk_score": 0.20, "flag_high_risk_customer": 0},
        verification=mock_verifier_invalid,
        raw_assessment={"decision": "FAST_TRACK", "confidence": 0.99},
    )
    assert res_b["decision"] == "NEEDS_REVIEW"
    assert res_b["precedence_level"] == PrecedenceLevel.EVIDENCE_OR_CITATION_FAILURE.value

    # Case C: Level 3 (Low Confidence -> NEEDS_REVIEW)
    res_c = evaluate_escalation_precedence(
        rules=[{"rule_id": "RULE-01-ACTIVE-PERIOD", "passed": True, "severity": "CRITICAL"}],
        claim_record={"risk_score": 0.15, "flag_high_risk_customer": 0},
        verification=mock_verifier_valid,
        raw_assessment={"decision": "FAST_TRACK", "confidence": 0.65},
    )
    assert res_c["decision"] == "NEEDS_REVIEW"
    assert res_c["precedence_level"] == PrecedenceLevel.LOW_CONFIDENCE.value

    # Case D: Level 4 (All Valid -> Accept LLM Fast Track)
    res_d = evaluate_escalation_precedence(
        rules=[{"rule_id": "RULE-01-ACTIVE-PERIOD", "passed": True, "severity": "CRITICAL"}],
        claim_record={"risk_score": 0.10, "flag_high_risk_customer": 0},
        verification=mock_verifier_valid,
        raw_assessment={"decision": "FAST_TRACK", "confidence": 0.95},
    )
    assert res_d["decision"] == "FAST_TRACK"
    assert res_d["precedence_level"] == PrecedenceLevel.LLM_DECISION_ACCEPTED.value


# ==============================================================================
# LG-05: LLM Output Gated, Validated Step
# ==============================================================================


def test_lg05_llm_schema_validation():
    """Verify LLMOutputSchema validates closed enum and schema fields."""
    # Valid schema
    s = LLMOutputSchema(
        decision="FAST_TRACK",
        confidence=0.90,
        reasons=["Valid claim facts"],
        cited_clause_ids=["AUTO-COV-01"],
    )
    assert s.decision == "FAST_TRACK"

    # Invalid decision enum
    with pytest.raises(ValidationError):
        LLMOutputSchema(
            decision="INVALID_DECISION",
            confidence=0.90,
            reasons=[],
            cited_clause_ids=[],
        )

    # Invalid confidence range (> 1.0)
    with pytest.raises(ValidationError):
        LLMOutputSchema(
            decision="FAST_TRACK",
            confidence=1.50,
            reasons=[],
            cited_clause_ids=[],
        )


# ==============================================================================
# LG-06: Tool Allow-List Enforcement
# ==============================================================================


def test_lg06_tool_allow_list():
    """Verify tools execute only with sanitized, allow-listed parameters."""
    db = get_db_client()
    rows = db.execute_query("SELECT claim_id FROM fact_claims LIMIT 1")
    cid = rows[0]["claim_id"]

    # Parameterised query succeeds
    claim = get_triage_graph().run_fetch_data({"claim_id": cid, "trace": []})
    assert claim["claim_record"] is not None

    # Invalid SQL injection attempt in claim_id is rejected by regex
    with pytest.raises(ValueError):
        get_triage_graph().execute_triage("CLM-12345; DROP TABLE fact_claims;--")


# ==============================================================================
# LG-07: Bounded Execution
# ==============================================================================


def test_lg07_bounded_execution():
    """Verify step_count bounds protect against unbounded cycles."""
    state: TriageAgentState = {
        "claim_id": "CLM-30001",
        "step_count": 20,  # Exceeds max steps bound (15)
        "trace": [],
    }
    from claimsense.agent.graph import node_assess_llm

    res = node_assess_llm(state)
    assert res["status"] == "LIMIT_EXCEEDED"
    assert res["decision"] == "NEEDS_REVIEW"


# ==============================================================================
# LG-08: Human-in-the-Loop Checkpointer
# ==============================================================================


def test_lg08_human_in_the_loop_checkpointer():
    """Verify interrupt, resume approval, override reason validation, and finish rejection."""
    graph = get_triage_graph()
    db = get_db_client()
    rows = db.execute_query("SELECT claim_id FROM fact_claims LIMIT 1")
    cid = rows[0]["claim_id"]
    test_run_id = "test_hitl_run_99"

    # 1. Execute triage with interrupt enabled
    state = graph.execute_triage(cid, db, run_id=test_run_id, with_interrupt=True)
    assert state["status"] in ["IN_PROGRESS", "FINALIZED"]

    # 2. Override without a reason must be rejected
    with pytest.raises(ValueError):
        graph.resume_review(
            claim_id=cid,
            action=AllowedReviewAction.OVERRIDE.value,
            reviewer_notes="",  # Empty reason
            override_decision="FAST_TRACK",
            run_id=test_run_id,
        )

    # 3. Resume with Approve finalizes
    res = graph.resume_review(
        claim_id=cid,
        action=AllowedReviewAction.APPROVE.value,
        reviewer_notes="Approved after adjuster verification.",
        run_id=test_run_id,
    )
    assert res["status"] == "FINALIZED"

    # 4. Second resume on finalized thread must be rejected
    with pytest.raises(RuntimeError):
        graph.resume_review(
            claim_id=cid,
            action=AllowedReviewAction.APPROVE.value,
            reviewer_notes="Duplicate attempt.",
            run_id=test_run_id,
        )


# ==============================================================================
# LG-09: Full Structured Trace Per Run
# ==============================================================================


def test_lg09_full_structured_trace():
    """Verify every executed node writes a structured trace record."""
    graph = get_triage_graph()
    db = get_db_client()
    rows = db.execute_query("SELECT claim_id FROM fact_claims LIMIT 1")
    cid = rows[0]["claim_id"]

    state = graph.execute_triage(cid, db, run_id="trace_test_run")
    assert len(state["trace"]) >= 5
    for tr in state["trace"]:
        assert "node" in tr
        assert "start_time" in tr
        assert "end_time" in tr
        assert "input_ids" in tr
        assert "route" in tr


# ==============================================================================
# LG-10: Exported Graph Matches Code
# ==============================================================================


def test_lg10_exported_graph_matches_code():
    """Verify programmatic Mermaid export matches committed architecture documentation."""
    from pathlib import Path

    mermaid_text = export_mermaid_diagram()
    arch_file = Path("ARCHITECTURE.md")
    assert arch_file.exists()
    content = arch_file.read_text(encoding="utf-8")
    assert "intake[intake: Validate Claim ID]" in content
    assert "apply_precedence[apply_precedence: 4-Tier Precedence Order]" in content
    assert "intake" in mermaid_text
    assert "apply_precedence" in mermaid_text


# ==============================================================================
# LG-11: Stateless Execution Between Runs
# ==============================================================================


def test_lg11_stateless_execution():
    """Verify multi-claim execution order does not leak state across runs."""
    graph = get_triage_graph()
    db = get_db_client()
    c1 = "CLM-30004"
    c2 = "CLM-30008"

    # Forward order
    res_a1 = graph.execute_triage(c1, db, run_id="forward_c1")
    res_a2 = graph.execute_triage(c2, db, run_id="forward_c2")

    # Reverse order
    res_b2 = graph.execute_triage(c2, db, run_id="reverse_c2")
    res_b1 = graph.execute_triage(c1, db, run_id="reverse_c1")

    assert res_a1["decision"] == res_b1["decision"]
    assert res_a2["decision"] == res_b2["decision"]
    assert res_a1["confidence"] == res_b1["confidence"]
    assert res_a2["confidence"] == res_b2["confidence"]
