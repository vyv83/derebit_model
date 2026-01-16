"""
UI Components
=============
Reusable UI components for the dashboard.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from config.theme import CUSTOM_CSS, style_card, style_kpi_label


def build_kpi_card(title, id_value):
    """
    Build a KPI card component.
    
    Args:
        title: Card title
        id_value: ID for the value display element
        
    Returns:
        dbc.Card component
    """
    return dbc.Card([
        html.Div(title, style=style_kpi_label),
        html.Div("-", id=id_value, style={
            "fontSize": "18px", 
            "fontWeight": "bold", 
            "color": CUSTOM_CSS["text_primary"]
        }),
    ], style=style_card)


def build_control_dock():
    """
    Build the time control dock (slider + play/back buttons).
    
    Returns:
        html.Div component with time controls
    """
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Span("TIME SNAPSHOT SELECTOR", style={
                        "fontSize": "10px", 
                        "fontWeight": "bold", 
                        "color": CUSTOM_CSS["text_secondary"]
                    }),
                    html.Span(id="time-display", style={
                        "fontSize": "10px", 
                        "fontWeight": "bold", 
                        "color": CUSTOM_CSS["text_primary"], 
                        "marginLeft": "10px"
                    })
                ], style={"marginBottom": "5px"}),
                dcc.Slider(
                    id="time-slider", min=0, max=1, value=0, disabled=True,
                    marks={0: 'Jan', 1: 'Dec'}, updatemode='drag'
                ),
            ], width=10),
            dbc.Col([
                html.Div([
                    dbc.Button("◀", id="btn-back", color="light", size="sm", 
                               style={
                                   "borderRadius": "50%", 
                                   "width": "35px", 
                                   "height": "35px", 
                                   "marginRight": "5px", 
                                   "display": "flex", 
                                   "alignItems": "center", 
                                   "justifyContent": "center", 
                                   "fontSize": "12px"
                               }),
                    dbc.Button("▶", id="btn-play", color="light", size="sm", 
                               style={
                                   "borderRadius": "50%", 
                                   "width": "35px", 
                                   "height": "35px", 
                                   "display": "flex", 
                                   "alignItems": "center", 
                                   "justifyContent": "center", 
                                   "fontSize": "12px"
                               })
                ], className="d-flex align-items-center justify-content-center")
            ], width=2)
        ])
    ], style={
        "position": "fixed", 
        "bottom": "0", 
        "left": "0", 
        "width": "100%",
        "backgroundColor": "rgba(255, 255, 255, 0.95)", 
        "borderTop": "1px solid #E0E0E0",
        "padding": "15px 40px", 
        "zIndex": "1000", 
        "backdropFilter": "blur(5px)"
    })
