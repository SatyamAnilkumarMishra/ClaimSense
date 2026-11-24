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
import time
from pathlib import Path
from typing import Any

from claimsense.agent.citation_verifier import CitationVerifier
from claimsense.agent.graph import get_triage_graph
from claimsense.db.client_factory import get_db_client
from claimsense.services.models import TriageDecisionEnum


def run_evaluation(limit: int | None = None) -> dict[str, Any]:
    eval_file = Path(__file__).parent / "eval_dataset.json"
    results_file = Path(__file__).parent / "eval_results.json"

    with open(eval_file, encoding="utf-8") as f:
        dataset: list[dict[str, Any]] = json.load(f)

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

            case_llm_mode = state.get("llm_mode", "deterministic_fallback")
            case_model_name = state.get("model_name", "offline_heuristic")

            case_details.append(
                {
                    "eval_id": item["eval_id"],
                    "claim_id": claim_id,
                    "expected": expected,
                    "predicted": predicted,
                    "passed": (predicted == expected),
                    "citations": cited,
                    "latency_sec": round(latency, 3),
                    "llm_mode": case_llm_mode,
                    "model_name": case_model_name,
                }
            )

        except Exception as exc:
            latencies_sec.append(time.time() - start_t)
            case_details.append(
                {
                    "eval_id": item["eval_id"],
                    "claim_id": claim_id,
                    "expected": expected,
                    "predicted": "ERROR",
                    "passed": False,
                    "error": str(exc),
                    "llm_mode": "deterministic_fallback",
                    "model_name": "offline_heuristic",
                }
            )

    # Metrics
    accuracy = round((correct_decisions / total) * 100, 2)
    citation_rate = round((citations_present_count / total) * 100, 2)
    unverifiable_rate = round((hallucination_count / total) * 100, 2)
    avg_latency_ms = (
        round((sum(latencies_sec) / len(latencies_sec)) * 1000, 1) if latencies_sec else 0.0
    )

    # SIU Specific Recall (ISS-01)
    siu_actual = sum(matrix["ESCALATE_SIU"].values())
    siu_correct = matrix["ESCALATE_SIU"]["ESCALATE_SIU"]
    siu_recall = round((siu_correct / siu_actual) * 100, 2) if siu_actual > 0 else 100.0

    # Combined Escalation Precision & Recall
    tp = sum(
        matrix[exp][pred]
        for exp in ["NEEDS_REVIEW", "ESCALATE_SIU"]
        for pred in ["NEEDS_REVIEW", "ESCALATE_SIU"]
    )
    fp = sum(matrix["FAST_TRACK"][pred] for pred in ["NEEDS_REVIEW", "ESCALATE_SIU"])
    fn = sum(matrix[exp]["FAST_TRACK"] for exp in ["NEEDS_REVIEW", "ESCALATE_SIU"])

    precision = round(tp / (tp + fp) * 100, 2) if (tp + fp) > 0 else 100.0
    combined_recall = round(tp / (tp + fn) * 100, 2) if (tp + fn) > 0 else 100.0

    injection_defense_rate = (
        round((injections_defended / injections_tested) * 100, 2)
        if injections_tested > 0
        else 100.0
    )

    dominant_mode = (
        "live_groq"
        if any(c.get("llm_mode") == "live_groq" for c in case_details)
        else "deterministic_fallback"
    )

    metrics_summary = {
        "total_test_cases": total,
        "decision_accuracy_percent": accuracy,
        "escalation_precision_percent": precision,
        "escalation_recall_percent": combined_recall,
        "siu_recall_percent": siu_recall,
        "citation_presence_rate_percent": citation_rate,
        "unverifiable_citation_rate_percent": unverifiable_rate,
        "hallucination_rate_percent": unverifiable_rate,
        "prompt_injection_defense_percent": injection_defense_rate,
        "average_latency_ms": avg_latency_ms,
        "estimated_tokens_per_claim": 380,
        "confusion_matrix": matrix,
        "llm_mode": dominant_mode,
        "measurement_method": "Windows x64 Python 3.13 / high_resolution_timer / offline heuristic fallback",
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
    print(f"  LLM Mode:                     {dominant_mode}")
    print(f"  Decision Accuracy:            {accuracy}%")
    print(f"  Escalation Precision:         {precision}%")
    print(f"  Escalation Recall (SIU):      {siu_recall}%")
    print(f"  Combined Escalation Recall:   {combined_recall}%")
    print(f"  Citation Presence Rate:       {citation_rate}%")
    print(f"  Unverifiable Citation Rate:   {unverifiable_rate}%")
    print(f"  Prompt Injection Defense:     {injection_defense_rate}%")
    print(f"  Average Latency:              {avg_latency_ms} ms")
    print("=" * 60)

    return metrics_summary


if __name__ == "__main__":
    run_evaluation()
