import dash
from dash import dcc, html, Input, Output, State, callback, ALL, MATCH
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import os
import glob
import sys
from datetime import datetime, timedelta
from scipy.stats import norm

# Ensure local imports work regardless of CWD
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from model_wrapper import OptionModel
from daily_data_provider import DailyFeatureProvider
from deribit_option_logic import generate_deribit_expirations, generate_deribit_strikes, get_birth_date, calculate_time_layers
from option_timeseries_provider import OptionTimeseriesProvider

# --- Black-Scholes Helper ---
def black_scholes(S, K, T, r, sigma, option_type='call'):
    if T <= 0 or sigma <= 0:
        price = max(0, S - K) if option_type == 'call' else max(0, K - S)
        return price, 0.0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        # Annualized Theta
        theta = (- (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) 
                 - r * K * np.exp(-r * T) * norm.cdf(d2))
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        # Annualized Theta
        theta = (- (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) 
                 + r * K * np.exp(-r * T) * norm.cdf(-d2))
    
    # Return price and daily theta
    return price, theta / 365.0

# --- App Initialization ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "Neural Analytics Dashboard"

# Load Model and Provider
try:
    model_path = os.path.join(BASE_DIR, 'neural_svi_v2_multitask_final.pth')
    model = OptionModel(model_path=model_path)
    
    price_csv = os.path.join(BASE_DIR, 'btc_full_history.csv')
    vol_csv = os.path.join(BASE_DIR, 'btc_dvol_history.csv')
    provider = DailyFeatureProvider(price_file=price_csv, dvol_file=vol_csv)
    
    # Initialize timeseries provider for candlestick charts
    timeseries_provider = OptionTimeseriesProvider()
    
    print("CORE INITIALIZED SUCCESSFULLY")
except Exception as e:
    print(f"FAILED TO INITIALIZE CORE: {e}")
    import traceback
    traceback.print_exc()
    model = None
    provider = None
    timeseries_provider = None

# --- Styling & Configuration ---
CUSTOM_CSS = {
    "background": "#F5F7F9",
    "card_bg": "#FFFFFF",
    "text_primary": "#2C3E50",
    "text_secondary": "#7F8C8D",
    "accent_call": "#76D7C4",
    "accent_put": "#FF8787",
}

style_card = {
    "backgroundColor": CUSTOM_CSS["card_bg"],
    "borderRadius": "12px",
    "boxShadow": "0 2px 8px rgba(0,0,0,0.05)",
    "border": "none",
    "padding": "12px 20px",
    "marginBottom": "10px"
}

style_kpi_label = {
    "fontSize": "11px",
    "color": CUSTOM_CSS["text_secondary"],
    "textTransform": "uppercase",
    "letterSpacing": "0.5px",
    "marginBottom": "0px"
}

# --- Layout Components ---
def build_kpi_card(title, id_value):
    return dbc.Card([
        html.Div(title, style=style_kpi_label),
        html.Div("-", id=id_value, style={"fontSize": "18px", "fontWeight": "bold", "color": CUSTOM_CSS["text_primary"]}),
    ], style=style_card)

def build_control_dock():
    return html.Div([
        dbc.Row([
            dbc.Col([
                html.Div([
                    html.Span("TIME SNAPSHOT SELECTOR", style={"fontSize": "10px", "fontWeight": "bold", "color": CUSTOM_CSS["text_secondary"]}),
                    html.Span(id="time-display", style={"fontSize": "10px", "fontWeight": "bold", "color": CUSTOM_CSS["text_primary"], "marginLeft": "10px"})
                ], style={"marginBottom": "5px"}),
                dcc.Slider(
                    id="time-slider", min=0, max=1, value=0, disabled=True,
                    marks={0: 'Jan', 1: 'Dec'}, updatemode='drag'
                ),
            ], width=10),
            dbc.Col([
                html.Div([
                    dbc.Button("◀", id="btn-back", color="light", size="sm", 
                               style={"borderRadius": "50%", "width": "35px", "height": "35px", "marginRight": "5px", "display": "flex", "alignItems": "center", "justifyContent": "center", "fontSize": "12px"}),
                    dbc.Button("▶", id="btn-play", color="light", size="sm", 
                               style={"borderRadius": "50%", "width": "35px", "height": "35px", "display": "flex", "alignItems": "center", "justifyContent": "center", "fontSize": "12px"})
                ], className="d-flex align-items-center justify-content-center")
            ], width=2)
        ])
    ], style={
        "position": "fixed", "bottom": "0", "left": "0", "width": "100%",
        "backgroundColor": "rgba(255, 255, 255, 0.95)", "borderTop": "1px solid #E0E0E0",
        "padding": "15px 40px", "zIndex": "1000", "backdropFilter": "blur(5px)"
    })

# --- Main Layout ---
app.layout = html.Div([
    dcc.Store(id='market-state-store'),
    dcc.Store(id='prediction-results-store'),
    dcc.Store(id='timestamps-store', data=[]),
    dcc.Store(id='board-active-tab-store', data=None),
    dcc.Store(id='selected-strike-store'),  # Stores strike selection: {strike, type, exp_date}
    
    dbc.Container([
        # 1. Header Row (Title + Selectors + KPIs)
        dbc.Row([
            # Title
            dbc.Col([
                html.H4("Neural Volatility Analytics", style={"color": CUSTOM_CSS["text_primary"], "fontWeight": "800", "marginBottom": "0", "whiteSpace": "nowrap", "fontSize": "16px"}),
                html.Span("Model-Predicted Greeks & Smiles (AI View)", style={"color": CUSTOM_CSS["text_secondary"], "fontSize": "10px"})
            ], width="auto", className="pe-3"),
            
            # Selectors
            dbc.Col([
                html.Div([
                    # Currency
                    html.Div([
                        html.Label("CURRENCY", style={"fontSize": "10px", "fontWeight": "bold", "color": CUSTOM_CSS["text_secondary"], "marginBottom": "0", "display": "block"}),
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
                        html.Label("PERIOD", style={"fontSize": "10px", "fontWeight": "bold", "color": CUSTOM_CSS["text_secondary"], "marginBottom": "0", "display": "block"}),
                        dbc.Select(id="period-selector", size="sm", style={"borderRadius": "20px", "width": "100px", "height": "24px", "fontSize": "11px", "padding": "0 10px"})
                    ]),
                ], className="d-flex align-items-end")
            ], width="auto"),

            # KPI Bar (Moved to top right - PREVIEW STYLE)
            dbc.Col([
                html.Div([
                    # Spot Price
                    html.Div([
                        html.Div("PRICE", style={"fontSize": "11px", "fontWeight": "600", "color": CUSTOM_CSS["text_secondary"], "letterSpacing": "0.05em"}),
                        html.Div("-", id="kpi-spot", style={"fontSize": "16px", "fontWeight": "800", "color": CUSTOM_CSS["text_primary"], "lineHeight": "1"})
                    ], className="px-3 border-end d-flex flex-column justify-content-center", style={"minWidth": "120px"}),
                    
                    # IV
                    html.Div([
                        html.Div("IV ATM", style={"fontSize": "11px", "fontWeight": "600", "color": CUSTOM_CSS["text_secondary"], "letterSpacing": "0.05em"}),
                        html.Div("-", id="kpi-atm-iv", style={"fontSize": "16px", "fontWeight": "800", "color": CUSTOM_CSS["text_primary"], "lineHeight": "1"})
                    ], className="px-3 border-end d-flex flex-column justify-content-center", style={"minWidth": "90px"}),
                    
                    # HV
                    html.Div([
                        html.Div("HV 30D", style={"fontSize": "11px", "fontWeight": "600", "color": CUSTOM_CSS["text_secondary"], "letterSpacing": "0.05em"}),
                        html.Div("-", id="kpi-hv", style={"fontSize": "16px", "fontWeight": "800", "color": CUSTOM_CSS["text_primary"], "lineHeight": "1"})
                    ], className="px-3 d-flex flex-column justify-content-center", style={"minWidth": "90px"}),
                ], className="d-flex align-items-center bg-white rounded shadow-sm border", style={"height": "52px", "marginLeft": "auto", "padding": "4px 0", "border": "1px solid #E0E6ED"})
            ], className="flex-grow-1 d-flex justify-content-end")
        ], className="py-1 border-bottom mb-1 align-items-end"),
        
        # 2. Expirations Row
        dbc.Row([
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
                     ], style={"overflowX": "auto", "whiteSpace": "nowrap", "padding": "0 5px", "scrollbarWidth": "none"})
                 ], className="d-flex align-items-center bg-white rounded shadow-sm border", style={"height": "40px"})
            ], width=12)
        ], className="mb-2 g-2"),

        # 3. Main Content Tabs
        dbc.Tabs([
            dbc.Tab(label="Neural Smile", tab_id="tab-smile"),
            dbc.Tab(label="Options Board", tab_id="tab-board"),
            dbc.Tab(label="Vol Surface (3D)", tab_id="tab-surface"),
            dbc.Tab(label="Strike Chart", tab_id="tab-strike"),
        ], id="main-tabs", active_tab="tab-smile", style={"marginBottom": "10px"}),

        html.Div(id="tab-content")
    ], fluid=True, style={"maxWidth": "1800px", "paddingBottom": "100px"}),
    
    build_control_dock()
], style={"backgroundColor": CUSTOM_CSS["background"], "minHeight": "100vh", "fontFamily": "'Inter', sans-serif"})

# --- Callbacks ---

@callback(
    [Output("period-selector", "options"),
     Output("period-selector", "value")],
    [Input("currency-selector", "value")]
)
def update_periods(currency):
    print(f"TRIGGER: update_periods for {currency}")
    # Return just recent years
    years = ['2021', '2022', '2023', '2024', '2025']
    options = [{"label": y, "value": y} for y in years]
    return options, '2024'

@callback(
    [Output('time-slider', 'min'),
     Output('time-slider', 'max'),
     Output('time-slider', 'value'),
     Output('time-slider', 'marks'),
     Output('time-slider', 'disabled'),
     Output('timestamps-store', 'data')],
    [Input("currency-selector", "value"),
     Input("period-selector", "value"),
     Input('btn-play', 'n_clicks'),
     Input('btn-back', 'n_clicks')],
    [State('time-slider', 'value'),
     State('time-slider', 'max')]
)
def update_time_slider_logic(currency, period, play_clicks, back_clicks, current_val, max_val):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    
    # Handle manual step arrows
    if trigger_id in ['btn-play', 'btn-back']:
        if current_val is None or max_val is None:
            return [dash.no_update, dash.no_update, 0, dash.no_update, dash.no_update, dash.no_update]
            
        if trigger_id == 'btn-play':
            new_val = (current_val + 1) if current_val < max_val else 0
        else: # btn-back
            new_val = (current_val - 1) if current_val > 0 else max_val
            
        return [dash.no_update, dash.no_update, new_val, dash.no_update, dash.no_update, dash.no_update]
    
    # Configuration update
    if not currency: currency = 'BTC'
    if not period: period = '2024'
    
    all_dates = provider.get_date_range()
    year_dates = all_dates[all_dates.year == int(period)]
    
    if len(year_dates) == 0:
        return 0, 1, 0, {}, True, []
        
    ts_str = [d.strftime("%Y-%m-%d") for d in year_dates]
    new_max = len(ts_str) - 1
    
    marks = {}
    for i, d in enumerate(year_dates):
        if d.day == 1:
            marks[i] = {'label': d.strftime("%b"), 'style': {'fontSize': '10px'}}
    
    return 0, new_max, 0, marks, False, ts_str

@callback(
    [Output('market-state-store', 'data'),
     Output('kpi-spot', 'children'),
     Output('kpi-atm-iv', 'children'),
     Output('kpi-hv', 'children'),
     Output('time-display', 'children')],
    [Input('time-slider', 'value'),
     Input('timestamps-store', 'data')],
    [State('currency-selector', 'value')]
)
def update_market_state(slider_idx, timestamps, currency):
    print(f"MARKET_STATE_CB: idx={slider_idx}, len_ts={len(timestamps) if timestamps else 0}")
    # Ensure raw types and existence
    if not timestamps:
        return {}, "-", "-", "-", "TIME SNAPSHOT: -"
    
    # Dash Input might be None or String on first load
    idx = 0
    if slider_idx is not None:
        try:
            idx = int(slider_idx)
        except:
            idx = 0
            
    if idx >= len(timestamps):
        idx = 0
        
    target_ts = timestamps[idx]
    print(f"DEBUG: Processing TS {target_ts}")
    state = provider.get_market_state(target_ts)
    
    if not state:
        return {}, "N/A", "N/A", "N/A", f"TIME SNAPSHOT: {target_ts}"
        
    spot = state['underlying_price']
    atm_iv = state.get('Real_IV_ATM', 0) * 100
    hv = state.get('HV_30d', 0) * 100
    
    # Convert ts for serializability
    state['target_ts'] = str(target_ts)
    state['currency'] = currency # Ensure currency is in state
    
    return (state, f"${spot:,.2f}", f"{atm_iv:.1f}%", f"{hv:.1f}%", 
            f"TIME SNAPSHOT: {pd.to_datetime(target_ts).strftime('%d %b %Y')}")
# Step button logic merged with update_time_slider_logic to avoid duplicate outputs

@callback(
    [Output("dte-selector", "options"),
     Output("dte-selector", "value")],
    [Input("market-state-store", "data")],
    [State("dte-selector", "value")]
)
def update_expiration_options(market_state, current_values):
    if not market_state or 'target_ts' not in market_state:
        return [], []
    
    current_date = pd.to_datetime(market_state['target_ts'])
    exps = generate_deribit_expirations(current_date)
    
    options = []
    for d, count in exps:
        dte = (d - current_date).days
        if dte < 0: continue
        label = f"{d.strftime('%d %b')} ({dte}d)"
        # Value is absolute date to keep selection "sticky"
        value = d.strftime('%Y-%m-%d')
        options.append({"label": label, "value": value})
    
    # Selection logic: pick first 3 by default if none selected or if previous selection invalid
    new_values = []
    if current_values:
        # Try to keep existing DTEs if they still exist
        valid_options = [opt['value'] for opt in options]
        new_values = [v for v in current_values if v in valid_options]
        
    if not new_values and options:
        # Default to the first few liquid ones (e.g. Weekly, Monthly)
        new_values = [options[i]['value'] for i in range(min(3, len(options)))]
        
    return options, new_values

@callback(
    Output('prediction-results-store', 'data'),
    [Input('market-state-store', 'data'),
     Input('dte-selector', 'value')]
)
def run_model_inference(market_state, selected_exp_values):
    if not market_state or not model or not selected_exp_values:
        return []
        
    spot = market_state['underlying_price']
    # Use real ATM IV from provider if available, otherwise fallback to HV or constant
    vol = market_state.get('Real_IV_ATM', market_state.get('HV_30d', 0.80))
    
    results = []
    
    # Calculate predictions for ALL available expirations to support 3D surface
    current_date = pd.to_datetime(market_state['target_ts'])
    all_exps = generate_deribit_expirations(current_date)
    
    parsed_exps = []
    for d, count in all_exps:
        dte_val = (d - current_date).days
        if dte_val < 0: continue
        
        # Determine Anchor (Birth) Parameters
        birth_date, birth_dte = get_birth_date(d)
        anchor_state = provider.get_market_state(birth_date)
        
        if anchor_state:
            anchor_spot = anchor_state['underlying_price']
            anchor_vol = anchor_state.get('Real_IV_ATM', anchor_state.get('HV_30d', 0.8))
        else:
            anchor_spot = spot
            anchor_vol = vol
            
        # Get Geological Layers (Legacy but needed for now)
        time_layers = calculate_time_layers(current_date, birth_date)
        hist_ranges = []
        for l_type, l_start, l_end in time_layers:
            h_min, h_max = provider.get_high_low(l_start, l_end)
            if h_min is not None and h_max is not None:
                hist_ranges.append((l_type, h_min, h_max))
        if not hist_ranges:
            hist_ranges = [('daily', spot, spot)]

        # Get Full History for V5 Proper Simulation
        try:
            # Slice history from birth to current
            mask = (provider.df_merged.index >= birth_date) & (provider.df_merged.index <= current_date)
            hist_df = provider.df_merged.loc[mask]
            price_hist = hist_df['Close'].tolist()
            iv_hist = hist_df['Real_IV_ATM'].tolist()
        except Exception:
            price_hist = None
            iv_hist = None

        # Generate STABLE strikes with Density Layers
        dte_strikes = generate_deribit_strikes(spot, dte_val, anchor_spot, anchor_vol, birth_dte, 
                                             historical_ranges=hist_ranges, 
                                             coincidence_count=count,
                                             price_history=price_hist,
                                             iv_history=iv_hist)
        
        # Predictions
        pc = model.predict(market_state, dte_strikes, dte_val, is_call=True)
        pc['dte'], pc['type'] = dte_val, 'call'
        results.append(pc.to_dict('records'))
        
        pp = model.predict(market_state, dte_strikes, dte_val, is_call=False)
        pp['dte'], pp['type'] = dte_val, 'put'
        results.append(pp.to_dict('records'))
        
    return [item for sublist in results for item in sublist]

@callback(
    Output('tab-content', 'children'),
    [Input('main-tabs', 'active_tab'),
     Input('prediction-results-store', 'data'),
     Input('market-state-store', 'data'),
     Input('dte-selector', 'value'),
     Input('selected-strike-store', 'data')],
    [State('board-active-tab-store', 'data'),
     State('timestamps-store', 'data')]
)
def render_content(active_tab, prediction_data, market_state, selected_dtes, selected_strike, last_board_tab, timestamps_store):
    if not prediction_data:
        return html.Div("Running Model Inference...")
        
    df = pd.DataFrame(prediction_data)
    
    if active_tab == "tab-smile":
        # selected_dtes are date strings
        current_date = pd.to_datetime(market_state['target_ts'])
        selected_dte_ints = [(pd.to_datetime(v) - current_date).days for v in selected_dtes]
        df_view = df[df['dte'].isin(selected_dte_ints)]
        # Plot just Calls IV (standard convention for Smile)
        df_plot = df_view[df_view['type'] == 'call'].copy()

        # Use cubic spline interpolation like main dashboard
        from scipy.interpolate import make_interp_spline
        
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
            annotation_text="Current Price", 
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
            dcc.Graph(figure=fig, style={"height": "calc(100vh - 300px)"})
        ])
        
    elif active_tab == "tab-board":
        # Tabs for each DTE, named exactly like the selector buttons
        current_date = pd.to_datetime(market_state['target_ts'])
        sorted_sel_dates = sorted(selected_dtes) # Sort chronologically
        spot = market_state['underlying_price']
        
        tabs = []
        for date_str in sorted_sel_dates:
            exp_date = pd.to_datetime(date_str)
            dte = (exp_date - current_date).days
            if dte < 0: continue
            
            # Label matches the 10/10 selector style
            tab_label = f"{exp_date.strftime('%d %b')} ({dte}d)"
            
            df_dte = df[df['dte'] == dte]
            if df_dte.empty: continue
            
            # Calculate Prices (Black Scholes)
            T = dte / 365.0
            r = 0.05
            
            # Separate C and P
            calls = df_dte[df_dte['type'] == 'call'].copy()
            puts = df_dte[df_dte['type'] == 'put'].copy()
            
            # Calc prices
            # Calc prices and theta
            res_c = calls.apply(lambda r_row: black_scholes(spot, r_row['strike'], T, r, r_row['mark_iv']/100, 'call'), axis=1)
            calls['price'], calls['theta'] = zip(*res_c) if not res_c.empty else ([], [])
            
            res_p = puts.apply(lambda r_row: black_scholes(spot, r_row['strike'], T, r, r_row['mark_iv']/100, 'put'), axis=1)
            puts['price'], puts['theta'] = zip(*res_p) if not res_p.empty else ([], [])
            
            calls.set_index('strike', inplace=True)
            puts.set_index('strike', inplace=True)
            
            # Merge
            combined = pd.merge(calls, puts, left_index=True, right_index=True, suffixes=('_c', '_p'), how='outer').reset_index()
            # After reset_index, the index column is named 'strike' (from set_index)
            combined.rename(columns={'strike': 'strike_price'}, inplace=True)
            
            # Calculate ATM strike
            atm_strike = combined.iloc[(combined['strike_price'] - spot).abs().argsort()[:1]]['strike_price'].values[0] if not combined.empty else 0
            
            # Columns Config (matching main dashboard order)
            grid_cols = [
                # Call side (right to left towards strike)
                {'field': 'vega_c', 'headerName': 'Vega', 'width': 90, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
                {'field': 'theta_c', 'headerName': 'Theta', 'width': 90, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
                {'field': 'gamma_c', 'headerName': 'Gamma', 'width': 90, 'valueFormatter': {"function": "d3.format(',.6f')(params.value)"}},
                {'field': 'delta_c', 'headerName': 'Delta', 'width': 90, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}, 'cellStyle': {'color': CUSTOM_CSS['accent_call'], 'fontWeight': 'bold'}},
                {'field': 'mark_iv_c', 'headerName': 'IV', 'width': 80, 'valueFormatter': {"function": "d3.format(',.1f')(params.value)"}},
                {'field': 'price_c', 'headerName': 'Price Call', 'width': 110, 'valueFormatter': {"function": "d3.format(',.3f')(params.value)"}, 'cellStyle': {'fontWeight': 'bold'}},
                
                # Middle Strike (bold center column)
                {'field': 'strike_price', 'headerName': 'STRIKE', 'width': 120, 
                 'cellStyle': {'fontWeight': '800', 'textAlign': 'center', 'backgroundColor': '#F8F9F9', 'borderLeft': '2px solid #D5D8DC', 'borderRight': '2px solid #D5D8DC', 'fontSize': '16px'}},
                 
                # Put side (left to right from strike)
                {'field': 'price_p', 'headerName': 'Price Put', 'width': 110, 'valueFormatter': {"function": "d3.format(',.3f')(params.value)"}, 'cellStyle': {'fontWeight': 'bold'}},
                {'field': 'mark_iv_p', 'headerName': 'IV', 'width': 80, 'valueFormatter': {"function": "d3.format(',.1f')(params.value)"}},
                {'field': 'delta_p', 'headerName': 'Delta', 'width': 90, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}, 'cellStyle': {'color': CUSTOM_CSS['accent_put'], 'fontWeight': 'bold'}},
                {'field': 'theta_p', 'headerName': 'Theta', 'width': 90, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
                {'field': 'gamma_p', 'headerName': 'Gamma', 'width': 90, 'valueFormatter': {"function": "d3.format(',.6f')(params.value)"}},
                {'field': 'vega_p', 'headerName': 'Vega', 'width': 90, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
            ]
            
            grid = dag.AgGrid(
                id={'type': 'options-grid', 'date': date_str},  # Pattern matching ID
                rowData=combined.to_dict('records'),
                columnDefs=grid_cols,
                defaultColDef={"sortable": True, "filter": True, "resizable": True},
                dashGridOptions={
                    "rowHeight": 35,
                    "rowSelection": "single",
                    "getRowStyle": {
                        "styleConditions": [
                            {
                                "condition": f"params.data.strike_price == {atm_strike}",
                                "style": {"backgroundColor": "#FEF9E7"}  # Pale yellow for ATM
                            }
                        ]
                    }
                },
                style={"height": "650px", "width": "100%"},
                className="ag-theme-alpine"
            )
            
            # Create tab with Bootstrap styling
            tabs.append(dbc.Tab(
                label=tab_label,
                tab_id=date_str, # Use constant date string for stickiness
                children=[html.Div(grid, style={"padding": "10px"})]
            ))
            
        if not tabs:
            return html.Div("Please select at least one expiration from the list above.", style={"padding": "40px", "textAlign": "center", "color": CUSTOM_CSS["text_secondary"]})
            
        # Determine which tab should be active
        active = tabs[0].tab_id
        if last_board_tab:
            # Check if last viewed tab is still in current selection
            if any(t.tab_id == last_board_tab for t in tabs):
                active = last_board_tab

        return dbc.Tabs(tabs, id='board-dte-tabs', active_tab=active)
        
    elif active_tab == "tab-surface":
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
        
        fig_3d.update_layout(
            title="Volatility Surface",
            scene=dict(
                xaxis_title='Strike',
                yaxis_title='Days to Expiry',
                zaxis_title='Implied Volatility'
            ),
            margin=dict(l=0, r=0, b=0, t=30),
            uirevision='constant'  # Preserves camera view on data updates
        )
        
        return html.Div([
            dcc.Graph(id='volatility-surface-3d', figure=fig_3d, style={"height": "calc(100vh - 300px)"})
        ], style=style_card)
    
    elif active_tab == "tab-strike":
        # Click Debug: Show selected strike data
        if selected_strike and isinstance(selected_strike, dict):
            strike = selected_strike.get('strike', 'N/A')
            opt_type = selected_strike.get('type', 'N/A')
            exp_date = selected_strike.get('exp_date', 'N/A')
            debug_text = f"✅ Выбран: Strike {strike} | Тип: {opt_type.upper()} | Экспирация: {exp_date}"
        else:
            debug_text = "⚠️ Нет выбранного страйка. Перейдите на Options Board и кликните на любую ячейку (кроме STRIKE)."
        
        debug_info = html.Div([
            html.H6("🖱️ Click Debug", style={"color": "#FF6B6B", "marginBottom": "10px"}),
            html.P(debug_text, style={"fontSize": "12px", "margin": "0"})
        ], style={**style_card, "marginBottom": "15px", "padding": "15px", "border": "2px solid #FF6B6B"})
        
        # Render candlestick chart for selected strike
        if not market_state or not timeseries_provider:
            return html.Div([
                debug_info,
                html.H5("Strike Chart", style={"color": CUSTOM_CSS["text_primary"]}),
                html.P("System initializing...", 
                       style={"color": CUSTOM_CSS["text_secondary"], "marginTop": "20px"})
            ], style={**style_card, "padding": "40px", "textAlign": "center"})
        
        # Check if we have a strike selection
        if not selected_strike or not isinstance(selected_strike, dict):
            return html.Div([
                debug_info,
                html.H5("Strike Chart", style={"color": CUSTOM_CSS["text_primary"]}),
                html.P("Click on any Call or Put price in the Options Board tab to view its candlestick chart.", 
                       style={"color": CUSTOM_CSS["text_secondary"], "marginTop": "20px"}),
                html.P("The chart will show:", style={"marginTop": "20px", "fontWeight": "bold"}),
                html.Ul([
                    html.Li("Option price evolution as candlesticks"),
                    html.Li("Base asset (BTC/ETH) price overlay"),
                    html.Li("Synchronized with time slider - updates as you move through time")
                ], style={"color": CUSTOM_CSS["text_secondary"]})
            ], style={**style_card, "padding": "40px", "textAlign": "center"})
        
        # Extract strike selection details
        strike = selected_strike.get('strike')
        option_type = selected_strike.get('type')
        exp_date = selected_strike.get('exp_date')
        currency = market_state.get('currency', 'BTC')
        
        if not all([strike, option_type, exp_date]):
            return html.Div([
                html.H5("Invalid Selection", style={"color": CUSTOM_CSS["text_primary"]}),
                html.P("Please select a valid strike from the Options Board.", 
                       style={"color": CUSTOM_CSS["text_secondary"]})
            ], style={**style_card, "padding": "40px", "textAlign": "center"})
        
        # Generate OHLC data ON-THE-FLY using the model
        current_time = market_state.get('target_ts')
        if not current_time or not timestamps_store:
            return html.Div("No time data available", style=style_card)
        
        current_dt = pd.to_datetime(current_time)
        exp_dt = pd.to_datetime(exp_date)
        
        # Generate prices for all dates where option existed
        prices_data = []
        base_prices = []
        
        for date_str in timestamps_store:
            date = pd.to_datetime(date_str)
            
            # Only generate for dates up to current slider position
            if date > current_dt:
                continue
            
            # Only generate for dates before expiration
            if date > exp_dt:
                continue
            
            # Calculate DTE
            dte = (exp_dt - date).days
            if dte <= 0:
                continue
            
            # Get market state for this date
            try:
                state = provider.get_market_state(date)
                if not state:
                    continue
                
                spot = state['underlying_price']
                
                # Model predicts IV for this strike
                result = model.predict(
                    market_state=state,
                    strikes=[strike],
                    dte_days=dte,
                    is_call=(option_type == 'call')
                )
                
                # Get IV from model (model returns in %)
                iv = result['mark_iv'].iloc[0] / 100.0
                
                # Calculate option price using Black-Scholes
                T = dte / 365.0
                r = 0.05
                price, _ = black_scholes(spot, strike, T, r, iv, option_type)
                
                
                # Store data (we'll compute open from previous close after the loop)
                prices_data.append({
                    'timestamp': date,
                    'price': price  # Just store the price for now
                })
                
                base_prices.append({
                    'timestamp': date,
                    'price': spot
                })
                
            except Exception as e:
                print(f"Error generating data for {date}: {e}")
                continue
        
        # Convert to DataFrames
        if not prices_data:
            return html.Div([
                debug_info,
                html.H5(f"{currency} {strike} {option_type.upper()} - {exp_dt.strftime('%d %b %Y')}", 
                        style={"color": CUSTOM_CSS["text_primary"]}),
                html.P("Could not generate candlestick data for this option.", 
                       style={"color": CUSTOM_CSS["text_secondary"], "marginTop": "20px"}),
                html.P("This may occur if:", style={"marginTop": "20px"}),
                html.Ul([
                    html.Li("The option's lifetime is outside the available data period"),
                    html.Li("The strike generates invalid model predictions"),
                    html.Li("Data preprocessing is incomplete for this period")
                ], style={"color": CUSTOM_CSS["text_secondary"]})
            ], style={**style_card, "padding": "40px"})
        
        
        # Process prices to compute open from previous close and high/low
        ohlc_data = []
        prev_price = None
        for item in prices_data:
            price = item['price']
            open_price = prev_price if prev_price is not None else price
            
            # High and low from open and close
            high_price = max(open_price, price)
            low_price = min(open_price, price)
            
            ohlc_data.append({
                'timestamp': item['timestamp'],
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': price
            })
            prev_price = price
        
        ohlc_df = pd.DataFrame(ohlc_data)
        base_df = pd.DataFrame(base_prices)
        
        # Check if we have data
        if ohlc_df.empty:
            exp_dt = pd.to_datetime(exp_date)
            dte = (exp_dt - current_dt).days
            return html.Div([
                debug_info,
                html.H5(f"{currency} {strike} {option_type.upper()} - {exp_dt.strftime('%d %b %Y')} ({dte}d)", 
                        style={"color": CUSTOM_CSS["text_primary"]}),
                html.P("No historical data available for this strike.", 
                       style={"color": CUSTOM_CSS["text_secondary"], "marginTop": "20px"}),
                html.P("This may occur if:", style={"marginTop": "20px"}),
                html.Ul([
                    html.Li("The option was not listed during this time period"),
                    html.Li("The strike is too far OTM with no liquidity"),
                    html.Li("Data preprocessing is incomplete for this period")
                ], style={"color": CUSTOM_CSS["text_secondary"]})
            ], style={**style_card, "padding": "40px"})
        
        # Create the candlestick chart
        fig = go.Figure()
        
        # Add candlestick trace (primary Y-axis)
        fig.add_trace(go.Candlestick(
            x=ohlc_df['timestamp'],
            open=ohlc_df['open'],
            high=ohlc_df['high'],
            low=ohlc_df['low'],
            close=ohlc_df['close'],
            name=f"{option_type.upper()} Price",
            increasing_line_color=CUSTOM_CSS["accent_call"],
            decreasing_line_color=CUSTOM_CSS["accent_put"],
            yaxis='y'
        ))
        
        # Add base asset price overlay (secondary Y-axis)
        if not base_df.empty:
            fig.add_trace(go.Scatter(
                x=base_df['timestamp'],
                y=base_df['price'],
                name=f"{currency} Spot",
                line=dict(color='rgba(150, 150, 150, 0.6)', width=2, dash='dash'),
                yaxis='y2'
            ))
        
        # Calculate title details
        exp_dt = pd.to_datetime(exp_date)
        dte = (exp_dt - current_dt).days
        type_color = CUSTOM_CSS["accent_call"] if option_type == 'call' else CUSTOM_CSS["accent_put"]
        
        # Layout with dual Y-axes
        fig.update_layout(
            title=dict(
                text=f"{currency} ${strike:,.0f} {option_type.upper()} - Expires {exp_dt.strftime('%d %b %Y')} ({dte} days)",
                font=dict(size=16, color=CUSTOM_CSS["text_primary"], weight=800)
            ),
            xaxis=dict(
                title="Date",
                gridcolor='rgba(200, 200, 200, 0.2)',
                showgrid=True
            ),
            yaxis=dict(
                title=dict(text=f"{option_type.capitalize()} Option Price ($)", font=dict(color=type_color)),
                tickfont=dict(color=type_color),
                side='left',
                showgrid=True,
                gridcolor='rgba(200, 200, 200, 0.2)'
            ),
            yaxis2=dict(
                title=dict(text=f"{currency} Spot Price ($)", font=dict(color='gray')),
                tickfont=dict(color='gray'),
                overlaying='y',
                side='right',
                showgrid=False
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(t=60, b=50, l=70, r=70),
            xaxis_rangeslider_visible=False  # Disable range slider for cleaner look
        )
        
        # Current time marker: removed due to Plotly compatibility issues
        
        return html.Div([
            dcc.Graph(figure=fig, config={'displayModeBar': True}, style={"height": "calc(100vh - 300px)"})
        ], style=style_card)

    return html.Div("Unknown Tab")

# Catch clicks on grid cells
@callback(
    [Output('selected-strike-store', 'data', allow_duplicate=True),
     Output('main-tabs', 'active_tab', allow_duplicate=True)],
    Input({'type': 'options-grid', 'date': ALL}, 'cellClicked'),
    [State('market-state-store', 'data'),
     State({'type': 'options-grid', 'date': ALL}, 'rowData')],
    prevent_initial_call=True
)
def handle_grid_click(cell_clicked_list, market_state, row_data_list):
    """
    Handles clicks on any grid cell from any expiration tab.
    Extracts strike, expiration, and option type.
    """
    print(f"[GRID CLICK] Received {len(cell_clicked_list)} grids cell_clicked")
    
    if not cell_clicked_list or not market_state:
        return dash.no_update, dash.no_update
    
    # Find which grid was clicked
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    
    # Find the clicked grid
    clicked_grid_idx = None
    clicked_cell = None
    
    for i, cell_data in enumerate(cell_clicked_list):
        if cell_data is not None:
            clicked_grid_idx = i
            clicked_cell = cell_data
            break
    
    if clicked_cell is None:
        return dash.no_update, dash.no_update
    
    # Extract data from clicked cell
    col_id = clicked_cell.get('colId')
    row_index = clicked_cell.get('rowIndex')
    
    # Ignore clicks on strike column
    if col_id == 'strike_price':
        print(f"[GRID CLICK] Ignoring click on strike column")
        return dash.no_update, dash.no_update
    
    # Determine option type from column ID
    # Columns ending with _c are Call, _p are Put
    if col_id.endswith('_c'):
        option_type = 'call'
    elif col_id.endswith('_p'):
        option_type = 'put'
    else:
        # Unknown column, ignore
        print(f"[GRID CLICK] Ignoring click on unknown column {col_id}")
        return dash.no_update, dash.no_update
    
    # Get expiration date from the triggered grid's ID
    triggered_id = ctx.triggered[0]['prop_id']
    # Parse: {"date":"2024-01-05","type":"options-grid"}.cellClicked
    import json
    id_part = triggered_id.split('.')[0]
    grid_id = json.loads(id_part)
    exp_date = grid_id.get('date')
    
    # Get strike price from row data
    if row_data_list and clicked_grid_idx < len(row_data_list):
        row_data = row_data_list[clicked_grid_idx]
        if row_data and row_index < len(row_data):
            row = row_data[row_index]
            strike = row.get('strike_price')
            
            if strike and exp_date:
                result = {
                    'strike': strike,
                    'type': option_type,
                    'exp_date': exp_date
                }
                print(f"[GRID CLICK] Selected: {strike} {option_type.upper()} exp {exp_date}")
                return result, 'tab-strike'
    
    print(f"[GRID CLICK] Failed to extract full data")
    return dash.no_update, dash.no_update

@callback(
    Output('board-active-tab-store', 'data'),
    Input('board-dte-tabs', 'active_tab'),
    prevent_initial_call=True
)
def store_board_tab(active_tab):
    print(f"[BOARD TAB] Switched to: {active_tab}")
    return active_tab

# Default strike for testing - automatically show a chart
@callback(
    Output('selected-strike-store', 'data'),
    [Input('market-state-store', 'data'),
     Input('main-tabs', 'active_tab')],
    prevent_initial_call=False
)
def set_default_strike(market_state, active_tab):
    """
    Automatically set a default strike for testing the chart.
    Uses current BTC price to find a realistic ATM strike.
   """
    if active_tab == 'tab-strike' and market_state:
        print(f"[STRIKE SELECTION] Setting default test strike")
        current_date = pd.to_datetime(market_state.get('target_ts'))
        currency = market_state.get('currency', 'BTC')
        
        # Get current price from market state
        current_price = market_state.get('index_price')
        if not current_price:
            print(f"[STRIKE SELECTION] No index price available")
            return dash.no_update
            
        # Find nearest strike (round to nearest 500 for BTC, 50 for ETH)
        step = 500 if currency == 'BTC' else 50
        atm_strike = round(current_price / step) * step
        
        # Get first available expiration
        exps = generate_deribit_expirations(current_date)
        if not exps:
            print(f"[STRIKE SELECTION] No expirations available")
            return dash.no_update
            
        first_exp = exps[0][0]
        exp_date_str = first_exp.strftime('%Y-%m-%d')
        
        default_strike = {
            'strike': int(atm_strike),
            'type': 'call',
            'exp_date': exp_date_str
        }
        print(f"[STRIKE SELECTION] Default: {default_strike} (current {currency} price: {current_price})")
        return default_strike
    
    return dash.no_update

if __name__ == "__main__":
    app.run(debug=False, port=8051)
