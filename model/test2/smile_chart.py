"""
ФАЙЛ: smile_chart.py (test2)
ОПИСАНИЕ: Smile Chart - Volatility Smile и греки по страйкам (CSS Grid layout).
ПРИНЦИП: PIXEL PERFECT (V11 Precision Blueprint).
"""

import pandas as pd
import numpy as np
import os
from typing import Dict, List, Optional, Any
from jinja2 import Template

from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool, NumeralTickFormatter
from bokeh.embed import components
from bokeh.resources import CDN

from bokeh_components import (
    COLORS, GREEK_ORDER, GREEK_SYMBOLS, GREEK_LABELS, GREEK_FORMATS,
    PANEL_STYLE, CONFIG,
    get_toggle_css, get_toggle_panel_html, get_grid_layout_css, get_grid_layout_js,
    get_dte_colors
)

# HTML Шаблон с поддержкой CSS Grid и переключения
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 8px; background: #ffffff; 
            height: 100vh; box-sizing: border-box; 
            display: flex; flex-direction: column; overflow: hidden; 
        }
        {{ toggle_css }}
        {{ grid_css }}
        .bk-root { height: 100% !important; width: 100% !important; }
        /* Precision Tabular Nums */
        .bk-tooltip { font-variant-numeric: tabular-nums; }
    </style>
    {{ bokeh_css }}
    {{ bokeh_js }}
    {{ plot_script }}
    <script>{{ grid_js }}</script>
</head>
<body>
    <div class="controls-container">
        <div class="controls" style="{{ panel_style }}">
            {{ toggle_panel_html }}
        </div>
    </div>
    
    <div id="main-grid" class="chart-grid layout-5">
        {% for key in greek_order %}
        <div id="container-{{ key }}" class="chart-container visible-slot-{{ loop.index }}">
            {{ divs[key] }}
        </div>
        {% endfor %}
    </div>
    <script>setTimeout(updateLayout, 100);</script>
</body>
</html>
"""

class SmileChart:
    """Smile Chart с Bokeh-графиками внутри CSS Grid."""
    
    def __init__(
        self,
        dte_data: Dict[int, pd.DataFrame],
        title: str = "Volatility Smile"
    ):
        self.dte_data = dte_data
        self.title = title

    def _create_single_chart(self, key: str) -> figure:
        base_color = COLORS[key]
        label = GREEK_LABELS[key]
        fmt = GREEK_FORMATS[key]
        
        p = figure(
            sizing_mode='stretch_both', toolbar_location=None, tools="hover",
            background_fill_color=COLORS['bg'], border_fill_color=COLORS['bg'],
            min_border_left=CONFIG.min_border_left, min_border_right=15,
            min_border_top=5, min_border_bottom=CONFIG.min_border_bottom,
            outline_line_color=None
        )
        p.toolbar.logo = None
        
        # Стилизация осей (V11 Precision)
        p.grid.grid_line_alpha = CONFIG.grid_alpha
        p.grid.grid_line_color = COLORS['grid']
        p.axis.major_label_text_font_size = "7pt"
        p.axis.major_label_text_color = "#888888"
        p.xaxis.axis_label = "Strike"
        p.xaxis.axis_label_text_font_size = "8pt"
        p.yaxis.axis_label = label
        p.yaxis.axis_label_text_color = base_color
        p.yaxis.axis_label_text_font_size = "8pt"
        p.yaxis.axis_label_text_font_style = "bold"
        p.axis.major_tick_line_color = COLORS['axis']
        p.xaxis.formatter = NumeralTickFormatter(format="0,0")
        p.yaxis.formatter = NumeralTickFormatter(format=fmt)
        
        # Линии для разных DTE
        dtes = sorted(self.dte_data.keys())
        dte_colors = get_dte_colors(base_color, dtes)
        
        for dte in dtes:
            df = self.dte_data[dte]
            src = ColumnDataSource(df)
            color = dte_colors[dte]
            
            p.line('strike', key, source=src, legend_label=f"{dte}D",
                   line_color=color, line_width=CONFIG.line_width)
            p.scatter('strike', key, source=src, color=color, size=CONFIG.scatter_size, alpha=0.7)
        
        # Hover (Precision)
        hover = p.select(dict(type=HoverTool))
        hover.tooltips = [("Strike", "@strike{0,0}"), (label, f"@{key}{{{fmt}}}") ]
        hover.mode = 'mouse'
        
        # Legend
        p.legend.location = "top_right"
        p.legend.label_text_font_size = "7pt"
        p.legend.background_fill_alpha = 0.6
        p.legend.border_line_alpha = 0
        
        return p

    def to_html(self) -> str:
        plots = {key: self._create_single_chart(key) for key in GREEK_ORDER}
        script, div_dict = components(plots)
        
        template = Template(HTML_TEMPLATE)
        return template.render(
            title=self.title,
            panel_style=PANEL_STYLE,
            toggle_css=get_toggle_css(),
            toggle_panel_html=get_toggle_panel_html(),
            grid_css=get_grid_layout_css(max_items=len(GREEK_ORDER)),
            grid_js=get_grid_layout_js(max_items=len(GREEK_ORDER)),
            bokeh_css=CDN.render_css(),
            bokeh_js=CDN.render_js(),
            plot_script=script,
            greek_order=GREEK_ORDER,
            symbols=GREEK_SYMBOLS,
            colors=COLORS,
            divs=div_dict,
        )

    def show(self):
        import webbrowser, tempfile
        fd, path = tempfile.mkstemp(suffix='.html')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(self.to_html())
        webbrowser.open(f'file://{path}')

if __name__ == '__main__':
    from test_data import generate_smile_data
    data = generate_smile_data()
    chart = SmileChart(data, "BTC Volatility Smile (V11)")
    chart.show()
