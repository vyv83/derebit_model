"""
Bokeh - Strike Chart Implementation v7.0 (REFACTORED)
======================================================
Полная реализация спецификации TASK_chart_lib_comparison.md
Исправления v7.0:
- ✅ Crosshair Sync - реальная синхронизация через Span на ВСЕХ графиках
- ✅ Legend Sync - динамическое обновление легенд при наведении курсора
- ✅ Full-screen layout - холст растягивается на всё окно
- ✅ Bottom chart height - компенсация высоты оси времени
- ✅ Auto-scaling Y - унифицированная функция для всех графиков
- ✅ DataFrame input - поддержка входных данных согласно спецификации
- ✅ Aligned Y-axes - гарантированное выравнивание всех графиков
- ✅ Price Lines на ВСЕХ графиках (включая греки)
- ✅ Правильный цвет свечей (close vs open)
- ✅ Дата в легенде при hover
- ✅ Унифицированные константы (Python = JavaScript)
Запуск: python test_bokeh.py
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
from bokeh.plotting import figure, show, output_file
from bokeh.models import (
    ColumnDataSource, CrosshairTool, HoverTool, Span,
    CustomJS, Range1d, LinearAxis, Label, Div, Toggle,
    NumeralTickFormatter, WheelZoomTool, PanTool, ResetTool,
    Legend, LegendItem, BasicTicker
)
from bokeh.layouts import column, row, Spacer
from bokeh.models.formatters import DatetimeTickFormatter
from strikes_layout_integrator import create_integrated_axis_plot, get_layout_manager_js, finalize_layout
# ============================================================================
# COLORS - ТОЧНО ПО СПЕЦИФИКАЦИИ
# ============================================================================
COLORS = {
    # Свечи - ТОЧНЫЕ цвета из спецификации
    'call': '#76D7C4',      # Зелёные свечи (Call акцент)
    'put': '#FF8787',       # Красные свечи (Put акцент)
    
    # Греки - точные цвета
    'iv': '#9B59B6',        # Purple - IV
    'theta': '#E67E22',     # Orange - Theta
    'delta': '#3498DB',     # Blue - Delta  
    'gamma': '#F1C40F',     # Yellow - Gamma
    'vega': '#1ABC9C',      # Cyan - Vega
    
    # Спот - точный цвет
    'spot': '#969696',      # Gray пунктир
    
    # UI
    'bg': '#FFFFFF',        # Строго белый фон
    'text': '#333333',
    'grid': '#C8C8C8',      # Сетка rgba(200,200,200,0.15)
    'crosshair': '#546E7A',
}
GREEKS = ['iv', 'theta', 'delta', 'gamma', 'vega']
GREEK_LABELS = {
    'iv': 'IV (%)',
    'theta': 'Theta ($)',
    'delta': 'Delta',
    'gamma': 'Gamma',
    'vega': 'Vega ($)',
}
GREEK_SYMBOLS = {
    'iv': 'IV',
    'theta': 'Θ',
    'delta': 'Δ',
    'gamma': 'Γ',
    'vega': 'ν',
}
# ============================================================================
# CHART CONFIGURATION - Unified constants for Python and JavaScript
# ============================================================================
@dataclass(frozen=True)
class ChartConfig:
    """Configuration for Strike Chart layout and styling."""
    # Layout borders
    min_border_left: int = 50
    min_border_right: int = 50
    xaxis_height: int = 40  # Height for X-axis area (unified!)
    
    # Heights
    default_total_height: int = 700
    
    # Candle width (fraction of daily interval in ms)
    candle_width_ratio: float = 0.6
    
    # Y-range padding ratios
    ohlc_y_padding: float = 0.12
    spot_y_padding: float = 0.08
    greek_y_padding: float = 0.15
    autoscale_padding: float = 0.10
    
    # Styling
    grid_alpha: float = 0.15
    crosshair_alpha: float = 0.7
CONFIG = ChartConfig()
# Legacy constants for backward compatibility
MIN_BORDER_LEFT = CONFIG.min_border_left
MIN_BORDER_RIGHT = CONFIG.min_border_right
XAXIS_HEIGHT = CONFIG.xaxis_height

# ============================================================================
# UNIFIED PANEL STYLING (SINGLE SOURCE OF TRUTH)
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
"""
# ============================================================================
# DATA GENERATION / DataFrame Support
# ============================================================================
def generate_dataframes(n_points: int = 200):
    """
    Generate synthetic option data as DataFrames per specification.
    Returns: df_ohlc, df_spot, df_greeks (dict)
    """
    np.random.seed(42)
    
    dates = pd.date_range(start='2024-01-01', periods=n_points, freq='D')
    
    # Spot (BTC) - базовый актив
    spot = 50000 + np.cumsum(np.random.normal(100, 400, n_points))
    
    # IV 30-100% - волатильность
    iv = np.clip(60 + np.cumsum(np.random.normal(0, 1.2, n_points)), 30, 100)
    
    # Option OHLC - цены опциона
    strike = 55000
    intrinsic = np.maximum(spot - strike, 0)
    time_decay = 1 - np.arange(n_points) / n_points
    base_price = intrinsic * 0.2 + iv * 10 * time_decay + 100
    
    opens, highs, lows, closes = [], [], [], []
    prev = base_price[0]
    for i in range(n_points):
        c = base_price[i] + np.random.normal(0, 15)
        h = max(prev, c) + abs(np.random.normal(0, 12))
        l = min(prev, c) - abs(np.random.normal(0, 12))
        opens.append(prev)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        prev = c
    
    # DataFrames согласно спецификации
    df_ohlc = pd.DataFrame({
        'timestamp': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
    })
    
    df_spot = pd.DataFrame({
        'timestamp': dates,
        'value': spot.tolist(),
    })
    
    # Греки - словарь DataFrame
    theta_vals = -25 - iv/8 + np.random.normal(0, 3, n_points)
    delta_vals = np.clip(0.4 + 0.15*np.sin(np.arange(n_points)/10) + 0.05*np.random.randn(n_points), 0, 1)
    gamma_vals = 0.001 + 0.0003*np.cos(np.arange(n_points)/15) + 0.00005*np.random.randn(n_points)
    vega_vals = 80 + 25*np.sin(np.arange(n_points)/20) + 5*np.random.randn(n_points)
    
    df_greeks = {
        'iv': pd.DataFrame({'timestamp': dates, 'value': iv.tolist()}),
        'theta': pd.DataFrame({'timestamp': dates, 'value': theta_vals.tolist()}),
        'delta': pd.DataFrame({'timestamp': dates, 'value': delta_vals.tolist()}),
        'gamma': pd.DataFrame({'timestamp': dates, 'value': gamma_vals.tolist()}),
        'vega': pd.DataFrame({'timestamp': dates, 'value': vega_vals.tolist()}),
    }
    
    return df_ohlc, df_spot, df_greeks
def validate_dataframe(df: pd.DataFrame, required_columns: List[str], name: str) -> None:
    """Validate DataFrame has required columns and is not empty."""
    if df is None or len(df) == 0:
        raise ValueError(f"{name} DataFrame is empty")
    
    missing = set(required_columns) - set(df.columns)
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")
def format_greek_value(key: str, value: float) -> str:
    """Format greek value for display on Price Line label."""
    if key == 'gamma':
        return f'{value:.6f}'
    elif key == 'delta':
        return f'{value:.4f}'
    elif key == 'iv':
        return f'{value:.1f}%'
    elif key in ['theta', 'vega']:
        return f'${value:.2f}'
    return f'{value:.2f}'
def dataframes_to_sources(
    df_ohlc: pd.DataFrame,
    df_spot: pd.DataFrame,
    df_greeks: Dict[str, pd.DataFrame]
) -> Tuple[ColumnDataSource, ColumnDataSource, Dict[str, ColumnDataSource]]:
    """
    Convert DataFrames to ColumnDataSources with formatted values.
    
    Args:
        df_ohlc: OHLC data with timestamp, open, high, low, close
        df_spot: Spot data with timestamp, value
        df_greeks: Dict of greek DataFrames with timestamp, value
    
    Returns:
        Tuple of (src_ohlc, src_spot, src_greeks dict)
    """
    # Validate inputs
    validate_dataframe(df_ohlc, ['timestamp', 'open', 'high', 'low', 'close'], 'OHLC')
    validate_dataframe(df_spot, ['timestamp', 'value'], 'Spot')
    for key, df in df_greeks.items():
        validate_dataframe(df, ['timestamp', 'value'], f'Greek {key}')
    
    # CRITICAL FIX: Candlestick color based on close vs open (not close vs previous close!)
    # Green (call) if price went UP during the period (close >= open)
    # Red (put) if price went DOWN during the period (close < open)
    colors = [
        COLORS['call'] if df_ohlc['close'].iloc[i] >= df_ohlc['open'].iloc[i] else COLORS['put']
        for i in range(len(df_ohlc))
    ]
    
    src_ohlc = ColumnDataSource(dict(
        timestamp=df_ohlc['timestamp'].tolist(),
        open=df_ohlc['open'].tolist(),
        high=df_ohlc['high'].tolist(),
        low=df_ohlc['low'].tolist(),
        close=df_ohlc['close'].tolist(),
        color=colors,
        open_fmt=[f'{v:.2f}' for v in df_ohlc['open']],
        high_fmt=[f'{v:.2f}' for v in df_ohlc['high']],
        low_fmt=[f'{v:.2f}' for v in df_ohlc['low']],
        close_fmt=[f'{v:.2f}' for v in df_ohlc['close']],
    ))
    
    src_spot = ColumnDataSource(dict(
        timestamp=df_spot['timestamp'].tolist(),
        value=df_spot['value'].tolist(),
        value_fmt=[f'{v:.0f}' for v in df_spot['value']],
    ))
    
    src_greeks = {}
    for key, df in df_greeks.items():
        if key == 'gamma':
            fmt = [f'{v:.6f}' for v in df['value']]
        elif key == 'delta':
            fmt = [f'{v:.4f}' for v in df['value']]
        elif key == 'iv':
            fmt = [f'{v:.2f}%' for v in df['value']]
        elif key in ['theta', 'vega']:
            fmt = [f'${v:.2f}' for v in df['value']]
        else:
            fmt = [f'{v:.2f}' for v in df['value']]
            
        src_greeks[key] = ColumnDataSource(dict(
            timestamp=df['timestamp'].tolist(),
            value=df['value'].tolist(),
            value_fmt=fmt,
        ))
    
    return src_ohlc, src_spot, src_greeks
# ============================================================================
# HEIGHT CALCULATION - Точная формула из спецификации
# ============================================================================
def calc_heights(n_greeks: int, total: int = 800):
    """
    Расчёт высот по формуле спецификации:
    - 1 грек: Main 75%, Greeks 25%
    - 2 грека: Main 62.5%, Greeks 37.5%
    - и т.д.
    """
    if n_greeks == 0:
        return total, 0
    
    # Прирост = 25% для первого, затем каждый следующий = половина предыдущего
    greek_area = sum(0.25 / (2**i) for i in range(n_greeks))
    main_h = int(total * (1 - greek_area))
    greek_h = int(total * greek_area / n_greeks) if n_greeks > 0 else 0
    
    return main_h, greek_h
# ============================================================================
# SYNCHRONIZED CROSSHAIR - Реальная синхронизация через Span
# ============================================================================
def create_sync_crosshair_spans(plots):
    """
    Создаёт синхронизированные Span crosshair на всех графиках.
    Returns: list of spans, JS callback code
    """
    spans = []
    for p in plots:
        # Вертикальный span для crosshair
        span = Span(
            location=0, 
            dimension='height',
            line_color=COLORS['crosshair'],
            line_width=1,
            line_alpha=0.7,
            line_dash='solid',
            visible=False
        )
        p.add_layout(span)
        spans.append(span)
    
    return spans
# ============================================================================
# MAIN CHART - Свечной график + Спот
# ============================================================================
def create_main_chart(src_ohlc, src_spot, height, x_range=None):
    """
    Создание главного графика со свечами и спотом.
    Включает: Price Lines, аннотации, легенду.
    """
    
    # Y-range для OHLC
    lo = min(src_ohlc.data['low'])
    hi = max(src_ohlc.data['high'])
    pad = (hi - lo) * 0.12
    
    # Параметры figure
    fig_kwargs = dict(
        x_axis_type='datetime',
        y_range=Range1d(lo - pad, hi + pad, bounds=(lo - pad, hi + pad)),
        height=height,
        tools='',
        background_fill_color=COLORS['bg'],
        min_border_left=MIN_BORDER_LEFT,
        min_border_right=MIN_BORDER_RIGHT,
        min_border_top=10,
        min_border_bottom=5,
        title=None,
        sizing_mode='stretch_width',  # Растягивается по ширине
    )
    
    if x_range is not None:
        fig_kwargs['x_range'] = x_range
    
    p = figure(**fig_kwargs)
    
    # Инструменты
    wheel_zoom = WheelZoomTool(maintain_focus=False)
    pan = PanTool()
    reset = ResetTool()
    p.add_tools(wheel_zoom, pan, reset)
    p.toolbar.active_scroll = wheel_zoom
    
    # Стилизация сетки - rgba(200,200,200,0.15)
    p.grid.grid_line_alpha = 0.15
    p.outline_line_color = None
    p.toolbar_location = None
    
    # Серые оси
    p.xaxis.axis_line_color = '#CCCCCC'
    p.yaxis.axis_line_color = '#CCCCCC'
    p.xaxis.major_tick_line_color = '#CCCCCC'
    p.yaxis.major_tick_line_color = '#CCCCCC'
    p.xaxis.minor_tick_line_color = '#CCCCCC'
    p.yaxis.minor_tick_line_color = '#CCCCCC'
    
    # ==================== CANDLESTICKS ====================
    w = 0.6 * 24 * 60 * 60 * 1000  # Ширина свечи
    
    # Wicks (тени)
    p.segment(
        'timestamp', 'low', 'timestamp', 'high',
        source=src_ohlc, color='color', line_width=1
    )
    
    # Bodies (тела свечей)
    p.vbar(
        'timestamp', w, 'close', 'open',
        source=src_ohlc, fill_color='color', line_color='color'
    )
    
    # ==================== SPOT LINE ON Y2 ====================
    smin, smax = min(src_spot.data['value']), max(src_spot.data['value'])
    spad = (smax - smin) * 0.08
    p.extra_y_ranges = {'spot': Range1d(smin - spad, smax + spad, bounds=(smin - spad, smax + spad))}
    
    # Правая ось для спота - серая с меньшим количеством тиков
    spot_axis = LinearAxis(y_range_name='spot', axis_label='Spot $')
    spot_axis.axis_label_text_color = '#888888'
    spot_axis.major_label_text_color = '#888888'
    spot_axis.major_label_text_font_size = '7pt'
    spot_axis.axis_label_text_font_size = '8pt'
    spot_axis.axis_label_text_font_style = 'bold'
    spot_axis.axis_line_color = '#CCCCCC'
    spot_axis.major_tick_line_color = '#CCCCCC'
    spot_axis.minor_tick_line_color = '#CCCCCC'
    spot_axis.major_tick_in = 2
    spot_axis.major_tick_out = 2
    spot_axis.ticker = BasicTicker(desired_num_ticks=4)  # Меньше тиков
    p.add_layout(spot_axis, 'right')
    
    # Линия спота - пунктирная серая (без легенды - ось Y уже подписана)
    p.line(
        'timestamp', 'value', source=src_spot,
        color=COLORS['spot'], line_width=1.5, line_dash='dashed',
        y_range_name='spot'
    )
    
    # ==================== PRICE LINES (STICKY LABELS) ====================
    last_close = src_ohlc.data['close'][-1]
    last_spot = src_spot.data['value'][-1]
    
    # Price Line для опциона
    option_price_line = Span(
        location=last_close, dimension='width',
        line_color=COLORS['call'], line_dash='dotted', line_width=1.5
    )
    p.add_layout(option_price_line)
    
    # Price Line для спота (на оси Y2)
    spot_price_line = Span(
        location=last_spot, dimension='width',
        line_color=COLORS['spot'], line_dash='dotted', line_width=1,
        y_range_name='spot'
    )
    p.add_layout(spot_price_line)
    
    # STICKY LABELS - привязаны к видимому краю через JS callback
    # Option label - справа
    option_label = Label(
        x=p.x_range.end if hasattr(p.x_range, 'end') else src_ohlc.data['timestamp'][-1],
        y=last_close,
        text=f'{last_close:.2f}',
        text_font_size='8pt',
        text_color='#888888',
        text_font_style='normal',
        text_align='right',
        x_offset=-5,
        y_offset=2,
    )
    p.add_layout(option_label)
    
    # Spot label - слева
    spot_label = Label(
        x=p.x_range.start if hasattr(p.x_range, 'start') else src_spot.data['timestamp'][0],
        y=last_spot,
        text=f'{last_spot:.0f}',
        text_font_size='8pt',
        text_color='#888888',
        text_font_style='normal',
        text_align='left',
        x_offset=5,
        y_offset=2,
        y_range_name='spot'
    )
    p.add_layout(spot_label)
    
    # JavaScript callback для sticky labels - обновляет позицию при pan/zoom
    sticky_labels_cb = CustomJS(args=dict(
        option_label=option_label, 
        spot_label=spot_label,
        x_range=p.x_range
    ), code="""
        // Обновляем позицию меток при изменении видимого диапазона
        option_label.x = x_range.end;
        spot_label.x = x_range.start;
    """)
    p.x_range.js_on_change('start', sticky_labels_cb)
    p.x_range.js_on_change('end', sticky_labels_cb)
    
    # Левая ось Y - серая с меньшим количеством тиков
    p.yaxis[0].axis_label = 'Option Price ($)'
    p.yaxis[0].axis_label_text_color = '#888888'
    p.yaxis[0].major_label_text_color = '#888888'
    p.yaxis[0].major_label_text_font_size = '7pt'
    p.yaxis[0].axis_label_text_font_size = '8pt'
    p.yaxis[0].axis_label_text_font_style = 'bold'
    p.yaxis[0].major_tick_in = 2
    p.yaxis[0].major_tick_out = 2
    p.yaxis[0].ticker = BasicTicker(desired_num_ticks=5)  # Меньше тиков
    
    # X-axis изначально скрыта
    p.xaxis.visible = False
    p.xaxis.formatter = DatetimeTickFormatter(
        days='%d %b',
        months='%b %Y'
    )
    
    return p, option_label, spot_label  # Возвращаем labels для возможного использования
# ============================================================================
# GREEK CHART - Subplot for individual Greek value
# ============================================================================
def create_greek_chart(
    src: ColumnDataSource,
    key: str,
    x_range: Range1d,
    height: int,
    show_xaxis: bool = False
) -> Tuple[Any, Span, Label]:
    """
    Create Greek subplot with Price Line per specification.
    
    Args:
        src: ColumnDataSource with timestamp and value
        key: Greek key (iv, theta, delta, gamma, vega)
        x_range: Shared X range
        height: Chart height
        show_xaxis: Whether to show X axis (only on bottom chart)
    
    Returns:
        Tuple of (figure, price_line, price_label) - for visibility management on toggle
    """
    color = COLORS[key]
    label = GREEK_LABELS[key]
    symbol = GREEK_SYMBOLS[key]
    
    vals = src.data['value']
    vmin, vmax = min(vals), max(vals)
    pad = (vmax - vmin) * CONFIG.greek_y_padding if vmax != vmin else 1
    
    # Add height for X-axis if this is the bottom chart
    actual_height = height + (XAXIS_HEIGHT if show_xaxis else 0)
    
    p = figure(
        x_axis_type='datetime',
        x_range=x_range,
        y_range=Range1d(vmin - pad, vmax + pad, bounds=(vmin - pad, vmax + pad)),
        height=actual_height,
        tools='',
        background_fill_color=COLORS['bg'],
        min_border_left=MIN_BORDER_LEFT,
        min_border_right=MIN_BORDER_RIGHT,
        min_border_top=3,
        min_border_bottom=3 if not show_xaxis else 25,
        title=None,
        sizing_mode='stretch_width',
    )
    
    # Tools
    wheel_zoom = WheelZoomTool(maintain_focus=False)
    pan = PanTool()
    p.add_tools(wheel_zoom, pan)
    p.toolbar.active_scroll = wheel_zoom
    
    # Styling
    p.grid.grid_line_alpha = CONFIG.grid_alpha
    p.outline_line_color = None
    p.toolbar_location = None
    
    # Серые оси
    p.xaxis.axis_line_color = '#CCCCCC'
    p.xaxis.major_tick_line_color = '#CCCCCC'
    p.xaxis.minor_tick_line_color = '#CCCCCC'
    
    # ==================== LEFT Y AXIS (JUST LINE) ====================
    # Включаем ось, но скрываем все метки, оставляя только линию для визуального "квадрата" слева
    p.yaxis.visible = True
    p.yaxis.axis_line_color = '#CCCCCC'
    p.yaxis.major_tick_line_color = None
    p.yaxis.minor_tick_line_color = None
    p.yaxis.major_label_text_font_size = '0pt'
    p.yaxis.major_label_text_color = None
    p.yaxis.axis_label = None
    
    # ==================== RIGHT Y AXIS (GREY, SPARSE TICKS) ====================
    right_axis = LinearAxis(
        axis_label=label,
        axis_label_text_color='#888888',  # Серый
        axis_label_text_font_style='bold',
        axis_label_text_font_size='8pt',
        major_label_text_color='#888888',  # Серый
        major_label_text_font_size='7pt',
        axis_line_color='#CCCCCC',
        major_tick_line_color='#CCCCCC',
        minor_tick_line_color='#CCCCCC',
    )
    
    # Меньше тиков (3) и короче черточки
    right_axis.major_tick_in = 2
    right_axis.major_tick_out = 2
    right_axis.ticker = BasicTicker(desired_num_ticks=3)
    
    # Number formatting based on greek type
    if key == 'gamma':
        right_axis.formatter = NumeralTickFormatter(format='0.0000')
    elif key == 'delta':
        right_axis.formatter = NumeralTickFormatter(format='0.00')
    elif key == 'iv':
        right_axis.formatter = NumeralTickFormatter(format='0')
    elif key in ['theta', 'vega']:
        right_axis.formatter = NumeralTickFormatter(format='0')
    
    p.add_layout(right_axis, 'right')
    
    # ==================== AREA + LINE ====================
    # Заливка области к нулю (varea)
    p.varea(x='timestamp', y1='value', y2=0, source=src, fill_color=color, fill_alpha=0.2)
    
    # Линия сверху для четкости
    p.line('timestamp', 'value', source=src, color=color, line_width=2.5)
    
    # ==================== PRICE LINE (STICKY LABEL) ====================
    last_value = vals[-1]
    price_line = Span(
        location=last_value,
        dimension='width',
        line_color=color,
        line_dash='dotted',
        line_width=1.5,
    )
    p.add_layout(price_line)
    
    # STICKY LABEL - справа (привязан к видимому краю)
    price_label = Label(
        x=x_range.end if hasattr(x_range, 'end') else src.data['timestamp'][-1],
        y=last_value,
        text=format_greek_value(key, last_value),
        text_font_size='8pt',
        text_color='#888888',
        text_font_style='normal',
        text_align='right',
        x_offset=-5,
        y_offset=2,
    )
    p.add_layout(price_label)
    
    # JS callback для sticky label
    sticky_label_cb = CustomJS(args=dict(
        label=price_label, 
        x_range=x_range
    ), code="""
        label.x = x_range.end;
    """)
    x_range.js_on_change('start', sticky_label_cb)
    x_range.js_on_change('end', sticky_label_cb)
    
    # ==================== X-AXIS ====================
    # В Dedicated Axis архитектуре оси на греках всегда скрыты
    p.xaxis.visible = False
    
    return p, price_line, price_label
# ============================================================================
# AUTO-SCALE Y AXIS - Unified JavaScript callback for Y auto-scaling
# ============================================================================
def create_autoscale_js(
    y_range_obj: Range1d,
    x_range_obj: Range1d,
    src: ColumnDataSource,
    value_fields: List[str],
    padding: float = 0.10
) -> CustomJS:
    """
    Universal auto-scale callback for Y axis.
    
    Args:
        y_range_obj: Range1d object to update (y_range or extra_y_ranges['spot'])
        x_range_obj: X range for filtering visible data
        src: ColumnDataSource with data
        value_fields: Field names to use for min/max (e.g., ['high', 'low'] or ['value'])
        padding: Padding ratio for Y range (uses CONFIG if not specified)
    
    Returns:
        CustomJS callback
    """
    fields_js = ', '.join([f"'{f}'" for f in value_fields])
    
    return CustomJS(args=dict(
        y_range=y_range_obj,
        x_range=x_range_obj,
        src=src,
        padding=padding
    ), code=f"""
        const data = src.data;
        const timestamps = data.timestamp;
        const fields = [{fields_js}];
        
        const x_start = x_range.start;
        const x_end = x_range.end;
        
        let min_val = Infinity;
        let max_val = -Infinity;
        
        for (let i = 0; i < timestamps.length; i++) {{
            const t = timestamps[i];
            if (t >= x_start && t <= x_end) {{
                for (let field of fields) {{
                    const v = data[field][i];
                    if (v < min_val) min_val = v;
                    if (v > max_val) max_val = v;
                }}
            }}
        }}
        
        if (min_val !== Infinity && max_val !== -Infinity) {{
            const pad = (max_val - min_val) * padding;
            y_range.start = min_val - pad;
            y_range.end = max_val + pad;
        }}
    """)
# Legacy wrappers for backward compatibility
def create_autoscale_js_ohlc(plot, src) -> CustomJS:
    """Auto-scale for OHLC using high/low values."""
    return create_autoscale_js(
        plot.y_range, plot.x_range, src,
        value_fields=['high', 'low'],
        padding=CONFIG.autoscale_padding
    )
def create_autoscale_js_spot(plot, src) -> CustomJS:
    """Auto-scale for spot (extra_y_ranges)."""
    return create_autoscale_js(
        plot.extra_y_ranges['spot'], plot.x_range, src,
        value_fields=['value'],
        padding=CONFIG.spot_y_padding
    )
def create_autoscale_js_greek(plot, src) -> CustomJS:
    """Auto-scale for greek values."""
    return create_autoscale_js(
        plot.y_range, plot.x_range, src,
        value_fields=['value'],
        padding=CONFIG.greek_y_padding
    )
# ============================================================================
# DYNAMIC LEGEND SYNC - JavaScript для обновления легенды при наведении
# ============================================================================
# ============================================================================
# DYNAMIC LEGEND SYNC - JavaScript для обновления легенды при наведении
# ============================================================================
def create_legend_sync_js(legend_div, src_ohlc, src_spot, src_greeks, all_spans, toggles, panel_style):
    """
    Creates JS callback to update legend on hover.
    ONLY SHOWS VALUES FOR ACTIVE GREEKS.
    """
    callback = CustomJS(args=dict(
        legend_div=legend_div,
        src_ohlc=src_ohlc,
        src_spot=src_spot,
        src_iv=src_greeks['iv'],
        src_theta=src_greeks['theta'],
        src_delta=src_greeks['delta'],
        src_gamma=src_greeks['gamma'],
        src_vega=src_greeks['vega'],
        spans=all_spans,
        toggles=toggles,
        colors=COLORS,
        panel_style=panel_style
    ), code="""
        const geometry = cb_data.geometry;
        const x = geometry.x;
        
        // Save coordinates for external updates (e.g. toggles)
        legend_div.tags = [x];
        
        // Sync crosshair spans & hide spans for inactive plots
        // Assumes order: [main, greek1, greek2..., greek5, axis]
        // Greeks start at index 1.
        for (let i = 0; i < spans.length; i++) {
            const span = spans[i];
            span.location = x;
            
            // Logic for visibility:
            // - Main span (0) always visible
            // - Axis span (last) always visible (or hidden logic separately)
            // - Greeks (1..5) depend on toggles (0..4)
            
            if (i === 0) {
                span.visible = true;
            } else if (i > 0 && i <= toggles.length) {
                // Determine if this greek chart is active
                const toggleIdx = i - 1;
                span.visible = toggles[toggleIdx].active;
            }
        }
        
        // Find nearest data point
        const timestamps = src_ohlc.data.timestamp;
        let minDist = Infinity;
        let idx = 0;
        
        for (let i = 0; i < timestamps.length; i++) {
            const dist = Math.abs(timestamps[i] - x);
            if (dist < minDist) {
                minDist = dist;
                idx = i;
            }
        }
        
        // Get values
        const o = src_ohlc.data.open[idx].toFixed(2);
        const h = src_ohlc.data.high[idx].toFixed(2);
        const l = src_ohlc.data.low[idx].toFixed(2);
        const c = src_ohlc.data.close[idx].toFixed(2);
        const spot = src_spot.data.value[idx].toFixed(0);
        
        const iv = src_iv.data.value[idx].toFixed(2);
        const theta = src_theta.data.value[idx].toFixed(2);
        const delta = src_delta.data.value[idx].toFixed(4);
        const gamma = src_gamma.data.value[idx].toFixed(6);
        const vega = src_vega.data.value[idx].toFixed(2);
        
        // Check toggle states
        const showIV = toggles[0].active ? 'inline' : 'none';
        const showTheta = toggles[1].active ? 'inline' : 'none';
        const showDelta = toggles[2].active ? 'inline' : 'none';
        const showGamma = toggles[3].active ? 'inline' : 'none';
        const showVega = toggles[4].active ? 'inline' : 'none';
        
        // Format date
        const dateObj = new Date(timestamps[idx]);
        const dateStr = dateObj.toLocaleDateString('en-US', { 
            day: '2-digit', 
            month: 'short', 
            year: 'numeric' 
        });
        
        // Update legend HTML
        legend_div.text = `
            <div style="${panel_style}">
                <span style="color:#666; font-weight: 500;">${dateStr}</span>
                <span style="color:${colors.call}; font-weight: 600;">O:${o} H:${h} L:${l} C:${c}</span>
                <span style="color:${colors.spot};">Spot: $${spot}</span>
                
                <span id="legend-iv-val" style="color:${colors.iv}; display:${showIV};">IV:${iv}%</span>
                <span id="legend-theta-val" style="color:${colors.theta}; display:${showTheta};">Θ:$${theta}</span>
                <span id="legend-delta-val" style="color:${colors.delta}; display:${showDelta};">Δ:${delta}</span>
                <span id="legend-gamma-val" style="color:${colors.gamma}; display:${showGamma};">Γ:${gamma}</span>
                <span id="legend-vega-val" style="color:${colors.vega}; display:${showVega};">ν:$${vega}</span>
            </div>
        `;
    """)
    return callback
def create_mouseleave_js(all_spans):
    """Hide crosshair spans when mouse leaves."""
    return CustomJS(args=dict(spans=all_spans), code="""
        for (let span of spans) {
            span.visible = false;
        }
    """)
# ============================================================================
# TOGGLE CALLBACKS - Динамическое управление layout
# ============================================================================
def create_toggle_js(toggles, greek_plots, main_plot, legend_div, src_ohlc, src_spot, src_greeks, base_total_height: int = 700, fixed_overhead: int = 155):
    """
    JavaScript for dynamic layout rebuild on toggle.
    Uses height=0 to hide plots (visible doesn't work in Bokeh layout).
    """
    xaxis_height = CONFIG.xaxis_height
    
    # Подготовка аргументов для JS
    args = dict(
        toggles=toggles,
        greek_plots=greek_plots,
        main_plot=main_plot,
        legend_div=legend_div,
        src_ohlc=src_ohlc,
        src_spot=src_spot,
        src_iv=src_greeks['iv'],
        src_theta=src_greeks['theta'],
        src_delta=src_greeks['delta'],
        src_gamma=src_greeks['gamma'],
        src_vega=src_greeks['vega'],
        colors=COLORS,
        panel_style=PANEL_STYLE
    )
    
    js_code = f"""
        // Calculate available height based on window size
        const overhead = {fixed_overhead};
        const TOTAL_HEIGHT = Math.max(window.innerHeight - overhead, 400);
        // Ось времени (AxisPlot) живет отдельно снизу и мы её не трогаем.
        
        // Count active greeks
        let activeCount = 0;
        const activeIndices = [];
        for (let i = 0; i < toggles.length; i++) {{
            if (toggles[i].active) {{
                activeCount++;
                activeIndices.push(i);
            }}
        }}
        
        // Расчёт высот (как раньше)
        let greekArea = 0;
        for (let i = 0; i < activeCount; i++) {{
            greekArea += 0.25 / Math.pow(2, i);
        }}
        
        const CONTENT_HEIGHT = TOTAL_HEIGHT; // Вся высота - контент
        let mainHeight, greekHeight;
        
        if (activeCount === 0) {{
            // Только Main
            mainHeight = TOTAL_HEIGHT;
            greekHeight = 0;
        }} else {{
            // Main + Greeks
            mainHeight = Math.round(CONTENT_HEIGHT * (1 - greekArea));
            const totalGreekHeight = CONTENT_HEIGHT - mainHeight;
            greekHeight = Math.round(totalGreekHeight / activeCount);
        }}
        
        const lastActiveIdx = activeIndices.length > 0 ? activeIndices[activeIndices.length - 1] : -1;
        
        // === ПРИМЕНЯЕМ ВЫСОТЫ ===
        
        function setRightYAxisVisible(plot, show) {{
            if (plot.right && plot.right.length > 0) {{
                const axis = plot.right[0];
                const alpha = show ? 1.0 : 0.0;
                axis.visible = show;
                axis.axis_line_alpha = alpha;
                axis.major_tick_line_alpha = alpha;
                axis.minor_tick_line_alpha = alpha;
                axis.major_label_text_alpha = alpha;
                axis.axis_label_text_alpha = alpha;
            }}
        }}
        
        // Main plot
        main_plot.height = mainHeight;
        main_plot.min_border_bottom = 0; // ZERO gaps
        // (Ось X у main всегда скрыта, тут не трогаем)
        
        // Greek plots
        // (Оси скрыты)
        
        for (let i = 0; i < greek_plots.length; i++) {{
            const isActive = toggles[i].active;
            
            if (isActive) {{
                greek_plots[i].visible = true;
                greek_plots[i].height = greekHeight;
                greek_plots[i].min_border_bottom = 0; // ZERO gaps
                greek_plots[i].min_border_top = 0;    // ZERO gaps
                greek_plots[i].min_border_right = 50;
                setRightYAxisVisible(greek_plots[i], true);
            }} else {{
                greek_plots[i].visible = false;
                greek_plots[i].height = 0;
                greek_plots[i].min_border_bottom = 0;
                greek_plots[i].min_border_top = 0;
                greek_plots[i].min_border_right = 0;
                setRightYAxisVisible(greek_plots[i], false);
            }}
        }}
        
        // === FORCE LEGEND UPDATE (FROM LAST MOUSE POSITION) ===
        if (legend_div.tags && legend_div.tags.length > 0) {{
            const x = legend_div.tags[0];
            
            // Find nearest data point
            const timestamps = src_ohlc.data.timestamp;
            let minDist = Infinity;
            let idx = 0;
            for (let i = 0; i < timestamps.length; i++) {{
                const dist = Math.abs(timestamps[i] - x);
                if (dist < minDist) {{
                    minDist = dist;
                    idx = i;
                }}
            }}
            
            // Get values
            const o = src_ohlc.data.open[idx].toFixed(2);
            const h = src_ohlc.data.high[idx].toFixed(2);
            const l = src_ohlc.data.low[idx].toFixed(2);
            const c = src_ohlc.data.close[idx].toFixed(2);
            const spot = src_spot.data.value[idx].toFixed(0);
            
            const iv = src_iv.data.value[idx].toFixed(2);
            const theta = src_theta.data.value[idx].toFixed(2);
            const delta = src_delta.data.value[idx].toFixed(4);
            const gamma = src_gamma.data.value[idx].toFixed(6);
            const vega = src_vega.data.value[idx].toFixed(2);
            
            // Check toggle states
            const showIV = toggles[0].active ? 'inline' : 'none';
            const showTheta = toggles[1].active ? 'inline' : 'none';
            const showDelta = toggles[2].active ? 'inline' : 'none';
            const showGamma = toggles[3].active ? 'inline' : 'none';
            const showVega = toggles[4].active ? 'inline' : 'none';
            
            // Format date
            const dateObj = new Date(timestamps[idx]);
            const dateStr = dateObj.toLocaleDateString('en-US', {{ 
                day: '2-digit', 
                month: 'short', 
                year: 'numeric' 
            }});
            
            // Update legend HTML
            legend_div.text = `
                <div style="${{panel_style}}">
                    <span style="color:#666; font-weight: 500;">${{dateStr}}</span>
                    <span style="color:${{colors.call}}; font-weight: 600;">O:${{o}} H:${{h}} L:${{l}} C:${{c}}</span>
                    <span style="color:${{colors.spot}};">Spot: ${{spot}}</span>
                    
                    <span id="legend-iv-val" style="color:${{colors.iv}}; display:${{showIV}};">IV:${{iv}}%</span>
                    <span id="legend-theta-val" style="color:${{colors.theta}}; display:${{showTheta}};">Θ:${{theta}}</span>
                    <span id="legend-delta-val" style="color:${{colors.delta}}; display:${{showDelta}};">Δ:${{delta}}</span>
                    <span id="legend-gamma-val" style="color:${{colors.gamma}}; display:${{showGamma}};">Γ:${{gamma}}</span>
                    <span id="legend-vega-val" style="color:${{colors.vega}}; display:${{showVega}};">ν:${{vega}}</span>
                </div>
            `;
        }}
    """
    
    callbacks = []
    for toggle in toggles:
        callback = CustomJS(args=args, code=js_code)
        callbacks.append(callback)
    
    return callbacks

def create_controls_update_js(controls_div, toggles, colors, panel_style):
    """
    Creates JS callback to update custom HTML controls when toggles change.
    """
    return CustomJS(args=dict(toggles=toggles, div=controls_div, colors=colors, symbols=GREEK_SYMBOLS, panel_style=panel_style), code="""
        const keys = ['iv', 'theta', 'delta', 'gamma', 'vega'];
        
        let html = `<div style="${panel_style}">`;
        
        // Global handler for clicks
        if (!window.toggleGreek) {
            window.toggleGreek = function(id) {
                // Try to find model in document
                let toggle = null;
                if (Bokeh.documents && Bokeh.documents.length > 0) {
                     toggle = Bokeh.documents[0].get_model_by_id(id);
                }
                
                if (toggle) {
                    toggle.active = !toggle.active;
                } else {
                    console.error("Toggle not found:", id);
                }
            }
        }

        for (let i = 0; i < toggles.length; i++) {
            const t = toggles[i];
            const key = keys[i];
            const color = colors[key];
            const active = t.active;
            
            const border = active ? `1px solid ${color}` : "1px solid #ced4da";
            const textColor = active ? color : "#7F8C8D";
            const bg = "rgba(255,255,255,0.8)";
            const sym = symbols[key];
            
            const btnStyle = `
                padding: 0 8px;
                height: 22px;
                border-radius: 3px;
                font-size: 10px;
                border: ${border};
                color: ${textColor};
                background-color: ${bg};
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                cursor: pointer;
                display: flex;
                align-items: center;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                transition: all 0.2s;
                outline: none;
                line-height: 1;
            `;
            
            const onclick = `window.toggleGreek('${t.id}')`;
            
            html += `
            <button type="button" style="${btnStyle}" onclick="${onclick}">
                <span style="font-size: 9px; opacity: 0.9; font-weight: 700;">${sym} ${key.toUpperCase()}</span>
            </button>
            `;
        }
        html += '</div>';
        div.text = html;
    """)
# ============================================================================
# MAIN - CREATE FULL CHART
# ============================================================================
def create_strike_chart_from_dataframes(df_ohlc, df_spot, df_greeks):
    """
    Создание полного Strike Chart из DataFrame согласно спецификации.
    
    Args:
        df_ohlc: DataFrame с timestamp, open, high, low, close
        df_spot: DataFrame с timestamp, value
        df_greeks: Dict[str, DataFrame] с timestamp, value для каждого грека
    
    Returns:
        Bokeh layout
    """
    
    t0 = time.time()
    
    # ==================== CONVERT TO SOURCES ====================
    src_ohlc, src_spot, src_greeks = dataframes_to_sources(df_ohlc, df_spot, df_greeks)
    
    # ==================== CALCULATE HEIGHTS ====================
    n_active = len(GREEKS)
    main_h, greek_h = calc_heights(n_active, total=700)
    
    # Явно задаем диапазон X и ОГРАНИЧИВАЕМ его (bounds), чтобы нельзя было утащить график в пустоту
    x_min = min(src_ohlc.data['timestamp'])
    x_max = max(src_ohlc.data['timestamp'])
    x_pad = (x_max - x_min) * 0.02
    
    # bounds=(start, end) запрещает pan/zoom за пределы данных
    initial_x_range = Range1d(
        start=x_min - x_pad, 
        end=x_max + x_pad, 
        bounds=(x_min - x_pad, x_max + x_pad)
    )
    
    p_main, main_option_label, main_spot_label = create_main_chart(
        src_ohlc, src_spot, main_h, x_range=initial_x_range
    )
    p_main.min_border_bottom = 0 # ZERO gaps override
    
    # ==================== GREEK CHARTS ====================
    greek_plots = []
    greek_price_lines = []  # Store price lines for visibility management
    greek_price_labels = []  # Store price labels for visibility management
    
    for i, key in enumerate(GREEKS):
        p, price_line, price_label = create_greek_chart(
            src_greeks[key], key,
            x_range=p_main.x_range,
            height=greek_h,
            show_xaxis=False # Всегда False, ось будет отдельной
        )
        p.min_border_top = 0    # ZERO gaps
        p.min_border_bottom = 0 # ZERO gaps
        greek_plots.append(p)
        greek_price_lines.append(price_line)
        greek_price_labels.append(price_label)
    
    # ==================== DEDICATED AXIS PLOT ====================
    # Создаем статичную ось в самом низу (теперь передаем source для масштаба)
    axis_plot = create_integrated_axis_plot(p_main.x_range, CONFIG, COLORS, src_ohlc)
    
    # ==================== ALL PLOTS LIST ====================
    all_plots = [p_main] + greek_plots + [axis_plot]
    
    # ==================== TOGGLE BUTTONS ====================
    toggles = []
    for i, key in enumerate(GREEKS):
        t = Toggle(
            label=f'{GREEK_SYMBOLS[key]} {key.upper()}',
            active=True,
            button_type='success',
            width=85,
            height=32,
        )
        toggles.append(t)
    # ==================== SYNCHRONIZED CROSSHAIR ====================
    all_spans = create_sync_crosshair_spans(all_plots)
    
    # ==================== DYNAMIC LEGEND ====================
    # ==================== DYNAMIC LEGEND ====================
    legend_display = Div(
        text=f'''
        <div style="{PANEL_STYLE}">
            <span style="color:{COLORS['call']}; font-weight: 600;">
            <span style="color:{COLORS['call']}; font-weight: 600;">
                O:{src_ohlc.data['close'][-1]:.2f}
                H:{max(src_ohlc.data['high']):.2f}
                L:{min(src_ohlc.data['low']):.2f}
                C:{src_ohlc.data['close'][-1]:.2f}
            </span>
            <span style="color:{COLORS['spot']};">
                Spot: ${src_spot.data['value'][-1]:.0f}
            </span>
            <span style="color:{COLORS['iv']};">IV:--</span>
            <span style="color:{COLORS['theta']};">Θ:--</span>
            <span style="color:{COLORS['delta']};">Δ:--</span>
            <span style="color:{COLORS['gamma']};">Γ:--</span>
            <span style="color:{COLORS['vega']};">ν:--</span>
        </div>
        ''',
        sizing_mode='stretch_width',
    )
    
    # Legend sync callback attached to main chart hover
    legend_sync_cb = create_legend_sync_js(
        legend_display, src_ohlc, src_spot, src_greeks, all_spans, toggles, PANEL_STYLE
    )
    mouseleave_cb = create_mouseleave_js(all_spans)
    
    # Add hover tool with sync callback to all plots
    for p in all_plots:
        hover = HoverTool(
            tooltips=None,
            mode='vline',
            callback=legend_sync_cb
        )
        p.add_tools(hover)
        p.js_on_event('mouseleave', mouseleave_cb)
    
    # ==================== AUTO-SCALE Y ====================
    # OHLC auto-scale (using high/low)
    main_autoscale = create_autoscale_js_ohlc(p_main, src_ohlc)
    p_main.x_range.js_on_change('start', main_autoscale)
    p_main.x_range.js_on_change('end', main_autoscale)
    
    # Spot auto-scale
    spot_autoscale = create_autoscale_js_spot(p_main, src_spot)
    p_main.x_range.js_on_change('start', spot_autoscale)
    p_main.x_range.js_on_change('end', spot_autoscale)
    
    # Greeks auto-scale
    for i, key in enumerate(GREEKS):
        autoscale = create_autoscale_js_greek(greek_plots[i], src_greeks[key])
        greek_plots[i].x_range.js_on_change('start', autoscale)
        greek_plots[i].x_range.js_on_change('end', autoscale)
    
    # ==================== TOGGLE BUTTONS DONE ABOVE ====================
    # (Toggles are created earlier to be used in legend callback)
    pass
    
    # NEW: Unified Layout Manager
    # Fixed overhead for header (approx 50) + controls (approx 50) + padding
    fixed_overhead = 140 
    layout_cb = get_layout_manager_js(
        main_plot=p_main,
        greek_plots=greek_plots,
        toggles=toggles,
        status_div=None,
        fixed_overhead=fixed_overhead,
        axis_height=25
    )
    
    # Toggle logic for layout + LEGEND update
    toggle_cbs = create_toggle_js(
        toggles, greek_plots, p_main,
        legend_display, src_ohlc, src_spot, src_greeks,
        base_total_height=700, # Explicitly pass base height
        fixed_overhead=fixed_overhead
    )
    
    for i, toggle in enumerate(toggles):
        # 1. Layout manager (heights) + Legend update & visibility
        toggle.js_on_change('active', toggle_cbs[i])
    
    # ==================== RENDER TIME ====================
    render_ms = (time.time() - t0) * 1000
    
    # ==================== HEADER ====================
    header = Div(text=f'''
        <div style="
            display: flex;
            align-items: center;
            gap: 20px;
            padding: 10px 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            border-bottom: 1px solid #eee;
            margin-bottom: 5px;
        ">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="
                    font-size: 18px;
                    font-weight: 700;
                    color: {COLORS['text']};
                ">
                    BTC $55,000 CALL
                </span>
                <span style="
                    font-size: 12px;
                    color: #888;
                    background: #f5f5f5;
                    padding: 2px 8px;
                    border-radius: 4px;
                ">
                    31 Aug 2024
                </span>
            </div>
            <div style="
                font-size: 11px;
                color: #999;
                margin-left: auto;
            ">
                Render: {render_ms:.0f}ms | Bokeh Strike Chart v7.0
            </div>
        </div>
    ''', sizing_mode='stretch_width')
    
    # ==================== CONTROLS ROW (CUSTOM HTML) ====================
    # 1. Callback для обновления HTML при изменении Toggles
    # Убираем sizing_mode='stretch_width', чтобы он не занимал всю ширину
    controls_div = Div(text="", height=40) 
    
    update_controls_js = create_controls_update_js(controls_div, toggles, COLORS, PANEL_STYLE)
    
    # 2. Привязываем callback ко всем toggles
    for t in toggles:
        t.js_on_change('active', update_controls_js)
        
    # 3. Генерируем начальный HTML (Python side) USING UNIFIED STYLE
    initial_html = f'<div style="{PANEL_STYLE}">'
    for i, key in enumerate(GREEKS):
        t = toggles[i]
        # Начальное состояние - active=True
        color = COLORS[key]
        border = f"1px solid {color}"
        text_color = color
        
        btn_style = f"""
            padding: 0 8px;
            height: 22px;
            border-radius: 3px;
            font-size: 10px;
            border: {border};
            color: {text_color};
            background-color: rgba(255,255,255,0.8);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            cursor: pointer;
            display: flex;
            align-items: center;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            transition: all 0.2s;
            outline: none;
            line-height: 1;
        """
        
        # Inject script for global helper if needed (handled in JS above but need initial onclick)
        onclick = f"window.toggleGreek('{t.id}')"
        
        initial_html += f"""
        <button type="button" style="{btn_style}" onclick="{onclick}">
            <span style="font-size: 9px; opacity: 0.9; font-weight: 700;">{GREEK_SYMBOLS[key]} {key.upper()}</span>
        </button>
        """
    initial_html += '</div>'
    
    # Добавляем скрипт инициализации глобальной функции
    initial_html += """
    <script>
        if (!window.toggleGreek) {
            window.toggleGreek = function(id) {
                if (Bokeh.documents && Bokeh.documents.length > 0) {
                     const toggle = Bokeh.documents[0].get_model_by_id(id);
                     if (toggle) toggle.active = !toggle.active;
                }
            }
        }
    </script>
    """
    
    controls_div.text = initial_html
    
    # Скрытый ряд для реальных моделей Toggle (чтобы они были в документе)
    hidden_toggles = row(toggles, visible=False)
    
    # ==================== ASSEMBLE LAYOUT ====================
    all_charts = finalize_layout(p_main, greek_plots, axis_plot)
    
    # Гарантируем видимость оси в финальном объекте
    axis_plot.xaxis.visible = True
    axis_plot.min_border_bottom = 25
    
    # Панель управления и легенды в одну строку
    # Используем row() для размещения их рядом
    control_panel = row(
        controls_div, 
        Spacer(width=20), 
        legend_display, 
        sizing_mode='stretch_width'
    )
    
    layout = column(
        header,
        control_panel,          # Buttons + Legend in one row
        all_charts,
        hidden_toggles,         # Invisible logic models
        sizing_mode='stretch_both'
    )
    
    print(f'✅ Chart created in {render_ms:.0f}ms')
    print(f'   Main: {main_h}px, Greeks: {greek_h}px each (x{n_active})')
    print(f'   Total points: {len(src_ohlc.data["timestamp"])}')
    
    return layout
def create_strike_chart():
    """Create chart with synthetic data (backward compatible)."""
    df_ohlc, df_spot, df_greeks = generate_dataframes(n_points=200)
    return create_strike_chart_from_dataframes(df_ohlc, df_spot, df_greeks)
# ============================================================================
# RUN
# ============================================================================
if __name__ == '__main__':
    from bokeh.resources import CDN
    from bokeh.embed import file_html
    
    print('=' * 60)
    print('🚀 Bokeh Strike Chart v7.0 - REFACTORED')
    print('=' * 60)
    print()
    print('Features:')
    print('  ✓ Synchronized Crosshair (real sync via Span)')
    print('  ✓ Dynamic Legends with DATE (live update on hover)')
    print('  ✓ Auto-scaling Y axes (unified function)')
    print('  ✓ Dynamic Height Toggle (spec formula)')
    print('  ✓ Price Lines with Labels on ALL charts')
    print('  ✓ Correct candle colors (close vs open)')
    print('  ✓ Full-screen responsive layout')
    print('  ✓ DataFrame input with validation')
    print('  ✓ Unified constants (Python = JavaScript)')
    print('  ✓ Exact Colors per Specification')
    print()
    
    layout = create_strike_chart()
    
    # Generate with custom template for full-screen
    html = file_html(layout, CDN, title='BTC $55K CALL Strike Chart - Bokeh v7.0')
    
    # Inject full-screen CSS and reactive Init Script
    html = html.replace(
        '</head>',
        '''<style>
            html, body {
                margin: 0;
                padding: 0;
                width: 100vw;
                height: 100vh;
                overflow: hidden;
                background: #FFFFFF;
            }
            .bk-root {
                height: 100vh !important;
                width: 100vw !important;
            }
            
            /* Улучшенные стили для кнопок Toggle */
            .bk-root .bk-btn {
                opacity: 0.6; /* Бледные по умолчанию */
                transition: all 0.2s ease;
                border: 1px solid transparent;
            }
            .bk-root .bk-btn.bk-active {
                opacity: 1 !important; /* Яркие когда нажаты */
                box-shadow: inset 0 3px 5px rgba(0,0,0,0.2) !important; /* Эффект "утопленности" */
                transform: translateY(1px);
                font-weight: bold;
                border: 1px solid rgba(0,0,0,0.1);
            }
            .bk-root .bk-btn:hover {
                opacity: 0.8;
            }
            .bk-root .bk-btn.bk-active:hover {
                opacity: 1;
            }
        </style>
        <script>
            // Автоматическая подстройка под размер окна при загрузке
            (function() {
                function triggerResize() {
                    const doc = Bokeh.documents[0];
                    if (!doc) return;
                    // Находим любой Toggle, чтобы вызвать его коллбэк пересчета высот
                    const models = doc._all_models;
                    for (const [id, model] of models) {
                        if (model.type === 'Toggle') {
                            model.properties.active.change.emit();
                            console.log('Layout initialized via toggle:', id);
                            return true;
                        }
                    }
                    return false;
                }
                
                function init() {
                    setTimeout(() => {
                        if (!triggerResize()) setTimeout(init, 100);
                    }, 200);
                }
                
                window.addEventListener('resize', triggerResize);
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', init);
                } else {
                    init();
                }
            })();
        </script>
        </head>'''
    )
    
    import os
    output_path = os.path.join(os.path.dirname(__file__), 'test_bokeh_strike_chart.html')
    with open(output_path, 'w') as f:
        f.write(html)
    
    print(f'📄 Output: {output_path}')
    print()
    print('Opening in browser...')
    
    import webbrowser
    webbrowser.open(f'file://{os.path.abspath(output_path)}')