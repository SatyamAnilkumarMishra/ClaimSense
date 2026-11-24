"""ClaimSense: About, Limitations & Production Roadmap Page."""

import streamlit as st


def render():
    st.title("ℹ️ About, Limitations & Production Roadmap")
    st.markdown(
        "Honest architectural transparency, operational boundaries, and production evolution paths."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### ⚠️ Known Gaps & Limitations (Honest Disclosure)")
        st.markdown("""
        1. **Synthetic Data**: All customers, policies, and claims are synthetically generated (`seed=42`). No real PII or proprietary insurance data is used.
        2. **Free-Tier Limits**: Databricks Free Edition enforces daily compute quotas and auto-suspension. The application handles this through transparent local snapshot fallbacks.
        3. **Single Environment**: Due to zero-cost boundaries, there is no physical cloud multi-environment split (e.g. dev, staging, prod VPCs). The codebase is structured with clear configuration separation ready for Terraform-managed environments.
        4. **Batch Orientation**: Ingestion runs via micro-batches (`availableNow=True`) rather than continuous real-time Kafka/Kinesis streaming.
        """)

    with col2:
        st.markdown("### 🗺️ Production Enterprise Roadmap")
        st.markdown("""
        * **Orchestration**: Transition from Databricks Workflows to managed **Apache Airflow** or **Astronomer** DAGs for cross-cloud orchestration.
        * **Transformation**: Adopt **dbt Core** (`dbt-databricks`) for declarative SQL modeling, documentation, and data testing.
        * **Infrastructure as Code**: Manage Unity Catalog, clusters, and warehouses using **Terraform** Databricks provider.
        * **Streaming Ingestion**: Connect real-time claims intake queues using **Delta Live Tables (DLT)** with expectations.
        * **Multi-Modal AI**: Integrate Vision LLMs to automatically extract and verify photos of vehicular or structural damage.
        """)

    st.divider()

    st.markdown("### 👨‍💻 Project Links & Artifacts")
    st.markdown("""
    * **Project Name**: ClaimSense
    * **Repository**: Public GitHub Repository
    * **Evaluation Set**: 45 ground-truth claims with 0.0% unverifiable citation rate
    * **API Documentation**: Interactive OpenAPI / Swagger UI
    """)


if __name__ == "__main__":
    render()
