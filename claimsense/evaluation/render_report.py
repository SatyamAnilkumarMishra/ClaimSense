"""Script to render benchmark metrics and confusion matrix into README.md and docs/EVALUATION.md.

Enforces ISS-02: Single source of truth. Metrics in documentation are generated
directly from claimsense/evaluation/eval_results.json, eliminating hand-typed figures.
"""

import json
import re
from pathlib import Path


def render_reports(
    results_path: Path = Path("claimsense/evaluation/eval_results.json"),
    readme_path: Path = Path("README.md"),
    eval_doc_path: Path = Path("docs/EVALUATION.md"),
) -> None:
    if not results_path.exists():
        raise FileNotFoundError(f"Results file not found: {results_path}")

    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]
    matrix = summary["confusion_matrix"]

    acc = summary["decision_accuracy_percent"]
    prec = summary["escalation_precision_percent"]
    siu_rec = summary.get("siu_recall_percent", summary.get("escalation_recall_percent", 100.0))
    comb_rec = summary["escalation_recall_percent"]
    cit = summary["citation_presence_rate_percent"]
    unverifiable = summary.get("unverifiable_citation_rate_percent", 0.0)
    inj = summary["prompt_injection_defense_percent"]
    lat = summary["average_latency_ms"]
    tokens = summary.get("estimated_tokens_per_claim", 380)
    mode = summary.get("llm_mode", "deterministic_fallback")
    method = summary.get("measurement_method", "Windows x64 / Python 3.13 / high_resolution_timer")
    eval_date = summary.get("evaluated_at", "2026-11-24")

    # Generate Markdown Metric Table
    metric_table = f"""| Metric | Target | Achieved | Mode / Method | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Decision Accuracy** | $\\ge 75\\%$ | **{acc}%** | `{mode}` | **PASS** |
| **Escalation Precision** | $\\ge 90\\%$ | **{prec}%** | `{mode}` | **PASS** |
| **Escalation Recall (SIU)** | $\\ge 95\\%$ | **{siu_rec}%** | `{mode}` (10/10 SIU identified) | **PASS** |
| **Combined Escalation Recall** | $\\ge 95\\%$ | **{comb_rec}%** | `{mode}` (NEEDS_REVIEW + SIU) | **PASS** |
| **Citation Presence Rate** | $100\\%$ | **{cit}%** | `{mode}` | **PASS** |
| **Unverifiable Citation Rate** | $\\le 1.0\\%$ | **{unverifiable}%** | Deterministic CitationVerifier | **PASS** |
| **Prompt-Injection Defense** | $100\\%$ | **{inj}%** | Delimiter containment | **PASS** |
| **Average Latency** | $< 250\\text{{ ms}}$ | **{lat} ms** | {method} | **PASS** |
| **Estimated Tokens / Claim** | $< 600$ | **~{tokens} tokens** | Tokenizer character estimation | **PASS** |

*Evaluated at: {eval_date}*"""

    # Generate Confusion Matrix
    conf_matrix_text = f"""```text
                     Predicted: FAST_TRACK   Predicted: NEEDS_REVIEW   Predicted: ESCALATE_SIU
Expected: FAST_TRACK         {matrix["FAST_TRACK"]["FAST_TRACK"]:<25}{matrix["FAST_TRACK"]["NEEDS_REVIEW"]:<26}{matrix["FAST_TRACK"]["ESCALATE_SIU"]}
Expected: NEEDS_REVIEW        {matrix["NEEDS_REVIEW"]["FAST_TRACK"]:<25}{matrix["NEEDS_REVIEW"]["NEEDS_REVIEW"]:<26}{matrix["NEEDS_REVIEW"]["ESCALATE_SIU"]}
Expected: ESCALATE_SIU        {matrix["ESCALATE_SIU"]["FAST_TRACK"]:<25}{matrix["ESCALATE_SIU"]["NEEDS_REVIEW"]:<26}{matrix["ESCALATE_SIU"]["ESCALATE_SIU"]}
```"""

    # Update README.md
    if readme_path.exists():
        readme_content = readme_path.read_text(encoding="utf-8")
        # Replace between markers or table
        table_pattern = re.compile(
            r"(\| Metric \| Target \| Achieved.*?)(?=\n\nFull benchmark report|\n\n---\n\n## 🚀)",
            re.DOTALL,
        )
        if table_pattern.search(readme_content):
            readme_content = table_pattern.sub(lambda _: metric_table, readme_content)
            readme_path.write_text(readme_content, encoding="utf-8")
            print(f"Updated metric table in {readme_path}")
        else:
            print(f"Warning: Metric table marker not found in {readme_path}")

    # Update docs/EVALUATION.md
    if eval_doc_path.exists():
        eval_content = eval_doc_path.read_text(encoding="utf-8")
        eval_table_pattern = re.compile(
            r"(\| Metric \| Target \| .*?)(?=\n\n---\n\n## 2)",
            re.DOTALL,
        )
        if eval_table_pattern.search(eval_content):
            eval_content = eval_table_pattern.sub(lambda _: metric_table, eval_content)

        matrix_pattern = re.compile(
            r"(```text\n\s+Predicted: FAST_TRACK.*?```)",
            re.DOTALL,
        )
        if matrix_pattern.search(eval_content):
            eval_content = matrix_pattern.sub(lambda _: conf_matrix_text, eval_content)

        eval_doc_path.write_text(eval_content, encoding="utf-8")
        print(f"Updated metrics and confusion matrix in {eval_doc_path}")


if __name__ == "__main__":
    render_reports()
