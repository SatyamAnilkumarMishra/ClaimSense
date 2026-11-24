"""ClaimSense: LangGraph AI Triage Agent Page."""

import pandas as pd
import streamlit as st

from claimsense.agent.audit_store import get_triage_audit_store
from claimsense.db.client_factory import get_db_client
from claimsense.services.claims_service import get_claims_service
from claimsense.services.models import HumanReviewRequest, TriageDecisionEnum


def render():
    st.title("🤖 LangGraph AI Claims Triage Agent")
    st.markdown(
        "Ground-truth AI triage engine running deterministic policy rules, vector clause retrieval, and anti-hallucination verification."
    )

    service = get_claims_service()
    db = get_db_client()
    audit_store = get_triage_audit_store()

    # Quick Pick Sample Claims
    st.markdown("#### ⚡ Quick-Select Sample Claim Scenarios")
    qcol1, qcol2, qcol3 = st.columns(3)

    if "selected_claim_id" not in st.session_state:
        st.session_state["selected_claim_id"] = "CLM-30079"

    with qcol1:
        if st.button("🟢 Clean Claim (Fast Track)", use_container_width=True):
            st.session_state["selected_claim_id"] = "CLM-30079"

    with qcol2:
        if st.button("🟡 Exception Claim (Review)", use_container_width=True):
            st.session_state["selected_claim_id"] = "CLM-30245"

    with qcol3:
        if st.button("🔴 High-Risk Claim (SIU Escalation)", use_container_width=True):
            st.session_state["selected_claim_id"] = "CLM-30372"

    # Claim Selector Dropdown
    claims_rows = db.execute_query(
        "SELECT claim_id, claim_type, claimed_amount, city FROM fact_claims ORDER BY claim_id LIMIT 60"
    )
    claim_options = [r["claim_id"] for r in claims_rows] if claims_rows else ["CLM-30079"]

    default_idx = (
        claim_options.index(st.session_state["selected_claim_id"])
        if st.session_state["selected_claim_id"] in claim_options
        else 0
    )
    chosen_claim_id = st.selectbox(
        "Or select claim from Lakehouse:", claim_options, index=default_idx
    )
    st.session_state["selected_claim_id"] = chosen_claim_id

    # Execute Triage Button
    if st.button("⚡ Run LangGraph Agent Triage", type="primary", use_container_width=True):
        with st.spinner(f"Executing LangGraph StateGraph for {chosen_claim_id}..."):
            assessment = service.triage_claim(chosen_claim_id)
            st.session_state["latest_assessment"] = assessment

    # Render Assessment Results
    if "latest_assessment" in st.session_state:
        assess = st.session_state["latest_assessment"]

        st.divider()

        # Decision Badge & Confidence Tile
        res_col1, res_col2 = st.columns([2, 1])

        with res_col1:
            dec = assess.decision
            if dec == TriageDecisionEnum.FAST_TRACK:
                st.markdown(
                    """
                <div style="background: rgba(0, 210, 186, 0.15); border: 2px solid #00D2BA; border-radius: 10px; padding: 1.25rem;">
                    <span class="badge-fast-track">FAST_TRACK RECOMMENDATION</span>
                    <h2 style="color: #00D2BA; margin: 0.5rem 0 0.25rem 0;">Straight-Through Processing Approved</h2>
                    <p style="color: #F0F4F8; margin: 0;">All deterministic rules passed. Eligible for automated rapid settlement.</p>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            elif dec == TriageDecisionEnum.NEEDS_REVIEW:
                st.markdown(
                    """
                <div style="background: rgba(255, 179, 0, 0.15); border: 2px solid #FFB300; border-radius: 10px; padding: 1.25rem;">
                    <span class="badge-needs-review">NEEDS_REVIEW RECOMMENDATION</span>
                    <h2 style="color: #FFB300; margin: 0.5rem 0 0.25rem 0;">Manual Adjuster Review Required</h2>
                    <p style="color: #F0F4F8; margin: 0;">Exceptions flagged (e.g. reporting delay, documentation shortage, or policy limits).</p>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                <div style="background: rgba(255, 75, 75, 0.15); border: 2px solid #FF4B4B; border-radius: 10px; padding: 1.25rem;">
                    <span class="badge-escalate-siu">ESCALATE_SIU RECOMMENDATION</span>
                    <h2 style="color: #FF4B4B; margin: 0.5rem 0 0.25rem 0;">Fraud Investigation Referral</h2>
                    <p style="color: #F0F4F8; margin: 0;">Elevated behavioral risk score or rapid filing cluster pattern detected.</p>
                </div>
                """,
                    unsafe_allow_html=True,
                )

        with res_col2:
            st.markdown(
                f"""
            <div class="kpi-card" style="height: 100%;">
                <div class="kpi-title">Agent Confidence</div>
                <div class="kpi-value">{assess.confidence * 100:.0f}%</div>
                <div class="kpi-subtext">Verified Policy Grounding</div>
            </div>
            """,
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # Tabs for Decision Details
        tab_reasons, tab_rules, tab_clauses, tab_trace = st.tabs(
            [
                "📋 Reasons & Citations",
                "⚖️ Deterministic Rules",
                "📜 Cited Policy Clauses",
                "🔍 Execution Trace",
            ]
        )

        with tab_reasons:
            st.markdown("#### Primary Assessment Reasons")
            for r in assess.reasons:
                st.markdown(f"- **{r}**")

            st.markdown("#### Cited Policy Clause Identifiers")
            st.write(assess.cited_clause_ids)

        with tab_rules:
            st.markdown("#### Deterministic Rule Engine Audit")
            rule_rows = [
                {
                    "Rule ID": r.rule_id,
                    "Description": r.description,
                    "Status": "PASS ✅" if r.passed else "FAIL ❌",
                    "Severity": r.severity,
                    "Audit Details": r.details,
                }
                for r in assess.rule_checks
            ]
            st.dataframe(pd.DataFrame(rule_rows), use_container_width=True, hide_index=True)

        with tab_clauses:
            st.markdown("#### Retrieved Policy Contract Text")
            for cid in assess.cited_clause_ids:
                st.info(f"**Clause [{cid}]**: Validated against master policy terms.")

        with tab_trace:
            st.markdown("#### LangGraph StateGraph Execution Trace")
            for step in assess.trace:
                st.markdown(
                    f"- **Step `{step.get('step')}`** at `{step.get('timestamp')}`: `{step}`"
                )

        # Human-in-the-Loop Review Panel
        st.divider()
        st.markdown("### 👤 Human Adjuster Review Panel")
        st.caption(
            "Human makes the final claim decision. Adjuster feedback resumes and finalizes the LangGraph StateGraph."
        )

        rev_col1, rev_col2 = st.columns([1, 2])

        with rev_col1:
            action_choice = st.selectbox("Action:", ["APPROVE", "OVERRIDE", "REJECT"])
            override_val = None
            if action_choice == "OVERRIDE":
                override_val = st.selectbox(
                    "Override To:", ["FAST_TRACK", "NEEDS_REVIEW", "ESCALATE_SIU"]
                )

        with rev_col2:
            notes_input = st.text_area(
                "Adjuster Compliance Notes:",
                "Claim details and repair receipts cross-checked. Approved for payment.",
            )

        if st.button("Submit Final Decision ➔", type="primary"):
            req = HumanReviewRequest(
                action=action_choice,
                override_decision=TriageDecisionEnum(override_val) if override_val else None,
                reviewer_notes=notes_input,
            )
            res = service.review_claim(assess.claim_id, req)
            st.success(
                f"Final Decision Recorded: {res.final_decision}. Graph execution finalized at {res.timestamp}."
            )

    st.divider()

    # Past Triage Audit Log Table
    st.markdown("### 📜 Past Triage Audit Trail (`triage_audit`)")
    audit_recs = audit_store.list_audit_records(limit=10)
    if audit_recs:
        st.dataframe(
            pd.DataFrame(audit_recs)[
                ["audit_id", "claim_id", "decision", "confidence", "created_at"]
            ],
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    render()
