"""
Application State Management
============================
Centralized state management using param.Parameterized for Panel application.
Replaces Dash dcc.Store components.
"""

import param
import pandas as pd
import logging
import os
import sys

# Ensure local imports work
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from daily_data_provider import DailyFeatureProvider
from option_timeseries_provider import OptionTimeseriesProvider
from deribit_option_logic import generate_deribit_expirations, generate_deribit_strikes, get_birth_date, calculate_time_layers
from ml import OptionModel
from services import GreeksCalculationService
from config.dashboard_config import RISK_FREE_RATE

logger = logging.getLogger(__name__)


class AppState(param.Parameterized):
    """
    Central application state.
    All reactive state is managed here via param parameters.
    """
    
    # ========== Selectors ==========
    currency = param.Selector(default='BTC', objects=['BTC', 'ETH'], doc="Selected cryptocurrency")
    period = param.Selector(default='2024', objects=['2021', '2022', '2023', '2024', '2025'], doc="Selected year")
    
    # ========== Time Navigation ==========
    timestamps = param.List(default=[], doc="List of available date strings")
    time_index = param.Integer(default=0, bounds=(0, None), doc="Current position in timestamps")
    
    # ========== Market Data ==========
    market_state = param.Dict(default={}, doc="Current market state dictionary")
    predictions = param.List(default=[], doc="Model predictions for all expirations")
    
    # ========== Expirations ==========
    dte_options = param.List(default=[], doc="Available DTE options [{'label': '...', 'value': '...'}]")
    selected_dtes = param.List(default=[], doc="Selected expiration date strings")
    _previous_dtes = param.List(default=[], doc="Previous selection for set difference logic")
    
    # ========== Board Tab ==========
    board_active_tab = param.String(default=None, allow_None=True, doc="Active board subtab date string")
    
    # ========== Strike Chart ==========
    selected_strike = param.Dict(default=None, allow_None=True, 
                                  doc="Selected strike: {'strike': float, 'type': str, 'exp_date': str}")
    visible_charts = param.List(default=['theta'], doc="Visible subplot charts ['iv', 'theta']")
    
    # ========== Active Tab ==========
    active_tab = param.String(default='Smile', doc="Currently active main tab")
    
    # ========== KPI Values (for display) ==========
    kpi_spot = param.String(default='-', doc="Spot price display value")
    kpi_atm_iv = param.String(default='-', doc="ATM IV display value")
    kpi_hv = param.String(default='-', doc="HV 30D display value")
    time_display = param.String(default='TIME SNAPSHOT: -', doc="Time display string")
    
    def __init__(self, **params):
        super().__init__(**params)
        
        # Initialize providers and model
        self._init_providers()
        
        # Initial data load
        self._reconfigure_timestamps()
    
    def _init_providers(self):
        """Initialize data providers and model."""
        try:
            # Model
            model_path = os.path.join(BASE_DIR, '../best_multitask_svi.pth')
            self.model = OptionModel(model_path=model_path)
            
            # Data providers
            price_csv = os.path.join(BASE_DIR, '../btc_full_history.csv')
            vol_csv = os.path.join(BASE_DIR, '../btc_dvol_history.csv')
            self.provider = DailyFeatureProvider(price_file=price_csv, dvol_file=vol_csv)
            
            # Timeseries provider for candlestick charts
            self.timeseries_provider = OptionTimeseriesProvider()
            
            # Greeks calculation service
            self.greeks_service = GreeksCalculationService(self.model)
            
            logger.info("AppState: All providers initialized successfully")
            
        except Exception as e:
            logger.error(f"AppState: Failed to initialize providers: {e}")
            import traceback
            traceback.print_exc()
            self.model = None
            self.provider = None
            self.timeseries_provider = None
            self.greeks_service = None
    
    # ========== Watchers ==========
    
    @param.depends('currency', 'period', watch=True)
    def _reconfigure_timestamps(self):
        """Reconfigure timestamps when currency or period changes."""
        if not self.provider:
            self.timestamps = []
            self.time_index = 0
            return
        
        try:
            all_dates = self.provider.get_date_range()
            year_dates = all_dates[all_dates.year == int(self.period)]
            
            if len(year_dates) == 0:
                self.timestamps = []
                self.time_index = 0
                return
            
            self.timestamps = [d.strftime("%Y-%m-%d") for d in year_dates]
            self.time_index = 0  # Reset to start
            
            logger.info(f"AppState: Loaded {len(self.timestamps)} timestamps for {self.currency}/{self.period}")
            
        except Exception as e:
            logger.error(f"AppState: Error loading timestamps: {e}")
            self.timestamps = []
            self.time_index = 0
    
    @param.depends('time_index', 'timestamps', watch=True)
    def _update_market_state(self):
        """Update market state when time_index changes."""
        if not self.timestamps or not self.provider:
            self.market_state = {}
            self.kpi_spot = '-'
            self.kpi_atm_iv = '-'
            self.kpi_hv = '-'
            self.time_display = 'TIME SNAPSHOT: -'
            return
        
        # Bounds check
        idx = min(max(0, self.time_index), len(self.timestamps) - 1)
        target_ts = self.timestamps[idx]
        
        try:
            state = self.provider.get_market_state(pd.to_datetime(target_ts))
            
            if not state:
                self.market_state = {}
                self.kpi_spot = 'N/A'
                self.kpi_atm_iv = 'N/A'
                self.kpi_hv = 'N/A'
                self.time_display = f"TIME SNAPSHOT: {pd.to_datetime(target_ts).strftime('%d %b %Y')}"
                return
            
            self.market_state = state
            
            # Update KPIs
            spot = state.get('underlying_price', 0)
            atm_iv = state.get('Real_IV_ATM', state.get('HV_30d', 0)) * 100
            hv = state.get('HV_30d', 0) * 100
            
            self.kpi_spot = f"${spot:,.2f}"
            self.kpi_atm_iv = f"{atm_iv:.1f}%"
            self.kpi_hv = f"{hv:.1f}%"
            self.time_display = f"TIME SNAPSHOT: {pd.to_datetime(target_ts).strftime('%d %b %Y')}"
            
            logger.debug(f"AppState: Market state updated for {target_ts}")
            
        except Exception as e:
            logger.error(f"AppState: Error updating market state: {e}")
            self.market_state = {}
    
    @param.depends('market_state', watch=True)
    def _update_dte_options(self):
        """Update DTE options when market_state changes. Implements STICKY selection."""
        if not self.market_state or 'target_ts' not in self.market_state:
            self.dte_options = []
            self.selected_dtes = []
            return
        
        try:
            current_date = pd.to_datetime(self.market_state['target_ts'])
            exps = generate_deribit_expirations(current_date)
            
            new_options = []
            for d, count in exps:
                dte = (d - current_date).days
                if dte < 0:
                    continue
                new_options.append({
                    'label': f"{d.strftime('%d %b')} ({dte}d)",
                    'value': d.strftime('%Y-%m-%d')
                })
            
            self.dte_options = new_options
            
            # STICKY: Keep selection if still valid
            valid_values = [opt['value'] for opt in new_options]
            kept_values = [v for v in self.selected_dtes if v in valid_values]
            
            # Default to first 3 if nothing selected
            if not kept_values and new_options:
                kept_values = [new_options[i]['value'] for i in range(min(3, len(new_options)))]
            
            self.selected_dtes = kept_values
            
            logger.debug(f"AppState: Updated DTE options, selected: {len(kept_values)}")
            
        except Exception as e:
            logger.error(f"AppState: Error updating DTE options: {e}")
            self.dte_options = []
            self.selected_dtes = []
    
    @param.depends('selected_dtes', watch=True)
    def _auto_activate_board_subtab(self):
        """Auto-activate newly added DTE in board tabs using set difference."""
        if not self.selected_dtes:
            return
        
        # If current active tab was removed, switch to first
        if self.board_active_tab and self.board_active_tab not in self.selected_dtes:
            sorted_dtes = sorted(self.selected_dtes)
            self.board_active_tab = sorted_dtes[0] if sorted_dtes else None
            self._previous_dtes = list(self.selected_dtes)
            return
        
        # Set difference: find newly added
        previous_set = set(self._previous_dtes) if self._previous_dtes else set()
        current_set = set(self.selected_dtes)
        newly_added = current_set - previous_set
        
        if newly_added:
            # Activate the newly added one
            self.board_active_tab = sorted(list(newly_added))[0]
        
        self._previous_dtes = list(self.selected_dtes)
    
    @param.depends('market_state', 'selected_dtes', watch=True)
    def _run_model_inference(self):
        """Run model inference for ALL expirations (not just selected)."""
        if not self.market_state or not self.model:
            self.predictions = []
            return
        
        try:
            current_date = pd.to_datetime(self.market_state['target_ts'])
            spot = self.market_state.get('underlying_price', 0)
            vol = self.market_state.get('Real_IV_ATM', self.market_state.get('HV_30d', 0.80))
            
            # Generate predictions for ALL expirations (for 3D surface)
            all_exps = generate_deribit_expirations(current_date)
            all_predictions = []
            
            for exp, cnt in all_exps:
                dte = (exp - current_date).days
                if dte <= 0:
                    continue
                
                # Determine Anchor (Birth) Parameters - matches original Dash logic
                birth_date, birth_dte = get_birth_date(exp)
                anchor_state = self.provider.get_market_state(birth_date)
                
                if anchor_state:
                    anchor_spot = anchor_state['underlying_price']
                    anchor_vol = anchor_state.get('Real_IV_ATM', anchor_state.get('HV_30d', 0.8))
                else:
                    anchor_spot = spot
                    anchor_vol = vol
                
                # Get Geological Layers
                time_layers = calculate_time_layers(current_date, birth_date)
                hist_ranges = []
                for l_type, l_start, l_end in time_layers:
                    h_min, h_max = self.provider.get_high_low(l_start, l_end)
                    if h_min is not None and h_max is not None:
                        hist_ranges.append((l_type, h_min, h_max))
                if not hist_ranges:
                    hist_ranges = [('daily', spot, spot)]
                
                # Get Full History for V5 Proper Simulation
                try:
                    mask = (self.provider.df_merged.index >= birth_date) & (self.provider.df_merged.index <= current_date)
                    hist_df = self.provider.df_merged.loc[mask]
                    price_hist = hist_df['Close'].tolist()
                    iv_hist = hist_df['Real_IV_ATM'].tolist()
                except Exception:
                    price_hist = None
                    iv_hist = None
                
                # Generate strikes with V5 logic (matches original Dash)
                dte_strikes = generate_deribit_strikes(
                    current_spot=spot,
                    current_dte=dte,
                    anchor_spot=anchor_spot,
                    anchor_vol=anchor_vol,
                    birth_dte=birth_dte,
                    historical_ranges=hist_ranges,
                    coincidence_count=cnt,
                    price_history=price_hist,
                    iv_history=iv_hist
                )
                
                if not dte_strikes:
                    continue
                
                # Predict for calls
                try:
                    result_call = self.model.predict(
                        market_state=self.market_state,
                        strikes=dte_strikes,
                        dte_days=dte,
                        is_call=True
                    )
                    result_call['type'] = 'call'
                    result_call['dte'] = dte
                    all_predictions.append(result_call)
                except Exception as e:
                    logger.warning(f"Call prediction failed for DTE {dte}: {e}")
                
                # Predict for puts
                try:
                    result_put = self.model.predict(
                        market_state=self.market_state,
                        strikes=dte_strikes,
                        dte_days=dte,
                        is_call=False
                    )
                    result_put['type'] = 'put'
                    result_put['dte'] = dte
                    all_predictions.append(result_put)
                except Exception as e:
                    logger.warning(f"Put prediction failed for DTE {dte}: {e}")
            
            # Combine all predictions
            if all_predictions:
                combined_df = pd.concat(all_predictions, ignore_index=True)
                self.predictions = combined_df.to_dict('records')
            else:
                self.predictions = []
            
            logger.info(f"AppState: Generated {len(self.predictions)} prediction records")
            
        except Exception as e:
            logger.error(f"AppState: Error running model inference: {e}")
            import traceback
            traceback.print_exc()
            self.predictions = []
    
    # ========== Navigation Methods ==========
    
    def on_play_click(self, event=None):
        """Move forward in time (cyclic)."""
        if not self.timestamps:
            return
        max_val = len(self.timestamps) - 1
        if self.time_index >= max_val:
            self.time_index = 0  # Wrap to start
        else:
            self.time_index = self.time_index + 1
    
    def on_back_click(self, event=None):
        """Move backward in time (cyclic)."""
        if not self.timestamps:
            return
        max_val = len(self.timestamps) - 1
        if self.time_index <= 0:
            self.time_index = max_val  # Wrap to end
        else:
            self.time_index = self.time_index - 1
    
    # ========== Toggle Methods ==========
    
    def toggle_iv(self, event=None):
        """Toggle IV subplot visibility."""
        if 'iv' in self.visible_charts:
            self.visible_charts = [c for c in self.visible_charts if c != 'iv']
        else:
            self.visible_charts = self.visible_charts + ['iv']
    
    def toggle_theta(self, event=None):
        """Toggle Theta subplot visibility."""
        if 'theta' in self.visible_charts:
            self.visible_charts = [c for c in self.visible_charts if c != 'theta']
        else:
            self.visible_charts = self.visible_charts + ['theta']
    
    # ========== Utility Methods ==========
    
    def get_predictions_df(self):
        """Get predictions as DataFrame."""
        if not self.predictions:
            return pd.DataFrame()
        return pd.DataFrame(self.predictions)
    
    def get_slider_marks(self):
        """Generate slider marks (only first day of each month)."""
        if not self.timestamps:
            return {}
        
        marks = {}
        for i, ts in enumerate(self.timestamps):
            dt = pd.to_datetime(ts)
            if dt.day == 1:
                marks[i] = dt.strftime("%b")
        return marks
    
    def set_default_strike(self):
        """Set default strike when Strike Chart tab is activated."""
        if not self.market_state or self.selected_strike:
            return
        
        # Get predictions
        df = self.get_predictions_df()
        if df.empty:
            return
        
        # Find ATM strike
        spot = self.market_state.get('index_price', self.market_state.get('underlying_price', 0))
        if not spot:
            return
        
        # Get first expiration
        if not self.selected_dtes:
            return
        
        exp_date = sorted(self.selected_dtes)[0]
        
        # Find closest strike to spot
        call_df = df[(df['type'] == 'call')]
        if call_df.empty:
            return
        
        closest_idx = (call_df['strike'] - spot).abs().idxmin()
        closest_strike = call_df.loc[closest_idx, 'strike']
        
        self.selected_strike = {
            'strike': closest_strike,
            'type': 'call',
            'exp_date': exp_date
        }
        
        logger.info(f"AppState: Set default strike to {closest_strike}")
