"""
ФАЙЛ: smile_chart.py
НАЗНАЧЕНИЕ: Smile Chart - Volatility Smile и греки по страйкам (CSS Grid layout)
ЗАВИСИМОСТИ: bokeh_components.py, bokeh, jinja2, scipy
ТЕСТ: python smile_chart.py → откроется браузер

ЧЕКЛИСТ ПРОВЕРКИ:
[ ] Toggle кнопки IV/Θ/Δ/Γ/ν работают
[ ] При отключении грека - grid перестраивается
[ ] Линии для разных DTE имеют разные оттенки
[ ] Hover показывает значения
"""

import pandas as pd
import numpy as np
import webbrowser
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool, NumeralTickFormatter, Label
from bokeh.embed import components
from bokeh.resources import CDN
from jinja2 import Template

# ИМПОРТ ИЗ ОБЩЕГО МОДУЛЯ
from bokeh_components import (
    COLORS, GREEK_ORDER, GREEK_SYMBOLS, GREEK_LABELS, GREEK_FORMATS,
    PANEL_STYLE, CONFIG,
    get_toggle_css, get_grid_layout_css, get_grid_layout_js,
    adjust_color, get_dte_colors, format_greek_value
)

# ============================================================================
# HTML TEMPLATE
# ============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        body { 
            font-family: 'SF Mono', Monaco, monospace; 
            margin: 0; 
            padding: 8px; 
            background: #f8f9fa; 
            height: 100vh; 
            box-sizing: border-box; 
            display: flex;
            flex-direction: column;
            overflow: hidden; 
        }
        {{ toggle_css }}
        {{ grid_css }}
    </style>
    
    {{ bokeh_css }}
    {{ bokeh_js }}
    {{ plot_script }}
    
    <script>
    {{ grid_js }}
    </script>
</head>
<body>
    <div class="controls-container">
        <div class="controls" style="{{ panel_style }}">
            <div class="toggle-group">
                {% for key in greek_order %}
                <label class="toggle-label" id="label-{{ key }}">
                    <input type="checkbox" class="chart-toggle" value="{{ key }}" checked data-color="{{ colors[key] }}">
                    <span>{{ symbols[key] }} {{ key.upper() }}</span>
                </label>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <div id="main-grid" class="chart-grid layout-5">
        {% for key in greek_order %}
        <div id="container-{{ key }}" class="chart-container visible-slot-{{ loop.index }}">
            {{ divs[key] }}
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

# ============================================================================
# DATA GENERATION
# ============================================================================
def generate_smile_data(
    spot: float = 50000,
    n_strikes: int = 25,
    dtes: List[int] = None
) -> Dict[int, pd.DataFrame]:
    """Generate smile data for multiple DTEs."""
    from scipy.stats import norm
    
    if dtes is None:
        dtes = [7, 30, 90]
    
    strikes = np.linspace(spot * 0.7, spot * 1.3, n_strikes)
    moneyness = np.log(strikes / spot)
    
    result = {}
    
    for dte in dtes:
        T = dte / 365.0
        
        base_iv = 50 + 10 / np.sqrt(T + 0.1)
        iv = np.clip(base_iv + 40 * moneyness**2 - 8 * moneyness, 20, 150)
        
        sigma = iv / 100
        d1 = (np.log(spot / strikes) + (0.05 + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        
        delta = norm.cdf(d1)
        gamma = norm.pdf(d1) / (spot * sigma * np.sqrt(T)) * 10000
        theta = -(spot * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) / 365
        vega = spot * np.sqrt(T) * norm.pdf(d1) / 100
        
        result[dte] = pd.DataFrame({
            'strike': strikes,
            'iv': iv,
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
        })
    
    return result

# ============================================================================
# CHART CREATION
# ============================================================================
def create_greek_chart(
    dte_data: Dict[int, pd.DataFrame],
    greek_key: str
) -> figure:
    """Create a single greek chart with lines for each DTE."""
    
    base_color = COLORS[greek_key]
    label = GREEK_LABELS[greek_key]
    fmt = GREEK_FORMATS[greek_key]
    
    p = figure(
        sizing_mode='stretch_both',
        toolbar_location=None,
        tools="hover",
        background_fill_color=COLORS['bg'],
        border_fill_color=COLORS['bg'],
        min_border_left=CONFIG.min_border_left,
        min_border_right=15, # Уменьшено, чтобы убрать пустоту справа
        min_border_top=5,    # Уменьшено, чтобы растянуть вверх
        min_border_bottom=CONFIG.min_border_bottom,
        outline_line_color=None,
    )
    p.toolbar.logo = None
    
    # Styling
    p.grid.grid_line_alpha = CONFIG.grid_alpha
    p.grid.grid_line_color = COLORS['grid']
    
    # Axes
    p.xaxis.axis_line_color = COLORS['axis']
    p.yaxis.axis_line_color = COLORS['axis']
    p.axis.major_label_text_font_size = "8pt"
    p.axis.major_label_text_color = "#888888"
    p.xaxis.axis_label = "Strike"
    p.xaxis.axis_label_text_color = "#888888"
    p.xaxis.axis_label_text_font_size = "8pt"
    p.yaxis.axis_label = label
    p.yaxis.axis_label_text_color = base_color
    p.yaxis.axis_label_text_font_size = "8pt"
    p.yaxis.axis_label_text_font_style = "bold"
    p.axis.major_tick_line_color = COLORS['axis']
    p.axis.minor_tick_line_color = None
    
    # Formatters
    p.xaxis.formatter = NumeralTickFormatter(format="0,0")
    p.yaxis.formatter = NumeralTickFormatter(format=fmt)
    
    # Title (Удалено по просьбе пользователя, достаточно метки оси Y)
    p.title.text = ""
    
    # Get colors for DTEs
    dtes = sorted(dte_data.keys())
    dte_colors = get_dte_colors(base_color, dtes)
    
    # Plot lines
    for dte in dtes:
        df = dte_data[dte]
        src = ColumnDataSource(df)
        color = dte_colors[dte]
        
        p.line(
            'strike', greek_key,
            source=src,
            legend_label=f"{dte}D",
            line_color=color,
            line_width=CONFIG.line_width,
            line_alpha=1.0,
        )
        
        p.scatter(
            'strike', greek_key,
            source=src,
            color=color,
            size=CONFIG.scatter_size,
            alpha=0.7,
        )
        
        # Sticky label (Удалено по просьбе пользователя)
        pass
    
    # Hover
    hover = p.select(dict(type=HoverTool))
    hover.tooltips = [
        ("Strike", "@strike{0,0}"),
        (label, f"@{greek_key}{{{fmt}}}"),
    ]
    hover.mode = 'mouse'
    
    # Legend
    p.legend.location = "top_right"
    p.legend.click_policy = "hide"
    p.legend.background_fill_alpha = 0.8
    p.legend.border_line_alpha = 0
    p.legend.label_text_font_size = "8pt"
    p.legend.label_text_color = "#666666"
    
    return p

# ============================================================================
# SMILE CHART CLASS
# ============================================================================
class SmileChart:
    """Smile Chart with CSS Grid layout."""
    
    def __init__(
        self,
        df: Optional[pd.DataFrame] = None,
        market_state: Optional[Dict[str, Any]] = None,
        selected_dtes: Optional[List[int]] = None,
        title: str = "Volatility Smile & Greeks"
    ):
        self.title = title
        self.market_state = market_state or {
            'spot_price': 50000,
            'timestamp': datetime.now(),
            'symbol': 'BTC-USD'
        }
        self.selected_dtes = selected_dtes or [7, 30, 90]
        
        if df is not None:
            self.dte_data = self._process_dataframe(df)
        else:
            self.dte_data = generate_smile_data(
                spot=self.market_state['spot_price'],
                dtes=self.selected_dtes
            )
    
    def _process_dataframe(self, df: pd.DataFrame) -> Dict[int, pd.DataFrame]:
        result = {}
        for dte in df['dte'].unique():
            result[dte] = df[df['dte'] == dte].copy()
        return result
    
    def render(self) -> str:
        """Render chart to HTML string."""
        
        # Create plots
        plots = {}
        for key in GREEK_ORDER:
            plots[key] = create_greek_chart(self.dte_data, key)
        
        script, div_dict = components(plots)
        
        # Title
        symbol = self.market_state.get('symbol', 'OPTION')
        timestamp = self.market_state.get('timestamp', datetime.now())
        time_str = timestamp.strftime("%Y-%m-%d %H:%M") if isinstance(timestamp, datetime) else str(timestamp)
        dte_str = ", ".join([f"{d}D" for d in sorted(self.dte_data.keys())])
        full_title = f"{symbol} | {self.title} | DTE: {dte_str} | {time_str}"
        
        # Render
        template = Template(HTML_TEMPLATE)
        html = template.render(
            title=full_title,
            panel_style=PANEL_STYLE,
            toggle_css=get_toggle_css(),
            grid_css=get_grid_layout_css(max_items=5),
            grid_js=get_grid_layout_js(max_items=5),
            bokeh_css=CDN.render_css(),
            bokeh_js=CDN.render_js(),
            plot_script=script,
            greek_order=GREEK_ORDER,
            symbols=GREEK_SYMBOLS,
            colors=COLORS,
            divs=div_dict,
        )
        
        return "<!-- Smile Chart v7.0 -->\n" + html
    
    def to_html(self) -> str:
        return self.render()
    
    def save(self, filepath: str) -> str:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.render())
        return filepath


# ============================================================================
# TEST
# ============================================================================
if __name__ == '__main__':
    print("=" * 60)
    print("SMILE CHART TEST")
    print("=" * 60)
    
    chart = SmileChart(
        market_state={'spot_price': 50000, 'timestamp': datetime.now(), 'symbol': 'BTC-USD'},
        selected_dtes=[7, 30, 90],
        title="BTC Volatility Smile"
    )
    
    output_path = "test_smile_chart_output.html"
    chart.save(output_path)
    
    print(f"Saved to {output_path}")
    webbrowser.open(f"file://{os.path.abspath(output_path)}")
