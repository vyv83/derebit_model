"""
Options Board Renderer
======================
Renders options board with Greeks enrichment using hybrid NN+BS approach.
"""

import pandas as pd
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash import html

from config.theme import CUSTOM_CSS, GLOBAL_CHART_STYLE
from config.dashboard_config import RISK_FREE_RATE
from core.black_scholes import black_scholes_safe


class BoardRenderer:
    """
    Renders options board with AG Grid.
    Uses hybrid approach: NN for IV/Delta/Vega, BS for Gamma/Theta/Price.
    """
    
    def __init__(self):
        """Initialize BoardRenderer."""
        pass
    
    def _enrich_with_bs_greeks(self, row, spot, T, option_type):
        """
        Enrich predictions with BS Greeks.
        
        Args:
            row: DataFrame row with model predictions
            spot: Current spot price
            T: Time to expiration in years
            option_type: 'call' or 'put'
            
        Returns:
            pd.Series with price, gamma, theta from BS
        """
        greeks = black_scholes_safe(
            S=spot,
            K=row['strike'],
            T=T,
            r=RISK_FREE_RATE,  # 0.0 для крипты
            sigma=row['mark_iv'] / 100,  # Конвертируем % → доли
            option_type=option_type
        )
        
        return pd.Series({
            'price': greeks['price'],
            'gamma': greeks['gamma'],  # ← Из BS (точнее в 4.5x!)
            'theta': greeks['theta']   # ← Из BS
        })
    
    def _build_grid_columns(self):
        """
        Build AG Grid column definitions.
        
        Returns:
            List of column definitions
        """
        return [
            # Call side (right to left towards strike)
            {'field': 'vega_c', 'headerName': 'Vega', 'width': 90, 
             'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
            {'field': 'theta_c', 'headerName': 'Theta', 'width': 90, 
             'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
            {'field': 'gamma_c', 'headerName': 'Gamma', 'width': 120, 
             'valueFormatter': {"function": "d3.format(',.6f')(params.value)"}},
            {'field': 'delta_c', 'headerName': 'Delta', 'width': 90, 
             'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}, 
             'cellStyle': {'color': CUSTOM_CSS['accent_call'], 'fontWeight': 'bold'}},
            {'field': 'mark_iv_c', 'headerName': 'IV', 'width': 80, 
             'valueFormatter': {"function": "d3.format(',.1f')(params.value)"}},
            {'field': 'price_c', 'headerName': 'Price Call', 'width': 145, 
             'valueFormatter': {"function": "d3.format(',.3f')(params.value)"}, 
             'cellStyle': {'fontWeight': 'bold'}},
            
            # Middle Strike (bold center column)
            {'field': 'strike_price', 'headerName': 'STRIKE', 'width': 120, 
             'cellStyle': {
                 'fontWeight': '800', 
                 'textAlign': 'center', 
                 'backgroundColor': '#F8F9F9', 
                 'borderLeft': '2px solid #D5D8DC', 
                 'borderRight': '2px solid #D5D8DC', 
                 'fontSize': '16px'
             }},
             
            # Put side (left to right from strike)
            {'field': 'price_p', 'headerName': 'Price Put', 'width': 145, 
             'valueFormatter': {"function": "d3.format(',.3f')(params.value)"}, 
             'cellStyle': {'fontWeight': 'bold'}},
            {'field': 'mark_iv_p', 'headerName': 'IV', 'width': 80, 
             'valueFormatter': {"function": "d3.format(',.1f')(params.value)"}},
            {'field': 'delta_p', 'headerName': 'Delta', 'width': 90, 
             'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}, 
             'cellStyle': {'color': CUSTOM_CSS['accent_put'], 'fontWeight': 'bold'}},
            {'field': 'theta_p', 'headerName': 'Theta', 'width': 90, 
             'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
            {'field': 'gamma_p', 'headerName': 'Gamma', 'width': 120, 
             'valueFormatter': {"function": "d3.format(',.6f')(params.value)"}},
            {'field': 'vega_p', 'headerName': 'Vega', 'width': 90, 
             'valueFormatter': {"function": "d3.format(',.2f')(params.value)"}},
        ]
    
    def render(self, df, market_state, selected_dtes, last_board_tab):
        """
        Render options board with tabs for each DTE.
        
        Args:
            df: DataFrame with prediction data
            market_state: Market state dictionary
            selected_dtes: List of selected expiration dates (strings)
            last_board_tab: Last active board tab (for stickiness)
            
        Returns:
            dbc.Tabs component or html.Div if no data
        """
        current_date = pd.to_datetime(market_state['target_ts'])
        sorted_sel_dates = sorted(selected_dtes)  # Sort chronologically
        spot = market_state['underlying_price']
        
        tabs = []
        for date_str in sorted_sel_dates:
            exp_date = pd.to_datetime(date_str)
            dte = (exp_date - current_date).days
            if dte < 0:
                continue
            
            # Label matches the 10/10 selector style
            tab_label = f"{exp_date.strftime('%d %b')} ({dte}d)"
            
            df_dte = df[df['dte'] == dte]
            if df_dte.empty:
                continue
            
            # ============================================================================
            # ГИБРИДНЫЙ ПОДХОД: NN (IV/Delta/Vega) + BS (Gamma/Theta/Price)
            # ============================================================================
            # Calculate Prices and Greeks via Black-Scholes
            T = dte / 365.0
            
            # Separate Call and Put data
            calls = df_dte[df_dte['type'] == 'call'].copy()
            puts = df_dte[df_dte['type'] == 'put'].copy()
            
            # Обогащаем Call опционы
            # calls уже содержит: ['strike', 'mark_iv', 'delta', 'vega'] из модели
            calls_bs = calls.apply(
                lambda row: self._enrich_with_bs_greeks(row, spot, T, 'call'),
                axis=1
            )
            calls = pd.concat([calls, calls_bs], axis=1)
            # Теперь calls: ['strike', 'mark_iv', 'delta', 'vega', 'price', 'gamma', 'theta']
            
            # Обогащаем Put опционы
            puts_bs = puts.apply(
                lambda row: self._enrich_with_bs_greeks(row, spot, T, 'put'),
                axis=1
            )
            puts = pd.concat([puts, puts_bs], axis=1)
            
            calls.set_index('strike', inplace=True)
            puts.set_index('strike', inplace=True)
            
            # Merge
            combined = pd.merge(
                calls, puts, 
                left_index=True, right_index=True, 
                suffixes=('_c', '_p'), 
                how='outer'
            ).reset_index()
            # After reset_index, the index column is named 'strike' (from set_index)
            combined.rename(columns={'strike': 'strike_price'}, inplace=True)
            
            # Calculate ATM strike
            atm_strike = combined.iloc[
                (combined['strike_price'] - spot).abs().argsort()[:1]
            ]['strike_price'].values[0] if not combined.empty else 0
            
            # Build grid
            grid = dag.AgGrid(
                id={'type': 'options-grid', 'date': date_str},  # Pattern matching ID
                rowData=combined.to_dict('records'),
                columnDefs=self._build_grid_columns(),
                defaultColDef={"sortable": True, "filter": True, "resizable": True},
                dashGridOptions={
                    "headerHeight": 28,  # Reduce header height
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
                style={**GLOBAL_CHART_STYLE, "width": "100%"},
                className="ag-theme-alpine"
            )
            
            # Create tab with Bootstrap styling
            tabs.append(dbc.Tab(
                label=tab_label,
                tab_id=date_str,  # Use constant date string for stickiness
                label_style={"fontSize": "12px", "padding": "5px 10px", "fontWeight": "400"},
                children=[html.Div(grid, style={"padding": "10px"})]
            ))
        
        if not tabs:
            return html.Div(
                "Please select at least one expiration from the list above.", 
                style={
                    "padding": "40px", 
                    "textAlign": "center", 
                    "color": CUSTOM_CSS["text_secondary"]
                }
            )
        
        # Determine which tab should be active
        active = tabs[0].tab_id
        if last_board_tab:
            # Check if last viewed tab is still in current selection
            if any(t.tab_id == last_board_tab for t in tabs):
                active = last_board_tab
        
        return dbc.Tabs(tabs, id='board-dte-tabs', active_tab=active)
