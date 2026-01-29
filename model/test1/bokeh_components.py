"""
ФАЙЛ: bokeh_components.py
НАЗНАЧЕНИЕ: Единый источник правды для всех графиков (цвета, стили, константы)
ЗАВИСИМОСТИ: bokeh
ИСПОЛЬЗУЕТСЯ: strike_chart.py, smile_chart.py, surface_chart.py
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any
import colorsys
from bokeh.models import (
    CustomJS, Div, Toggle, Range1d, LinearAxis, Span,
    BasicTicker, NumeralTickFormatter, WheelZoomTool, PanTool, ResetTool
)
from bokeh.plotting import figure
from bokeh.models.formatters import DatetimeTickFormatter

# ============================================================================
# COLORS - ЕДИНСТВЕННЫЙ ИСТОЧНИК ПРАВДЫ (из 1.txt)
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
# GREEK CONFIGURATION (из 1.txt)
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

# ============================================================================
# PANEL STYLE - ЕДИНЫЙ ДЛЯ ВСЕХ ГРАФИКОВ
# ============================================================================
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
# UI FACTORY - ЕДИНЫЙ КОНСТРУКТОР ИНТЕРФЕЙСА
# ============================================================================
class UIFactory:
    """Генерирует общие компоненты интерфейса (шапки, кнопки) для всех графиков."""
    
    HEADER_CSS = f"""
    .unified-header {{
        display: flex;
        align-items: center;
        gap: 20px;
        padding: 5px 0;
        margin-bottom: 5px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        border-bottom: 1px solid #eee;
        width: 100%;
        box-sizing: border-box;
    }}
    .header-title-group {{
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    .header-title {{
        font-size: 16px; 
        font-weight: 700; 
        color: {COLORS['text']};
        white-space: nowrap;
    }}
    .header-info-tag {{
        font-size: 11px;
        color: #777;
        background: #f0f2f5;
        padding: 2px 8px;
        border-radius: 4px;
        font-family: 'SF Mono', Monaco, monospace;
    }}
    .header-controls {{
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 10px;
    }}
    .header-render-info {{
        font-size: 10px;
        color: #bbb;
        text-align: right;
    }}
    """

    @staticmethod
    def create_header(title: str, tags: List[str], render_ms: Optional[float] = None, extra_html: str = "") -> str:
        """Создает HTML-код шапки."""
        tags_html = "".join([f'<span class="header-info-tag">{tag}</span>' for tag in tags])
        render_html = f'<div class="header-render-info">Render: {render_ms:.0f}ms</div>' if render_ms is not None else ""
        
        return f'''
        <div class="unified-header">
            <div class="header-title-group">
                <span class="header-title">{title}</span>
                {tags_html}
            </div>
            <div class="header-controls">
                {extra_html}
                {render_html}
            </div>
        </div>
        '''

# ============================================================================
# CHART CONFIGURATION (из 1.txt)
# ============================================================================
@dataclass(frozen=True)
class ChartConfig:
    """Configuration for chart layout and styling."""
    min_border_left: int = 50
    min_border_right: int = 50
    min_border_top: int = 15
    min_border_bottom: int = 30
    xaxis_height: int = 40
    default_total_height: int = 700
    candle_width_ratio: float = 0.6
    grid_alpha: float = 0.3
    line_width: float = 2.0
    scatter_size: int = 6
    
    # Параметры из старой версии для обратной совместимости
    ohlc_y_padding: float = 0.12
    spot_y_padding: float = 0.08
    greek_y_padding: float = 0.15
    autoscale_padding: float = 0.10

CONFIG = ChartConfig()

# ============================================================================
# LEGACY WRAPPERS (для обратной совместимости с strike_chart.py)
# ============================================================================

class ChartTheme:
    """Legacy wrapper for COLORS."""
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
    CROSSHAIR_ALPHA = 0.7
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
    """Legacy wrapper for greek configuration."""
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
    
    @classmethod
    def get_label(cls, key: str) -> str:
        return GREEK_LABELS.get(key, key.upper())
    
    @classmethod
    def get_symbol(cls, key: str) -> str:
        return GREEK_SYMBOLS.get(key, key.upper())

# ============================================================================
# ПАНЕЛЬ TOGGLE КНОПОК (из старой версии)
# ============================================================================

class TogglePanel:
    """Legacy toggle panel creator."""
    @staticmethod
    def create_toggles() -> List[Toggle]:
        toggles = []
        for key in GREEK_ORDER:
            t = Toggle(
                label=f'{GREEK_SYMBOLS[key]} {key.upper()}',
                active=True,
                button_type='success',
                width=85,
                height=32,
            )
            toggles.append(t)
        return toggles
    
    @staticmethod
    def create_html_controls(toggles: List[Toggle]) -> Div:
        controls_div = Div(text="", height=40)
        html = f'<div style="{PANEL_STYLE}">'
        for i, key in enumerate(GREEK_ORDER):
            t = toggles[i]
            color = COLORS[key]
            symbol = GREEK_SYMBOLS[key]
            label_text = f"{symbol} {key.upper()}" if symbol != key.upper() else key.upper()
            btn_style = ChartTheme.get_button_style(color, active=True)
            onclick = f"window.toggleGreek('{t.id}')"
            html += f'''
            <button type="button" style="{btn_style}" onclick="{onclick}">
                <span style="font-size: 9px; opacity: 0.9; font-weight: 700;">{label_text}</span>
            </button>
            '''
        html += '</div>'
        controls_div.text = html
        return controls_div
    
    @staticmethod
    def create_update_callback(controls_div: Div, toggles: List[Toggle]) -> CustomJS:
        return CustomJS(
            args=dict(
                toggles=toggles,
                div=controls_div,
                colors=COLORS,
                symbols=GREEK_SYMBOLS,
                panel_style=PANEL_STYLE
            ),
            code="""
            let html = `<div style="${panel_style}">`;
            const keys = ['iv', 'theta', 'delta', 'gamma', 'vega'];
            for (let i = 0; i < toggles.length; i++) {
                const t = toggles[i];
                const key = keys[i];
                const color = colors[key];
                const active = t.active;
                // Use basic logic to mimic get_button_style
                const border = active ? `1px solid ${color}` : "1px solid #ced4da";
                const textColor = active ? color : "#7F8C8D";
                
                const btnStyle = `padding: 0 8px; height: 22px; border-radius: 3px; font-size: 10px; border: ${border}; color: ${textColor}; background-color: rgba(255,255,255,0.8); box-shadow: 0 1px 3px rgba(0,0,0,0.05); cursor: pointer; display: flex; align-items: center; font-family: -apple-system, BlinkMacSystemFont, sans-serif; transition: all 0.2s; outline: none; line-height: 1;`;
                const onclick = `window.toggleGreek('${t.id}')`;
                const sym = symbols[key];
                const keyUpper = key.toUpperCase();
                const labelText = (sym !== keyUpper) ? `${sym} ${keyUpper}` : keyUpper;
                html += `<button type="button" style="${btnStyle}" onclick="${onclick}"><span style="font-size: 9px; opacity: 0.9; font-weight: 700;">${labelText}</span></button>`;
            }
            html += '</div>';
            div.text = html;
            """
        )

# ============================================================================
# КАЛЬКУЛЯТОР ВЫСОТ
# ============================================================================

class HeightCalculator:
    """Calculation of plot heights for Strike Chart."""
    @staticmethod
    def calculate(n_greeks: int, total_height: int = 700) -> Tuple[int, int]:
        if n_greeks == 0:
            return total_height, 0
        greek_area = sum(0.25 / (2**i) for i in range(n_greeks))
        main_h = int(total_height * (1 - greek_area))
        greek_h = int(total_height * greek_area / n_greeks) if n_greeks > 0 else 0
        return main_h, greek_h

# ============================================================================
# TOGGLE CALLBACKS
# ============================================================================

class ToggleCallbackBuilder:
    """Builds CustomJS callbacks for layout toggling."""
    @staticmethod
    def build(toggles, greek_plots, main_plot, legend_div, src_ohlc, src_spot, src_greeks, fixed_overhead=155):
        args = dict(
            toggles=toggles, greek_plots=greek_plots, main_plot=main_plot,
            legend_div=legend_div, src_ohlc=src_ohlc, src_spot=src_spot,
            src_iv=src_greeks['iv'], src_theta=src_greeks['theta'],
            src_delta=src_greeks['delta'], src_gamma=src_greeks['gamma'],
            src_vega=src_greeks['vega'], colors=COLORS, panel_style=PANEL_STYLE
        )
        js_code = f"""
            const overhead = {fixed_overhead};
            const TOTAL_HEIGHT = Math.max(window.innerHeight - overhead, 400);
            let activeCount = 0;
            for (let i = 0; i < toggles.length; i++) {{ if (toggles[i].active) activeCount++; }}
            let greekArea = 0;
            for (let i = 0; i < activeCount; i++) {{ greekArea += 0.25 / Math.pow(2, i); }}
            let mainHeight, greekHeight;
            if (activeCount === 0) {{ mainHeight = TOTAL_HEIGHT; greekHeight = 0; }}
            else {{ 
                mainHeight = Math.round(TOTAL_HEIGHT * (1 - greekArea));
                greekHeight = Math.round((TOTAL_HEIGHT - mainHeight) / activeCount);
            }}
            main_plot.height = mainHeight;
            for (let i = 0; i < greek_plots.length; i++) {{
                const isActive = toggles[i].active;
                greek_plots[i].visible = isActive;
                greek_plots[i].height = isActive ? greekHeight : 0;
            }}
            if (legend_div.tags && legend_div.tags.length > 0) {{
                const x = legend_div.tags[0];
                const timestamps = src_ohlc.data.timestamp;
                let minDist = Infinity, idx = 0;
                for (let i = 0; i < timestamps.length; i++) {{
                    const d = Math.abs(timestamps[i] - x);
                    if (d < minDist) {{ minDist = d; idx = i; }}
                }}
                const showIV = toggles[0].active ? 'inline' : 'none';
                const showTheta = toggles[1].active ? 'inline' : 'none';
                const showDelta = toggles[2].active ? 'inline' : 'none';
                const showGamma = toggles[3].active ? 'inline' : 'none';
                const showVega = toggles[4].active ? 'inline' : 'none';
                const dateStr = new Date(timestamps[idx]).toLocaleDateString('en-US', {{day:'2-digit', month:'short', year:'numeric'}});
                legend_div.text = `<div style="${{panel_style}}"><span style="color:#666;">${{dateStr}}</span> <span style="color:${{colors.iv}};">O:${{src_ohlc.data.open[idx].toFixed(2)}} H:${{src_ohlc.data.high[idx].toFixed(2)}} L:${{src_ohlc.data.low[idx].toFixed(2)}} C:${{src_ohlc.data.close[idx].toFixed(2)}}</span> <span style="color:#969696;">Spot: $${{src_spot.data.value[idx].toFixed(0)}}</span> <span style="color:${{colors.iv}}; display:${{showIV}};">IV:${{src_iv.data.value[idx].toFixed(2)}}%</span> <span style="color:${{colors.theta}}; display:${{showTheta}};">Θ:$${{src_theta.data.value[idx].toFixed(2)}}</span> <span style="color:${{colors.delta}}; display:${{showDelta}};">Δ:${{src_delta.data.value[idx].toFixed(4)}}</span> <span style="color:${{colors.gamma}}; display:${{showGamma}};">Γ:${{src_gamma.data.value[idx].toFixed(6)}}</span> <span style="color:${{colors.vega}}; display:${{showVega}};">ν:$${{src_vega.data.value[idx].toFixed(2)}}</span></div>`;
            }}
        """
        return [CustomJS(args=args, code=js_code) for _ in toggles]

    @staticmethod
    def build_smile(toggles, greek_plots, main_plot, axis_plot, total_height):
        args = dict(toggles=toggles, greek_plots=greek_plots, main_plot=main_plot, axis_plot=axis_plot, total_h=total_height)
        js_code = """
            const activeCount = toggles.slice(1).filter(t => t.active).length;
            let greekArea = 0;
            for (let i = 0; i < activeCount; i++) { greekArea += 0.25 / Math.pow(2, i); }
            let mainHeight = activeCount === 0 ? total_h : Math.round(total_h * (1 - greekArea));
            let greekHeight = activeCount === 0 ? 0 : Math.round((total_h - mainHeight) / activeCount);
            main_plot.height = mainHeight;
            const gToggles = toggles.slice(1);
            for (let i = 0; i < greek_plots.length; i++) {
                const act = gToggles[i].active;
                greek_plots[i].visible = act;
                greek_plots[i].height = act ? greekHeight : 0;
            }
        """
        return [CustomJS(args=args, code=js_code) for _ in toggles]

class HoverSyncBuilder:
    """Builds CustomJS for synchronized hover."""
    @staticmethod
    def build(legend_div, src_ohlc, src_spot, src_greeks, all_spans, toggles):
        args = dict(
            legend_div=legend_div, src_ohlc=src_ohlc, src_spot=src_spot,
            src_iv=src_greeks['iv'], src_theta=src_greeks['theta'],
            src_delta=src_greeks['delta'], src_gamma=src_greeks['gamma'],
            src_vega=src_greeks['vega'], spans=all_spans, toggles=toggles,
            colors=COLORS, panel_style=PANEL_STYLE
        )
        js_code = """
            const x = cb_data.geometry.x;
            legend_div.tags = [x];
            for (let i = 0; i < spans.length; i++) {
                spans[i].location = x;
                if (i === 0) spans[i].visible = true;
                else if (i > 0 && i <= toggles.length) spans[i].visible = toggles[i-1].active;
            }
            const ts = src_ohlc.data.timestamp;
            let minDist = Infinity, idx = 0;
            for (let i = 0; i < ts.length; i++) {
                const d = Math.abs(ts[i] - x);
                if (d < minDist) { minDist = d; idx = i; }
            }
            const showIV = toggles[0].active ? 'inline' : 'none';
            const showTheta = toggles[1].active ? 'inline' : 'none';
            const showDelta = toggles[2].active ? 'inline' : 'none';
            const showGamma = toggles[3].active ? 'inline' : 'none';
            const showVega = toggles[4].active ? 'inline' : 'none';
            const dateStr = new Date(ts[idx]).toLocaleDateString('en-US', {day:'2-digit', month:'short', year:'numeric'});
            legend_div.text = `<div style="${panel_style}"><span style="color:#666;">${dateStr}</span> <span style="color:${colors.iv};">O:${src_ohlc.data.open[idx].toFixed(2)} H:${src_ohlc.data.high[idx].toFixed(2)} L:${src_ohlc.data.low[idx].toFixed(2)} C:${src_ohlc.data.close[idx].toFixed(2)}</span> <span style="color:#969696;">Spot: $${src_spot.data.value[idx].toFixed(0)}</span> <span style="color:${colors.iv}; display:${showIV};">IV:${src_iv.data.value[idx].toFixed(2)}%</span> <span style="color:${colors.theta}; display:${showTheta};">Θ:$${src_theta.data.value[idx].toFixed(2)}</span> <span style="color:${colors.delta}; display:${showDelta};">Δ:${src_delta.data.value[idx].toFixed(4)}</span> <span style="color:${colors.gamma}; display:${showGamma};">Γ:${src_gamma.data.value[idx].toFixed(6)}</span> <span style="color:${colors.vega}; display:${showVega};">ν:$${src_vega.data.value[idx].toFixed(2)}</span></div>`;
        """
        return CustomJS(args=args, code=js_code)

class PlotFactory:
    """Creates configured figure objects."""
    @staticmethod
    def create_main_figure(height: int, x_range: Range1d = None) -> figure:
        kwargs = dict(x_axis_type='datetime', height=height, tools='', background_fill_color=COLORS['bg'], min_border_left=CONFIG.min_border_left, min_border_right=CONFIG.min_border_right, min_border_top=10, min_border_bottom=5, title=None, sizing_mode='stretch_width')
        if x_range is not None: kwargs['x_range'] = x_range
        p = figure(**kwargs)
        wheel_zoom, pan, reset = WheelZoomTool(maintain_focus=False), PanTool(), ResetTool()
        p.add_tools(wheel_zoom, pan, reset)
        p.toolbar.active_scroll, p.grid.grid_line_alpha, p.outline_line_color, p.toolbar_location = wheel_zoom, CONFIG.grid_alpha, None, None
        p.xaxis.axis_line_color = p.yaxis.axis_line_color = p.xaxis.major_tick_line_color = p.yaxis.major_tick_line_color = COLORS['axis']
        p.yaxis.major_tick_in = 2
        p.yaxis.major_tick_out = 2
        return p
    
    @staticmethod
    def create_greek_figure(key: str, x_range: Range1d, y_range: Range1d, height: int) -> figure:
        p = figure(
            x_axis_type='datetime', 
            x_range=x_range, 
            y_range=y_range, 
            height=height, 
            tools='', 
            background_fill_color=COLORS['bg'], 
            min_border_left=CONFIG.min_border_left,
            min_border_right=45,          # Место для подписи справа
            min_border_top=3, 
            min_border_bottom=3, 
            title=None, 
            sizing_mode='stretch_width',
            y_axis_location='left'        # Числа возвращаем налево
        )
        wheel_zoom, pan = WheelZoomTool(maintain_focus=False), PanTool()
        p.add_tools(wheel_zoom, pan)
        p.toolbar.active_scroll, p.grid.grid_line_alpha, p.outline_line_color, p.toolbar_location = wheel_zoom, CONFIG.grid_alpha, None, None
        
        # Левая ось (только числа)
        p.yaxis.axis_line_color = COLORS['axis']
        p.yaxis.major_tick_line_color = COLORS['axis'] # Включено для симметрии
        p.yaxis.minor_tick_line_color = None
        p.yaxis.major_tick_in = 2
        p.yaxis.major_tick_out = 2
        p.yaxis.major_label_text_font_size = '7pt'
        p.yaxis.major_label_text_color = '#888888'
        p.yaxis.axis_label = None        # Убираем имя слева
        p.yaxis.ticker = BasicTicker(desired_num_ticks=4)
        p.yaxis.formatter = NumeralTickFormatter(format=GREEK_FORMATS.get(key, '0.0'))
        
        # Правая ось (только название грека)
        p.extra_y_ranges = {"label_range": y_range}
        label_axis = LinearAxis(y_range_name="label_range", axis_label=GREEK_LABELS.get(key, key.upper()))
        label_axis.axis_label_text_color = COLORS[key]
        label_axis.axis_label_text_font_size = '8pt'
        label_axis.axis_label_text_font_style = 'bold'
        label_axis.major_label_text_font_size = '0pt' # Скрыть цифры справа
        label_axis.major_tick_line_color = COLORS['axis'] # Включено для симметрии
        label_axis.major_tick_in = 2
        label_axis.major_tick_out = 2
        label_axis.minor_tick_line_color = None
        label_axis.axis_line_color = COLORS['axis']
        p.add_layout(label_axis, 'right')
        
        p.xaxis.visible = False
        return p

# ============================================================================
# NEW HELPERS (из 1.txt)
# ============================================================================

def get_toggle_button_html(key: str, checked: bool = True) -> str:
    color = COLORS[key]
    symbol = GREEK_SYMBOLS[key]
    checked_attr = 'checked' if checked else ''
    return f'<label class="toggle-label" id="label-{key}"><input type="checkbox" class="chart-toggle" value="{key}" {checked_attr} data-color="{color}"><span>{symbol} {key.upper()}</span></label>'

def get_toggle_panel_html(keys: List[str] = None) -> str:
    if keys is None: keys = GREEK_ORDER
    buttons = ''.join([get_toggle_button_html(key) for key in keys])
    return f'<div class="controls-container"><div class="controls" style="{PANEL_STYLE}"><div class="toggle-group">{buttons}</div></div></div>'

def get_toggle_css() -> str:
    return """
    .controls-container { display: flex; justify-content: center; flex-shrink: 0; margin-bottom: 5px; }
    .toggle-group { display: flex; gap: 12px; align-items: center; }
    .toggle-label { display: flex; align-items: center; padding: 0 10px; height: 24px; border-radius: 4px; font-size: 11px; font-weight: 700; border: 1px solid #ced4da; color: #7F8C8D; background: rgba(255,255,255,0.9); box-shadow: 0 1px 3px rgba(0,0,0,0.05); cursor: pointer; transition: all 0.2s; user-select: none; font-family: -apple-system, BlinkMacSystemFont, sans-serif; text-transform: uppercase; letter-spacing: 0.3px; }
    .toggle-label:hover { border-color: #bbb; background: #fff; }
    .toggle-label input { display: none; }
    .toggle-label.active { background: #fff; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1); }
    """

def get_grid_layout_css(max_items: int = 5) -> str:
    css = """
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
    if max_items >= 6: css += ".layout-6 { grid-template-columns: 1fr 1fr 1fr; grid-template-rows: 1fr 1fr; }"
    return css

def get_grid_layout_js(max_items: int = 5) -> str:
    return f"""
    function updateLayout() {{
        const toggleInputs = document.querySelectorAll('.chart-toggle');
        const grid = document.getElementById('main-grid');
        let activeCount = 0;
        toggleInputs.forEach(input => {{
            const key = input.value;
            const container = document.getElementById('container-' + key);
            const label = input.parentElement;
            const color = input.dataset.color;
            if (input.checked) {{
                activeCount++;
                container.classList.remove('hidden');
                label.classList.add('active');
                label.style.borderColor = color;
                label.style.color = color;
                container.classList.forEach(cls => {{ if (cls.startsWith('visible-slot-')) container.classList.remove(cls); }});
                container.classList.add('visible-slot-' + activeCount);
            }} else {{
                container.classList.add('hidden');
                label.classList.remove('active');
                label.style.borderColor = '#ced4da';
                label.style.color = '#7F8C8D';
            }}
        }});
        grid.className = 'chart-grid';
        if (activeCount > 0) {{ grid.classList.add('layout-' + Math.min(activeCount, {max_items})); }}
        window.dispatchEvent(new Event('resize'));
    }}
    document.addEventListener('DOMContentLoaded', () => {{
        updateLayout();
        document.querySelectorAll('.chart-toggle').forEach(t => t.addEventListener('change', updateLayout));
    }});
    """

def adjust_color(hex_color: str, factor: float) -> str:
    if hex_color.startswith('#'): hex_color = hex_color[1:]
    r, g, b = int(hex_color[0:2], 16) / 255.0, int(hex_color[2:4], 16) / 255.0, int(hex_color[4:6], 16) / 255.0
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    new_l = max(0, min(1, l * factor))
    s = s * 0.8 if factor > 1 else s * 1.2
    r, g, b = colorsys.hls_to_rgb(h, new_l, min(1, s))
    return '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))

def get_dte_colors(base_color: str, dtes: List[int]) -> Dict[int, str]:
    dtes = sorted(dtes)
    colors = {}
    if len(dtes) == 1: colors[dtes[0]] = base_color
    elif len(dtes) == 2: colors[dtes[0]], colors[dtes[1]] = base_color, adjust_color(base_color, 0.7)
    else:
        colors[dtes[0]], colors[dtes[1]] = base_color, adjust_color(base_color, 0.75)
        for i, dte in enumerate(dtes[2:], start=2): colors[dte] = adjust_color(base_color, 0.5 - i * 0.1)
    return colors

def format_greek_value(key: str, value: float) -> str:
    if key == 'gamma': return f'{value:.6f}'
    elif key == 'delta': return f'{value:.4f}'
    elif key == 'iv': return f'{value:.1f}%'
    elif key in ['theta', 'vega']: return f'${value:.2f}'
    return f'{value:.2f}'
