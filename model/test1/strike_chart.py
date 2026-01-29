"""
ФАЙЛ: strike_chart.py
ОПИСАНИЕ: Strike Chart - свечной график опциона с греками.
          Полная реализация с toggle кнопками, crosshair sync, auto-scale Y.

ЗАВИСИМОСТИ: 
    - bokeh_workarounds.py (должен быть в той же папке)
    - bokeh_components.py (должен быть в той же папке)

ТЕСТ: python strike_chart.py → откроется браузер с тестовым графиком

ЧЕКЛИСТ ПРОВЕРКИ:
[ ] Toggle кнопки IV/Theta/Delta/Gamma/Vega работают
[ ] При отключении грека - высоты пересчитываются  
[ ] Crosshair синхронизирован на всех графиках
[ ] Y-axis автомасштабируется при zoom X
[ ] Свечи правильного цвета (зелёные вверх, красные вниз)
[ ] Легенда обновляется при наведении
[ ] Price lines отображаются на всех графиках
[ ] Ось X только внизу (общая для всех)
"""

import pandas as pd
import numpy as np
from datetime import datetime
import time
from typing import Dict, List, Tuple, Optional, Any

from bokeh.plotting import figure
from bokeh.models import (
    ColumnDataSource, HoverTool, Span, Range1d, LinearAxis, 
    Label, Div, BasicTicker, NumeralTickFormatter, DatetimeTickFormatter,
    CustomJS, WheelZoomTool, PanTool, ResetTool
)
from bokeh.layouts import column, row, Spacer
from bokeh.embed import file_html
from bokeh.resources import CDN

# Импорт наших модулей
from bokeh_workarounds import (
    CrosshairSync, AutoScaleY, StickyLabel, LayoutFixer,
    SharedAxisPlot, Candlestick, SmartBounds, WindowResize, SafeModelAccess
)
from bokeh_components import (
    ChartTheme, GreekConfig, ChartConfig, CONFIG,
    HeightCalculator, TogglePanel, ToggleCallbackBuilder,
    HoverSyncBuilder, PlotFactory, UIFactory
)


# ============================================================================
# ГЕНЕРАЦИЯ ТЕСТОВЫХ ДАННЫХ
# ============================================================================

def generate_test_data(n_points: int = 200):
    """
    Генерирует синтетические данные для тестирования.
    
    Returns:
        df_ohlc: DataFrame с OHLC данными опциона
        df_spot: DataFrame с ценой базового актива
        df_greeks: Dict[str, DataFrame] с греками
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
    
    # DataFrames
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
    
    # Греки
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


# ============================================================================
# КОНВЕРТАЦИЯ ДАННЫХ В COLUMNDATASOURCE
# ============================================================================

def dataframes_to_sources(
    df_ohlc: pd.DataFrame,
    df_spot: pd.DataFrame,
    df_greeks: Dict[str, pd.DataFrame]
) -> Tuple[ColumnDataSource, ColumnDataSource, Dict[str, ColumnDataSource]]:
    """
    Конвертирует DataFrame в ColumnDataSource с форматированными значениями.
    
    Args:
        df_ohlc: OHLC данные с timestamp, open, high, low, close
        df_spot: Spot данные с timestamp, value
        df_greeks: Dict DataFrame с timestamp, value для каждого грека
    
    Returns:
        Tuple of (src_ohlc, src_spot, src_greeks dict)
    """
    # Цвет свечей: зелёный если close >= open, красный если close < open
    colors = [
        ChartTheme.CANDLE_UP if df_ohlc['close'].iloc[i] >= df_ohlc['open'].iloc[i] 
        else ChartTheme.CANDLE_DOWN
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
# СОЗДАНИЕ ГЛАВНОГО ГРАФИКА (СВЕЧИ + СПОТ)
# ============================================================================

def create_main_chart(
    src_ohlc: ColumnDataSource,
    src_spot: ColumnDataSource,
    height: int,
    x_range: Range1d = None
) -> Tuple[Any, Label, Label]:
    """
    Создаёт главный график со свечами и спотом.
    
    Args:
        src_ohlc: ColumnDataSource для OHLC
        src_spot: ColumnDataSource для спота
        height: высота графика
        x_range: общий X range или None
        
    Returns:
        Tuple (figure, option_label, spot_label)
    """
    # Y-range для OHLC
    lo = min(src_ohlc.data['low'])
    hi = max(src_ohlc.data['high'])
    pad = (hi - lo) * CONFIG.ohlc_y_padding
    
    y_range = Range1d(lo - pad, hi + pad, bounds=(lo - pad, hi + pad))
    
    # Создаём figure
    p = PlotFactory.create_main_figure(height, x_range)
    p.y_range = y_range
    
    # ==================== CANDLESTICKS ====================
    Candlestick.render(p, src_ohlc, CONFIG.candle_width_ratio)
    
    # ==================== SPOT LINE (Y2) ====================
    smin, smax = min(src_spot.data['value']), max(src_spot.data['value'])
    spad = (smax - smin) * CONFIG.spot_y_padding
    p.extra_y_ranges = {
        'spot': Range1d(smin - spad, smax + spad, bounds=(smin - spad, smax + spad))
    }
    
    # Правая ось для спота
    spot_axis = LinearAxis(y_range_name='spot', axis_label='Spot $')
    spot_axis.axis_label_text_color = ChartTheme.TEXT_SECONDARY
    spot_axis.major_label_text_color = ChartTheme.TEXT_SECONDARY
    spot_axis.major_label_text_font_size = '7pt'
    spot_axis.axis_label_text_font_size = '8pt'
    spot_axis.axis_label_text_font_style = 'bold'
    spot_axis.axis_line_color = ChartTheme.AXIS
    spot_axis.major_tick_line_color = ChartTheme.AXIS
    spot_axis.minor_tick_line_color = ChartTheme.AXIS
    spot_axis.major_tick_in = 2
    spot_axis.major_tick_out = 2
    spot_axis.ticker = BasicTicker(desired_num_ticks=4)
    p.add_layout(spot_axis, 'right')
    
    # Линия спота
    p.line(
        'timestamp', 'value', source=src_spot,
        color=ChartTheme.SPOT, line_width=1.5, line_dash='dashed',
        y_range_name='spot'
    )
    
    # ==================== PRICE LINES ====================
    last_close = src_ohlc.data['close'][-1]
    last_spot = src_spot.data['value'][-1]
    
    # Price Line для опциона
    option_price_line = Span(
        location=last_close, dimension='width',
        line_color=ChartTheme.CANDLE_UP, line_dash='dotted', line_width=1.5
    )
    p.add_layout(option_price_line)
    
    # Price Line для спота
    spot_price_line = Span(
        location=last_spot, dimension='width',
        line_color=ChartTheme.SPOT, line_dash='dotted', line_width=1,
        y_range_name='spot'
    )
    p.add_layout(spot_price_line)
    
    # ==================== STICKY LABELS ====================
    option_label, _ = StickyLabel.create_right(
        p, last_close, f'{last_close:.2f}', ChartTheme.TEXT_SECONDARY
    )
    
    spot_label, _ = StickyLabel.create_left(
        p, last_spot, f'{last_spot:.0f}', ChartTheme.TEXT_SECONDARY, y_range_name='spot'
    )
    
    # ==================== Y-AXIS STYLING ====================
    p.yaxis[0].axis_label = 'Option Price ($)'
    p.yaxis[0].axis_label_text_color = ChartTheme.TEXT_SECONDARY
    p.yaxis[0].major_label_text_color = ChartTheme.TEXT_SECONDARY
    p.yaxis[0].major_label_text_font_size = '7pt'
    p.yaxis[0].axis_label_text_font_size = '8pt'
    p.yaxis[0].axis_label_text_font_style = 'bold'
    p.yaxis[0].axis_line_color = ChartTheme.AXIS
    p.yaxis[0].major_tick_line_color = ChartTheme.AXIS
    p.yaxis[0].minor_tick_line_color = None
    p.yaxis[0].major_tick_in = 2
    p.yaxis[0].major_tick_out = 2
    p.yaxis[0].ticker = BasicTicker(desired_num_ticks=5)
    
    return p, option_label, spot_label


# ============================================================================
# СОЗДАНИЕ ГРАФИКА ГРЕКА
# ============================================================================

def create_greek_chart(
    src: ColumnDataSource,
    key: str,
    x_range: Range1d,
    height: int
) -> Tuple[Any, Span, Label]:
    """
    Создаёт график для одного грека.
    
    Args:
        src: ColumnDataSource с timestamp и value
        key: ключ грека (iv, theta, delta, gamma, vega)
        x_range: общий X range
        height: высота графика
        
    Returns:
        Tuple (figure, price_line, price_label)
    """
    color = ChartTheme.get_greek_color(key)
    
    vals = src.data['value']
    vmin, vmax = min(vals), max(vals)
    pad = (vmax - vmin) * CONFIG.greek_y_padding if vmax != vmin else 1
    
    y_range = Range1d(vmin - pad, vmax + pad, bounds=(vmin - pad, vmax + pad))
    
    # Создаём figure
    p = PlotFactory.create_greek_figure(key, x_range, y_range, height)
    
    # ==================== AREA + LINE ====================
    # Заливка области к нулю
    p.varea(x='timestamp', y1='value', y2=0, source=src, fill_color=color, fill_alpha=ChartTheme.AREA_FILL_ALPHA)
    
    # Линия сверху
    p.line('timestamp', 'value', source=src, color=color, line_width=2.5)
    
    # ==================== PRICE LINE ====================
    last_value = vals[-1]
    price_line = Span(
        location=last_value,
        dimension='width',
        line_color=color,
        line_dash='dotted',
        line_width=1.5,
    )
    p.add_layout(price_line)
    
    # ==================== STICKY LABEL ====================
    price_label, _ = StickyLabel.create_right(
        p, last_value, GreekConfig.format_value(key, last_value), ChartTheme.TEXT_SECONDARY
    )
    
    return p, price_line, price_label


# ============================================================================
# ГЛАВНАЯ ФУНКЦИЯ СОЗДАНИЯ ГРАФИКА
# ============================================================================

def create_strike_chart(
    df_ohlc: pd.DataFrame,
    df_spot: pd.DataFrame,
    df_greeks: Dict[str, pd.DataFrame],
    title: str = "BTC $55,000 CALL",
    expiry: str = "31 Aug 2024"
) -> str:
    """
    Создаёт полный Strike Chart и возвращает HTML.
    
    Args:
        df_ohlc: DataFrame с OHLC данными
        df_spot: DataFrame со спотом
        df_greeks: Dict с DataFrame для каждого грека
        title: заголовок графика
        expiry: дата экспирации
        
    Returns:
        HTML строка
    """
    t0 = time.time()
    
    # ==================== CONVERT TO SOURCES ====================
    src_ohlc, src_spot, src_greeks = dataframes_to_sources(df_ohlc, df_spot, df_greeks)
    
    # ==================== CALCULATE HEIGHTS ====================
    n_active = len(GreekConfig.KEYS)
    # Увеличиваем базовую высоту для случаев без ресайза
    main_h, greek_h = HeightCalculator.calculate(n_active, total_height=800)
    
    # ==================== X RANGE ====================
    x_min = min(src_ohlc.data['timestamp'])
    x_max = max(src_ohlc.data['timestamp'])
    # Без padding, чтобы края данных совпадали с осями
    initial_x_range = SmartBounds.create_x_range(x_min, x_max, padding=0)
    
    # ==================== MAIN CHART ====================
    p_main, main_option_label, main_spot_label = create_main_chart(
        src_ohlc, src_spot, main_h, x_range=initial_x_range
    )
    p_main.min_border_bottom = 0
    
    # ==================== GREEK CHARTS ====================
    greek_plots = []
    greek_price_lines = []
    greek_price_labels = []
    
    for key in GreekConfig.KEYS:
        p, price_line, price_label = create_greek_chart(
            src_greeks[key], key,
            x_range=p_main.x_range,
            height=greek_h
        )
        p.min_border_top = 0
        p.min_border_bottom = 0
        greek_plots.append(p)
        greek_price_lines.append(price_line)
        greek_price_labels.append(price_label)
    
    # ==================== AXIS PLOT ====================
    # Используем функцию интегратор из оригинала для создания X-оси
    axis_plot = create_integrated_axis_plot(
        p_main.x_range, CONFIG, ChartTheme.GREEKS, src_ohlc
    )
    
    # ==================== ALL PLOTS ====================
    all_plots = [p_main] + greek_plots + [axis_plot]
    
    # ==================== TOGGLE BUTTONS ====================
    toggles = TogglePanel.create_toggles()
    
    # ==================== CROSSHAIR SYNC ====================
    all_spans = CrosshairSync.create_spans(all_plots, color=ChartTheme.CROSSHAIR)
    
    # ==================== DYNAMIC LEGEND ====================
    legend_div = Div(
        text=f'''
        <div style="{ChartTheme.PANEL_STYLE}">
            <span style="color:{ChartTheme.CANDLE_UP}; font-weight: 700; font-size: 12px; font-variant-numeric: tabular-nums;">
                O:{src_ohlc.data['close'][-1]:.2f}
                H:{max(src_ohlc.data['high']):.2f}
                L:{min(src_ohlc.data['low']):.2f}
                C:{src_ohlc.data['close'][-1]:.2f}
            </span>
            <span style="color:{ChartTheme.SPOT}; font-weight: 700; font-size: 12px; font-variant-numeric: tabular-nums;">
                Spot: ${src_spot.data['value'][-1]:.0f}
            </span>
            <span style="color:{ChartTheme.GREEKS['iv']}; font-weight: 600; font-variant-numeric: tabular-nums;">IV:--</span>
            <span style="color:{ChartTheme.GREEKS['theta']}; font-weight: 600; font-variant-numeric: tabular-nums;">Θ:--</span>
            <span style="color:{ChartTheme.GREEKS['delta']}; font-weight: 600; font-variant-numeric: tabular-nums;">Δ:--</span>
            <span style="color:{ChartTheme.GREEKS['gamma']}; font-weight: 600; font-variant-numeric: tabular-nums;">Γ:--</span>
            <span style="color:{ChartTheme.GREEKS['vega']}; font-weight: 600; font-variant-numeric: tabular-nums;">ν:--</span>
        </div>
        ''',
        sizing_mode='stretch_width',
    )
    
    # ==================== HOVER SYNC CALLBACK ====================
    hover_sync_cb = HoverSyncBuilder.build(
        legend_div, src_ohlc, src_spot, src_greeks, all_spans, toggles
    )
    mouseleave_cb = CrosshairSync.create_hide_callback(all_spans)
    
    # Добавляем hover tool на все графики
    for p in all_plots:
        hover = HoverTool(tooltips=None, mode='vline', callback=hover_sync_cb)
        p.add_tools(hover)
        p.js_on_event('mouseleave', mouseleave_cb)
    
    # ==================== AUTO-SCALE Y ====================
    # OHLC
    AutoScaleY.attach_to_plot(p_main, src_ohlc, ['high', 'low'], CONFIG.autoscale_padding)
    
    # Spot
    AutoScaleY.attach_to_extra_y_range(p_main, 'spot', src_spot, ['value'], CONFIG.spot_y_padding)
    
    # Greeks
    for i, key in enumerate(GreekConfig.KEYS):
        AutoScaleY.attach_to_plot(greek_plots[i], src_greeks[key], ['value'], CONFIG.greek_y_padding)
    
    # ==================== TOGGLE CALLBACKS ====================
    # Панель управления (HTML кнопки)
    controls_div = TogglePanel.create_html_controls(toggles)
    
    # Используем интегрированную логику высот
    # Уменьшаем overhead т.к. заголовок удален (остались только кнопки)
    fixed_overhead = 55 
    axis_h = 25
    layout_cb = get_layout_manager_js(
        p_main, greek_plots, toggles, None, fixed_overhead, axis_h
    )
    
    # Реакция кнопок
    for i, toggle in enumerate(toggles):
        toggle.js_on_change('active', layout_cb)
        # Также обновляем HTML вид кнопок
        toggle.js_on_change('active', TogglePanel.create_update_callback(controls_div, toggles))
    
    # ==================== RENDER TIME ====================
    render_ms = (time.time() - t0) * 1000
    
    # ==================== HEADER ====================
    # ==================== HEADER ====================
    # Заголовок удален по требованию
    header = Div(text="", sizing_mode='stretch_width', height=0)
    
    # ==================== LAYOUT ====================
    # Используем функцию интегратор для сборки стопки графиков
    chart_stack = finalize_layout(p_main, greek_plots, axis_plot)
    
    # Панель управления
    control_panel = row(
        controls_div,
        Spacer(width=20),
        legend_div,
        sizing_mode='stretch_width'
    )
    
    # Скрытые toggle модели
    hidden_toggles = row(toggles, visible=False)
    
    # Финальный layout
    layout = column(
        header,
        control_panel,
        chart_stack,
        hidden_toggles,
        sizing_mode='stretch_both'
    )
    
    # ==================== GENERATE HTML ====================
    html = file_html(layout, CDN, title=f'{title} - Strike Chart')
    
    # Inject responsive CSS и init script
    responsive_css = LayoutFixer.get_responsive_html_wrapper()
    init_script = WindowResize.get_init_script()
    
    # Дополнительные стили для кнопок
    extra_styles = '''
    <style>
        .bk-root .bk-btn {
            opacity: 0.6;
            transition: all 0.2s ease;
            border: 1px solid transparent;
        }
        .bk-root .bk-btn.bk-active {
            opacity: 1 !important;
            box-shadow: inset 0 3px 5px rgba(0,0,0,0.2) !important;
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
    '''
    
    style_block = f"<style>{UIFactory.HEADER_CSS}</style>"
    html = html.replace('</head>', f'{style_block}{responsive_css}{extra_styles}{init_script}</head>')
    
    print(f'✅ Chart created in {render_ms:.0f}ms')
    print(f'   Main: {main_h}px, Greeks: {greek_h}px each (x{n_active})')
    print(f'   Total points: {len(src_ohlc.data["timestamp"])}')
    
    return html


# ============================================================================
# КЛАСС-ОБЁРТКА ДЛЯ ИНТЕГРАЦИИ
# ============================================================================

class StrikeChart:
    """
    Класс для создания Strike Chart.
    Удобен для интеграции в Dash.
    
    Использование:
        chart = StrikeChart(df_ohlc, df_spot, df_greeks)
        html = chart.to_html()
        
        # Для Dash:
        # html.Iframe(srcDoc=chart.to_html(), style={'width': '100%', 'height': '100%'})
    """
    
    def __init__(
        self,
        df_ohlc: pd.DataFrame,
        df_spot: pd.DataFrame,
        df_greeks: Dict[str, pd.DataFrame],
        title: str = "BTC $55,000 CALL",
        expiry: str = "31 Aug 2024"
    ):
        """
        Args:
            df_ohlc: DataFrame с timestamp, open, high, low, close
            df_spot: DataFrame с timestamp, value
            df_greeks: Dict[str, DataFrame] с timestamp, value для каждого грека
            title: заголовок графика
            expiry: дата экспирации
        """
        self.df_ohlc = df_ohlc
        self.df_spot = df_spot
        self.df_greeks = df_greeks
        self.title = title
        self.expiry = expiry
    
    def to_html(self) -> str:
        """Генерирует HTML."""
        return create_strike_chart(
            self.df_ohlc,
            self.df_spot,
            self.df_greeks,
            self.title,
            self.expiry
        )
    
    def save(self, filepath: str):
        """Сохраняет в файл."""
        html = self.to_html()
        with open(filepath, 'w') as f:
            f.write(html)
        print(f'📄 Saved to {filepath}')
    
    def show(self):
        """Открывает в браузере."""
        import webbrowser
        import tempfile
        import os
        
        html = self.to_html()
        
        # Сохраняем во временный файл
        fd, path = tempfile.mkstemp(suffix='.html')
        with os.fdopen(fd, 'w') as f:
            f.write(html)
        
        webbrowser.open(f'file://{path}')
        print(f'🌐 Opened in browser: {path}')


# ============================================================================
# STANDALONE TEST
# ============================================================================

# ============================================================================
# STRIKES LAYOUT INTEGRATOR (Код из оригинала)
# ============================================================================

def create_integrated_axis_plot(shared_x_range, config, colors, source):
    """
    Создает статичный график оси времени, стилизованный под основной проект.
    """
    axis_h = 25 
    p = figure(
        height=axis_h, sizing_mode='stretch_width', x_axis_type='datetime',
        x_range=shared_x_range,
        min_border_left=config.min_border_left,
        min_border_right=config.min_border_right,
        min_border_top=0, min_border_bottom=axis_h,
        tools='', toolbar_location=None, outline_line_color=None,
        background_fill_alpha=0, border_fill_alpha=0
    )
    p.line('timestamp', 'close', source=source, alpha=0, line_width=0)
    p.yaxis.visible = True
    p.yaxis.axis_line_color = '#CCCCCC'
    p.yaxis.major_tick_line_color = None
    p.yaxis.minor_tick_line_color = None
    p.yaxis.major_label_text_font_size = '0pt'
    p.yaxis.major_label_text_color = None
    p.xgrid.visible = False
    p.ygrid.visible = False
    p.xaxis.axis_line_color = '#CCCCCC'
    p.xaxis.major_tick_line_color = '#CCCCCC'
    p.xaxis.major_label_text_color = '#888888'
    p.xaxis.major_label_text_font_size = '7pt'
    p.xaxis.major_tick_in = 2
    p.xaxis.major_tick_out = 2
    p.xaxis.formatter = DatetimeTickFormatter(days='%d %b', months='%b %Y')
    p.margin = 0
    return p

def get_layout_manager_js(main_plot, greek_plots, toggles, status_div, fixed_overhead, axis_height):
    """
    JS-коллбэк для управления высотами.
    """
    return CustomJS(
        args=dict(
            main_plot=main_plot, greek_plots=greek_plots, toggles=toggles,
            status_div=status_div, FIXED_H=fixed_overhead, AXIS_H=axis_height
        ),
        code="""
        const totalH = window.innerHeight - FIXED_H - AXIS_H;
        const activeIdxs = [];
        for (let i = 0; i < toggles.length; i++) {
            if (toggles[i].active) activeIdxs.push(i);
        }
        const count = activeIdxs.length;
        let greekPct = 0;
        for (let i = 0; i < count; i++) {
            greekPct += 0.25 / Math.pow(2, i);
        }
        let mainH = (count === 0) ? totalH : Math.floor(totalH * (1 - greekPct));
        main_plot.height = mainH;
        main_plot.change.emit();
        let remH = totalH - mainH;
        for (let i = 0; i < greek_plots.length; i++) {
            const p = greek_plots[i];
            const pos = activeIdxs.indexOf(i);
            if (pos === -1) {
                p.height = 0;
            } else {
                if (pos === count - 1) {
                    p.height = remH;
                } else {
                    const h = Math.floor(remH / (count - pos));
                    p.height = h;
                    remH -= h;
                }
            }
            p.change.emit();
        }
        """
    )

def finalize_layout(main_plot, greek_plots, axis_plot, other_components=None):
    """
    Собирает финальный stack и обнуляет отступы.
    """
    all_plots = [main_plot] + list(greek_plots) + [axis_plot]
    chart_stack = column(*all_plots, sizing_mode='stretch_both', spacing=0)
    for p in all_plots:
        p.margin = 0
        p.min_border_bottom = 0
        p.min_border_top = 0
        if p != axis_plot:
            p.xaxis.visible = False
        else:
            p.xaxis.visible = True
            # Технический прием: нижний отступ равен высоте, а верхний 0 
            # Это заставляет саму ось подняться на стык с графиком выше
            p.min_border_bottom = p.height
    chart_stack.margin = 0
    return chart_stack


if __name__ == '__main__':
    print('=' * 60)
    print('🚀 Strike Chart - Standalone Test')
    print('=' * 60)
    print()
    print('Генерация тестовых данных...')
    
    # Генерируем тестовые данные
    df_ohlc, df_spot, df_greeks = generate_test_data(n_points=200)
    
    print(f'   OHLC: {len(df_ohlc)} points')
    print(f'   Spot: {len(df_spot)} points')
    print(f'   Greeks: {list(df_greeks.keys())}')
    print()
    
    # Создаём график
    chart = StrikeChart(
        df_ohlc=df_ohlc,
        df_spot=df_spot,
        df_greeks=df_greeks,
        title="BTC $55,000 CALL",
        expiry="31 Aug 2024"
    )
    
    # Сохраняем и открываем
    output_path = 'test_strike_chart_output.html'
    chart.save(output_path)
    
    print()
    print('ЧЕКЛИСТ ПРОВЕРКИ:')
    print('[ ] Toggle кнопки IV/Theta/Delta/Gamma/Vega работают')
    print('[ ] При отключении грека - высоты пересчитываются')
    print('[ ] Crosshair синхронизирован на всех графиках')
    print('[ ] Y-axis автомасштабируется при zoom X')
    print('[ ] Свечи правильного цвета (зелёные вверх, красные вниз)')
    print('[ ] Легенда обновляется при наведении')
    print('[ ] Price lines отображаются на всех графиках')
    print('[ ] Ось X только внизу (общая для всех)')
    print()
    
    # Открываем в браузере
    import webbrowser
    import os
    webbrowser.open(f'file://{os.path.abspath(output_path)}')
    
    print('✅ График открыт в браузере')
