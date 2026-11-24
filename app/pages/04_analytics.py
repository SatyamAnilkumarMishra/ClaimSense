"""ClaimSense: Claims Analytics & Star Schema BI Dashboard."""

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
    st.title("📈 Claims Analytics & Star Schema BI")
    st.markdown("Query the Gold star schema (`fact_claims`, `dim_customer`, `dim_policy`, `dim_claim_type`, `dim_date`) with live interactive filters.")

    service = get_claims_service()
    db = get_db_client()

    # Top KPI Metrics
    kpi = service.get_kpi_summary()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Total Valid Claims</div>
            <div class="kpi-value">{kpi.total_claims:,}</div>
            <div class="kpi-subtext">Gold Fact Grain: 1 row / claim</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Total Claimed Value</div>
            <div class="kpi-value">${kpi.total_claimed_amount:,.2f}</div>
            <div class="kpi-subtext">Avg: ${kpi.average_claimed_amount:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Avg Reporting Delay</div>
            <div class="kpi-value">{kpi.average_reporting_delay_days:.1f} Days</div>
            <div class="kpi-subtext">Incident to Intake</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">High Risk Rate</div>
            <div class="kpi-value" style="color: {'#FF4B4B' if kpi.high_risk_rate_percent > 20 else '#00D2BA'};">{kpi.high_risk_rate_percent:.1f}%</div>
            <div class="kpi-subtext">{kpi.high_risk_claims_count} Flagged Claims</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Interactive Filter Bar
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        claim_type_filter = st.selectbox("Filter Claim Type:", ["ALL", "AUTO", "HEALTH", "HOME"])
    with f_col2:
        status_filter = st.selectbox("Filter Status:", ["ALL", "SUBMITTED", "IN_REVIEW", "APPROVED", "SETTLED"])
    with f_col3:
        city_filter = st.selectbox("Filter Metro Region:", ["ALL", "Columbus", "Cleveland", "Cincinnati", "Chicago", "Indianapolis", "Detroit"])

    # Build dynamic Gold query
    query = """
        SELECT
            f.claim_id, f.incident_date, f.reported_date, f.reporting_delay_days,
            f.claimed_amount, f.claim_status, f.documents_count, f.city,
            f.flag_high_risk_customer,
            t.claim_type,
            p.policy_id, p.policy_type, p.sum_insured,
            u.customer_id, u.full_name, u.risk_score
        FROM fact_claims f
        JOIN dim_policy p ON f.policy_sk = p.policy_sk
        JOIN dim_customer u ON f.customer_sk = u.customer_sk
        JOIN dim_claim_type t ON f.claim_type_sk = t.claim_type_sk
        WHERE 1=1
    """
    params = []
    if claim_type_filter != "ALL":
        query += " AND t.claim_type = ?"
        params.append(claim_type_filter)
    if status_filter != "ALL":
        query += " AND f.claim_status = ?"
        params.append(status_filter)
    if city_filter != "ALL":
        query += " AND f.city = ?"
        params.append(city_filter)

    query += " ORDER BY f.incident_date DESC"
    raw_data = db.execute_query(query, params)
    df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()

    # Visualizations
    if not df.empty:
        ch_col1, ch_col2 = st.columns(2)

        with ch_col1:
            st.markdown("#### Claims Volume by Type")
            type_counts = df["claim_type"].value_counts().reset_index()
            type_counts.columns = ["claim_type", "count"]
            if HAS_PLOTLY:
                fig_type = px.pie(
                    type_counts,
                    names="claim_type",
                    values="count",
                    hole=0.45,
                    title="Claim Distribution by Coverage Class",
                )
                apply_plotly_theme(fig_type)
                st.plotly_chart(fig_type, use_container_width=True)
            else:
                st.bar_chart(type_counts.set_index("claim_type")["count"])

        with ch_col2:
            st.markdown("#### Claimed Amount Distribution")
            if HAS_PLOTLY:
                fig_amt = px.histogram(
                    df,
                    x="claimed_amount",
                    color="claim_type",
                    nbins=25,
                    title="Claim Value Histogram ($ USD)",
                    labels={"claimed_amount": "Claimed Amount ($)"},
                )
                apply_plotly_theme(fig_amt)
                st.plotly_chart(fig_amt, use_container_width=True)
            else:
                st.line_chart(df[["claimed_amount"]])

    st.divider()

    # Claim Detail Explorer
    st.markdown("### 🔍 Claims Explorer")
    if not df.empty:
        st.dataframe(
            df[[
                "claim_id", "policy_id", "full_name", "claim_type", "incident_date",
                "claimed_amount", "claim_status", "city", "documents_count"
            ]],
            use_container_width=True,
            hide_index=True,
        )

        csv_exp = df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Export Filtered Analytics (CSV)", data=csv_exp, file_name="claims_analytics_export.csv", mime="text/csv")
    else:
        st.info("No claims match the selected filter combination.")

    st.divider()

    # Star Schema Architecture Expander
    with st.expander("📐 Star Schema Architecture & Dimensional Modeling"):
        st.markdown("""
        ```text
           ┌────────────────┐           ┌─────────────────────────────┐           ┌──────────────────┐
           │  dim_customer  │           │         fact_claims         │           │    dim_policy    │
           ├────────────────┤           ├─────────────────────────────┤           ├──────────────────┤
           │ customer_sk PK │ 1       * │ claim_sk (PK)               │ *       1 │ policy_sk (PK)   │
           │ customer_id    │───────────│ customer_sk (FK)            │───────────│ policy_id        │
           │ full_name      │           │ policy_sk (FK)              │           │ customer_id (FK) │
           │ risk_score     │           │ claim_type_sk (FK)          │           │ policy_type      │
           │ city, state    │           │ incident_date_key (FK)      │           │ sum_insured      │
           └────────────────┘           │ reported_date_key (FK)      │           │ deductible       │
                                        │ claimed_amount (DECIMAL)    │           │ policy_status    │
                                        │ reporting_delay_days (INT)  │           └──────────────────┘
                                        │ documents_count (INT)       │
                                        │ is_settled (TINYINT)        │
                                        └──────────────┬──────────────┘
                                                       │ *
                                                       │
                                                       │ 1
                                        ┌──────────────┴──────────────┐
                                        │          dim_date           │
                                        ├─────────────────────────────┤
                                        │ date_key (PK, INT YYYYMMDD) │
                                        │ full_date (DATE)            │
                                        │ year, quarter, month        │
                                        │ is_weekend (TINYINT)        │
                                        └─────────────────────────────┘
        ```
        """)


if __name__ == "__main__":
    render()
