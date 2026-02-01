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
        self._tab_cache = {}  # Map date_str -> (container, tabulator, base_css)
        self._current_tab_labels = [] # Track current labels to avoid unnecessary updates
        
        # Initialize the tabs widget once
        self._tabs_widget = pn.Tabs(
            tabs_location='above',
            css_classes=['board-subtabs'],
            dynamic=True
        )
        self._tabs_widget.param.watch(self._on_tab_ui_change, 'active')
        
        # Main container that holds the view
        self._main_container = pn.Column(
            css_classes=['card'],
            sizing_mode='stretch_both'
        )
        
        # Watchers for data updates
        self.state.param.watch(self._update_view, ['predictions', 'selected_dtes', 'market_state'])
        
        # Watch state for programmatic tab switching
        self.state.param.watch(self._sync_active_tab_from_state, 'board_active_tab')
        
        # Initial render
        self._update_view()

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

    def _prepare_display_data(self, df_dte, spot, dte):
        """Prepare DataFrame and ATM CSS for a given expiration."""
        T = dte / 365.0
        
        # Separate Calls and Puts
        calls = df_dte[df_dte['type'] == 'call'].copy()
        puts = df_dte[df_dte['type'] == 'put'].copy()
        
        if calls.empty or puts.empty:
            return None, None
        
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
            'price_p', 'mark_iv_p', 'delta_p', 'theta_p', 'gamma_p', 'vega_p',
            '_is_atm'
        ]
        
        # Only keep columns that exist
        available_cols = [c for c in display_cols if c in combined.columns]
        display_df = combined[available_cols].copy()
        
        # Create css for ATM row
        atm_row_idx = display_df[display_df['_is_atm']].index.tolist()
        atm_css = ""
        if atm_row_idx:
            # CSS nth-child is 1-indexed, +1 for header
            atm_row_num = atm_row_idx[0] + 1
            atm_css = f":host .tabulator-row:nth-child({atm_row_num}) {{ background-color: #FEF9E7 !important; }}"
        
        # Drop helper column
        if '_is_atm' in display_df.columns:
            display_df = display_df.drop(columns=['_is_atm'])
            
        return display_df, atm_css

    def _create_tabulator(self, display_df, atm_css, exp_date_str):
        """Create a new Tabulator widget."""
        # Col titles
        col_titles = {
            'vega_c': 'Vega', 'theta_c': 'Θ', 'gamma_c': 'Γ', 
            'delta_c': 'Δ', 'mark_iv_c': 'IV', 'price_c': 'Price Call',
            'strike_price': 'STRIKE',
            'price_p': 'Price Put', 'mark_iv_p': 'IV',
            'delta_p': 'Δ', 'theta_p': 'Θ', 'gamma_p': 'Γ', 'vega_p': 'Vega'
        }
        
        # Formatters
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
        
        # Base Stylesheet
        base_css = f'''
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
        '''
        
        table = pn.widgets.Tabulator(
            display_df,
            layout='fit_columns',
            sizing_mode='stretch_both',
            height_policy='max',
            min_height=600,
            show_index=False,
            titles=col_titles,
            formatters=formatters,
            editors={c: None for c in display_df.columns},
            text_align={'strike_price': 'center'},
            header_align='center',
            selectable='row',
            theme='bootstrap5',
            configuration={
                'rowHeight': 28,
                'headerHeight': 32,
                'renderVerticalBuffer': 300,
            },
            stylesheets=[base_css + atm_css]
        )
        
        # Click Handler
        def on_row_click(event):
            if event.row is None:
                return
            
            # Note: event.model is the table, we can get data from it
            # But safer to look up in the current value df
            current_df = table.value
            if current_df is None or len(current_df) <= event.row:
                return
                
            row_data = current_df.iloc[event.row]
            col = event.column
            
            if col == 'strike_price':
                return
            
            if col.endswith('_c'):
                option_type = 'call'
            elif col.endswith('_p'):
                option_type = 'put'
            else:
                return
            
            strike = row_data['strike_price']
            
            self.state.selected_strike = {
                'strike': strike,
                'type': option_type,
                'exp_date': exp_date_str
            }
            self.state.active_tab = 'Strike Chart'
            logger.info(f"BoardView: Selected {option_type} strike {strike} for {exp_date_str}")
            
        table.on_click(on_row_click)
        return table, base_css

    def _update_view(self, event=None):
        """Update the board view safely."""
        df = self.state.get_predictions_df()
        market_state = self.state.market_state
        selected_dtes = self.state.selected_dtes
        
        # Validation
        if df.empty:
            self._set_empty("No prediction data available")
            return
        if not market_state or 'target_ts' not in market_state:
            self._set_empty("Market state not available")
            return
        if not selected_dtes:
            self._set_empty("Please select at least one expiration from the list above")
            return
            
        # NORMALIZE to midnight to allow DTE=0 (same day expiration)
        current_date = pd.to_datetime(market_state['target_ts']).normalize()
        spot = market_state.get('underlying_price', 0)
        
        sorted_dtes = sorted(selected_dtes)
        new_tabs = []
        new_labels = []
        
        for date_str in sorted_dtes:
            exp_date = pd.to_datetime(date_str)
            dte = (exp_date - current_date).days
            
            if dte < 0:
                continue
                
            df_dte = df[df['dte'] == dte]
            if df_dte.empty:
                continue
                
            # Prepare data
            display_df, atm_css = self._prepare_display_data(df_dte, spot, dte)
            if display_df is None:
                continue
                
            # Check cache
            if date_str in self._tab_cache:
                container, table, base_css = self._tab_cache[date_str]
                # Update data
                if not table.value.equals(display_df):
                    table.value = display_df
                # Always update stylesheets to ensure ATM highlight is correct
                # Doing this is cheap if string is same, but useful if ATM moved
                new_css_list = [base_css + atm_css]
                if table.stylesheets != new_css_list:
                    table.stylesheets = new_css_list
            else:
                # Create new
                table, base_css = self._create_tabulator(display_df, atm_css, date_str)
                container = pn.Column(table, margin=5)
                self._tab_cache[date_str] = (container, table, base_css)
            
            tab_label = f"{exp_date.strftime('%d %b')} ({dte}d)"
            new_tabs.append((tab_label, container))
            new_labels.append(tab_label)
            
        if not new_tabs:
            self._set_empty("No data for selected expirations")
            return
            
        # Update tabs list logic
        # Optimize: Only reset objects if list structure (labels) changed
        if self._current_tab_labels != new_labels:
             self._tabs_widget[:] = new_tabs
             self._current_tab_labels = new_labels
        
        # Ensure correct active tab
        self._sync_active_tab_from_state()
        
        # Ensure main container shows tabs
        if self._main_container.objects != [self._tabs_widget]:
            self._main_container[:] = [self._tabs_widget]

    def _sync_active_tab_from_state(self, event=None):
        """Sync widget active tab to match state."""
        target_date = self.state.board_active_tab
        if not target_date or len(self._tabs_widget) == 0:
            return
            
        # Re-derive valid dates in order
        df = self.state.get_predictions_df()
        if df.empty: return
        market_state = self.state.market_state
        if not market_state: return
        current_date = pd.to_datetime(market_state.get('target_ts'))
        sorted_dtes = sorted(self.state.selected_dtes)
        
        valid_dates = []
        for d in sorted_dtes:
             exp_date = pd.to_datetime(d)
             dte = (exp_date - current_date).days
             if dte >= 0 and not df[df['dte'] == dte].empty:
                  valid_dates.append(d)
        
        if target_date in valid_dates:
            idx = valid_dates.index(target_date)
            # Check range
            if idx < len(self._tabs_widget):
                # Only update if different to avoid event loops or visual jarring
                if self._tabs_widget.active != idx:
                    self._tabs_widget.active = idx

    def _on_tab_ui_change(self, event):
        """Handle user changing tab in UI."""
        df = self.state.get_predictions_df()
        if df.empty: return
        market_state = self.state.market_state
        if not market_state: return
        current_date = pd.to_datetime(market_state.get('target_ts'))
        sorted_dtes = sorted(self.state.selected_dtes)
        
        valid_dates = []
        for d in sorted_dtes:
             exp_date = pd.to_datetime(d)
             dte = (exp_date - current_date).days
             if dte >= 0 and not df[df['dte'] == dte].empty:
                  valid_dates.append(d)
                  
        if event.new < len(valid_dates):
            new_date = valid_dates[event.new]
            if self.state.board_active_tab != new_date:
                self.state.board_active_tab = new_date

    def _set_empty(self, message):
        """Show empty message."""
        self._current_tab_labels = [] # Reset labels
        obj = pn.pane.HTML(
            f'''
            <div class="placeholder-message">
                <h5>Options Board</h5>
                <p>{message}</p>
            </div>
            ''',
            sizing_mode='stretch_both'
        )
        self._main_container[:] = [obj]

    def __panel__(self):
        return self._main_container
