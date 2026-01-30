"""
Surface View
=============
3D volatility surface visualization.
Shows Scatter3d (points, not mesh) for ALL expirations.
"""

import panel as pn
import param
import pandas as pd
import plotly.graph_objects as go

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.theme import CHART_THEME, apply_chart_theme


class SurfaceView(pn.viewable.Viewer):
    """3D Volatility Surface chart view."""
    
    def __init__(self, state, **params):
        super().__init__(**params)
        self.state = state
    
    def _render_chart(self):
        """Render the 3D volatility surface chart."""
        # Get predictions as DataFrame
        df = self.state.get_predictions_df()
        
        if df.empty:
            return self._empty_message("No prediction data available")
        
        # Plot Call IV Surface - ALL DTEs (not filtered by selected_dtes!)
        df_surf = df[df['type'] == 'call']
        
        if df_surf.empty:
            return self._empty_message("No call option data available")
        
        fig = go.Figure(data=[go.Scatter3d(
            x=df_surf['strike'],
            y=df_surf['dte'],
            z=df_surf['mark_iv'],
            mode='markers',
            marker=dict(
                size=3,
                color=df_surf['mark_iv'],
                colorscale='Viridis',
                opacity=0.8,
                colorbar=dict(title='IV (%)')
            )
        )])
        
        # Apply theme
        apply_chart_theme(fig, "Volatility Surface (3D)")
        
        # Special layout for 3D
        fig.update_layout(
            scene=dict(
                xaxis_title='Strike',
                yaxis_title='Days to Expiry',
                zaxis_title='IV (%)',
                xaxis=dict(gridcolor=CHART_THEME["grid_color"]),
                yaxis=dict(gridcolor=CHART_THEME["grid_color"]),
                zaxis=dict(gridcolor=CHART_THEME["grid_color"])
            ),
            margin=dict(l=0, r=0, b=0, t=40)  # Different margins for 3D!
        )
        
        return pn.pane.Plotly(fig, sizing_mode='stretch_both', min_height=500)
    
    def _empty_message(self, message):
        """Create empty state message."""
        return pn.pane.HTML(
            f'''
            <div class="placeholder-message">
                <h5>Volatility Surface</h5>
                <p>{message}</p>
            </div>
            ''',
            sizing_mode='stretch_both'
        )
    
    @param.depends('state.predictions')
    def __panel__(self):
        return pn.Column(
            self._render_chart(),
            css_classes=['card'],
            sizing_mode='stretch_both'
        )
