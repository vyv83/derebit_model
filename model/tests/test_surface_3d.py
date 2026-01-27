
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from jinja2 import Template
import os
import math
import json

# ============================================================================
# CONSTANTS & COLORS (Matching test_bokeh_smile_greeks.py)
# ============================================================================
COLORS = {
    'iv': '#9B59B6',        # Purple
    'delta': '#3498DB',     # Blue
    'gamma': '#F1C40F',     # Yellow
    'vega': '#1ABC9C',      # Cyan
    'theta': '#E67E22',     # Orange
    'rho': '#95A5A6',       # Gray
    'bg': '#FFFFFF',
    'text': '#333333',
    'grid': '#F0F0F0',
}

PANEL_STYLE = """
    font-family: 'SF Mono', Monaco, monospace;
    font-size: 11px;
    padding: 6px 15px;
    background: linear-gradient(90deg, rgba(255,255,255,0.98), rgba(248,249,250,0.98));
    border-radius: 6px;
    border: 1px solid #e0e0e0;
    display: inline-flex;
    gap: 15px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    align-items: center;
    height: 36px;
    box-sizing: border-box;
    margin-bottom: 2px;
"""

def norm_pdf(x):
    return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)

def norm_cdf(x):
    erf_vec = np.vectorize(math.erf)
    return 0.5 * (1 + erf_vec(x / np.sqrt(2)))

# ============================================================================
# DATA GENERATION
# ============================================================================
def generate_surface_data(n_strikes=40, n_dtes=15):
    spot = 50000
    strikes = np.linspace(spot * 0.6, spot * 1.4, n_strikes)
    dtes = np.linspace(1, 120, n_dtes) 
    
    S_mesh, T_mesh = np.meshgrid(strikes, dtes)
    T_years = T_mesh / 365.0
    
    def calc_greeks(S, K, T, v, r=0.0):
        v = v / 100.0  
        d1 = (np.log(S / K) + (r + 0.5 * v**2) * T) / (v * np.sqrt(T))
        d2 = d1 - v * np.sqrt(T)
        
        delta = norm_cdf(d1)
        gamma = norm_pdf(d1) / (S * v * np.sqrt(T))
        theta = -(S * norm_pdf(d1) * v) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm_cdf(d2)
        vega = S * np.sqrt(T) * norm_pdf(d1)
        rho = K * T * np.exp(-r * T) * norm_cdf(d2)
        
        return delta, gamma * 10000, theta / 365.0, vega / 100.0, rho / 100.0

    # Only Current scenario
    base_iv = 50
    moneyness = np.log(S_mesh / spot)
    iv_surface = base_iv + 60 * moneyness**2 + 5 / np.sqrt(T_years + 0.05)
    iv_surface = np.clip(iv_surface, 15, 180)
    
    delta, gamma, theta, vega, rho = calc_greeks(spot, S_mesh, T_years, iv_surface)
    
    data = {
        'strikes': strikes.tolist(),
        'dtes': dtes.tolist(),
        'iv': iv_surface.tolist(),
        'delta': delta.tolist(),
        'gamma': gamma.tolist(),
        'theta': theta.tolist(),
        'vega': vega.tolist(),
        'rho': rho.tolist(),
    }
        
    return data

# ============================================================================
# TEMPLATE
# ============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>3D Volatility Surface & Greeks</title>
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
        
        .controls-container {
            display: flex;
            justify-content: center;
            flex-shrink: 0;
            margin-bottom: 5px;
        }
        
        .panel {
            {{ panel_style }}
        }
        
        .toggle-group { display: flex; gap: 10px; align-items: center; }
        
        .toggle-label {
            display: flex;
            align-items: center;
            padding: 0 10px;
            height: 24px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            border: 1px solid #ced4da;
            color: #7F8C8D;
            background: rgba(255,255,255,0.9);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            cursor: pointer;
            transition: all 0.2s;
            user-select: none;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        
        .toggle-label:hover {
            border-color: #bbb;
            background: #fff;
        }

        .toggle-label.active {
            background: #fff;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
        }

        .toggle-label input { display: none; }
        
        .chart-grid {
            flex-grow: 1;
            display: grid;
            gap: 5px;
            width: 100%;
            height: 100%;
            transition: all 0.3s ease;
            box-sizing: border-box;
        }
        
        .chart-container {
            background: white;
            border-radius: 4px;
            overflow: hidden;
            border: 1px solid #eee;
            position: relative;
        }
        
        .hidden { display: none !important; }

        /* Layout styles matching sample */
        .layout-1 { grid-template-columns: 1fr; grid-template-rows: 1fr; }
        .layout-2 { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr; }
        .layout-3 { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }
        .layout-3 .visible-slot-1 { grid-row: 1 / span 2; grid-column: 1; }
        .layout-3 .visible-slot-2 { grid-row: 1; grid-column: 2; }
        .layout-3 .visible-slot-3 { grid-row: 2; grid-column: 2; }
        .layout-4 { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }
        .layout-5 { grid-template-columns: 1fr 1fr 1fr; grid-template-rows: 1fr 1fr; }
        .layout-5 .visible-slot-1 { grid-row: 1; grid-column: 1; }
        .layout-5 .visible-slot-2 { grid-row: 1; grid-column: 2; }
        .layout-5 .visible-slot-3 { grid-row: 2; grid-column: 1; }
        .layout-5 .visible-slot-4 { grid-row: 2; grid-column: 2; }
        .layout-5 .visible-slot-5 { grid-row: 1 / span 2; grid-column: 3; }
        .layout-6 { grid-template-columns: 1fr 1fr 1fr; grid-template-rows: 1fr 1fr; }

        .chart-title {
            position: absolute;
            top: 8px;
            left: 12px;
            font-size: 10px;
            font-weight: 800;
            z-index: 10;
            pointer-events: none;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
    </style>
</head>
<body>
    <div class="controls-container">
        <div class="panel">
            <div class="toggle-group">
                {% for key, label in chart_defs %}
                <label class="toggle-label chart-toggle-label" id="label-{{ key }}">
                    <input type="checkbox" class="chart-toggle" value="{{ key }}" checked data-color="{{ colors[key] }}">
                    <span>{{ label }}</span>
                </label>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <div id="main-grid" class="chart-grid">
        {% for key, label in chart_defs %}
        <div id="container-{{ key }}" class="chart-container">
            <div class="chart-title" style="color: {{ colors[key] }}">{{ label }} (3D SURFACE)</div>
            <div id="plot-{{ key }}" style="width:100%; height:100%;"></div>
        </div>
        {% endfor %}
    </div>

    <script>
        const data = {{ data_json }};
        const colors = {{ colors_json }};

        function createSurface(elementId, key, label, color) {
            const z = data[key];
            const x = data.strikes;
            const y = data.dtes;

            const trace = {
                z: z,
                x: x,
                y: y,
                type: 'surface',
                colorscale: [
                    [0, 'rgba(255,255,255,0.1)'],
                    [1, color]
                ],
                showscale: false,
                opacity: 0.9,
                lighting: {
                    ambient: 0.6,
                    diffuse: 0.8,
                    fresnel: 0.2,
                    specular: 0.1,
                    roughness: 0.5
                },
                contours: {
                    z: { show: true, uselevels: true, project: { z: true }, color: '#eee' }
                }
            };

            const layout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                margin: { l: 0, r: 0, b: 0, t: 0 },
                scene: {
                    xaxis: { title: '', gridcolor: '#f0f0f0', showbackground: false, showticklabels: true, tickfont: {size: 10, color: '#666'} },
                    yaxis: { title: '', gridcolor: '#f0f0f0', showbackground: false, showticklabels: true, tickfont: {size: 10, color: '#666'} },
                    zaxis: { title: '', gridcolor: '#f0f0f0', showbackground: false, showticklabels: true, tickfont: {size: 10, color: '#666'} },
                    camera: {
                        eye: { x: 1.6, y: 1.6, z: 1.2 }
                    }
                }
            };

            Plotly.newPlot(elementId, [trace], layout, { displayModeBar: false });
        }

        function updatePlots() {
            const activeToggles = document.querySelectorAll('.chart-toggle:checked');
            activeToggles.forEach(input => {
                const key = input.value;
                createSurface('plot-' + key, key, key, colors[key]);
            });
        }

        function updateLayout() {
            const toggleInputs = document.querySelectorAll('.chart-toggle');
            const grid = document.getElementById('main-grid');
            let activeCount = 0;
            
            toggleInputs.forEach(input => {
                const key = input.value;
                const container = document.getElementById('container-' + key);
                const label = input.parentElement;
                const color = input.dataset.color;
                
                if (input.checked) {
                    activeCount++;
                    container.classList.remove('hidden');
                    label.classList.add('active');
                    label.style.borderColor = color;
                    label.style.color = color;
                    
                    container.className = 'chart-container'; 
                    container.classList.add('visible-slot-' + activeCount);
                } else {
                    container.classList.add('hidden');
                    label.classList.remove('active');
                    label.style.borderColor = '#ced4da';
                    label.style.color = '#7F8C8D';
                }
            });
            
            grid.className = 'chart-grid';
            if (activeCount > 0) {
                grid.classList.add('layout-' + Math.min(activeCount, 6));
            }
            window.dispatchEvent(new Event('resize'));
            updatePlots();
        }

        document.querySelectorAll('.chart-toggle').forEach(t => t.addEventListener('change', updateLayout));

        // Initialize
        updateLayout();
        
        window.addEventListener('resize', () => {
            document.querySelectorAll('.chart-toggle:checked').forEach(input => {
                Plotly.Plots.resize('plot-' + input.value);
            });
        });
    </script>
</body>
</html>
"""

# ============================================================================
# MAIN
# ============================================================================
def main():
    data = generate_surface_data()
    
    chart_defs = [
        ('iv', 'IV'),
        ('delta', 'Delta'),
        ('gamma', 'Gamma'),
        ('vega', 'Vega'),
        ('theta', 'Theta'),
        ('rho', 'Rho'),
    ]
    
    template = Template(HTML_TEMPLATE)
    
    html = template.render(
        panel_style=PANEL_STYLE,
        chart_defs=chart_defs,
        data_json=json.dumps(data),
        colors=COLORS,
        colors_json=json.dumps(COLORS)
    )
    
    output_path = "/Users/user/work/Python/derebit_download1/model/tests/test_surface_3d.html"
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Generated {output_path}")

if __name__ == "__main__":
    main()
