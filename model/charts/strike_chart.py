"""
Strike Chart Builder
====================
Renders strike chart with OHLC candlesticks and optional IV/Theta subplots.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import dcc, html

from config.theme import CUSTOM_CSS, CHART_THEME, GLOBAL_CHART_STYLE, style_card, apply_chart_theme
from config.dashboard_config import RISK_FREE_RATE, SUBPLOT_CONFIG
from core.black_scholes import black_scholes_safe


class StrikeChartBuilder:
    """
    Builds strike chart with OHLC candlesticks and dynamic subplots.
    Generates option price history on-the-fly using the model.
    """
    
    def __init__(self, model, provider, timeseries_provider):
        """
        Initialize StrikeChartBuilder.
        
        Args:
            model: Option pricing model
            provider: Data provider for market state
            timeseries_provider: Timeseries data provider
        """
        self.model = model
        self.provider = provider
        self.timeseries_provider = timeseries_provider
    
    def _generate_ohlc_data(self, strike, option_type, exp_date, current_time, timestamps_store, currency):
        """
        Generate OHLC data for the option using model predictions.
        
        Returns:
            tuple: (ohlc_df, base_df) or (None, None) if no data
        """
        current_dt = pd.to_datetime(current_time)
        exp_dt = pd.to_datetime(exp_date)
        
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
                state = self.provider.get_market_state(date)
                if not state:
                    continue
                
                spot = state['underlying_price']
                
                # Model predicts IV for this strike
                result = self.model.predict(
                    market_state=state,
                    strikes=[strike],
                    dte_days=dte,
                    is_call=(option_type == 'call')
                )
                
                # Get IV from model (model returns in %)
                iv = result['mark_iv'].iloc[0] / 100.0
                
                # Calculate Greeks using Black-Scholes
                T = dte / 365.0
                greeks = black_scholes_safe(
                    S=spot,
                    K=strike,
                    T=T,
                    r=RISK_FREE_RATE,
                    sigma=iv,
                    option_type=option_type
                )
                
                prices_data.append({
                    'timestamp': date,
                    'price': greeks['price'],
                    'iv': iv * 100.0,
                    'theta': greeks['theta']
                })
                
                base_prices.append({
                    'timestamp': date,
                    'price': spot
                })
                
            except Exception as e:
                print(f"Error generating data for {date}: {e}")
                continue
        
        if not prices_data:
            return None, None
        
        # Process prices to compute OHLC
        ohlc_data = []
        prev_price = None
        for item in prices_data:
            price = item['price']
            open_price = prev_price if prev_price is not None else price
            
            high_price = max(open_price, price)
            low_price = min(open_price, price)
            
            ohlc_data.append({
                'timestamp': item['timestamp'],
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': price,
                'iv': item.get('iv', 0),
                'theta': item.get('theta', 0)
            })
            prev_price = price
        
        ohlc_df = pd.DataFrame(ohlc_data)
        base_df = pd.DataFrame(base_prices)
        
        return ohlc_df, base_df
    
    def _build_figure(self, ohlc_df, base_df, strike, option_type, exp_date, currency, current_time, visible_charts):
        """
        Build the plotly figure with candlesticks and subplots.
        """
        current_dt = pd.to_datetime(current_time)
        exp_dt = pd.to_datetime(exp_date)
        dte = (exp_dt - current_dt).days
        type_color = CUSTOM_CSS["accent_call"] if option_type == 'call' else CUSTOM_CSS["accent_put"]
        
        # Calculate ranges for subplots
        iv_min = ohlc_df['iv'].min()
        iv_max = ohlc_df['iv'].max()
        iv_range = [iv_min - (iv_max - iv_min)*0.1, iv_max + (iv_max - iv_min)*0.1] if iv_max > iv_min else [iv_min - 2, iv_min + 2]

        theta_min = ohlc_df['theta'].min()
        theta_max = ohlc_df['theta'].max()
        if theta_max > theta_min:
            buffer = (theta_max - theta_min) * 0.1
            theta_range = [theta_min - buffer, theta_max + buffer]
        else:
            val = theta_min
            theta_range = [val - abs(val)*0.2 - 0.01, val + abs(val)*0.2 + 0.01]

        # Determine enabled subplots
        active_subplots = []
        if isinstance(visible_charts, list):
            for key in SUBPLOT_CONFIG.keys():
                if key in visible_charts:
                    active_subplots.append(key)
        elif visible_charts is None:
            active_subplots = ['theta']

        # Dynamic Row Height Calculation
        num_subplots = len(active_subplots)
        
        if num_subplots == 0:
            row_heights = [1.0]
            specs = [[{"secondary_y": True}]]
            vertical_spacing = 0.0
        elif num_subplots == 1:
            row_heights = [0.72, 0.28]
            specs = [[{"secondary_y": True}], [{"secondary_y": False}]]
            vertical_spacing = 0.04
        else:
            price_h = 0.55
            sub_h = (1.0 - price_h) / num_subplots
            row_heights = [price_h] + [sub_h] * num_subplots
            specs = [[{"secondary_y": True}]] + [[{"secondary_y": False}]] * num_subplots
            vertical_spacing = 0.03

        fig = make_subplots(
            rows=1 + num_subplots,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=vertical_spacing,
            row_heights=row_heights,
            specs=specs
        )
        
        # Add candlestick trace
        fig.add_trace(go.Candlestick(
            x=ohlc_df['timestamp'],
            open=ohlc_df['open'],
            high=ohlc_df['high'],
            low=ohlc_df['low'],
            close=ohlc_df['close'],
            name=f"{option_type.upper()} Price",
            increasing_line_color=CUSTOM_CSS["accent_call"],
            decreasing_line_color=CUSTOM_CSS["accent_put"]
        ), row=1, col=1, secondary_y=False)
        
        # Add spot price overlay
        if not base_df.empty:
            fig.add_trace(go.Scatter(
                x=base_df['timestamp'],
                y=base_df['price'],
                name=f"{currency} Spot",
                line=dict(color='rgba(150, 150, 150, 0.6)', width=2, dash='dash')
            ), row=1, col=1, secondary_y=True)
        
        # Add subplot traces
        for i, metric_key in enumerate(active_subplots):
            row_idx = i + 2
            config = SUBPLOT_CONFIG[metric_key]
            
            fig.add_trace(go.Scatter(
                x=ohlc_df['timestamp'],
                y=ohlc_df[config['data_col']],
                name=config['title'],
                line=dict(color=config['color'], width=2),
                fill='tozeroy',
                fillcolor='rgba(155, 89, 182, 0.1)' if metric_key == 'iv' else 'rgba(230, 126, 34, 0.1)'
            ), row=row_idx, col=1)
        
        # Add horizontal lines for current prices
        current_option_price = ohlc_df.iloc[-1]['close'] if not ohlc_df.empty else None
        current_spot_price = base_df.iloc[-1]['price'] if not base_df.empty else None
        
        if current_option_price is not None:
            fig.add_shape(
                type="line",
                xref="x domain", x0=0.01, x1=0.99,
                yref="y", y0=current_option_price, y1=current_option_price,
                line=dict(
                    width=1.5,
                    color=f"rgba({int(type_color[1:3], 16)}, {int(type_color[3:5], 16)}, {int(type_color[5:7], 16)}, 0.4)"
                )
            )
            fig.add_annotation(
                xref="paper", x=0.01,
                yref="y", y=current_option_price,
                text=f" <b>${current_option_price:.2f}</b> ",
                showarrow=False,
                xanchor="left",
                yanchor="middle",
                font=dict(size=10, color=type_color),
                bgcolor="white",
                bordercolor=type_color,
                borderwidth=1,
                borderpad=4
            )
        
        if current_spot_price is not None:
            fig.add_shape(
                type="line",
                xref="x domain", x0=0.01, x1=0.96,
                yref="y2", y0=current_spot_price, y1=current_spot_price,
                line=dict(width=1.5, color="rgba(100, 100, 100, 0.3)")
            )
            fig.add_annotation(
                xref="paper", x=0.93,
                yref="y2", y=current_spot_price,
                text=f" <b>${current_spot_price:,.2f}</b> ",
                showarrow=False,
                xanchor="right",
                yanchor="middle",
                font=dict(size=10, color="rgba(60, 60, 60, 1)"),
                bgcolor="white",
                bordercolor="rgba(100, 100, 100, 0.5)",
                borderwidth=1,
                borderpad=4
            )
        
        # Apply theme and layout
        title_str = f"{currency} ${strike:,.0f} {option_type.upper()} - {exp_dt.strftime('%d %b %Y')} ({dte}d)"
        apply_chart_theme(fig, title_str)
        
        fig.update_layout(
            margin=dict(l=5, r=0, t=35, b=0),
            xaxis_rangeslider_visible=False,
            xaxis=dict(showticklabels=(num_subplots == 0)),
            yaxis=dict(title="Option Price ($)", color=type_color),
            yaxis2=dict(title="Spot Price ($)", color='gray', showgrid=False)
        )
        
        # Configure subplot axes
        for i, metric_key in enumerate(active_subplots):
            config = SUBPLOT_CONFIG[metric_key]
            y_axis_key = f"yaxis{i + 3}"
            
            axis_update = {
                y_axis_key: dict(
                    title=dict(text=config['title'], font=dict(color=config['color'], size=CHART_THEME["axis_label_size"])),
                    tickfont=dict(color=config['color'], size=CHART_THEME["tick_size"]),
                    side='left', showgrid=True, gridcolor=CHART_THEME["grid_color"],
                    fixedrange=False
                )
            }
            
            if metric_key == 'iv':
                axis_update[y_axis_key]['range'] = iv_range
            
            if metric_key == 'theta':
                axis_update[y_axis_key]['range'] = theta_range

            fig.update_layout(**axis_update)
        
        return fig
    
    def render(self, selected_strike, market_state, timestamps_store, visible_charts):
        """
        Render the strike chart.
        
        Args:
            selected_strike: Selected strike information dict
            market_state: Market state dictionary
            timestamps_store: List of timestamps
            visible_charts: List of visible chart keys
            
        Returns:
            html.Div component with the chart
        """
        # Debug info
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
        
        # Check prerequisites
        if not market_state or not self.timeseries_provider:
            return html.Div([
                debug_info,
                html.H5("Strike Chart", style={"color": CUSTOM_CSS["text_primary"]}),
                html.P("System initializing...", 
                       style={"color": CUSTOM_CSS["text_secondary"], "marginTop": "20px"})
            ], style={**style_card, "padding": "40px", "textAlign": "center"})
        
        # Check strike selection
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
        
        # Extract selection details
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
        
        # Generate OHLC data
        current_time = market_state.get('target_ts')
        if not current_time or not timestamps_store:
            return html.Div("No time data available", style=style_card)
        
        ohlc_df, base_df = self._generate_ohlc_data(
            strike, option_type, exp_date, current_time, timestamps_store, currency
        )
        
        if ohlc_df is None or ohlc_df.empty:
            current_dt = pd.to_datetime(current_time)
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
        
        # Build figure
        fig = self._build_figure(
            ohlc_df, base_df, strike, option_type, exp_date, currency, current_time, visible_charts
        )
        
        return html.Div([
            dcc.Graph(figure=fig, config={'displayModeBar': False, 'responsive': True}, style=GLOBAL_CHART_STYLE)
        ], style={**style_card, "padding": "10px 0px", "position": "relative"})
