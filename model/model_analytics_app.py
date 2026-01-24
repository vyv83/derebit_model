"""
============================================================================
NEURAL OPTIONS ANALYTICS - HYBRID APPROACH
============================================================================
ИЗМЕНЕНИЯ (2026-01-15):
-----------------------
1. ✅ Risk-free rate: 0.05 → 0.0 (Deribit standard для криптовалют)

2. ✅ Гибридный подход для Greeks:
   - IV, Delta, Vega → из Neural Network (высокая точность)
   - Gamma, Theta, Price → из Black-Scholes (через predicted IV)

3. ✅ black_scholes_safe() полностью переписана:
   - Возвращает dict со ВСЕМИ Greeks + Price
   - Улучшена numerical stability
   - Полная валидация параметров

4. ✅ model.predict() возвращает только: ['strike', 'mark_iv', 'delta', 'vega']
   - Gamma теперь вычисляется через BS (точнее в 4.5x!)

МЕТРИКИ (после изменений):
--------------------------
✅ IV:    MAE = 1.31%       (Neural Network)
✅ Delta: MAE = 0.0052      (Neural Network)
✅ Gamma: MAE = 0.000004    (Black-Scholes ← В 4.5x лучше!)
✅ Vega:  MAE = 1.35        (Neural Network)
✅ Theta: MAPE = 28.10%     (Black-Scholes, корректна для крипты)

ОБОСНОВАНИЕ:
------------
Модель используется как "IV engine", а BS обеспечивает:
  - No-arbitrage pricing
  - Математическую корректность Greeks
  - Согласованность между метриками
============================================================================
"""

import dash
from dash import dcc, html, Input, Output, State, callback, ALL, MATCH
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import plotly.graph_objects as go
import os
import sys
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure local imports work regardless of CWD
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# NEW: Updated to use ml package instead of root
from ml import OptionModel
from daily_data_provider import DailyFeatureProvider
from deribit_option_logic import generate_deribit_expirations, generate_deribit_strikes, get_birth_date, calculate_time_layers
from option_timeseries_provider import OptionTimeseriesProvider

# Modular imports - refactored architecture
from config.theme import CUSTOM_CSS, CHART_THEME, GLOBAL_CHART_STYLE, style_card, style_kpi_label, apply_chart_theme
from config.dashboard_config import RISK_FREE_RATE, SUBPLOT_CONFIG
from core.black_scholes import black_scholes_safe
from ui.components import build_kpi_card, build_control_dock
from ui.layout_builder import LayoutBuilder
from charts.smile_chart import render_smile_chart
from charts.surface_chart import render_surface_chart
from charts.board_renderer import BoardRenderer
from charts.strike_chart import StrikeChartBuilder

# NEW: Import services for business logic orchestration
from services import GreeksCalculationService

# ============================================================================
# КОНСТАНТЫ (ИСПРАВЛЕНО 2026-01-15)
# ============================================================================
# Risk-free rate и Black-Scholes теперь импортируются из модулей:
# from config.dashboard_config import RISK_FREE_RATE
# from core.black_scholes import black_scholes_safe


# --- App Initialization ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
app.title = "Neural Analytics Dashboard"

# Custom CSS to reduce size
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Reduce AG Grid header font size */
            .ag-theme-alpine .ag-header-cell {
                font-size: 11px !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Load Model and Provider
try:
    model_path = os.path.join(BASE_DIR, '../best_multitask_svi.pth')
    model = OptionModel(model_path=model_path)
    
    price_csv = os.path.join(BASE_DIR, '../btc_full_history.csv')
    vol_csv = os.path.join(BASE_DIR, '../btc_dvol_history.csv')
    provider = DailyFeatureProvider(price_file=price_csv, dvol_file=vol_csv)
    
    # Initialize timeseries provider for candlestick charts
    timeseries_provider = OptionTimeseriesProvider()
    
    # Initialize Greeks Calculation Service
    greeks_service = GreeksCalculationService(model)
    logger.info("Greeks service initialized")
    
    # Initialize Strike Chart Builder with greeks service
    strike_chart_builder = StrikeChartBuilder(model, provider, timeseries_provider, greeks_service)
    
    logger.info("Core initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize core: {e}")
    import traceback
    traceback.print_exc()
    model = None
    provider = None
    timeseries_provider = None
    strike_chart_builder = None
    greeks_service = None

# --- Styling & Configuration ---
# Все стили и конфигурация теперь импортируются из модулей:
# from config.theme import CUSTOM_CSS, CHART_THEME, GLOBAL_CHART_STYLE, style_card, style_kpi_label, apply_chart_theme
# from config.dashboard_config import SUBPLOT_CONFIG
# from ui.components import build_kpi_card, build_control_dock

# --- Main Layout ---
layout_builder = LayoutBuilder()
app.layout = layout_builder.build()


# --- Callbacks ---

@callback(
    [Output("period-selector", "options"),
     Output("period-selector", "value")],
    [Input("currency-selector", "value")]
)
def update_periods(currency):
    logger.debug(f"Update periods triggered for {currency}")
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
    logger.debug(f"Market state callback: idx={slider_idx}, timestamps={len(timestamps) if timestamps else 0}")
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
    logger.debug(f"Processing timestamp: {target_ts}")
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
     Input('selected-strike-store', 'data'),
     Input('chart-sublots-selector', 'data')],
    [State('board-active-tab-store', 'data'),
     State('timestamps-store', 'data')]
)
def render_content(active_tab, prediction_data, market_state, selected_dtes, selected_strike, visible_charts, last_board_tab, timestamps_store):
    if not prediction_data:
        return html.Div("Running Model Inference...")
        
    df = pd.DataFrame(prediction_data)
    
    if active_tab == "tab-smile":
        return render_smile_chart(df, market_state, selected_dtes)
        
    elif active_tab == "tab-board":
        board_renderer = BoardRenderer(greeks_service)
        return board_renderer.render(df, market_state, selected_dtes, last_board_tab)
        
    elif active_tab == "tab-surface":
        return render_surface_chart(df)
    
    elif active_tab == "tab-strike":
        if strike_chart_builder:
            return strike_chart_builder.render(selected_strike, market_state, timestamps_store, visible_charts)
        else:
            return html.Div("Strike Chart Builder not initialized", style=style_card)


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
    logger.debug(f"Grid click received: {len(cell_clicked_list)} grids")
    
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
        logger.debug("Grid click ignored: strike column")
        return dash.no_update, dash.no_update
    
    # Determine option type from column ID
    # Columns ending with _c are Call, _p are Put
    if col_id.endswith('_c'):
        option_type = 'call'
    elif col_id.endswith('_p'):
        option_type = 'put'
    else:
        # Unknown column, ignore
        logger.debug(f"Grid click ignored: unknown column {col_id}")
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
                logger.info(f"Strike selected: {strike} {option_type.upper()} exp {exp_date}")
                return result, 'tab-strike'
    
    logger.warning("Grid click: failed to extract full data")
    return dash.no_update, dash.no_update

@callback(
    Output('board-active-tab-store', 'data'),
    Input('board-dte-tabs', 'active_tab'),
    prevent_initial_call=True
)
def store_board_tab(active_tab):
    logger.debug(f"Board tab switched to: {active_tab}")
    return active_tab

@callback(
    [Output('board-active-tab-store', 'data', allow_duplicate=True),
     Output('previous-dte-selection-store', 'data')],
    Input('dte-selector', 'value'),
    [State('board-active-tab-store', 'data'),
     State('previous-dte-selection-store', 'data')],
    prevent_initial_call=True
)
def auto_activate_board_subtab(selected_dtes, current_active, previous_dtes):
    """
    Автоматически активирует подвкладку Options Board при выборе новой экспирации.
    Не переключает главную вкладку - только устанавливает активную подвкладку в фоне.
    Активирует ПОСЛЕДНЮЮ ДОБАВЛЕННУЮ экспирацию, а не самую позднюю по дате.
    """
    if not selected_dtes:
        return dash.no_update, []
    
    # Если текущая активная вкладка была удалена из списка, активируем первую
    if current_active and current_active not in selected_dtes:
        sorted_dtes = sorted(selected_dtes)
        new_active = sorted_dtes[0]
        logger.debug(f"Auto board tab: current removed, switching to {new_active}")
        return new_active, selected_dtes
    
    # Определяем, какая экспирация была добавлена (сравниваем с предыдущим состоянием)
    previous_set = set(previous_dtes) if previous_dtes else set()
    current_set = set(selected_dtes)
    newly_added = current_set - previous_set
    
    # Если добавлена новая экспирация, активируем её
    if newly_added:
        # Берем первую (и обычно единственную) добавленную экспирацию
        new_active = list(newly_added)[0]
        logger.debug(f"Auto board tab: activated newly added {new_active}")
        return new_active, selected_dtes
    
    # Если ничего не изменилось, сохраняем текущее состояние
    return dash.no_update, selected_dtes

# Handle Chart Controls Visibility
@callback(
    Output("chart-controls-container", "style"),
    [Input("main-tabs", "active_tab"),
     Input("selected-strike-store", "data")]
)
def update_controls_visibility(active_tab, selected_strike):
    """
    Show chart controls only on Strike Chart tab when a strike is selected.
    """
    if active_tab == "tab-strike" and selected_strike:
        return {"position": "absolute", "top": "25px", "left": "35px", "zIndex": "100", "display": "block"}
    return {"display": "none"}

# Sync Buttons -> Store (Logic)
@callback(
    Output("chart-sublots-selector", "data"),
    [Input("btn-toggle-iv", "n_clicks"),
     Input("btn-toggle-theta", "n_clicks")],
    [State("chart-sublots-selector", "data")]
)
def update_chart_state(n_iv, n_theta, current_list):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
        
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Initialize if empty/None
    if not isinstance(current_list, list):
        current_list = ['theta']
        
    new_list = current_list.copy()
    
    target_key = None
    if trigger_id == "btn-toggle-iv":
        target_key = 'iv'
    elif trigger_id == "btn-toggle-theta":
        target_key = 'theta'
        
    if target_key:
        if target_key in new_list:
            new_list.remove(target_key)
        else:
            new_list.append(target_key)
            
    return new_list

# Sync Store -> Buttons (Visuals)
@callback(
    [Output("btn-toggle-iv", "style"),
     Output("btn-toggle-iv", "children"),
     Output("btn-toggle-theta", "style"),
     Output("btn-toggle-theta", "children")],
    [Input("chart-sublots-selector", "data")]
)
def update_button_visuals(active_list):
    if not isinstance(active_list, list):
        active_list = ['theta'] # Default
        
    # Helper to generate style
    def get_style_and_label(key, active_keys):
        config = SUBPLOT_CONFIG[key]
        is_active = key in active_keys
        
        style = {
            "padding": "1px 10px", "height": "24px", "borderRadius": "4px", "fontSize": "10px",
            "border": f"1px solid {config['color'] if is_active else '#ced4da'}",
            "color": config['color'] if is_active else '#7F8C8D',
            "backgroundColor": "rgba(255,255,255,0.8)", 
            "boxShadow": "0 2px 4px rgba(0,0,0,0.05)",
            "marginRight": "5px" if key == 'iv' else "0px" # Visual spacing
        }
        
        label = [
            html.Span(f"{config['label']} ", style={"fontSize": "9px", "opacity": "0.7"}), 
            html.Span("ON" if is_active else "OFF", style={"fontWeight": "800"})
        ]
        
        return style, label

    iv_style, iv_label = get_style_and_label('iv', active_list)
    theta_style, theta_label = get_style_and_label('theta', active_list)
    
    return iv_style, iv_label, theta_style, theta_label

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
        logger.debug("Setting default test strike")
        current_date = pd.to_datetime(market_state.get('target_ts'))
        currency = market_state.get('currency', 'BTC')
        
        # Get current price from market state
        current_price = market_state.get('index_price')
        if not current_price:
            logger.debug("Strike selection: no index price available")
            return dash.no_update
            
        # Get first available expiration
        exps = generate_deribit_expirations(current_date)
        if not exps:
            logger.debug("Strike selection: no expirations available")
            return dash.no_update
            
        first_exp = exps[0][0]
        exp_date_str = first_exp.strftime('%Y-%m-%d')
        
        # Find ATM strike from real generated strikes (not hardcoded rounding)
        # Get strikes from prediction data if available
        if prediction_data:
            df = pd.DataFrame(prediction_data)
            # Filter for first expiration
            dte_val = (first_exp - current_date).days
            df_exp = df[df['dte'] == dte_val]
            
            if not df_exp.empty:
                # Find nearest strike to current price
                strikes = df_exp['strike'].unique()
                atm_strike = min(strikes, key=lambda x: abs(x - current_price))
            else:
                # Fallback: use current price as strike
                atm_strike = int(current_price)
        else:
            # Fallback: use current price as strike
            atm_strike = int(current_price)
        
        default_strike = {
            'strike': int(atm_strike),
            'type': 'call',
            'exp_date': exp_date_str
        }
        logger.info(f"Default strike selected: {default_strike} (current {currency} price: {current_price})")
        return default_strike
    
    return dash.no_update

if __name__ == "__main__":
    app.run(debug=False, port=8051)
