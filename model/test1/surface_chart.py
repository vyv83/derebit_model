"""
ФАЙЛ: surface_chart.py
НАЗНАЧЕНИЕ: Surface Chart - 3D поверхность греков (Plotly)
ЗАВИСИМОСТИ: bokeh_components.py (только константы), plotly, jinja2
ТЕСТ: python surface_chart.py → откроется браузер
"""

import numpy as np
import json
import math
import webbrowser
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

# ИМПОРТ ИЗ ОБЩЕГО МОДУЛЯ
from bokeh_components import (
    COLORS, GREEK_ORDER, GREEK_SYMBOLS, PANEL_STYLE,
    get_toggle_css, get_grid_layout_css, get_grid_layout_js
)

# ============================================================================
# MATH HELPERS
# ============================================================================
def norm_pdf(x):
    return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)

def norm_cdf(x):
    erf_vec = np.vectorize(math.erf)
    return 0.5 * (1 + erf_vec(x / np.sqrt(2)))

# ============================================================================
# DATA GENERATION
# ============================================================================
def generate_surface_data(
    spot: float = 50000,
    n_strikes: int = 40,
    n_dtes: int = 15
) -> Dict[str, Any]:
    """Generate 3D surface data."""
    
    strikes = np.linspace(spot * 0.6, spot * 1.4, n_strikes)
    dtes = np.linspace(1, 120, n_dtes)
    
    S_mesh, T_mesh = np.meshgrid(strikes, dtes)
    T_years = T_mesh / 365.0
    
    # IV Surface
    moneyness = np.log(S_mesh / spot)
    iv_surface = 50 + 60 * moneyness**2 + 5 / np.sqrt(T_years + 0.05)
    iv_surface = np.clip(iv_surface, 15, 180)
    
    # Greeks
    v = iv_surface / 100.0
    sqrt_T = np.sqrt(np.maximum(T_years, 1e-10))
    d1 = (np.log(spot / S_mesh) + 0.5 * v**2 * T_years) / (v * sqrt_T)
    
    delta = norm_cdf(d1)
    gamma = norm_pdf(d1) / (spot * v * sqrt_T) * 10000
    theta = -(spot * norm_pdf(d1) * v) / (2 * sqrt_T) / 365
    vega = spot * sqrt_T * norm_pdf(d1) / 100
    
    return {
        'strikes': strikes.tolist(),
        'dtes': dtes.tolist(),
        'iv': iv_surface.tolist(),
        'delta': delta.tolist(),
        'gamma': gamma.tolist(),
        'theta': theta.tolist(),
        'vega': vega.tolist(),
        'spot': spot
    }

# ============================================================================
# HTML TEMPLATE
# ============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
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
        
        .chart-title {
            position: absolute;
            top: 8px;
            left: 12px;
            font-size: 10px;
            font-weight: 800;
            z-index: 10;
            pointer-events: none;
            text-transform: uppercase;
        }
    </style>
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
            <div class="chart-title" style="color: {{ colors[key] }}">{{ symbols[key] }} (3D SURFACE)</div>
            <div id="plot-{{ key }}" style="width:100%; height:100%;"></div>
        </div>
        {% endfor %}
    </div>

    <script>
        const surfaceData = {{ data_json }};
        const greekColors = {{ colors_json }};
        
        function createSurface(elementId, key, color) {
            const trace = {
                z: surfaceData[key],
                x: surfaceData.strikes,
                y: surfaceData.dtes,
                type: 'surface',
                colorscale: [[0, 'rgba(255,255,255,0.1)'], [1, color]],
                showscale: false,
                opacity: 0.9,
            };

            const layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { l: 0, r: 0, b: 0, t: 0 },
                scene: {
                    xaxis: { 
                        title: { text: 'Strike', font: { size: 11, color: '#888888' } },
                        tickfont: { size: 10, color: '#888888' },
                        gridcolor: '#f0f0f0', 
                        showbackground: false 
                    },
                    yaxis: { 
                        title: { text: 'DTE', font: { size: 11, color: '#888888' } },
                        tickfont: { size: 10, color: '#888888' },
                        gridcolor: '#f0f0f0', 
                        showbackground: false 
                    },
                    zaxis: { 
                        title: { text: '', font: { size: 11, color: '#888888' } },
                        tickfont: { size: 10, color: '#888888' },
                        gridcolor: '#f0f0f0', 
                        showbackground: false 
                    },
                    camera: { eye: { x: 1.6, y: 1.6, z: 1.2 } }
                }
            };

            Plotly.newPlot(elementId, [trace], layout, { displayModeBar: false, responsive: true });
        }

        function updatePlots() {
            document.querySelectorAll('.chart-toggle:checked').forEach(input => {
                createSurface('plot-' + input.value, input.value, greekColors[input.value]);
            });
        }
        
        {{ grid_js }}
        
        // Override to also update plots
        const originalUpdateLayout = updateLayout;
        updateLayout = function() {
            originalUpdateLayout();
            setTimeout(updatePlots, 50);
        };
        
        window.addEventListener('resize', () => {
            document.querySelectorAll('.chart-toggle:checked').forEach(input => {
                const el = document.getElementById('plot-' + input.value);
                if (el && el.data) Plotly.Plots.resize(el);
            });
        });
    </script>
</body>
</html>
"""

# ============================================================================
# SURFACE CHART CLASS
# ============================================================================
class SurfaceChart:
    """3D Surface Chart using Plotly."""
    
    def __init__(
        self,
        data: Optional[Dict[str, Any]] = None,
        spot: float = 50000,
        title: str = "3D Volatility Surface"
    ):
        self.title = title
        self.data = data if data else generate_surface_data(spot)
    
    def render(self) -> str:
        from jinja2 import Template
        
        template = Template(HTML_TEMPLATE)
        html = template.render(
            title=self.title,
            panel_style=PANEL_STYLE,
            toggle_css=get_toggle_css(),
            grid_css=get_grid_layout_css(max_items=5),
            grid_js=get_grid_layout_js(max_items=5),
            greek_order=GREEK_ORDER,
            symbols=GREEK_SYMBOLS,
            colors=COLORS,
            colors_json=json.dumps({k: COLORS[k] for k in GREEK_ORDER}),
            data_json=json.dumps(self.data),
        )
        
        return "<!-- Surface Chart v7.0 -->\n" + html
    
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
    print("SURFACE CHART TEST")
    
    chart = SurfaceChart(title="BTC 3D Volatility Surface")
    output_path = "test_surface_chart_output.html"
    chart.save(output_path)
    
    print(f"Saved to {output_path}")
    webbrowser.open(f"file://{os.path.abspath(output_path)}")
