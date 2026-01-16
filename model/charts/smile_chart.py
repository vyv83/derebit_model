"""
Volatility Smile Chart
======================
Renders volatility smile chart with cubic spline interpolation.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy.interpolate import make_interp_spline
from dash import dcc, html

from config.theme import CUSTOM_CSS, GLOBAL_CHART_STYLE, style_card


def render_smile_chart(df, market_state, selected_dtes):
    """
    Render volatility smile chart with cubic spline interpolation.
    
    Args:
        df: DataFrame with prediction data
        market_state: Market state dictionary
        selected_dtes: List of selected expiration dates (strings)
        
    Returns:
        html.Div with the chart
    """
    # selected_dtes are date strings
    current_date = pd.to_datetime(market_state['target_ts'])
    selected_dte_ints = [(pd.to_datetime(v) - current_date).days for v in selected_dtes]
    df_view = df[df['dte'].isin(selected_dte_ints)]
    
    # Plot just Calls IV (standard convention for Smile)
    df_plot = df_view[df_view['type'] == 'call'].copy()

    fig = go.Figure()
    colors = px.colors.qualitative.Plotly
    
    dtes = sorted(df_plot['dte'].unique())
    for i, dte in enumerate(dtes):
        df_dte = df_plot[df_plot['dte'] == dte].sort_values('strike')
        
        # Show actual points
        fig.add_trace(go.Scatter(
            x=df_dte['strike'], 
            y=df_dte['mark_iv'],
            mode='markers',
            name=f"{dte} DTE (actual)",
            marker=dict(size=5, opacity=0.4, color=colors[i % len(colors)]),
            showlegend=False
        ))
        
        # Add smooth spline if enough points
        if len(df_dte) >= 4:
            try:
                x, y = df_dte['strike'].values, df_dte['mark_iv'].values
                x_new = np.linspace(x.min(), x.max(), 200)
                spl = make_interp_spline(x, y, k=3)
                fig.add_trace(go.Scatter(
                    x=x_new, 
                    y=spl(x_new),
                    mode='lines',
                    name=f"{dte} DTE",
                    line=dict(width=2, color=colors[i % len(colors)])
                ))
            except:
                # Fallback to simple line
                fig.add_trace(go.Scatter(
                    x=df_dte['strike'], 
                    y=df_dte['mark_iv'],
                    mode='lines',
                    name=f"{dte} DTE",
                    line=dict(width=2, color=colors[i % len(colors)])
                ))
        else:
            fig.add_trace(go.Scatter(
                x=df_dte['strike'], 
                y=df_dte['mark_iv'],
                mode='lines+markers',
                name=f"{dte} DTE",
                line=dict(width=2, color=colors[i % len(colors)])
            ))
        
    # Add spot line with annotation (matching main dashboard style)
    spot = market_state['underlying_price']
    fig.add_vline(
        x=spot, 
        line_width=1, 
        line_color="rgba(180, 180, 180, 0.6)",
        line_dash="dash",
        annotation_text=f"${spot:,.0f}", 
        annotation_position="top left",
        annotation_font_size=10,
        annotation_font_color="gray"
    )
    
    fig.update_layout(
        title="Volatility Smile (Cubic Spline)",
        xaxis_title="Strike", 
        yaxis_title="IV (%)",
        plot_bgcolor="white", 
        paper_bgcolor="white", 
        font={"color": CUSTOM_CSS["text_primary"]},
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=50, b=50, l=50, r=20),
        hovermode="x unified"
    )
    
    return html.Div([
        dcc.Graph(figure=fig, style=GLOBAL_CHART_STYLE)
    ], style=style_card)
