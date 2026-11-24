"""ClaimSense: Data Quality & Quarantine View."""

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    from app.styles.plotly_theme import apply_plotly_theme
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

from claimsense.db.client_factory import get_db_client
from claimsense.services.claims_service import get_claims_service


def render():
    st.title("🛡️ Data Quality & Quarantine View")
    st.markdown("Inspect defective claim rows quarantined during Silver transformation, analyze violation patterns, and examine before/after remediation lineages.")

    service = get_claims_service()
    db = get_db_client()

    # Quarantine Summary Metrics
    q_data = service.get_quality_summary()
    total_q = q_data["total_quarantined"]

    st.markdown("### 📊 Quarantine Rejection Distribution")

    col_chart, col_stats = st.columns([2, 1])

    with col_chart:
        df_rules = pd.DataFrame(q_data["rule_breakdown"])
        if not df_rules.empty:
            if HAS_PLOTLY:
                fig = px.bar(
                    df_rules,
                    x="reject_reason",
                    y="failed_count",
                    color="reject_reason",
                    labels={"reject_reason": "Rejection Code", "failed_count": "Quarantined Rows"},
                    title="Quarantined Records by Violation Rule",
                )
                apply_plotly_theme(fig)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(df_rules.set_index("reject_reason")["failed_count"])

    with col_stats:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Total Quarantined</div>
            <div class="kpi-value" style="color: #FFB300;">{total_q}</div>
            <div class="kpi-subtext">Isolated from Gold Analytics</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        #### 🛑 Rule Hierarchy
        * `ERR_DUP_CLAIM`: Duplicate batch transmission
        * `ERR_NULL_INCIDENT_DATE`: Missing temporal event
        * `ERR_INVALID_AMOUNT`: Zero or negative claim value
        * `ERR_ORPHAN_POLICY`: Broken foreign key linkage
        * `ERR_FUTURE_INCIDENT_DATE`: Temporal anomaly
        """)

    st.divider()

    # Filterable Quarantine Table
    st.markdown("### 📋 Quarantined Records Explorer")

    reasons_list = ["ALL"] + [r["reject_reason"] for r in q_data["rule_breakdown"]]
    selected_reason = st.selectbox("Filter by Rejection Reason:", reasons_list)

    query = "SELECT claim_id, policy_id, claim_type, raw_incident_date, raw_claimed_amount, raw_status, reject_reason, _source_file, quarantined_at FROM quarantine_claims"
    if selected_reason != "ALL":
        query += f" WHERE reject_reason = '{selected_reason}'"
    query += " ORDER BY quarantine_id DESC LIMIT 50"

    q_rows = db.execute_query(query)
    if q_rows:
        df_q = pd.DataFrame(q_rows)
        st.dataframe(df_q, use_container_width=True, hide_index=True)

        # CSV Download
        csv_bytes = df_q.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Quarantined Records as CSV",
            data=csv_bytes,
            file_name="quarantined_claims_export.csv",
            mime="text/csv",
        )

    st.divider()

    # Before and After Dirty Record Comparison
    st.markdown("### 🔄 Dirty vs. Remediated Data Comparison")
    st.caption("Side-by-side view showing raw upstream messiness vs. Silver cleaned output.")

    col_dirty, col_clean = st.columns(2)

    with col_dirty:
        st.markdown("""
        <div style="background: rgba(255, 75, 75, 0.08); border: 1px solid rgba(255, 75, 75, 0.3); border-radius: 8px; padding: 1rem;">
            <h4 style="color: #FF4B4B; margin-top: 0;">❌ Raw Bronze Record (Messy)</h4>
            <code>
            claim_id: "CLM-30018"<br>
            policy_id: "POL-20042"<br>
            incident_date: "2026-04-12"<br>
            claimed_amount: "4500.00"<br>
            status: "  in_review  " (whitespace/casing)<br>
            documents_count: null<br>
            city: "  columbus  "<br>
            duplicate_row_present: YES
            </code>
        </div>
        """, unsafe_allow_html=True)

    with col_clean:
        st.markdown("""
        <div style="background: rgba(0, 210, 186, 0.08); border: 1px solid rgba(0, 210, 186, 0.3); border-radius: 8px; padding: 1rem;">
            <h4 style="color: #00D2BA; margin-top: 0;">✅ Silver Remediated Record</h4>
            <code>
            claim_id: "CLM-30018"<br>
            policy_id: "POL-20042"<br>
            incident_date: 2026-04-12 (DATE)<br>
            claimed_amount: $4,500.00 (DECIMAL)<br>
            status: "IN_REVIEW" (standardized enum)<br>
            documents_count: 0 (default null coalesce)<br>
            city: "Columbus" (trimmed)<br>
            deduplicated: YES (Window row_number = 1)
            </code>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    render()
