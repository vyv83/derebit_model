
import pandas as pd
import numpy as np
import colorsys
from bokeh.plotting import figure, save
from bokeh.models import ColumnDataSource, HoverTool, CrosshairTool, Span, CustomJS, CheckboxGroup, Div, Label
from bokeh.layouts import row, column
from bokeh.embed import components
from bokeh.resources import CDN
from jinja2 import Template

# ============================================================================
# STYLES & CONSTANTS
# ============================================================================
COLORS = {
    'call': '#76D7C4',      # Green
    'put': '#FF8787',       # Red
    'iv': '#9B59B6',        # Purple
    'theta': '#E67E22',     # Orange
    'delta': '#3498DB',     # Blue
    'gamma': '#F1C40F',     # Yellow
    'vega': '#1ABC9C',      # Cyan
    'rho': '#95A5A6',       # Gray
    'spot': '#969696',
    'bg': '#FFFFFF',
    'text': '#333333',
    'grid': '#F0F0F0',      # Lighter grid
    'crosshair': '#546E7A',
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

# ============================================================================
# DATA GENERATION
# ============================================================================
def generate_base_data(n_strikes=100):
    """Generate the base curves."""
    spot = 50000
    strikes = np.linspace(50000 * 0.5, 50000 * 1.5, n_strikes)
    
    # Base computations
    moneyness = np.log(strikes / spot)
    iv = np.clip(60 + 50 * moneyness**2 - 10 * moneyness, 20, 150)
    
    from scipy.stats import norm
    d1 = (np.log(spot / strikes) + (0.05 + 0.5 * (iv/100)**2) * 0.1) / ((iv/100) * np.sqrt(0.1))
    
    delta = norm.cdf(d1)
    gamma = norm.pdf(d1) / (spot * (iv/100) * np.sqrt(0.1)) * 10000 
    theta = - (spot * norm.pdf(d1) * (iv/100)) / (2 * np.sqrt(0.1))
    vega = spot * np.sqrt(0.1) * norm.pdf(d1) / 100
    rho = strikes * 0.1 * np.exp(-0.05 * 0.1) * norm.cdf(d1 - (iv/100)*np.sqrt(0.1)) / 100

    return pd.DataFrame({
        'strike': strikes,
        'iv': iv,
        'delta': delta,
        'gamma': gamma,
        'theta': theta,
        'vega': vega,
        'rho': rho
    })

def generate_multi_smile_data():
    """
    Generates scenarios by simply shifting the base data up.
    """
    base = generate_base_data()
    
    # Simple vertical shifts for scenarios
    # This avoids complex logic/formulas for scenarios as requested
    s1 = base.copy()
    s2 = base.copy()
    
    cols = ['iv', 'delta', 'gamma', 'theta', 'vega', 'rho']
    
    for col in cols:
        # Shift up by a fraction of the value range or mean to ensure they are visible and separated
        val_range = base[col].max() - base[col].min()
        if val_range == 0: val_range = base[col].mean() * 0.1
        if val_range == 0: val_range = 1.0
        
        s1[col] = s1[col] + val_range * 0.2
        s2[col] = s2[col] + val_range * 0.4

    return {
        'Current': base,
        'Scenario 1': s1,
        'Scenario 2': s2,
    }

# ============================================================================
# HELPER: COLOR MANIPULATION (Pure Python)
# ============================================================================
def adjust_color(hex_color, factor):
    """
    Adjust brightness of a color using colorsys.
    factor > 1 lightens, factor < 1 darkens.
    """
    if hex_color.startswith('#'):
        hex_color = hex_color[1:]
    
    # RGB 0-1
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    
    # Adjust Lightness
    # factor 1.0 = no change. 0.5 = dark. 1.5 = light.
    # To darken: new_l = l * factor
    # To lighten: approach 1.0? Or just multiply?
    # Simple multiply with clamp
    new_l = max(0, min(1, l * factor))
    
    # Slight Saturation Boost for lighter colors to keep them visible
    if factor > 1:
        s = max(0, min(1, s * 0.8)) # Desaturate slightly if lightening
    else:
        s = max(0, min(1, s * 1.2)) # Saturate if darkening
        
    r, g, b = colorsys.hls_to_rgb(h, new_l, s)
    
    return '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))

# ============================================================================
# CUSTOM TEMPLATE
# ============================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Smile & Greeks Analysis</title>
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
        
        /* CONTROL PANEL */
        .controls-container {
            display: flex;
            justify-content: center;
            flex-shrink: 0;
            margin-bottom: 5px;
        }
        
        .controls {
            {{ panel_style }}
        }
        
        .toggle-group { display: flex; gap: 12px; align-items: center; }
        
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
        
        /* Hidden checkbox for state */
        .toggle-label input {
            display: none;
        }
        
        .toggle-label.active {
            background: #fff;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* GRID LAYOUT - COMPACT 5px GAP */
        .chart-grid {
            flex-grow: 1;
            display: grid;
            gap: 5px; 
            padding: 0;
            width: 100%;
            height: 100%;
            transition: all 0.3s ease;
            box-sizing: border-box;
        }
        
        .chart-container {
            background: white;
            border-radius: 4px;
            overflow: hidden;
            position: relative;
            border: 1px solid #eee;
        }
        
        /* LAYOUT LOGIC */
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

        .hidden { display: none !important; }

        .bk-root { height: 100% !important; width: 100% !important; }
    </style>
    
    {{ script_resources }}
    {{ script_content }}
    
    <script>
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
                
                // Reset slot classes and assign new one
                container.classList.forEach(cls => {
                    if (cls.startsWith('visible-slot-')) container.classList.remove(cls);
                });
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
    }

    document.addEventListener('DOMContentLoaded', () => {
        updateLayout();
        document.querySelectorAll('.chart-toggle').forEach(t => t.addEventListener('change', updateLayout));
    });
    </script>
</head>
<body>
    <div class="controls-container">
        <div class="controls">
            <div class="toggle-group">
                {% for key, label in charts.items() %}
                <label class="toggle-label" id="label-{{ key }}">
                    <input type="checkbox" class="chart-toggle" value="{{ key }}" checked data-color="{{ colors[key] }}">
                    <span>{{ label }}</span>
                </label>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <div id="main-grid" class="chart-grid layout-{{ charts|length }}">
        {% for key, div in divs.items() %}
        <div id="container-{{ key }}" class="chart-container visible-slot-{{ loop.index }}">
            {{ div }}
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

# ============================================================================
# CHART CREATION
# ============================================================================
def create_chart(scenario_data, key, label, base_color):
    """
    Create a chart.
    - No Toolbar
    - Minimized borders
    - Solid lines only, different colors
    """
    p = figure(
        sizing_mode='stretch_both',
        toolbar_location=None,
        tools="hover", 
        background_fill_color=COLORS['bg'],
        border_fill_color=COLORS['bg'],
        min_border_left=40,
        min_border_right=10,
        min_border_top=15,
        min_border_bottom=20,
        outline_line_color=None,
    )
    p.toolbar.logo = None
    
    # Styling
    p.grid.grid_line_alpha = 0.3
    p.grid.grid_line_color = '#E0E0E0'
    p.grid.grid_line_dash = [] # Solid grid lines
    
    # Axes
    p.xaxis.axis_line_color = '#CCCCCC'
    p.yaxis.axis_line_color = '#CCCCCC'
    p.axis.major_label_text_font_size = "8pt"
    p.axis.major_label_text_color = "#999999"
    p.axis.major_label_standoff = 2
    p.xaxis.axis_label = None 
    p.yaxis.axis_label = None
    p.axis.major_tick_line_color = None
    p.axis.minor_tick_line_color = None
    
    # Minimal Title inside
    p.title.text = label
    p.title.text_color = base_color
    p.title.text_font_size = "9pt"
    p.title.align = "left"
    p.title.offset = 0
    p.title.standoff = 5
    
    # Colors: Shades of base_color
    colors = {
        'Current': base_color,
        'Scenario 1': adjust_color(base_color, 0.7), # Darker
        'Scenario 2': adjust_color(base_color, 1.3), # Lighter
    }
    
    for name, df in scenario_data.items():
        src = ColumnDataSource(df)
        c = colors.get(name, base_color)
        
        # Solid lines, no dash/dots
        p.line(
            'strike', key,
            source=src,
            legend_label=name,
            line_color=c,
            line_width=2,
            line_alpha=1.0, 
            line_cap='round',
        )
    
    # Hover
    hover = p.select(dict(type=HoverTool))
    hover.tooltips = [
        ("Scenario", "$name"),
        ("Value", f"@{key}{{0.00}}")
    ]
    hover.mode = 'mouse'
    
    # Legend - Minimal inside chart
    p.legend.location = "top_right"
    p.legend.click_policy = "none" # Static
    p.legend.background_fill_alpha = 0
    p.legend.border_line_alpha = 0
    p.legend.label_text_font_size = "8pt"
    p.legend.label_text_color = "#888888"
    p.legend.spacing = 0
    p.legend.padding = 2
    p.legend.margin = 5
    
    return p

# ============================================================================
# MAIN
# ============================================================================
def main():
    # 1. Generate Data
    data_map = generate_multi_smile_data()
    
    # 2. Charts
    chart_defs = [
        ('iv', 'IV', COLORS['iv']),
        ('delta', 'Delta', COLORS['delta']),
        ('gamma', 'Gamma', COLORS['gamma']),
        ('vega', 'Vega', COLORS['vega']),
        ('theta', 'Theta', COLORS['theta']),
        ('rho', 'Rho', COLORS['rho']),
    ]
    
    chart_map = {}
    
    plots = {}
    for key, label, color in chart_defs:
        plots[key] = create_chart(data_map, key, label, color)
        chart_map[key] = label

    script, div_dict = components(plots)
    
    # 3. Render
    template = Template(HTML_TEMPLATE)
    
    html = template.render(
        panel_style=PANEL_STYLE,
        script_resources=CDN.render(),
        script_content=script,
        charts={k: v for k, v in chart_map.items()},
        divs=div_dict,
        colors={k: c for k, _, c in chart_defs}
    )
    
    output_path = "model/tests/test_bokeh_smile_greeks.html"
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Generated {output_path}")

if __name__ == "__main__":
    main()
