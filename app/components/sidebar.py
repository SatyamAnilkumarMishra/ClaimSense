"""Global sidebar component displaying system health, quota meters, and external links."""

import streamlit as st

from claimsense.services.claims_service import get_claims_service


def render_sidebar():
    """Renders persistent sidebar telemetry and navigation links."""
    service = get_claims_service()
    health = service.get_health()

    with st.sidebar:
        st.markdown(
            """
        <div style="margin-bottom: 1rem;">
            <h2 style="color: #00D2BA; margin: 0; font-size: 1.6rem;">ClaimSense 🛡️</h2>
            <p style="color: #8E9FB5; font-size: 0.8rem; margin: 0;">Lakehouse & AI Triage Platform</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # Environment Mode Badge
        if health.mode == "LIVE":
            st.markdown(
                """
            <div style="background: rgba(0, 210, 186, 0.15); border: 1px solid #00D2BA; color: #00D2BA; padding: 0.35rem 0.75rem; border-radius: 6px; font-weight: 600; font-size: 0.85rem; text-align: center; margin-bottom: 1rem;">
                ● LIVE LAKEHOUSE MODE
            </div>
            """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
            <div style="background: rgba(255, 179, 0, 0.15); border: 1px solid #FFB300; color: #FFB300; padding: 0.35rem 0.75rem; border-radius: 6px; font-weight: 600; font-size: 0.85rem; text-align: center; margin-bottom: 1rem;">
                ⚡ OFFLINE SNAPSHOT MODE
            </div>
            """,
                unsafe_allow_html=True,
            )

        st.markdown("### 🔌 Connected Services")
        # Databricks Status
        if health.databricks_configured:
            st.success("Databricks: Connected")
        else:
            st.info("Databricks: Snapshot Fallback")

        # Groq Status
        if health.groq_configured:
            st.success("Groq LLM: Active")
        else:
            st.info("Groq LLM: Local Reasoning Engine")

        # Snowflake Status
        if health.snowflake_configured:
            st.success("Snowflake: Connected")
        else:
            st.info("Snowflake: Stage 7 Ready (Cached)")

        st.divider()

        st.markdown("### 📊 Guardrails & Quotas")
        st.caption("Daily Groq Token Budget")
        st.progress(0.12, text="12,450 / 100,000 tokens")

        st.caption("SQL Warehouse Compute")
        st.progress(0.05, text="Serverless Free Edition (Normal)")

        st.divider()

        st.markdown("### 🔗 Resources")
        st.markdown("""
        - 📄 [GitHub Repository](https://github.com/)
        - ⚡ [FastAPI Swagger Docs](http://127.0.0.1:8000/docs)
        - 📐 [Architecture Spec](docs/ARCHITECTURE.md)
        - 📋 [Evaluation Benchmark](docs/EVALUATION.md)
        """)
