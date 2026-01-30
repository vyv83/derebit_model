"""
Board View
==========
Options board with Greeks using Tabulator.
Shows both Calls and Puts with hybrid NN+BS Greeks calculation.
"""

import panel as pn
import param
import pandas as pd
import logging

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.theme import CUSTOM_CSS
from config.dashboard_config import RISK_FREE_RATE
from core.black_scholes import black_scholes_safe

logger = logging.getLogger(__name__)


class BoardView(pn.viewable.Viewer):
    """Options Board view with Tabulator grids."""
    
    def __init__(self, state, **params):
        super().__init__(**params)
        self.state = state
        self._tabs = None
    
    def _enrich_with_bs_greeks(self, row, spot, T, option_type):
        """Enrich predictions with BS Greeks (Gamma, Theta, Price)."""
        try:
            greeks = black_scholes_safe(
                S=spot,
                K=row['strike'],
                T=T,
                r=RISK_FREE_RATE,  # 0.0 for crypto
                sigma=row['mark_iv'] / 100,  # Convert % to decimal
                option_type=option_type
            )
            return pd.Series({
                'price': greeks['price'],
                'gamma': greeks['gamma'],
                'theta': greeks['theta']
            })
        except Exception as e:
            logger.warning(f"BS calculation failed: {e}")
            return pd.Series({'price': 0, 'gamma': 0, 'theta': 0})
    
    def _create_grid_for_dte(self, df_dte, exp_date, spot, dte):
        """Create a Tabulator grid for one expiration."""
        T = dte / 365.0
        
        # Separate Calls and Puts
        calls = df_dte[df_dte['type'] == 'call'].copy()
        puts = df_dte[df_dte['type'] == 'put'].copy()
        
        if calls.empty or puts.empty:
            return pn.pane.HTML(f"<p>Insufficient data for {exp_date}</p>")
        
        # Enrich with BS Greeks
        calls_bs = calls.apply(
            lambda row: self._enrich_with_bs_greeks(row, spot, T, 'call'),
            axis=1
        )
        calls = pd.concat([calls, calls_bs], axis=1)
        
        puts_bs = puts.apply(
            lambda row: self._enrich_with_bs_greeks(row, spot, T, 'put'),
            axis=1
        )
        puts = pd.concat([puts, puts_bs], axis=1)
        
        # Set index for merge
        calls.set_index('strike', inplace=True)
        puts.set_index('strike', inplace=True)
        
        # Merge with suffixes
        combined = pd.merge(
            calls, puts,
            left_index=True, right_index=True,
            suffixes=('_c', '_p'),
            how='outer'
        ).reset_index()
        combined.rename(columns={'strike': 'strike_price'}, inplace=True)
        
        # Calculate ATM strike
        atm_strike = 0
        if not combined.empty:
            closest_idx = (combined['strike_price'] - spot).abs().idxmin()
            atm_strike = combined.loc[closest_idx, 'strike_price']
        
        # Add ATM marker column for styling
        combined['_is_atm'] = combined['strike_price'] == atm_strike
        
        # Select and reorder columns for display
        display_cols = [
            'vega_c', 'theta_c', 'gamma_c', 'delta_c', 'mark_iv_c', 'price_c',
            'strike_price',
            'price_p', 'mark_iv_p', 'delta_p', 'theta_p', 'gamma_p', 'vega_p'
        ]
        
        # Only keep columns that exist
        available_cols = [c for c in display_cols if c in combined.columns]
        display_df = combined[available_cols].copy()
        
        # Format column names for display
        col_titles = {
            'vega_c': 'Vega', 'theta_c': 'Θ', 'gamma_c': 'Γ', 
            'delta_c': 'Δ', 'mark_iv_c': 'IV', 'price_c': 'Price Call',
            'strike_price': 'STRIKE',
            'price_p': 'Price Put', 'mark_iv_p': 'IV',
            'delta_p': 'Δ', 'theta_p': 'Θ', 'gamma_p': 'Γ', 'vega_p': 'Vega'
        }
        
        # Configure Tabulator formatters
        formatters = {
            'vega_c': {'type': 'money', 'precision': 2},
            'theta_c': {'type': 'money', 'precision': 2},
            'gamma_c': {'type': 'money', 'precision': 6},
            'delta_c': {'type': 'money', 'precision': 2},
            'mark_iv_c': {'type': 'money', 'precision': 1},
            'price_c': {'type': 'money', 'precision': 3},
            'strike_price': {'type': 'money', 'precision': 0},
            'price_p': {'type': 'money', 'precision': 3},
            'mark_iv_p': {'type': 'money', 'precision': 1},
            'delta_p': {'type': 'money', 'precision': 2},
            'theta_p': {'type': 'money', 'precision': 2},
            'gamma_p': {'type': 'money', 'precision': 6},
            'vega_p': {'type': 'money', 'precision': 2},
        }
        
        # Find ATM row index for CSS styling
        atm_row_idx = combined[combined['_is_atm']].index.tolist()
        atm_css = ""
        if atm_row_idx:
            # CSS nth-child is 1-indexed, +1 for header
            atm_row_num = atm_row_idx[0] + 1
            atm_css = f":host .tabulator-row:nth-child({atm_row_num}) {{ background-color: #FEF9E7 !important; }}"
        
        # Tabulator configuration with compact styling - NO row_content (removes arrows!)
        table = pn.widgets.Tabulator(
            display_df,
            layout='fit_columns',
            sizing_mode='stretch_both',
            height_policy='max',
            min_height=600,
            show_index=False,
            titles=col_titles,
            formatters=formatters,
            editors={c: None for c in display_df.columns}, # Explicitly disable all editors
            text_align={'strike_price': 'center'},
            header_align='center',
            selectable='row',
            theme='bootstrap5',  # Compact theme
            configuration={
                'rowHeight': 28,  # Compact rows
                'headerHeight': 32,  # Sufficient height for centering
                'renderVerticalBuffer': 300,  # Reduce flickering
            },
            stylesheets=[f'''
                :host .tabulator {{
                    font-size: 11px !important;
                }}
                :host .tabulator-header {{
                    font-size: 10px !important;
                    font-weight: 600 !important;
                    height: 32px !important;
                }}
                :host .tabulator-row {{
                    min-height: 28px !important;
                    max-height: 28px !important;
                }}
                :host .tabulator-cell {{
                    padding: 2px 4px !important;
                }}
                :host .tabulator-cell[tabulator-field="strike_price"] {{
                    font-weight: 800 !important;
                    font-size: 12px !important;
                    background-color: #F8F9F9 !important;
                }}
                :host .tabulator-cell[tabulator-field="delta_c"] {{ color: #76D7C4 !important; font-weight: bold !important; }}
                :host .tabulator-cell[tabulator-field="delta_p"] {{ color: #FF8787 !important; font-weight: bold !important; }}
                :host .tabulator-cell[tabulator-field="price_c"],
                :host .tabulator-cell[tabulator-field="price_p"] {{ font-weight: bold !important; }}
                {atm_css}
            ''']
        )
        
        # Add click handler with closure for exp_date
        def on_row_click(event):
            if event.row is None:
                return
            
            row_data = display_df.iloc[event.row]
            col = event.column
            
            # Ignore strike_price clicks
            if col == 'strike_price':
                return
            
            # Determine option type from column suffix
            if col.endswith('_c'):
                option_type = 'call'
            elif col.endswith('_p'):
                option_type = 'put'
            else:
                return
            
            strike = row_data['strike_price']
            
            # Update state
            self.state.selected_strike = {
                'strike': strike,
                'type': option_type,
                'exp_date': exp_date  # From closure!
            }
            self.state.active_tab = 'Strike Chart'
            
            logger.info(f"BoardView: Selected {option_type} strike {strike} for {exp_date}")
        
        table.on_click(on_row_click)
        
        return pn.Column(table, margin=5)
    
    def _render_board(self):
        """Render the options board with tabs for each DTE."""
        df = self.state.get_predictions_df()
        market_state = self.state.market_state
        selected_dtes = self.state.selected_dtes
        
        if df.empty:
            return self._empty_message("No prediction data available")
        
        if not market_state or 'target_ts' not in market_state:
            return self._empty_message("Market state not available")
        
        if not selected_dtes:
            return self._empty_message("Please select at least one expiration from the list above")
        
        current_date = pd.to_datetime(market_state['target_ts'])
        spot = market_state.get('underlying_price', 0)
        
        # Build tabs for each selected DTE
        tabs = []
        sorted_dtes = sorted(selected_dtes)
        
        for date_str in sorted_dtes:
            exp_date = pd.to_datetime(date_str)
            dte = (exp_date - current_date).days
            
            if dte < 0:
                continue
            
            # Filter predictions for this DTE
            df_dte = df[df['dte'] == dte]
            
            if df_dte.empty:
                continue
            
            # Tab label matches original style
            tab_label = f"{exp_date.strftime('%d %b')} ({dte}d)"
            
            # Create grid for this expiration
            grid = self._create_grid_for_dte(df_dte, date_str, spot, dte)
            
            tabs.append((tab_label, grid))
        
        if not tabs:
            return self._empty_message("No data for selected expirations")
        
        # Create Tabs widget
        tabs_widget = pn.Tabs(
            *tabs,
            tabs_location='above',
            css_classes=['board-subtabs'],
            dynamic=True
        )
        
        # Handle active tab persistence - check bounds first
        if self.state.board_active_tab and len(tabs) > 0:
            # Find matching tab index
            for i, date_str in enumerate(sorted_dtes):
                if date_str == self.state.board_active_tab and i < len(tabs):
                    tabs_widget.active = i
                    break
        
        # Watch for tab changes
        def on_tab_change(event):
            if event.new < len(sorted_dtes):
                self.state.board_active_tab = sorted_dtes[event.new]
        
        tabs_widget.param.watch(on_tab_change, 'active')
        
        return tabs_widget
    
    def _empty_message(self, message):
        """Create empty state message."""
        return pn.pane.HTML(
            f'''
            <div class="placeholder-message">
                <h5>Options Board</h5>
                <p>{message}</p>
            </div>
            ''',
            sizing_mode='stretch_both'
        )
    
    @param.depends('state.predictions', 'state.selected_dtes', 'state.market_state')
    def __panel__(self):
        return pn.Column(
            self._render_board(),
            css_classes=['card'],
            sizing_mode='stretch_both'
        )
