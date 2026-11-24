"""Custom CSS design system for ClaimSense Streamlit UI.

Enforces deep navy background (#0A1128), vibrant teal accents (#00D2BA),
glassmorphism cards, rounded borders, and consistent typography.
"""

import streamlit as st


def apply_theme():
    """Injects custom global CSS into the Streamlit app."""
    st.markdown(
        """
    <style>
    /* Global Container Adjustments */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        padding-left: 2.5rem;
        padding-right: 2.5rem;
        max-width: 1300px;
    }

    /* KPI Cards */
    .kpi-container {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
    }
    .kpi-card {
        background: linear-gradient(135deg, #131F3F 0%, #0E172E 100%);
        border: 1px solid rgba(0, 210, 186, 0.2);
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        flex: 1;
        min-width: 200px;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: rgba(0, 210, 186, 0.5);
    }
    .kpi-title {
        color: #8E9FB5;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.35rem;
    }
    .kpi-value {
        color: #F0F4F8;
        font-size: 1.85rem;
        font-weight: 700;
    }
    .kpi-subtext {
        color: #00D2BA;
        font-size: 0.8rem;
        margin-top: 0.25rem;
    }

    /* Badges */
    .badge-fast-track {
        background-color: rgba(0, 210, 186, 0.15);
        color: #00D2BA;
        border: 1px solid #00D2BA;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .badge-needs-review {
        background-color: rgba(255, 179, 0, 0.15);
        color: #FFB300;
        border: 1px solid #FFB300;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .badge-escalate-siu {
        background-color: rgba(255, 75, 75, 0.15);
        color: #FF4B4B;
        border: 1px solid #FF4B4B;
        padding: 0.25rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }

    /* Architecture Pipeline Strip */
    .arch-strip {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #131F3F;
        border: 1px solid #1E2D56;
        border-radius: 10px;
        padding: 1rem 1.5rem;
        margin: 1.5rem 0;
        overflow-x: auto;
    }
    .arch-step {
        text-align: center;
        flex: 1;
        min-width: 100px;
    }
    .arch-label {
        color: #8E9FB5;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .arch-count {
        color: #00D2BA;
        font-size: 1.3rem;
        font-weight: 700;
    }
    .arch-arrow {
        color: #4A5D78;
        font-size: 1.5rem;
        margin: 0 0.5rem;
    }

    /* System Status Banner */
    .status-banner {
        padding: 0.75rem 1.25rem;
        border-radius: 8px;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .banner-live {
        background: rgba(0, 210, 186, 0.1);
        border: 1px solid #00D2BA;
        color: #00D2BA;
    }
    .banner-offline {
        background: rgba(255, 179, 0, 0.1);
        border: 1px solid #FFB300;
        color: #FFB300;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )
