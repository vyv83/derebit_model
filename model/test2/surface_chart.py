"""
ФАЙЛ: surface_chart.py (test2)
ОПИСАНИЕ: Surface Chart - 3D поверхность греков (Plotly) внутри CSS Grid.
ПРИНЦИП: PIXEL PERFECT (V11 Precision Blueprint).
"""

import json
import os
from typing import Dict, List, Optional, Any
from jinja2 import Template

from bokeh_components import (
    COLORS, GREEK_ORDER, GREEK_SYMBOLS, GREEK_LABELS, PANEL_STYLE,
    get_toggle_css, get_toggle_panel_html, get_grid_layout_css, get_grid_layout_js
)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 8px; background: #ffffff; 
            height: 100vh; box-sizing: border-box; 
            display: flex; flex-direction: column; overflow: hidden; 
        }
        {{ toggle_css }}
        {{ grid_css }}
        .chart-title {
            position: absolute; top: 8px; left: 12px;
            font-size: 10px; font-weight: 800; z-index: 10;
            pointer-events: none; text-transform: uppercase;
        }
    </style>
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
            <div class="chart-title" style="color: {{ colors[key] }}">{{ symbols[key] }} (3D SURFACE)</div>
            <div id="plot-{{ key }}" style="width:100%; height:100%;"></div>
        </div>
        {% endfor %}
    </div>

    <script>
        const surfaceData = {{ data_json }};
        const greekColors = {{ colors_json }};
        const greekLabels = {{ labels_json }};
        const greekSymbols = {{ symbols_json }};
        
        const plotsInitialized = {};

        function initPlot(key) {
            if (plotsInitialized[key]) return;
            const pid = 'plot-' + key;
            const el = document.getElementById(pid);
            if (!el) return;
            
            const color = greekColors[key];
            const sym = greekSymbols[key];
            const label = sym && sym !== key.toUpperCase() ? sym : key.toUpperCase();
            
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
                        title: { text: 'Strike', font: { size: 10, color: '#888888' } },
                        tickfont: { size: 9, color: '#888888' },
                        gridcolor: '#f0f0f0', showbackground: false 
                    },
                    yaxis: { 
                        title: { text: 'DTE', font: { size: 10, color: '#888888' } },
                        tickfont: { size: 9, color: '#888888' },
                        gridcolor: '#f0f0f0', showbackground: false 
                    },
                    zaxis: { 
                        title: { text: label, font: { size: 10, color: '#888888' } },
                        tickfont: { size: 9, color: '#888888' },
                        gridcolor: '#f0f0f0', showbackground: false 
                    },
                    camera: { eye: { x: 1.6, y: 1.6, z: 1.2 } }
                }
            };

            Plotly.newPlot(pid, [trace], layout, { displayModeBar: false, responsive: true });
            plotsInitialized[key] = true;
        }

        function updateLayout() {
            const toggleInputs = document.querySelectorAll('.chart-toggle');
            const grid = document.getElementById('main-grid');
            let activeCount = 0;
            if (!grid) return;

            toggleInputs.forEach(input => {
                const key = input.value;
                const container = document.getElementById('container-' + key);
                if (input.checked) {
                    activeCount++;
                    container.classList.remove('hidden');
                    container.classList.forEach(cls => { if (cls.startsWith('visible-slot-')) container.classList.remove(cls); });
                    container.classList.add('visible-slot-' + activeCount);
                    // Lazy init
                    if (!plotsInitialized[key]) {
                        initPlot(key);
                    } else {
                        const el = document.getElementById('plot-' + key);
                        if (el && el.data) Plotly.Plots.resize(el);
                    }
                } else {
                    container.classList.add('hidden');
                }
            });
            grid.className = 'chart-grid layout-' + Math.min(activeCount, 5);
            
            // Re-resize after CSS transition
            setTimeout(() => {
                document.querySelectorAll('.chart-toggle:checked').forEach(input => {
                    const el = document.getElementById('plot-' + input.value);
                    if (el && el.data) Plotly.Plots.resize(el);
                });
            }, 300);
        }
        
        window.addEventListener('resize', () => {
            document.querySelectorAll('.chart-toggle:checked').forEach(input => {
                const el = document.getElementById('plot-' + input.value);
                if (el && el.data) Plotly.Plots.resize(el);
            });
        });
        
        // Initial setup
        document.addEventListener('DOMContentLoaded', updateLayout);
        document.querySelectorAll('.chart-toggle').forEach(t => t.addEventListener('change', updateLayout));
    </script>
</body>
</html>
"""

class SurfaceChart:
    """3D Surface Chart (Plotly) внутри CSS Grid."""
    
    def __init__(
        self,
        data: Dict[str, Any],
        title: str = "3D Volatility Surface"
    ):
        self.data = data
        self.title = title

    def to_html(self) -> str:
        template = Template(HTML_TEMPLATE)
        return template.render(
            title=self.title,
            panel_style=PANEL_STYLE,
            toggle_css=get_toggle_css(),
            toggle_panel_html=get_toggle_panel_html(),
            grid_css=get_grid_layout_css(max_items=len(GREEK_ORDER)),
            grid_js=get_grid_layout_js(max_items=len(GREEK_ORDER)),
            greek_order=GREEK_ORDER,
            symbols=GREEK_SYMBOLS,
            colors=COLORS,
            colors_json=json.dumps({k: COLORS[k] for k in GREEK_ORDER}),
            labels_json=json.dumps(GREEK_LABELS),
            symbols_json=json.dumps(GREEK_SYMBOLS),
            data_json=json.dumps(self.data),
        )

    def show(self):
        import webbrowser, tempfile
        fd, path = tempfile.mkstemp(suffix='.html')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(self.to_html())
        webbrowser.open(f'file://{path}')

if __name__ == '__main__':
    from test_data import generate_surface_data
    data = generate_surface_data()
    chart = SurfaceChart(data, "BTC 3D Surface (V11)")
    chart.show()
