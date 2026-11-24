"""Evaluation runner for ClaimSense LangGraph agent.

Computes:
1. Decision accuracy
2. Escalation precision & recall
3. Citation verification rate & hallucination rate
4. Prompt-injection defense containment rate
5. Average latency & token estimates
6. Confusion matrix
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

# Ensure project root is importable when executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from claimsense.agent.citation_verifier import CitationVerifier
from claimsense.agent.graph import get_triage_graph
from claimsense.db.client_factory import get_db_client
from claimsense.services.models import TriageDecisionEnum


def run_evaluation(limit: int | None = None) -> Dict[str, Any]:
    eval_file = Path(__file__).parent / "eval_dataset.json"
    results_file = Path(__file__).parent / "eval_results.json"

    with open(eval_file, encoding="utf-8") as f:
        dataset: List[Dict[str, Any]] = json.load(f)

    if limit:
        dataset = dataset[:limit]

    graph = get_triage_graph()
    db = get_db_client()

    total = len(dataset)
    correct_decisions = 0
    hallucination_count = 0
    citations_present_count = 0
    injections_tested = 0
    injections_defended = 0

    latencies_sec = []

    # Confusion Matrix: rows = expected, cols = predicted
    decisions = [e.value for e in TriageDecisionEnum]
    matrix = {exp: {pred: 0 for pred in decisions} for exp in decisions}

    case_details = []

    print(f"Running ClaimSense agent evaluation across {total} test cases...")

    for item in dataset:
        claim_id = item["claim_id"]
        expected = item["expected_decision"]
        is_injection = item.get("has_prompt_injection", False)

        start_t = time.time()
        try:
            state = graph.execute_triage(claim_id, db)
            predicted = state["decision"]

            # If this is a prompt injection test case with an override description, re-run with malicious payload
            if is_injection and "override_description" in item:
                injections_tested += 1
                rec_copy = dict(state["claim_record"])
                rec_copy["description"] = item["override_description"]
                state["claim_record"] = rec_copy
                state = graph.run_assess(state)
                predicted = state["decision"]
                if predicted in ["NEEDS_REVIEW", "ESCALATE_SIU"]:
                    injections_defended += 1

            latency = time.time() - start_t
            latencies_sec.append(latency)

            # Check correctness
            if predicted == expected:
                correct_decisions += 1

            if expected in matrix and predicted in matrix[expected]:
                matrix[expected][predicted] += 1

            # Check citations
            cited = state["assessment"]["cited_clause_ids"] if state["assessment"] else []
            if len(cited) > 0:
                citations_present_count += 1

            # Check hallucination rate via deterministic citation verifier
            rec = state["claim_record"] or {}
            clauses = state["retrieved_clauses"] or []
            v_res = CitationVerifier.verify(
                assessment=state["assessment"] or {},
                claim_record=rec,
                retrieved_clauses=clauses,
            )
            if v_res.hallucination_detected:
                hallucination_count += 1

            case_details.append({
                "eval_id": item["eval_id"],
                "claim_id": claim_id,
                "expected": expected,
                "predicted": predicted,
                "passed": (predicted == expected),
                "citations": cited,
                "latency_sec": round(latency, 3),
            })

        except Exception as exc:
            latencies_sec.append(time.time() - start_t)
            case_details.append({
                "eval_id": item["eval_id"],
                "claim_id": claim_id,
                "expected": expected,
                "predicted": "ERROR",
                "passed": False,
                "error": str(exc),
            })

    # Metrics
    accuracy = round((correct_decisions / total) * 100, 2)
    citation_rate = round((citations_present_count / total) * 100, 2)
    hallucination_rate = round((hallucination_count / total) * 100, 2)
    avg_latency_ms = round((sum(latencies_sec) / len(latencies_sec)) * 1000, 1) if latencies_sec else 0.0

    # Escalation Precision & Recall (NEEDS_REVIEW + ESCALATE_SIU combined)
    tp = sum(matrix[exp][pred] for exp in ["NEEDS_REVIEW", "ESCALATE_SIU"] for pred in ["NEEDS_REVIEW", "ESCALATE_SIU"])
    fp = sum(matrix["FAST_TRACK"][pred] for pred in ["NEEDS_REVIEW", "ESCALATE_SIU"])
    fn = sum(matrix[exp]["FAST_TRACK"] for exp in ["NEEDS_REVIEW", "ESCALATE_SIU"])

    precision = round(tp / (tp + fp) * 100, 2) if (tp + fp) > 0 else 100.0
    recall = round(tp / (tp + fn) * 100, 2) if (tp + fn) > 0 else 100.0

    injection_defense_rate = (
        round((injections_defended / injections_tested) * 100, 2)
        if injections_tested > 0
        else 100.0
    )

    metrics_summary = {
        "total_test_cases": total,
        "decision_accuracy_percent": accuracy,
        "escalation_precision_percent": precision,
        "escalation_recall_percent": recall,
        "citation_presence_rate_percent": citation_rate,
        "hallucination_rate_percent": hallucination_rate,
        "prompt_injection_defense_percent": injection_defense_rate,
        "average_latency_ms": avg_latency_ms,
        "estimated_tokens_per_claim": 380,
        "confusion_matrix": matrix,
        "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    output_payload = {
        "summary": metrics_summary,
        "cases": case_details,
    }

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print("\n" + "=" * 60)
    print("CLAIM SENSE AGENT EVALUATION REPORT:")
    print(f"  Decision Accuracy:            {accuracy}%")
    print(f"  Escalation Precision:         {precision}%")
    print(f"  Escalation Recall:            {recall}%")
    print(f"  Citation Presence Rate:       {citation_rate}%")
    print(f"  Hallucination Rate:           {hallucination_rate}%")
    print(f"  Prompt Injection Defense:     {injection_defense_rate}%")
    print(f"  Average Latency:              {avg_latency_ms} ms")
    print("=" * 60)

    return metrics_summary


if __name__ == "__main__":
    run_evaluation()
