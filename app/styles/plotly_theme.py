"""Shared Plotly theme matching the ClaimSense dark design system."""

import plotly.graph_objects as go

PLOTLY_COLORWAY = ["#00D2BA", "#4361EE", "#FFB300", "#FF4B4B", "#9D4EDD", "#2EC4B6"]


def apply_plotly_theme(fig: go.Figure) -> go.Figure:
    """Applies deep navy and vibrant teal styling to any Plotly figure."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(19, 31, 63, 0.5)",
        font=dict(color="#F0F4F8", family="sans-serif"),
        colorway=PLOTLY_COLORWAY,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(
            gridcolor="rgba(255, 255, 255, 0.08)",
            zerolinecolor="rgba(255, 255, 255, 0.15)",
            tickfont=dict(color="#8E9FB5"),
        ),
        yaxis=dict(
            gridcolor="rgba(255, 255, 255, 0.08)",
            zerolinecolor="rgba(255, 255, 255, 0.15)",
            tickfont=dict(color="#8E9FB5"),
        ),
        legend=dict(
            font=dict(color="#F0F4F8"),
            bgcolor="rgba(19, 31, 63, 0.7)",
            bordercolor="rgba(255, 255, 255, 0.1)",
        ),
    )
    return fig
