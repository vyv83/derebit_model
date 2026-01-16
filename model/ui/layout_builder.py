"""
Layout Builder
==============
Builds the main application layout with all components.
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from config.theme import CUSTOM_CSS
from ui.components import build_control_dock


class LayoutBuilder:
    """
    Builds the main Dash application layout.
    Encapsulates all layout logic in a single class.
    """
    
    def __init__(self):
        """Initialize LayoutBuilder."""
        pass
    
    def _build_header_row(self):
        """Build the header row with title, selectors, and KPIs."""
        return dbc.Row([
            # Title
            dbc.Col([
                html.H4("Neural Volatility Analytics", 
                       style={"color": CUSTOM_CSS["text_primary"], "fontWeight": "800", 
                             "marginBottom": "0", "whiteSpace": "nowrap", "fontSize": "16px"}),
                html.Span("Model-Predicted Greeks & Smiles (AI View)", 
                         style={"color": CUSTOM_CSS["text_secondary"], "fontSize": "10px"})
            ], width="auto", className="pe-3"),
            
            # Selectors
            dbc.Col([
                html.Div([
                    # Currency
                    html.Div([
                        html.Label("CURRENCY", style={"fontSize": "10px", "fontWeight": "bold", 
                                                     "color": CUSTOM_CSS["text_secondary"], 
                                                     "marginBottom": "0", "display": "block"}),
                        dbc.RadioItems(
                            id="currency-selector",
                            options=[{"label": "BTC", "value": "BTC"}, {"label": "ETH", "value": "ETH"}],
                            value="BTC", inline=True, input_class_name="btn-check",
                            label_class_name="btn btn-sm btn-outline-primary rounded-pill px-2 py-0",
                            label_checked_class_name="active",
                            style={"gap": "3px", "display": "flex"}
                        )
                    ], className="me-2"),
                    
                    # Period
                    html.Div([
                        html.Label("PERIOD", style={"fontSize": "10px", "fontWeight": "bold", 
                                                   "color": CUSTOM_CSS["text_secondary"], 
                                                   "marginBottom": "0", "display": "block"}),
                        dbc.Select(id="period-selector", size="sm", 
                                 style={"borderRadius": "20px", "width": "100px", 
                                       "height": "24px", "fontSize": "11px", "padding": "0 10px"})
                    ]),
                ], className="d-flex align-items-end")
            ], width="auto"),

            # KPI Bar
            dbc.Col([
                html.Div([
                    # Spot Price
                    html.Div([
                        html.Div("PRICE", style={"fontSize": "11px", "fontWeight": "600", 
                                               "color": CUSTOM_CSS["text_secondary"], "letterSpacing": "0.05em"}),
                        html.Div("-", id="kpi-spot", style={"fontSize": "16px", "fontWeight": "800", 
                                                           "color": CUSTOM_CSS["text_primary"], "lineHeight": "1"})
                    ], className="px-3 border-end d-flex flex-column justify-content-center", 
                       style={"minWidth": "120px"}),
                    
                    # IV
                    html.Div([
                        html.Div("IV ATM", style={"fontSize": "11px", "fontWeight": "600", 
                                                 "color": CUSTOM_CSS["text_secondary"], "letterSpacing": "0.05em"}),
                        html.Div("-", id="kpi-atm-iv", style={"fontSize": "16px", "fontWeight": "800", 
                                                             "color": CUSTOM_CSS["text_primary"], "lineHeight": "1"})
                    ], className="px-3 border-end d-flex flex-column justify-content-center", 
                       style={"minWidth": "90px"}),
                    
                    # HV
                    html.Div([
                        html.Div("HV 30D", style={"fontSize": "11px", "fontWeight": "600", 
                                                 "color": CUSTOM_CSS["text_secondary"], "letterSpacing": "0.05em"}),
                        html.Div("-", id="kpi-hv", style={"fontSize": "16px", "fontWeight": "800", 
                                                         "color": CUSTOM_CSS["text_primary"], "lineHeight": "1"})
                    ], className="px-3 d-flex flex-column justify-content-center", 
                       style={"minWidth": "90px"}),
                ], className="d-flex align-items-center bg-white rounded shadow-sm border", 
                   style={"height": "52px", "marginLeft": "auto", "padding": "4px 0", 
                         "border": "1px solid #E0E6ED"})
            ], className="flex-grow-1 d-flex justify-content-end")
        ], className="py-1 border-bottom mb-1 align-items-end")
    
    def _build_expirations_row(self):
        """Build the expirations selector row."""
        return dbc.Row([
            dbc.Col([
                html.Div([
                    html.Div([
                        dbc.Checklist(
                            id="dte-selector",
                            options=[],
                            value=[],
                            inline=True,
                            input_class_name="btn-check",
                            label_class_name="btn btn-outline-primary btn-sm rounded-pill px-2 py-0",
                            label_style={"fontSize": "10px", "margin": "0"},
                            label_checked_class_name="active",
                            style={"gap": "3px", "display": "flex", "flexWrap": "nowrap"}
                        )
                    ], style={"overflowX": "auto", "whiteSpace": "nowrap", "padding": "0 5px", 
                             "scrollbarWidth": "none"})
                ], className="d-flex align-items-center bg-white rounded shadow-sm border", 
                   style={"height": "40px"})
            ], width=12)
        ], className="mb-2 g-2")
    
    def _build_tabs(self):
        """Build the main content tabs."""
        return dbc.Tabs([
            dbc.Tab(label="Neural Smile", tab_id="tab-smile", 
                   label_style={"fontSize": "13px", "padding": "6px 12px", "fontWeight": "500"}),
            dbc.Tab(label="Options Board", tab_id="tab-board",
                   label_style={"fontSize": "13px", "padding": "6px 12px", "fontWeight": "500"}),
            dbc.Tab(label="Vol Surface (3D)", tab_id="tab-surface",
                   label_style={"fontSize": "13px", "padding": "6px 12px", "fontWeight": "500"}),
            dbc.Tab(label="Strike Chart", tab_id="tab-strike",
                   label_style={"fontSize": "13px", "padding": "6px 12px", "fontWeight": "500"}),
        ], id="main-tabs", active_tab="tab-smile", style={"marginBottom": "10px"})
    
    def _build_chart_controls(self):
        """Build the floating chart controls for Strike Chart."""
        return html.Div([
            # Hidden Store for Robust Logic
            dcc.Store(id="chart-sublots-selector", data=['theta']),
            
            # Visual Buttons Container
            html.Div([
                dbc.Button(
                    [html.Span("VOL ", style={"fontSize": "9px", "opacity": "0.7"}), 
                     html.Span("OFF", id="btn-iv-label", style={"fontWeight": "800"})],
                    id="btn-toggle-iv",
                    size="sm", color="light",
                    style={
                        "padding": "1px 10px", "height": "24px", "borderRadius": "4px", "fontSize": "10px",
                        "border": "1px solid #ced4da",
                        "color": "#7F8C8D",
                        "backgroundColor": "rgba(255,255,255,0.8)", "boxShadow": "0 2px 4px rgba(0,0,0,0.05)",
                        "marginRight": "5px"
                    }
                ),
                dbc.Button(
                    [html.Span("THETA ", style={"fontSize": "9px", "opacity": "0.7"}), 
                     html.Span("ON", id="btn-theta-label", style={"fontWeight": "800"})],
                    id="btn-toggle-theta",
                    size="sm", color="light",
                    style={
                        "padding": "1px 10px", "height": "24px", "borderRadius": "4px", "fontSize": "10px",
                        "border": "1px solid #E67E22",
                        "color": "#E67E22",
                        "backgroundColor": "rgba(255,255,255,0.8)", "boxShadow": "0 2px 4px rgba(0,0,0,0.05)"
                    } 
                ),
            ], style={"display": "flex"})
        ], id="chart-controls-container", 
           style={"position": "absolute", "top": "25px", "left": "35px", "zIndex": "100", "display": "none"})
    
    def build(self):
        """
        Build the complete application layout.
        
        Returns:
            html.Div with complete layout
        """
        return html.Div([
            # Data Stores
            dcc.Store(id='market-state-store'),
            dcc.Store(id='prediction-results-store'),
            dcc.Store(id='timestamps-store', data=[]),
            dcc.Store(id='board-active-tab-store', data=None),
            dcc.Store(id='previous-dte-selection-store', data=[]),
            dcc.Store(id='selected-strike-store'),
            dcc.Store(id='iv-visibility-store', data=True),
            
            dbc.Container([
                # Header
                self._build_header_row(),
                
                # Expirations
                self._build_expirations_row(),
                
                # Tabs
                self._build_tabs(),
                
                # Content area with floating controls
                html.Div([
                    self._build_chart_controls(),
                    html.Div(id="tab-content")
                ], style={"position": "relative"})
            ], fluid=True, style={"maxWidth": "1800px", "paddingBottom": "100px"}),
            
            # Control dock
            build_control_dock()
        ], style={"backgroundColor": CUSTOM_CSS["background"], "minHeight": "100vh", 
                 "fontFamily": "'Inter', sans-serif"})
