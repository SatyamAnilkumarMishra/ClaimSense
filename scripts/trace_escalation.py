"""Script to trace the 10 ESCALATE_SIU cases for Phase 1 diagnostic."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claimsense.agent.graph import get_triage_graph
from claimsense.agent.tools import get_claim, validate_claim
from claimsense.db.client_factory import get_db_client


def main():
    db = get_db_client()
    graph = get_triage_graph()

    dataset_path = Path("claimsense/evaluation/eval_dataset.json")
    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    siu_cases = [c for c in dataset if c.get("expected_decision") == "ESCALATE_SIU"]

    lines = [
        "# Escalation Trace Analysis (Phase 1 / ISS-01)\n",
        f"Diagnostic trace for the {len(siu_cases)} expected `ESCALATE_SIU` cases.\n",
    ]

    for item in siu_cases:
        cid = item["claim_id"]
        eval_id = item["eval_id"]
        rec = get_claim(cid)
        rules = validate_claim(cid)
        state = graph.execute_triage(cid, db)

        lines.append(f"## {eval_id}: {cid}")
        lines.append(f"- **Expected Decision**: `{item['expected_decision']}`")
        lines.append(f"- **Actual Decision**: `{state['decision']}`")
        lines.append(f"- **Customer Risk Score**: `{rec.get('risk_score')}`")
        lines.append(f"- **Flag High Risk Customer**: `{rec.get('flag_high_risk_customer')}`")
        lines.append("- **Rule Validation Results**:")
        for r in rules:
            status = "PASS" if r["passed"] else "FAIL"
            lines.append(f"  - `{r['rule_id']}` ({r['severity']}): {status} - {r['details']}")
        lines.append("- **Routing Execution Trace**:")
        for t in state["trace"]:
            step = t.get("step")
            st = t.get("status") or t.get("decision")
            lines.append(f"  - Node `{step}`: result={st}")
        lines.append("\n---\n")

    evidence_file = Path("docs/evidence/escalation_trace.md")
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    with open(evidence_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {len(siu_cases)} traces to {evidence_file}")


if __name__ == "__main__":
    main()
