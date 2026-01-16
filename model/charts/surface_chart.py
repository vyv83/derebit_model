"""
3D Volatility Surface Chart
============================
Renders 3D volatility surface visualization.
"""

import plotly.graph_objects as go
from dash import dcc, html

from config.theme import CHART_THEME, GLOBAL_CHART_STYLE, style_card, apply_chart_theme


def render_surface_chart(df):
    """
    Render 3D volatility surface chart.
    
    Args:
        df: DataFrame with prediction data
        
    Returns:
        html.Div with the 3D chart
    """
    # Plot Call IV Surface (Show ALL DTEs always)
    df_surf = df[df['type'] == 'call']
    
    fig_3d = go.Figure(data=[go.Scatter3d(
        x=df_surf['strike'],
        y=df_surf['dte'],
        z=df_surf['mark_iv'],
        mode='markers',
        marker=dict(
            size=3,
            color=df_surf['mark_iv'],
            colorscale='Viridis',
            opacity=0.8
        )
    )])
    
    apply_chart_theme(fig_3d, "Volatility Surface (3D)")
    fig_3d.update_layout(
        scene=dict(
            xaxis_title='Strike',
            yaxis_title='Days to Expiry',
            zaxis_title='IV (%)',
            xaxis=dict(gridcolor=CHART_THEME["grid_color"]),
            yaxis=dict(gridcolor=CHART_THEME["grid_color"]),
            zaxis=dict(gridcolor=CHART_THEME["grid_color"])
        ),
        margin=dict(l=0, r=0, b=0, t=40) 
    )
    
    return html.Div([
        dcc.Graph(id='volatility-surface-3d', figure=fig_3d, style=GLOBAL_CHART_STYLE)
    ], style=style_card)
