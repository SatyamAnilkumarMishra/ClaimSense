"""Tests ensuring metrics in README.md and docs/EVALUATION.md match eval_results.json (ISS-02)."""

import json
from pathlib import Path


def test_readme_and_evaluation_docs_match_eval_results():
    """Verify that every metric displayed in documentation is derived from eval_results.json."""
    results_file = Path("claimsense/evaluation/eval_results.json")
    assert results_file.exists(), "eval_results.json must exist"

    with open(results_file, encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]
    accuracy = str(summary["decision_accuracy_percent"])
    precision = str(summary["escalation_precision_percent"])
    latency = str(summary["average_latency_ms"])

    # Check README.md
    readme_file = Path("README.md")
    assert readme_file.exists()
    readme_text = readme_file.read_text(encoding="utf-8")

    assert f"**{accuracy}%**" in readme_text, f"README does not contain accuracy {accuracy}%"
    assert f"**{precision}%**" in readme_text, f"README does not contain precision {precision}%"
    assert f"**{latency} ms**" in readme_text, f"README does not contain latency {latency} ms"

    # Check docs/EVALUATION.md if present
    eval_doc_file = Path("docs/EVALUATION.md")
    if eval_doc_file.exists():
        eval_text = eval_doc_file.read_text(encoding="utf-8")
        assert f"**{accuracy}%**" in eval_text, (
            f"EVALUATION.md does not contain accuracy {accuracy}%"
        )
        assert f"**{precision}%**" in eval_text, (
            f"EVALUATION.md does not contain precision {precision}%"
        )
        assert f"**{latency} ms**" in eval_text, (
            f"EVALUATION.md does not contain latency {latency} ms"
        )
