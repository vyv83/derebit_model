"""
ФАЙЛ: bokeh_components.py (test2)
НАЗНАЧЕНИЕ: Дизайн-система (цвета, стили, константы).
ПРИНЦИП: PIXEL PERFECT. Полное соответствие test1.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import colorsys
from bokeh.models import (
    CustomJS, Div, Toggle, Range1d, LinearAxis, Span,
    BasicTicker, NumeralTickFormatter, WheelZoomTool, PanTool, ResetTool
)
from bokeh.plotting import figure

# ============================================================================
# COLORS - ЕДИНСТВЕННЫЙ ИСТОЧНИК ПРАВДЫ (из test1)
# ============================================================================
COLORS = {
    # Свечи
    'call': '#76D7C4',      # Зелёные свечи
    'put': '#FF8787',       # Красные свечи
    
    # Греки
    'iv': '#9B59B6',        # Purple
    'theta': '#E67E22',     # Orange
    'delta': '#3498DB',     # Blue
    'gamma': '#F1C40F',     # Yellow
    'vega': '#1ABC9C',      # Cyan
    
    # UI
    'spot': '#969696',      # Gray
    'bg': '#FFFFFF',
    'text': '#333333',
    'grid': '#E0E0E0',
    'axis': '#CCCCCC',
    'crosshair': '#546E7A',
    
    # Toggle inactive
    'inactive_border': '#ced4da',
    'inactive_text': '#7F8C8D',
}

# ============================================================================
# CONFIGURATIONS
# ============================================================================
GREEK_ORDER = ['iv', 'theta', 'delta', 'gamma', 'vega']

GREEK_SYMBOLS = {
    'iv': 'IV',
    'theta': 'Θ',
    'delta': 'Δ',
    'gamma': 'Γ',
    'vega': 'ν',
}

GREEK_LABELS = {
    'iv': 'IV (%)',
    'theta': 'Theta ($)',
    'delta': 'Delta',
    'gamma': 'Gamma',
    'vega': 'Vega ($)',
}

GREEK_FORMATS = {
    'iv': '0.0',
    'theta': '0.00',
    'delta': '0.00',
    'gamma': '0.0000',
    'vega': '0.0',
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

@dataclass(frozen=True)
class ChartConfig:
    min_border_left: int = 50
    min_border_right: int = 50
    min_border_top: int = 15
    min_border_bottom: int = 30
    candle_width_ratio: float = 0.6
    grid_alpha: float = 0.3
    line_width: float = 2.0
    scatter_size: int = 6
    ohlc_y_padding: float = 0.12
    spot_y_padding: float = 0.08
    greek_y_padding: float = 0.15
    autoscale_padding: float = 0.10

CONFIG = ChartConfig()

class ChartTheme:
    CANDLE_UP = COLORS['call']
    CANDLE_DOWN = COLORS['put']
    GREEKS = {k: COLORS[k] for k in GREEK_ORDER}
    SPOT = COLORS['spot']
    BG = COLORS['bg']
    TEXT = COLORS['text']
    TEXT_SECONDARY = COLORS['inactive_text']
    GRID = COLORS['grid']
    AXIS = COLORS['axis']
    CROSSHAIR = COLORS['crosshair']
    GRID_ALPHA = CONFIG.grid_alpha
    AREA_FILL_ALPHA = 0.2
    PANEL_STYLE = PANEL_STYLE
    
    @classmethod
    def get_greek_color(cls, key: str) -> str:
        return COLORS.get(key, cls.TEXT)
    
    @classmethod
    def get_button_style(cls, color: str, active: bool) -> str:
        if active:
            return f"padding: 0 8px; height: 22px; border-radius: 3px; font-size: 10px; border: 1px solid {color}; color: {color}; background-color: rgba(255,255,255,0.8); box-shadow: 0 1px 3px rgba(0,0,0,0.05); cursor: pointer; display: flex; align-items: center; font-family: -apple-system, BlinkMacSystemFont, sans-serif; transition: all 0.2s; outline: none; line-height: 1;"
        else:
            return f"padding: 0 8px; height: 22px; border-radius: 3px; font-size: 10px; border: 1px solid #ced4da; color: #7F8C8D; background-color: rgba(255,255,255,0.8); box-shadow: 0 1px 3px rgba(0,0,0,0.05); cursor: pointer; display: flex; align-items: center; font-family: -apple-system, BlinkMacSystemFont, sans-serif; transition: all 0.2s; outline: none; line-height: 1;"

class GreekConfig:
    KEYS = GREEK_ORDER
    LABELS = GREEK_LABELS
    SYMBOLS = GREEK_SYMBOLS
    VALUE_FORMATS = {
        'iv': '{:.2f}%',
        'theta': '${:.2f}',
        'delta': '{:.4f}',
        'gamma': '{:.6f}',
        'vega': '${:.2f}',
    }
    @classmethod
    def format_value(cls, key: str, value: float) -> str:
        fmt = cls.VALUE_FORMATS.get(key, '{:.2f}')
        return fmt.format(value)

class HeightCalculator:
    @staticmethod
    def calculate(n_greeks: int, total_height: int = 700) -> Tuple[int, int]:
        if n_greeks == 0: return total_height, 0
        greek_area = sum(0.25 / (2**i) for i in range(n_greeks))
        main_h = int(total_height * (1 - greek_area))
        greek_h = int(total_height * greek_area / n_greeks) if n_greeks > 0 else 0
        return main_h, greek_h

class TogglePanel:
    @staticmethod
    def create_toggles() -> List[Toggle]:
        toggles = []
        for key in GREEK_ORDER:
            t = Toggle(label=f'{GREEK_SYMBOLS[key]} {key.upper()}', active=True, button_type='success', width=85, height=32)
            toggles.append(t)
        return toggles
    @staticmethod
    def create_html_controls(toggles: List[Toggle]) -> Div:
        controls_div = Div(text="", height=40)
        html = f'<div style="{PANEL_STYLE}">'
        for i, key in enumerate(GREEK_ORDER):
            t = toggles[i]
            color = COLORS[key]
            sym = GREEK_SYMBOLS[key]
            key_up = key.upper()
            label_text = f"{sym} {key_up}" if sym != key_up else key_up
            btn_style = ChartTheme.get_button_style(color, active=True)
            html += f'<button type="button" style="{btn_style}" onclick="window.toggleGreek(\'{t.id}\')"><span style="font-size: 9px; opacity: 0.9; font-weight: 700;">{label_text}</span></button>'
        html += '</div>'
        controls_div.text = html
        return controls_div
    @staticmethod
    def create_update_callback(controls_div: Div, toggles: List[Toggle]) -> CustomJS:
        return CustomJS(args=dict(toggles=toggles, div=controls_div, colors=COLORS, symbols=GREEK_SYMBOLS, panel_style=PANEL_STYLE), 
        code="""
            let html = `<div style="${panel_style}">`;
            const keys = ['iv', 'theta', 'delta', 'gamma', 'vega'];
            for (let i = 0; i < toggles.length; i++) {
                const t = toggles[i]; const key = keys[i]; const color = colors[key]; const active = t.active;
                const border = active ? `1px solid ${color}` : "1px solid #ced4da";
                const textColor = active ? color : "#7F8C8D";
                const btnStyle = `padding: 0 8px; height: 22px; border-radius: 3px; font-size: 10px; border: ${border}; color: ${textColor}; background-color: rgba(255,255,255,0.8); box-shadow: 0 1px 3px rgba(0,0,0,0.05); cursor: pointer; display: flex; align-items: center; font-family: -apple-system, BlinkMacSystemFont, sans-serif; transition: all 0.2s; outline: none; line-height: 1;`;
                const onclick = `window.toggleGreek('${t.id}')`;
                const sym = symbols[key]; const keyUp = key.toUpperCase();
                const labelText = (sym !== keyUp) ? `${sym} ${keyUp}` : keyUp;
                html += `<button type="button" style="${btnStyle}" onclick="${onclick}"><span style="font-size: 9px; opacity: 0.9; font-weight: 700;">${labelText}</span></button>`;
            }
            html += '</div>';
            div.text = html;
        """)

class UIFactory:
    HEADER_CSS = f"""
    .unified-header {{ display: flex; align-items: center; gap: 20px; padding: 5px 0; margin-bottom: 5px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; border-bottom: 1px solid #eee; width: 100%; box-sizing: border-box; }}
    .header-title-group {{ display: flex; align-items: center; gap: 12px; }}
    .header-title {{ font-size: 16px; font-weight: 700; color: {COLORS['text']}; white-space: nowrap; }}
    .header-info-tag {{ font-size: 11px; color: #777; background: #f0f2f5; padding: 2px 8px; border-radius: 4px; font-family: 'SF Mono', Monaco, monospace; }}
    .header-controls {{ margin-left: auto; display: flex; align-items: center; gap: 10px; }}
    .header-render-info {{ font-size: 10px; color: #bbb; text-align: right; }}
    """
    @staticmethod
    def create_header(title: str, tags: List[str], render_ms: Optional[float] = None, extra_html: str = "") -> str:
        tags_html = "".join([f'<span class="header-info-tag">{{tag}}</span>' for tag in tags])
        render_html = f'<div class="header-render-info">Render: {render_ms:.0f}ms</div>' if render_ms is not None else ""
        return f'<div class="unified-header"><div class="header-title-group"><span class="header-title">{title}</span>{tags_html}</div><div class="header-controls">{extra_html}{render_html}</div></div>'

def adjust_color(hex_color: str, factor: float) -> str:
    if hex_color.startswith('#'): hex_color = hex_color[1:]
    r, g, b = int(hex_color[0:2], 16) / 255.0, int(hex_color[2:4], 16) / 255.0, int(hex_color[4:6], 16) / 255.0
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    new_l = max(0, min(1, l * factor))
    r, g, b = colorsys.hls_to_rgb(h, new_l, s)
    return '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))

def get_dte_colors(base_color: str, dtes: List[int]) -> Dict[int, str]:
    colors = {}
    dtes = sorted(dtes)
    for i, dte in enumerate(dtes):
        factor = 1.0 - (i / len(dtes)) * 0.4
        colors[dte] = adjust_color(base_color, factor)
    return colors

def get_toggle_css() -> str:
    return """
    .toggle-group { display: flex; gap: 6px; align-items: center; }
    .toggle-label { 
        display: flex; align-items: center; padding: 0 8px; height: 22px; border-radius: 3px; 
        font-size: 10px; font-weight: 700; border: 1px solid #ced4da; color: #7F8C8D; 
        background: rgba(255,255,255,0.8); cursor: pointer; transition: all 0.2s; user-select: none;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        line-height: 1; outline: none;
    }
    .toggle-label:hover { background: #f8f9fa; }
    .toggle-label input { display: none; }
    .toggle-label.active { border-color: var(--color); color: var(--color); }
    """

def get_toggle_panel_html(keys: List[str] = None) -> str:
    if keys is None: keys = GREEK_ORDER
    html = '<div class="toggle-group">'
    for k in keys:
        c = COLORS[k]
        sym = GREEK_SYMBOLS[k]
        k_up = k.upper()
        label_text = f"{sym} {k_up}" if sym != k_up else k_up
        html += f'<label class="toggle-label active" style="--color: {c}" id="label-{k}"><input type="checkbox" class="chart-toggle" value="{k}" checked onchange="this.checked ? this.parentElement.classList.add(\'active\') : this.parentElement.classList.remove(\'active\'); updateLayout();"><span>{label_text}</span></label>'
    html += '</div>'
    return html

def get_grid_layout_css(max_items: int = 5) -> str:
    return """
    .chart-grid { flex-grow: 1; display: grid; gap: 5px; padding: 0; width: 100%; height: 100%; transition: all 0.3s ease; box-sizing: border-box; }
    .chart-container { background: white; border-radius: 4px; overflow: hidden; position: relative; border: 1px solid #eee; }
    .hidden { display: none !important; }
    .bk-root { height: 100% !important; width: 100% !important; }
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
    """

def get_grid_layout_js(max_items: int = 5) -> str:
    return f"""
    function updateLayout() {{
        const toggleInputs = document.querySelectorAll('.chart-toggle');
        const grid = document.getElementById('main-grid');
        let activeCount = 0;
        if (!grid) return;
        toggleInputs.forEach(input => {{
            const container = document.getElementById('container-' + input.value);
            const label = input.parentElement;
            if (input.checked) {{
                activeCount++;
                if (container) {{
                    container.classList.remove('hidden');
                    container.classList.forEach(cls => {{ if (cls.startsWith('visible-slot-')) container.classList.remove(cls); }});
                    container.classList.add('visible-slot-' + activeCount);
                }}
            }} else if (container) {{
                container.classList.add('hidden');
            }}
        }});
        grid.className = 'chart-grid layout-' + Math.min(activeCount, {max_items});
        window.dispatchEvent(new Event('resize'));
    }}
    """
