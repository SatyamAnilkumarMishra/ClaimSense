"""ClaimSense: Streamlit Multi-Page Entrypoint Application."""

import streamlit as st

from app.components.sidebar import render_sidebar
from app.styles.theme import apply_theme

# Page Configuration
st.set_page_config(
    page_title="ClaimSense | Insurance Lakehouse & AI Triage",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply global dark styling & sidebar
apply_theme()
render_sidebar()

# Define Navigation Pages using st.Page
pages = [
    st.Page("pages/01_overview.py", title="Overview", icon="🏠", default=True),
    st.Page("pages/02_pipeline.py", title="Pipeline Control Room", icon="⚙️"),
    st.Page("pages/03_data_quality.py", title="Data Quality", icon="🛡️"),
    st.Page("pages/04_analytics.py", title="Claims Analytics", icon="📈"),
    st.Page("pages/05_triage_agent.py", title="Triage Agent", icon="🤖"),
    st.Page("pages/06_snowflake.py", title="Snowflake Serving", icon="❄️"),
    st.Page("pages/07_evaluation.py", title="Evaluation", icon="🎯"),
    st.Page("pages/08_architecture.py", title="Architecture & Decisions", icon="🏛️"),
    st.Page("pages/09_about.py", title="About & Roadmap", icon="ℹ️"),
]

nav = st.navigation(pages)
nav.run()
