# LangGraph Strictness Gap Analysis Table (LG-01 to LG-11)

| Requirement ID | Requirement Title | Current Implementation State | Gap Description & Plan |
| :--- | :--- | :---: | :--- |
| **LG-01** | Typed, validated state | **Partial** | `TriageAgentState` is a `TypedDict` without runtime Pydantic validation on node boundaries. Add `TriageStateModel` Pydantic schema with validation test. |
| **LG-02** | Explicit topology, no implicit edges | **Partial** | Sequential calls in `execute_triage` rather than a formal graph topology builder. Build explicit `StateGraph` builder with fixed nodes, explicit edges, entry, and finish. |
| **LG-03** | Deterministic routing functions | **Partial** | Conditional branches mixed inside `run_assess`. Extract pure Python routing functions over closed enums with human review fallback. |
| **LG-04** | Escalation precedence is explicit | **Missing** | High fraud risk (`RULE-05-FRAUD-RISK`) was not deterministically routing to `ESCALATE_SIU` in code. Implement explicit 4-tier precedence order. |
| **LG-05** | LLM output is a gated, validated step | **Partial** | Output parsed with `json.loads` without Pydantic schema validation or bounded 1-attempt repair contract. Add `LLMOutputSchema` and repair handler. |
| **LG-06** | Tool allow-list enforced by graph | **Met** | Tools are strictly hardcoded functions in `tools.py` with parameterised queries. Enforce tool name allow-list checks. |
| **LG-07** | Bounded execution | **Partial** | No recursion limit or execution step counter in state. Add `step_count` bound and `limit_exceeded` handler. |
| **LG-08** | Human-in-the-loop with real checkpointer | **Partial** | In-memory dictionary `_checkpoints` keyed only by `claim_id`. Add persistent SQLite/thread-keyed checkpointer (`claim_id + run_id`) with strict action validation. |
| **LG-09** | Full trace for every run | **Partial** | Trace records basic steps but lacks explicit `llm_mode`, model name, start/end timestamps, and input IDs. Add structured trace schema. |
| **LG-10** | Exported graph matches code | **Missing** | Architecture Mermaid diagram was manually written. Add programmatic Mermaid exporter and test asserting graph equals architecture doc. |
| **LG-11** | Stateless between runs | **Met** | Agent controller maintains singleton cache. Add multi-run idempotency test to verify zero state leakage across calls. |
