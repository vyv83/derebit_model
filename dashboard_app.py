import dash
from dash import dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import os
import glob
import threading
import time
from datetime import datetime
from preprocess_hourly import preprocess_month
from expand_timeline import download_file

# --- Configuration & Theme ---
EXTERNAL_STYLESHEETS = [dbc.themes.BOOTSTRAP] 

# --- Global Status for Harvesting ---
PROCESS_LOG_BUFFER = []
IS_PROCESSING = False
SHOULD_STOP = False
STATUS_DATA = {
    "date": "-",
    "stage": "IDLE",
    "progress": 0,
    "speed": "0.0 MB/s",
    "file": "-",
    "api_key": "",
    "downloaded": "0",
    "total": "0"
}

def background_logger(msg):
    global PROCESS_LOG_BUFFER, STATUS_DATA
    
    # Check if this is a structured status update
    if msg.startswith("PROGRESS:"):
        try:
            # Format: PROGRESS:date|stage|progress_val|speed|file|downloaded|total
            _, data = msg.split(":", 1)
            parts = data.strip().split("|")
            
            date = parts[0]
            stage = parts[1]
            progress = parts[2]
            speed = parts[3]
            filename = parts[4]
            downloaded = parts[5] if len(parts) > 5 else "0"
            total = parts[6] if len(parts) > 6 else "0"

            STATUS_DATA.update({
                "date": date,
                "stage": stage,
                "progress": float(progress),
                "speed": speed,
                "file": filename,
                "downloaded": downloaded,
                "total": total
            })
            return # Don't log progress spam
        except:
            pass

    clean_msg = msg.replace('\r', '\n')
    if not clean_msg.endswith('\n'):
        clean_msg += '\n'
    
    PROCESS_LOG_BUFFER.append(clean_msg)
    if len(PROCESS_LOG_BUFFER) > 500: 
        PROCESS_LOG_BUFFER.pop(0)

from harvest_manager import DataHarvester, STAGING_DIR, PROCESSED_DIR

app = dash.Dash(__name__, external_stylesheets=EXTERNAL_STYLESHEETS, suppress_callback_exceptions=True)
app.title = "Deribit Options Analytics"

# --- Data Loading helpers ---
def get_available_raw_files():
    files = glob.glob("archives_all_years/TARDIS_Snap_*.csv.gz")
    return sorted([os.path.basename(f) for f in files])

# --- Data Discovery ---

def get_processed_metadata():
    """Returns a dict of available data: {currency: {year: [months]}}"""
    files = glob.glob(os.path.join(PROCESSED_DIR, "*.parquet"))
    metadata = {}
    for f in files:
        # Format: BTC_2021-02.parquet
        base = os.path.basename(f).replace(".parquet", "")
        parts = base.split("_")
        if len(parts) != 2: continue
        currency = parts[0]
        date_parts = parts[1].split("-")
        if len(date_parts) != 2: continue
        year = date_parts[0]
        month = date_parts[1]
        
        if currency not in metadata: metadata[currency] = {}
        if year not in metadata[currency]: metadata[currency][year] = []
        metadata[currency][year].append(month)
    
    # Merge with staging files (individual days)
    staging_files = glob.glob(os.path.join(STAGING_DIR, "*.snap"))
    for f in staging_files:
        base = os.path.basename(f).replace(".snap", "")
        parts = base.split("_")
        if len(parts) != 2: continue
        currency = parts[0]
        date_str = parts[1] # 2021-01-01
        year = date_str[:4]
        month_part = date_str[5:7]
        
        if currency not in metadata: metadata[currency] = {}
        if year not in metadata[currency]: metadata[currency][year] = []
        if month_part not in metadata[currency][year]:
            metadata[currency][year].append(month_part)
    
    # Sort years and months
    for curr in metadata:
        for yr in metadata[curr]:
            # Ensure unique months and sort numerically as strings
            metadata[curr][yr] = sorted(list(set(metadata[curr][yr])), key=lambda x: int(x) if x.isdigit() else 0)
    return metadata

def load_processed_file(currency, year, month):
    # 1. Try monthly parquet
    filepath = os.path.join(PROCESSED_DIR, f"{currency}_{year}-{month}.parquet")
    if not os.path.exists(filepath):
        # 2. Try day-1 snap from staging (common in Demo Mode)
        filepath = os.path.join(STAGING_DIR, f"{currency}_{year}-{month}-01.snap")
        
    if not os.path.exists(filepath):
        # 3. Try any other snap for that month in staging
        snaps = glob.glob(os.path.join(STAGING_DIR, f"{currency}_{year}-{month}-*.snap"))
        if snaps:
            filepath = snaps[0]
        else:
            return pd.DataFrame()
            
    try:
        df = pd.read_parquet(filepath)
        if df.empty: return df
        if not pd.api.types.is_datetime64_any_dtype(df['snapshot_time']):
            df['snapshot_time'] = pd.to_datetime(df['snapshot_time'])
        df['currency'] = df['symbol'].str.split('-').str[0]
        
        # Consistent expiry parsing
        try:
            df['expiration_date'] = pd.to_datetime(df['expiration'], unit='us')
        except:
            df['expiration_date'] = pd.to_datetime(df['expiration'])
            
        df['expiration_str'] = df['expiration_date'].dt.strftime('%d%b%y').str.upper()
        return df.sort_values('snapshot_time')
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return pd.DataFrame()

# --- Custom Styling (The "10/10" Pale Look) ---
CUSTOM_CSS = {
    "background": "#F5F7F9",
    "card_bg": "#FFFFFF",
    "text_primary": "#2C3E50",
    "text_secondary": "#7F8C8D",
    "accent_call": "#76D7C4", # Soft Teal
    "accent_put": "#FF8787",  # Soft Coral
    "scrubber_bg": "#EAECEE",
    "scrubber_fill": "#BDC3C7",
}

style_card = {
    "backgroundColor": CUSTOM_CSS["card_bg"],
    "borderRadius": "12px",
    "boxShadow": "0 2px 8px rgba(0,0,0,0.05)",
    "border": "none",
    "padding": "20px",
    "marginBottom": "20px"
}

style_kpi_value = {
    "fontSize": "18px",
    "fontWeight": "bold",
    "color": CUSTOM_CSS["text_primary"]
}

style_kpi_label = {
    "fontSize": "11px",
    "color": CUSTOM_CSS["text_secondary"],
    "textTransform": "uppercase",
    "letterSpacing": "0.5px",
    "marginBottom": "0px"
}

# --- Components ---

def build_kpi_card(title, id_value, id_sub=None):
    return dbc.Card([
        html.Div(title, style=style_kpi_label),
        html.Div("-", id=id_value, style=style_kpi_value),
        html.Div("", id=id_sub, style={"fontSize": "12px", "color": CUSTOM_CSS["text_secondary"]}) if id_sub else None
    ], style=style_card)

def build_control_dock():
    # Now dynamic - skeleton layout
    return html.Div([
        dbc.Row([
            dbc.Col(id="slider-container", children=[
                html.Div(dcc.Slider(id="time-slider", min=0, max=1, value=0), style={"display": "none"})
            ], width=11),
            dbc.Col([
                dbc.Button("▶", id="btn-play", color="light", size="sm", style={"borderRadius": "50%", "width": "35px", "height": "35px"})
            ], width=1, className="d-flex align-items-center justify-content-center")
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

# --- Layout ---

# ... (Imports)

# --- Components ---

# ... (build_kpi_card, build_control_dock remain same)

# --- Layout ---

app.layout = html.Div([
    dcc.Store(id='current-snapshot-data'),
    dcc.Store(id='active-board-expiry'),
    dcc.Store(id='full-monthly-data'), # All snapshots for the selected month
    dcc.Store(id='available-metadata-store', data=get_processed_metadata()),
    dcc.Interval(id='loader-interval', interval=2000, n_intervals=0, disabled=False),
    
    dbc.Tabs([
        # --- TAB 1: DATA LOADER ---
        # --- TAB 1: DATA LOADER ---
        dbc.Tab(label="DATA LOADER", tab_id="tab-loader", children=[
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        html.H2("Data Management", style={"fontWeight": "800", "color": CUSTOM_CSS["text_primary"]}),
                        html.P("Automated background collection and processing.", className="text-muted")
                    ], width=12)
                ], className="my-4"),

                dbc.Row([
                    # LEFT: Stats & Controls
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Live Progress Panel", className="fw-bold bg-primary text-white"),
                            dbc.CardBody([
                                html.Div([
                                    dbc.Row([
                                        dbc.Col([
                                            html.Small("STAGE", className="text-muted fw-bold d-block"),
                                            html.Div(id="status-stage", children="IDLE", className="fw-bold text-primary")
                                        ], width=6),
                                        dbc.Col([
                                            html.Small("DATE", className="text-muted fw-bold d-block"),
                                            html.Div(id="status-date", children="-", className="fw-bold")
                                        ], width=6),
                                    ], className="mb-3"),
                                    
                                    html.Small("TARDIS API KEY (OPTIONAL)", className="text-muted fw-bold d-block mb-1"),
                                    dbc.Input(id="tardis-api-key", type="password", placeholder="Paste key for full history...", size="sm", className="mb-3"),
                                    
                                    html.Small("PROGRESS", className="text-muted fw-bold d-block mb-1"),
                                    dbc.Progress(id="status-progress-bar", value=0, striped=True, animated=True, style={"height": "12px"}, className="mb-1"),
                                    html.Div([
                                        html.Span(id="status-download-info", children="0/0 MB", className="small text-muted")
                                    ], className="text-end mb-2"),
                                    
                                    dbc.Row([
                                        dbc.Col([
                                            html.Small("SPEED", className="text-muted fw-bold d-block"),
                                            html.Div(id="status-speed", children="0.0 MB/s", className="fw-bold text-success")
                                        ], width=4),
                                        dbc.Col([
                                            html.Small("CURRENT FILE", className="text-muted fw-bold d-block"),
                                            html.Div(id="status-file", children="-", className="small", style={"wordBreak": "break-all"})
                                        ], width=8)
                                    ])
                                ], id="progress-panel-container")
                            ])
                        ], className="shadow border-0 mb-4"),

                        dbc.Card([
                            dbc.CardHeader("Auto-Harvest Controls", className="fw-bold"),
                            dbc.CardBody([
                                html.Div([
                                    dbc.Button("🚀 START AUTO-HARVEST", id="btn-start-harvest", color="success", className="w-100 mb-2 py-2 fw-bold"),
                                    dbc.Button("⏹ STOP", id="btn-stop-harvest", color="danger", outline=True, className="w-100 mb-3", disabled=True),
                                ]),
                                html.Hr(),
                                html.Div([
                                    html.Small("PROGRESS METRICS", className="text-muted fw-bold d-block mb-2"),
                                    dbc.Row([
                                        dbc.Col([
                                            html.Div("Days Processed", style={"fontSize": "10px", "color": "#7F8C8D"}),
                                            html.Div(id="stat-days-done", children="0", className="h4 mb-0 fw-bold")
                                        ]),
                                        dbc.Col([
                                            html.Div("Space Saved", style={"fontSize": "10px", "color": "#7F8C8D"}),
                                            html.Div(id="stat-space-saved", children="0.0 GB", className="h4 mb-0 fw-bold text-success")
                                        ])
                                    ])
                                ])
                            ])
                        ], className="shadow-sm border-0 mb-4"),
                        
                        dbc.Card([
                            dbc.CardHeader("Manual Task", className="fw-bold"),
                            dbc.CardBody([
                                html.Label("Select Individual Date:", className="small fw-bold"),
                                dcc.Dropdown(
                                    id='raw-file-dropdown',
                                    options=[{'label': f, 'value': f} for f in get_available_raw_files()],
                                    placeholder="Select a specific file...",
                                    className="mb-3"
                                ),
                                dbc.Button("Process Selected Only", id="btn-run-preprocess", color="secondary", outline=True, className="w-100")
                            ])
                        ], className="shadow-sm border-0")
                    ], width=4),

                    # RIGHT: Live Stream Log
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader([
                                "Live Process Stream",
                                dbc.Badge("IDLE", id="harvest-status-badge", color="secondary", className="float-end")
                            ], className="fw-bold"),
                            dbc.CardBody([
                                html.Pre(
                                    id='loader-log',
                                    children="Ready to initialize...",
                                    style={
                                        'height': '450px', 
                                        'overflowY': 'auto', 
                                        'backgroundColor': '#1E1E1E', 
                                        'color': '#D4D4D4', 
                                        'padding': '15px',
                                        'fontSize': '11px',
                                        'borderRadius': '8px',
                                        'fontFamily': 'Monaco, monospace'
                                    }
                                )
                            ])
                        ], className="shadow-sm border-0")
                    ], width=8)
                ])
            ], fluid=True, style={"padding": "0 40px"})
        ]),

        # --- TAB 2: ANALYZER (Current Dashboard) ---
        dbc.Tab(label="DERIBIT ANALYZER", tab_id="tab-analyzer", children=[
            # 1. Top Bar & Data Explorer
            dbc.Container([
                dbc.Row([
                    dbc.Col([
                        html.H4("Deribit Analyzer", style={"color": CUSTOM_CSS["text_primary"], "fontWeight": "800", "marginBottom": "0", "whiteSpace": "nowrap"}),
                        html.Span("Advanced Historical Explorer", style={"color": CUSTOM_CSS["text_secondary"], "fontSize": "11px"})
                    ], width="auto", className="pe-4"),
                    
                    # Data selection tools
                    dbc.Col([
                        html.Div([
                            # Currency
                            html.Div([
                                html.Label("CURRENCY", style={"fontSize": "10px", "fontWeight": "bold", "color": CUSTOM_CSS["text_secondary"], "marginBottom": "2px", "display": "block"}),
                                dbc.RadioItems(
                                    id="currency-selector",
                                    options=[{"label": "BTC", "value": "BTC"}, {"label": "ETH", "value": "ETH"}],
                                    value="BTC",
                                    inline=True,
                                    input_class_name="btn-check",
                                    label_class_name="btn btn-sm btn-outline-primary rounded-pill px-2 py-0",
                                    label_checked_class_name="active"
                                )
                            ], className="me-3"),
                            
                            # Year selection
                            html.Div([
                                html.Label("YEAR", style={"fontSize": "10px", "fontWeight": "bold", "color": CUSTOM_CSS["text_secondary"], "marginBottom": "2px", "display": "block"}),
                                dbc.Select(id="year-selector", size="sm", style={"borderRadius": "20px", "width": "100px"})
                            ], className="me-3"),

                            # Month selector
                            html.Div([
                                html.Label("MONTH", style={"fontSize": "10px", "fontWeight": "bold", "color": CUSTOM_CSS["text_secondary"], "marginBottom": "2px", "display": "block"}),
                                html.Div(id="month-selector-container", children=[
                                    dbc.RadioItems(
                                        id="month-selector",
                                        options=[],
                                        value=None,
                                        input_class_name="btn-check",
                                        label_class_name="btn btn-sm btn-outline-secondary rounded-pill px-2 py-0",
                                        label_checked_class_name="active bg-secondary text-white",
                                        style={"display": "flex", "gap": "4px"}
                                    )
                                ])
                            ]),
                        ], className="d-flex align-items-end")
                    ], width="auto")
                ], className="py-2 border-bottom mb-2 align-items-end"),
                
                # Unified Control & KPI Bar
                dbc.Row([
                    # KPI Bar
                    dbc.Col([
                        html.Div([
                            html.Div([
                                html.Small("UNDERLYING", style=style_kpi_label),
                                html.Div("-", id="kpi-underlying", style={"fontSize": "16px", "fontWeight": "bold", "color": CUSTOM_CSS["text_primary"]})
                            ], className="px-2 border-end", style={"flex": "1.4"}),
                            html.Div([
                                html.Small("P/C VOLUME", style=style_kpi_label),
                                html.Div("-", id="kpi-pcr", style={"fontSize": "16px", "fontWeight": "bold", "color": CUSTOM_CSS["text_primary"]})
                            ], className="px-2 border-end", style={"flex": "1"}),
                            html.Div([
                                html.Small("ATM IV", style=style_kpi_label),
                                html.Div("-", id="kpi-atm-iv", style={"fontSize": "16px", "fontWeight": "bold", "color": CUSTOM_CSS["text_primary"]})
                            ], className="px-2", style={"flex": "1"}),
                        ], className="d-flex align-items-center bg-white rounded shadow-sm py-1 border", style={"height": "48px"})
                    ], width=4),
                    
                    # Expiration Selector
                    dbc.Col([
                         html.Div([
                             html.Div([
                                 dbc.Checklist(
                                     id='expiry-selector',
                                     options=[],
                                     value=[],
                                     input_class_name="btn-check",
                                     label_class_name="btn btn-outline-secondary btn-xs rounded-pill px-2 py-0",
                                     label_style={"fontSize": "11px", "margin": "0"},
                                     label_checked_class_name="active bg-primary text-white",
                                     style={"display": "flex", "gap": "3px", "flexWrap": "nowrap"}
                                 )
                             ], style={"overflowX": "auto", "whiteSpace": "nowrap", "padding": "0 5px", "scrollbarWidth": "none"})
                         ], className="d-flex align-items-center bg-white rounded shadow-sm border", style={"height": "48px"})
                    ], width=8)
                ], className="mb-2 g-2"),

                # 3. Content Tabs
                dbc.Tabs([
                    dbc.Tab(label="Market Overview", tab_id="tab-overview", active_tab_class_name="fw-bold text-primary"),
                    dbc.Tab(label="Options Board", tab_id="tab-board", active_tab_class_name="fw-bold text-primary"),
                    dbc.Tab(label="Vol Surface (3D)", tab_id="tab-3d", active_tab_class_name="fw-bold text-primary"),
                ], id="main-tabs", active_tab="tab-overview", style={"marginBottom": "10px"}),
                
                html.Div(id="tab-content", style={"paddingTop": "0px"}),
                
                # Bottom Spacer (to prevent dock overlap)
                html.Div(style={"height": "130px"}),

            ], fluid=True, style={"maxWidth": "1800px"}),
            
            build_control_dock()
        ]),
    ], id="global-tabs", active_tab="tab-analyzer", className="bg-white sticky-top shadow-sm", style={"padding": "0 20px"})

], style={"backgroundColor": CUSTOM_CSS["background"], "minHeight": "100vh", "fontFamily": "'Inter', sans-serif"})

@callback(
    [Output("year-selector", "options"),
     Output("year-selector", "value")],
    [Input("currency-selector", "value")],
    [State("available-metadata-store", "data")]
)
def update_year_options(currency, metadata):
    if not metadata or currency not in metadata:
        return [], None
    years = sorted(list(metadata[currency].keys()))
    return [{"label": y, "value": y} for y in years], years[0]

@callback(
    [Output("month-selector", "options"),
     Output("month-selector", "value")],
    [Input("currency-selector", "value"),
     Input("year-selector", "value")],
    [State("available-metadata-store", "data")]
)
def update_month_selector(currency, year, metadata):
    if not metadata or currency not in metadata or year not in metadata[currency]:
        return [], None
    
    months = metadata[currency][year]
    return [{"label": m, "value": m} for m in months], months[0]

@callback(
    Output("full-monthly-data", "data"),
    [Input("currency-selector", "value"),
     Input("year-selector", "value"),
     Input("month-selector", "value")],
    prevent_initial_call=False
)
def load_monthly_data_to_store(currency, year, month):
    if not all([currency, year, month]) or month == 'none':
        return [] # Explicitly clear store
    df_month = load_processed_file(currency, year, month)
    if df_month.empty:
        return []
    
    # CRITICAL: Convert Timestamps to strings for JSON serialization in Store
    for col in df_month.columns:
        if pd.api.types.is_datetime64_any_dtype(df_month[col]):
            df_month[col] = df_month[col].dt.strftime('%Y-%m-%d %H:%M:%S')
            
    # Convert to JSON serializable list
    return df_month.to_dict('records')

@callback(
    Output("slider-container", "children"),
    [Input("full-monthly-data", "data")]
)
def update_slider(data):
    if not data:
        return html.Div([
            html.Small("No time data available.", className="text-muted"),
            html.Div(dcc.Slider(id="time-slider", min=0, max=1, value=0), style={"display": "none"})
        ])
    
    df_temp = pd.DataFrame(data)
    if 'snapshot_time' not in df_temp.columns:
        return html.Div([
            html.Small("Invalid data format.", className="text-muted"),
            html.Div(dcc.Slider(id="time-slider", min=0, max=1, value=0), style={"display": "none"})
        ])
        
    df_temp['snapshot_time'] = pd.to_datetime(df_temp['snapshot_time'])
    timestamps = sorted(df_temp['snapshot_time'].unique())
    ts_str = [ts.strftime("%H:%M") for ts in timestamps]
    ts_full = [ts.strftime("%d %b %H:%M") for ts in timestamps]
    
    max_idx = len(timestamps) - 1
    marks = {i: {'label': ts, 'style': {'fontSize': '10px', 'color': '#95A5A6'}} 
             for i, ts in enumerate(ts_str) if i % (max(1, len(ts_str)//10)) == 0} 

    return [
        html.Div("TIME SNAPSHOT SELECTOR", style={"fontSize": "10px", "fontWeight": "bold", "color": CUSTOM_CSS["text_secondary"], "marginBottom": "5px"}),
        dcc.Slider(
            id='time-slider',
            min=0,
            max=max_idx,
            step=1,
            value=0,
            marks=marks,
            updatemode='drag',
            tooltip={"placement": "top", "always_visible": True, "template": "{value}"} # Note: JS formatting would be better for date
        )
    ]

@callback(
    [Output('current-snapshot-data', 'data'),
     Output('expiry-selector', 'options'),
     Output('expiry-selector', 'value')],
    [Input('full-monthly-data', 'data'),
     Input('time-slider', 'value'),
     Input('currency-selector', 'value')],
    [State('expiry-selector', 'value')]
)
def update_global_data(full_data, slider_value, currency, current_selected):
    if not full_data or slider_value is None:
        return [], [], []
    
    df_month = pd.DataFrame(full_data)
    df_month['snapshot_time'] = pd.to_datetime(df_month['snapshot_time'])
    
    timestamps = sorted(df_month['snapshot_time'].unique())
    if slider_value >= len(timestamps):
        slider_value = 0
    
    current_ts = timestamps[slider_value]
    
    snapshot = df_month[
        (df_month['snapshot_time'] == current_ts) & 
        (df_month['currency'] == currency)
    ].copy()
    
    if snapshot.empty:
        return [], [], []
    
    # Use formatted string for display
    def parse_date(x):
        try: return datetime.strptime(x, '%d%b%y')
        except: return datetime.min

    expirations = sorted(snapshot['expiration_str'].unique(), key=parse_date)
    
    # Create toggle options
    exp_options = [{'label': exp, 'value': exp} for exp in expirations]
    
    # Logic to preserve selection
    if current_selected and isinstance(current_selected, list):
        # Keep only those that exist in the new snapshot
        new_selection = [e for e in current_selected if e in expirations]
        # If the intersection is empty (e.g. switched currency or entire list changed), fallback
        if not new_selection:
             new_selection = expirations[:3] if len(expirations) >= 3 else expirations
    else:
        new_selection = expirations[:3] if len(expirations) >= 3 else expirations
    
    print(f"DEBUG: Previous selection: {current_selected} -> New selection: {new_selection}")
    
    snapshot['snapshot_time'] = snapshot['snapshot_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    if 'expiration_date' in snapshot.columns:
        snapshot['expiration_date'] = snapshot['expiration_date'].astype(str)
    
    return snapshot.to_dict('records'), exp_options, new_selection

@callback(
    [Output('kpi-underlying', 'children'),
     Output('kpi-pcr', 'children'),
     Output('kpi-atm-iv', 'children')],
    [Input('current-snapshot-data', 'data')]
)
def update_kpis(data):
    if not data: return "-", "-", "-"
    df_snap = pd.DataFrame(data)
    if df_snap.empty: return "-", "-", "-"
    
    price = df_snap['underlying_price'].iloc[0]
    
    # Simple ATM IV approximation
    try:
        # Find nearest expiry + closest strike
        price_col = 'underlying_price'
        df_snap['dist'] = (df_snap['strike_price'] - df_snap[price_col]).abs()
        atm_row = df_snap.sort_values('dist').iloc[0]
        iv = atm_row['mark_iv']
    except:
        iv = 0
        
    puts = df_snap[df_snap['type'] == 'put']['open_interest'].sum()
    calls = df_snap[df_snap['type'] == 'call']['open_interest'].sum()
    pcr = puts / calls if calls > 0 else 0
    
    return f"${price:,.2f}", f"{pcr:.2f}", f"{iv:.2f}%"


@callback(
    Output('tab-content', 'children'),
    [Input('main-tabs', 'active_tab'),
     Input('current-snapshot-data', 'data'),
     Input('expiry-selector', 'value')],
    [State('active-board-expiry', 'data')]
)
def render_tab_content(active_tab, data, selected_expiries, stored_board_expiry):
    if not data: return html.Div("Loading Data...")
    df_snap = pd.DataFrame(data)
    if df_snap.empty: return html.Div("No data.")

    if selected_expiries:
        df_filtered = df_snap[df_snap['expiration_str'].isin(selected_expiries)]
    else:
        df_filtered = df_snap
        selected_expiries = df_filtered['expiration_str'].unique()
        
    if active_tab == "tab-overview":
        return render_overview_tab(df_filtered)
    elif active_tab == "tab-board":
        return render_board_tab(df_filtered, selected_expiries, stored_board_expiry)
    elif active_tab == "tab-3d":
        return render_3d_tab(df_snap)
    return html.Div("Unknown Tab")

def render_overview_tab(df_filtered):
    # Sort
    df_sorted = df_filtered.sort_values(by=['expiration_str', 'strike_price'])
    
    from scipy.interpolate import make_interp_spline
    df_clean = df_sorted[df_sorted['mark_iv'] > 0].copy()
    fig_smile = go.Figure()
    
    if not df_clean.empty:
        expiries = df_clean['expiration_str'].unique()
        colors = px.colors.qualitative.Plotly
        for i, exp in enumerate(expiries):
            df_exp = df_clean[df_clean['expiration_str'] == exp].sort_values('strike_price')
            if len(df_exp) < 4:
                fig_smile.add_trace(go.Scatter(x=df_exp['strike_price'], y=df_exp['mark_iv'], mode='lines+markers', name=exp, line=dict(color=colors[i % len(colors)])))
                continue
            fig_smile.add_trace(go.Scatter(x=df_exp['strike_price'], y=df_exp['mark_iv'], mode='markers', name=f"{exp} (actual)", marker=dict(size=5, opacity=0.4, color=colors[i % len(colors)]), showlegend=False))
            try:
                x, y = df_exp['strike_price'].values, df_exp['mark_iv'].values
                x_new = np.linspace(x.min(), x.max(), 200)
                spl = make_interp_spline(x, y, k=3)
                fig_smile.add_trace(go.Scatter(x=x_new, y=spl(x_new), mode='lines', name=exp, line=dict(color=colors[i % len(colors)], width=2)))
            except:
                fig_smile.add_trace(go.Scatter(x=df_exp['strike_price'], y=df_exp['mark_iv'], mode='lines', name=exp, line=dict(color=colors[i % len(colors)])))

    # Add vertical line for current underlying price
    current_price = df_filtered['underlying_price'].mean() if not df_filtered.empty else 0
    if current_price > 0:
        fig_smile.add_vline(
            x=current_price, 
            line_width=1, 
            line_color="rgba(180, 180, 180, 0.6)", # Light gray, transparent
            line_dash="dash",
            annotation_text="Current Price", 
            annotation_position="top left",
            annotation_font_size=10,
            annotation_font_color="gray"
        )

    fig_smile.update_layout(
        title="Volatility Smile (Cubic Spline)",
        xaxis_title="Strike", yaxis_title="IV (%)",
        plot_bgcolor="white", paper_bgcolor="white",
        font={"color": CUSTOM_CSS["text_primary"]},
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=50, b=50, l=50, r=20)
    )
    
    # 2. Open Interest - Use go.Figure to avoid px template issues in some environments
    fig_oi = go.Figure()
    for t in ['call', 'put']:
        df_t = df_sorted[df_sorted['type'] == t]
        if not df_t.empty:
            fig_oi.add_trace(go.Bar(
                x=df_t['strike_price'],
                y=df_t['open_interest'],
                name=t.upper(),
                marker_color=CUSTOM_CSS['accent_call'] if t == 'call' else CUSTOM_CSS['accent_put'],
                opacity=0.7
            ))
            
    fig_oi.update_layout(
         title="Open Interest Distribution",
         xaxis_title="Strike",
         yaxis_title="Open Interest",
         barmode='overlay',
         plot_bgcolor="white",
         paper_bgcolor="white",
         font={"color": CUSTOM_CSS["text_primary"]},
         height=225,
         margin=dict(t=50, b=20, l=40, r=20),
         legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return html.Div([
        dbc.Row([dbc.Col(dcc.Graph(figure=fig_smile), width=12)]),
        dbc.Row([dbc.Col(dcc.Graph(figure=fig_oi), width=12)])
    ])

def render_board_tab(df_filtered, selected_expiries, active_expiry=None):
    if not selected_expiries or len(selected_expiries) == 0:
        return html.Div("Select expirations to view the board.")
        
    def parse_date(x):
        try: return datetime.strptime(x, '%d%b%y')
        except: return datetime.min
        
    sorted_expiries = sorted(selected_expiries, key=parse_date)
    
    tabs = []
    for exp in sorted_expiries:
        df_exp = df_filtered[df_filtered['expiration_str'] == exp]
        
        calls = df_exp[df_exp['type'] == 'call'].set_index('strike_price')
        puts = df_exp[df_exp['type'] == 'put'].set_index('strike_price')
        
        combined = pd.merge(calls, puts, left_index=True, right_index=True, suffixes=('_c', '_p'), how='outer').reset_index()
        combined.fillna(0, inplace=True)
        
        # Calculate ATM strike
        underlying = df_exp['underlying_price'].iloc[0] if not df_exp.empty else 0
        atm_strike = combined.iloc[(combined['strike_price'] - underlying).abs().argsort()[:1]]['strike_price'].values[0] if not combined.empty else 0
        
        # EXPANDED COLUMNS (ENGLISH NAMES + MORE WIDTH)
        cols = [
            # Call side
            {'field': 'theta_c', 'headerName': 'Theta', 'width': 100, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
            {'field': 'vega_c', 'headerName': 'Vega', 'width': 100, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
            {'field': 'gamma_c', 'headerName': 'Gamma', 'width': 100, 'valueFormatter': {"function": "d3.format(',.6f')(params.value)"}},
            {'field': 'delta_c', 'headerName': 'Delta', 'width': 100, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}, 'cellStyle': {'color': CUSTOM_CSS['accent_call'], 'fontWeight': 'bold'}},
            {'field': 'bid_iv_c', 'headerName': 'IV Bid', 'width': 100, 'valueFormatter': {"function": "d3.format(',.1f')(params.value)"}},
            {'field': 'bid_price_c', 'headerName': 'Bid Call', 'width': 120, 'cellStyle': {'fontWeight': 'bold'}},
            {'field': 'ask_price_c', 'headerName': 'Ask Call', 'width': 120},
            
            # Strike
            {'field': 'strike_price', 'headerName': 'STRIKE', 'width': 140, 
             'cellStyle': {'fontWeight': '800', 'textAlign': 'center', 'backgroundColor': '#F8F9F9', 'borderLeft': '2px solid #D5D8DC', 'borderRight': '2px solid #D5D8DC', 'fontSize': '16px'}},
            
            # Put side
            {'field': 'bid_price_p', 'headerName': 'Bid Put', 'width': 120, 'cellStyle': {'fontWeight': 'bold'}},
            {'field': 'ask_price_p', 'headerName': 'Ask Put', 'width': 120},
            {'field': 'bid_iv_p', 'headerName': 'IV Bid', 'width': 100, 'valueFormatter': {"function": "d3.format(',.1f')(params.value)"}},
            {'field': 'delta_p', 'headerName': 'Delta', 'width': 100, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}, 'cellStyle': {'color': CUSTOM_CSS['accent_put'], 'fontWeight': 'bold'}},
            {'field': 'gamma_p', 'headerName': 'Gamma', 'width': 100, 'valueFormatter': {"function": "d3.format(',.6f')(params.value)"}},
            {'field': 'vega_p', 'headerName': 'Vega', 'width': 100, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
            {'field': 'theta_p', 'headerName': 'Theta', 'width': 100, 'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
        ]
        
        grid = dag.AgGrid(
            id=f"grid-{exp}",
            rowData=combined.to_dict("records"),
            columnDefs=cols,
            defaultColDef={"sortable": True, "filter": True, "resizable": True},
            dashGridOptions={
                "rowHeight": 35,
                "getRowStyle": {
                    "styleConditions": [
                        {
                            "condition": f"params.data.strike_price == {atm_strike}",
                            "style": {"backgroundColor": "#FEF9E7"} # Очень бледный желтый для ATM
                        }
                    ]
                }
            }, 
            style={"height": "650px", "width": "100%"}, # Slightly taller
            className="ag-theme-alpine"
        )
        
        tabs.append(dcc.Tab(
            label=exp, 
            value=exp,
            children=[html.Div(grid, style={"padding": "10px"})],
            style={"padding": "10px", "fontSize": "12px", "fontWeight": "bold"},
            selected_style={"padding": "10px", "fontSize": "12px", "fontWeight": "bold", "color": CUSTOM_CSS['text_primary'], "borderTop": "2px solid #2C3E50"}
        ))
        
    # Validation: ensure current active_expiry exists in new list
    if active_expiry not in sorted_expiries:
        active_expiry = sorted_expiries[0]

    return html.Div([
        dcc.Tabs(tabs, id='board-expiry-tabs', value=active_expiry, colors={"border": "#E0E0E0", "primary": "#2C3E50", "background": "#F5F7F9"})
    ])

@callback(
    Output('active-board-expiry', 'data'),
    Input('board-expiry-tabs', 'value'),
    prevent_initial_call=True
)
def store_active_board_expiry(val):
    return val

# ... (render_3d_tab and main remain same)

def render_3d_tab(df_snap):
    # Fix expiry calculation using expiration_str
    current_time = pd.to_datetime(df_snap['snapshot_time'].iloc[0])
    # Map str back to date
    df_snap['exp_dt'] = pd.to_datetime(df_snap['expiration_str'], format='%d%b%y')
    df_snap['days_to_expiry'] = (df_snap['exp_dt'] - current_time).dt.days
    
    fig_3d = go.Figure(data=[go.Scatter3d(
        x=df_snap['strike_price'],
        y=df_snap['days_to_expiry'],
        z=df_snap['mark_iv'],
        mode='markers',
        marker=dict(
            size=3,
            color=df_snap['mark_iv'],
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
        height=600
    )
    
    return html.Div([
        dcc.Graph(figure=fig_3d)
    ], style=style_card)

@callback(
    [Output("harvest-status-badge", "children"),
     Output("harvest-status-badge", "color"),
     Output("btn-start-harvest", "disabled"),
     Output("btn-stop-harvest", "disabled"),
     Output("stat-days-done", "children"),
     Output("stat-space-saved", "children")],
    [Input("btn-start-harvest", "n_clicks"),
     Input("btn-stop-harvest", "n_clicks")],
    [State("btn-start-harvest", "disabled"),
     State("tardis-api-key", "value")],
    prevent_initial_call=True
)
def manage_harvest(start_clicks, stop_clicks, start_disabled, api_key):
    global IS_PROCESSING, SHOULD_STOP, PROCESS_LOG_BUFFER
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Load current metrics
    harvester = DataHarvester()
    days_count = len(harvester.state["processed_days"])
    space_saved = f"{harvester.space_saved_bytes / 1e9:.2f} GB"

    if trigger_id == "btn-start-harvest" and not IS_PROCESSING:
        SHOULD_STOP = False
        PROCESS_LOG_BUFFER = ["--- Init Harvesting Pipeline ---\n"]
        if not api_key:
            background_logger("ℹ️ No API Key: Running in FREE MODE (1st of each month only).")
        IS_PROCESSING = True
        
        def run_harvest():
            global IS_PROCESSING, SHOULD_STOP
            try:
                h = DataHarvester(logger=background_logger)
                h.repair_staging(demo_mode=(not api_key))
                target_dates = h.get_date_range()
                for date_str in target_dates:
                    if SHOULD_STOP:
                        break
                    
                    # Logic: Only 1st of month if no API key
                    if not api_key and not date_str.endswith("-01"):
                        continue

                    if date_str in h.state["processed_days"]: 
                        background_logger(f"⏭ Skipping {date_str} (Processed)")
                        continue
                    
                    year_month = date_str[:7]
                    url = f"https://datasets.tardis.dev/v1/deribit/options_chain/{date_str.replace('-','/')}/OPTIONS.csv.gz"
                    save_name = f"TARDIS_Snap_{date_str}.csv.gz"
                    
                    def get_stop(): return SHOULD_STOP
                    
                    # Retry logic (up to 10 attempts with heavy exponential backoff)
                    success = False
                    for attempt in range(10):
                        if SHOULD_STOP: break
                        if attempt > 0:
                            wait_time = 30 * (2 ** (attempt - 1)) # 30s, 60s, 120s, 240s...
                            background_logger(f"🔄 Retry attempt {attempt+1}/10 for {date_str} (waiting {wait_time}s)...")
                            for _ in range(wait_time): # Interruption-friendly sleep
                                if SHOULD_STOP: break
                                time.sleep(1)
                            if SHOULD_STOP: break

                        if download_file(url, save_name, logger=background_logger, stop_signal=get_stop, context_date=date_str, api_key=api_key):
                            
                            # Gap detection and market state reset BEFORE processing
                            last_done = h.state["processed_days"][-1] if h.state["processed_days"] else None
                            if last_done:
                                d1 = datetime.strptime(last_done, "%Y-%m-%d")
                                d2 = datetime.strptime(date_str, "%Y-%m-%d")
                                if (d2 - d1).days > 2:
                                    background_logger(f"🔄 Large gap detected ({ (d2-d1).days } days). Resetting market state for fresh start.")
                                    h.market_state = {"BTC": {}, "ETH": {}}

                            h.process_daily_file(save_name, date_str, stop_signal=get_stop)
                            gz_path = os.path.join("archives_all_years", save_name)
                            if os.path.exists(gz_path):
                                sz = os.path.getsize(gz_path)
                                os.remove(gz_path)
                                h.space_saved_bytes += sz
                            h.state["processed_days"].append(date_str)
                            h.state["space_saved"] = h.space_saved_bytes
                            h.save_state()
                            h.save_market_state()
                            h.check_and_consolidate(year_month, demo_mode=(not api_key))
                            success = True
                            break
                    
                    if not success and not SHOULD_STOP:
                        background_logger(f"❌ Failed to download {date_str} after 3 attempts. Moving to next.")
                
                background_logger("\n✅ Pipeline Finished or Paused.")
            except Exception as e:
                background_logger(f"\n❌ CRITICAL ERROR: {e}")
            finally:
                IS_PROCESSING = False

        thread = threading.Thread(target=run_harvest)
        thread.daemon = True
        thread.start()
        return "RUNNING", "success", False, True, str(days_count), space_saved

    elif trigger_id == "btn-stop-harvest":
        SHOULD_STOP = True
        return "STOPPING...", "warning", False, True, str(days_count), space_saved


@callback(
    [Output("loader-log", "children"),
     Output("available-metadata-store", "data", allow_duplicate=True),
     Output("status-stage", "children"),
     Output("status-date", "children"),
     Output("status-progress-bar", "value"),
     Output("status-progress-bar", "label"),
     Output("status-speed", "children"),
     Output("status-file", "children"),
     Output("status-download-info", "children")],
    [Input("loader-interval", "n_intervals")],
    prevent_initial_call=True
)
def update_loader_log(n):
    global PROCESS_LOG_BUFFER, IS_PROCESSING, STATUS_DATA
    log_text = "".join(list(reversed(PROCESS_LOG_BUFFER)))
    
    # Also refresh metadata periodically so new months appear in Analyzer
    metadata = get_processed_metadata() if n % 10 == 0 else dash.no_update
    
    download_info = f"{STATUS_DATA['downloaded']} / {STATUS_DATA['total']} MB"
    
    return (
        log_text, 
        metadata,
        STATUS_DATA["stage"],
        STATUS_DATA["date"],
        STATUS_DATA["progress"],
        f"{STATUS_DATA['progress']:.1f}%" if STATUS_DATA["progress"] > 0 else "",
        STATUS_DATA["speed"],
        STATUS_DATA["file"],
        download_info
    )


if __name__ == '__main__':
    app.run(debug=True, port=8050)
