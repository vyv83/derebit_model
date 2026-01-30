"""
Smile View
==========
Volatility smile chart with cubic spline interpolation.
Shows only Calls (standard convention).
"""

import panel as pn
import param
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy.interpolate import make_interp_spline

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.theme import CUSTOM_CSS, CHART_THEME, apply_chart_theme


class SmileView(pn.viewable.Viewer):
    """Volatility Smile chart view."""
    
    def __init__(self, state, **params):
        super().__init__(**params)
        self.state = state
    
    def _render_chart(self):
        """Render the volatility smile chart."""
        # Get predictions as DataFrame
        df = self.state.get_predictions_df()
        
        if df.empty:
            return self._empty_message("No prediction data available")
        
        market_state = self.state.market_state
        selected_dtes = self.state.selected_dtes
        
        if not market_state or 'target_ts' not in market_state:
            return self._empty_message("Market state not available")
        
        if not selected_dtes:
            return self._empty_message("Please select at least one expiration")
        
        # Filter by selected DTEs
        current_date = pd.to_datetime(market_state['target_ts'])
        selected_dte_ints = [(pd.to_datetime(v) - current_date).days for v in selected_dtes]
        df_view = df[df['dte'].isin(selected_dte_ints)]
        
        # Plot just Calls IV (standard convention for Smile)
        df_plot = df_view[df_view['type'] == 'call'].copy()
        
        if df_plot.empty:
            return self._empty_message("No call option data for selected expirations")
        
        fig = go.Figure()
        colors = px.colors.qualitative.Plotly
        
        dtes = sorted(df_plot['dte'].unique())
        for i, dte in enumerate(dtes):
            df_dte = df_plot[df_plot['dte'] == dte].sort_values('strike')
            color = colors[i % len(colors)]
            
            # Show actual points (hidden in legend)
            fig.add_trace(go.Scatter(
                x=df_dte['strike'], 
                y=df_dte['mark_iv'],
                mode='markers',
                name=f"{dte} DTE (actual)",
                marker=dict(size=5, opacity=0.4, color=color),
                showlegend=False
            ))
            
            # Add smooth spline if enough points
            if len(df_dte) >= 4:
                try:
                    x = df_dte['strike'].values
                    y = df_dte['mark_iv'].values
                    x_new = np.linspace(x.min(), x.max(), 200)
                    spl = make_interp_spline(x, y, k=3)
                    fig.add_trace(go.Scatter(
                        x=x_new, 
                        y=spl(x_new),
                        mode='lines',
                        name=f"{dte} DTE",
                        line=dict(width=2, color=color)
                    ))
                except Exception:
                    # Fallback to simple line
                    fig.add_trace(go.Scatter(
                        x=df_dte['strike'], 
                        y=df_dte['mark_iv'],
                        mode='lines',
                        name=f"{dte} DTE",
                        line=dict(width=2, color=color)
                    ))
            else:
                # Few points: use lines+markers
                fig.add_trace(go.Scatter(
                    x=df_dte['strike'], 
                    y=df_dte['mark_iv'],
                    mode='lines+markers',
                    name=f"{dte} DTE",
                    line=dict(width=2, color=color)
                ))
        
        # Add spot line with annotation
        spot = market_state.get('underlying_price', 0)
        if spot:
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
        
        # Apply theme
        apply_chart_theme(fig, "Volatility Smile (Cubic Spline)")
        
        fig.update_layout(
            xaxis_title="Strike", 
            yaxis_title="IV (%)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=50, b=50, l=50, r=20),
            hovermode="x unified"
        )
        
        return pn.pane.Plotly(fig, sizing_mode='stretch_both', min_height=400)
    
    def _empty_message(self, message):
        """Create empty state message."""
        return pn.pane.HTML(
            f'''
            <div class="placeholder-message">
                <h5>Volatility Smile</h5>
                <p>{message}</p>
            </div>
            ''',
            sizing_mode='stretch_both'
        )
    
    @param.depends('state.predictions', 'state.selected_dtes', 'state.market_state')
    def __panel__(self):
        return pn.Column(
            self._render_chart(),
            css_classes=['card'],
            sizing_mode='stretch_both'
        )
