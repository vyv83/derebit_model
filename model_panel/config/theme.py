"""
Theme and Styling Configuration
================================
Centralized styling constants for the Neural Analytics Dashboard.
"""

# Color Palette
CUSTOM_CSS = {
    "background": "#F5F7F9",
    "card_bg": "#FFFFFF",
    "text_primary": "#2C3E50",
    "text_secondary": "#7F8C8D",
    "accent_call": "#76D7C4",
    "accent_put": "#FF8787",
    "accent_iv": "#9B59B6",
}

# Card Style
style_card = {
    "backgroundColor": CUSTOM_CSS["card_bg"],
    "borderRadius": "12px",
    "boxShadow": "0 2px 8px rgba(0,0,0,0.05)",
    "border": "none",
    "padding": "12px 20px",
    "marginBottom": "10px"
}

# Global Chart Style
GLOBAL_CHART_STYLE = {"height": "calc(100vh - 280px)", "minHeight": "500px"}

# Chart Theme Constants
CHART_THEME = {
    "title_size": 13,
    "axis_label_size": 10,
    "tick_size": 9,
    "grid_color": "rgba(200, 200, 200, 0.15)",
    "font_family": "'Inter', sans-serif"
}

# KPI Label Style
style_kpi_label = {
    "fontSize": "11px",
    "color": CUSTOM_CSS["text_secondary"],
    "textTransform": "uppercase",
    "letterSpacing": "0.5px",
    "marginBottom": "0px"
}


def apply_chart_theme(fig, title_text):
    """
    Universal approach for chart styling to ensure consistency across all tabs.
    
    Args:
        fig: Plotly figure object
        title_text: Chart title
    """
    fig.update_layout(
        title=dict(
            text=title_text,
            font=dict(size=CHART_THEME["title_size"], color=CUSTOM_CSS["text_primary"], weight=800),
            x=0.5, xanchor='center'
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family=CHART_THEME["font_family"], color=CUSTOM_CSS["text_primary"]),
        margin=dict(t=35, b=30, l=45, r=20),
        hovermode='x unified',
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=CHART_THEME["tick_size"], family=CHART_THEME["font_family"])
        ),
        uirevision='constant',
        modebar=dict(
            orientation='v',
            bgcolor='rgba(255, 255, 255, 0.0)',
            color='rgba(0, 0, 0, 0.2)',
            activecolor=CUSTOM_CSS["accent_iv"]
        )
    )
    
    # Standardize all existing X/Y axes in the figure
    fig.update_xaxes(
        gridcolor=CHART_THEME["grid_color"],
        showgrid=True,
        tickfont=dict(size=CHART_THEME["tick_size"], family=CHART_THEME["font_family"]),
        title_font=dict(size=CHART_THEME["axis_label_size"], family=CHART_THEME["font_family"])
    )
    fig.update_yaxes(
        gridcolor=CHART_THEME["grid_color"],
        showgrid=True,
        tickfont=dict(size=CHART_THEME["tick_size"], family=CHART_THEME["font_family"]),
        title_font=dict(size=CHART_THEME["axis_label_size"], family=CHART_THEME["font_family"])
    )
