# План Рефакторинга Графиков для Panel

**Версия:** 2.0  
**Дата:** 2026-02-04  
**Автор:** AI Assistant  
**Срок выполнения:** 5 рабочих дней  
**Git ветка:** `feature/panel-charts-refactor`

---

## 🎯 Цель

Адаптировать графики из `model/test1` для нативной интеграции в Panel-приложение (`model_panel`), сохранив 100% визуального дизайна.

---

## 📐 Архитектурное Решение (ФИНАЛЬНОЕ)

| График | Библиотека | Источник | Интеграция в Panel |
|--------|-----------|----------|-------------------|
| **Strike Chart** | Bokeh | `test1/strike_chart.py` | `pn.pane.Bokeh(figure)` |
| **Smile Chart** | Plotly | `test1/smile_chart.py` → Plotly | `pn.pane.Plotly(fig)` |
| **Surface 3D** | Plotly | `test1/surface_chart.py` | `pn.pane.Plotly(fig)` |

**Обоснование:**
- Strike Chart имеет сложную Bokeh-логику (свечи, crosshair sync, autoscale) → оставляем Bokeh
- Smile Chart в Panel уже на Plotly → сохраняем Plotly, добавляем toggle
- Surface 3D - Plotly единственный вариант для 3D → Plotly

---

## 📁 Целевая Структура Файлов

```
model/test1/
├── REFACTORING_PLAN.md          # Этот документ
├── panel_constants.py           # ← НОВЫЙ: единый источник констант
├── bokeh_utils.py               # ← НОВЫЙ: очищенные workarounds
├── strike_chart_provider.py     # ← НОВЫЙ: провайдер для Panel
├── smile_chart_provider.py      # ← НОВЫЙ: провайдер для Panel
├── surface_chart_provider.py    # ← НОВЫЙ: провайдер для Panel
├── test_providers.py            # ← НОВЫЙ: автотесты
│
├── strike_chart.py              # Оригинал (не трогаем)
├── smile_chart.py               # Оригинал (не трогаем)
├── surface_chart.py             # Оригинал (не трогаем)
├── bokeh_components.py          # Оригинал (не трогаем)
└── bokeh_workarounds.py         # Оригинал (не трогаем)
```

**Принцип:** Оригиналы НЕ ТРОГАЕМ. Создаём новые файлы-провайдеры.

---

## 📅 ДЕНЬ 1: Фундамент

### Задача 1.1: Создать `panel_constants.py`

**Файл:** `model/test1/panel_constants.py`

**Содержимое:**
```python
"""
Единый источник констант для Panel-интеграции.
Извлечено из bokeh_components.py
"""

# =============================================================================
# ЦВЕТА
# =============================================================================
COLORS = {
    # Свечи
    'call': '#76D7C4',
    'put': '#FF8787',
    
    # Греки
    'iv': '#9B59B6',
    'theta': '#E67E22',
    'delta': '#3498DB',
    'gamma': '#F1C40F',
    'vega': '#1ABC9C',
    
    # UI
    'spot': '#969696',
    'bg': '#FFFFFF',
    'text': '#333333',
    'grid': '#E0E0E0',
    'axis': '#CCCCCC',
    'crosshair': '#546E7A',
}

# =============================================================================
# ГРЕКИ
# =============================================================================
GREEK_ORDER = ['iv', 'theta', 'delta', 'gamma', 'vega']

GREEK_CONFIG = {
    'iv': {
        'symbol': 'IV',
        'label': 'IV (%)',
        'format': '0.0',
        'value_format': '{:.1f}%',
        'color': '#9B59B6'
    },
    'theta': {
        'symbol': 'Θ',
        'label': 'Theta ($)',
        'format': '0.00',
        'value_format': '${:.2f}',
        'color': '#E67E22'
    },
    'delta': {
        'symbol': 'Δ',
        'label': 'Delta',
        'format': '0.00',
        'value_format': '{:.4f}',
        'color': '#3498DB'
    },
    'gamma': {
        'symbol': 'Γ',
        'label': 'Gamma',
        'format': '0.0000',
        'value_format': '{:.6f}',
        'color': '#F1C40F'
    },
    'vega': {
        'symbol': 'ν',
        'label': 'Vega ($)',
        'format': '0.0',
        'value_format': '${:.2f}',
        'color': '#1ABC9C'
    },
}

# =============================================================================
# РАЗМЕРЫ
# =============================================================================
CHART_CONFIG = {
    'min_border_left': 50,
    'min_border_right': 50,
    'min_border_top': 15,
    'min_border_bottom': 30,
    'grid_alpha': 0.3,
    'line_width': 2.0,
    'candle_width_ratio': 0.6,
    'autoscale_padding': 0.10,
}

# =============================================================================
# ХЕЛПЕРЫ
# =============================================================================
def get_greek_color(key: str) -> str:
    return GREEK_CONFIG.get(key, {}).get('color', COLORS['text'])

def format_greek_value(key: str, value: float) -> str:
    fmt = GREEK_CONFIG.get(key, {}).get('value_format', '{:.2f}')
    return fmt.format(value)
```

**Критерий успеха:**
```python
from panel_constants import COLORS, GREEK_CONFIG
assert COLORS['iv'] == '#9B59B6'
assert GREEK_CONFIG['theta']['symbol'] == 'Θ'
```

---

### Задача 1.2: Создать `bokeh_utils.py`

**Файл:** `model/test1/bokeh_utils.py`

**Содержимое:** Очищенные workarounds (только нужные для Panel)

```python
"""
Утилиты Bokeh для Panel-интеграции.
Очищено от HTML/JS костылей.
"""

from bokeh.models import CustomJS, Span, Range1d, Label, ColumnDataSource
from bokeh.plotting import figure

# =============================================================================
# CROSSHAIR SYNC
# =============================================================================
class CrosshairSync:
    """Синхронизация crosshair между графиками."""
    
    @staticmethod
    def create_spans(plots, color='#546E7A', line_width=1):
        spans = []
        for p in plots:
            span = Span(
                location=0, dimension='height',
                line_color=color, line_width=line_width,
                line_alpha=0.7, visible=False
            )
            p.add_layout(span)
            spans.append(span)
        return spans
    
    @staticmethod
    def create_move_callback(spans):
        return CustomJS(args=dict(spans=spans), code="""
            const x = cb_data.geometry.x;
            for (let span of spans) {
                span.location = x;
                span.visible = true;
            }
        """)
    
    @staticmethod
    def create_hide_callback(spans):
        return CustomJS(args=dict(spans=spans), code="""
            for (let span of spans) { span.visible = false; }
        """)

# =============================================================================
# AUTOSCALE Y
# =============================================================================
class AutoScaleY:
    """Автомасштабирование Y при pan/zoom X."""
    
    @staticmethod
    def attach(plot, source, y_fields, padding=0.10):
        fields_js = ', '.join([f"'{f}'" for f in y_fields])
        callback = CustomJS(args=dict(
            y_range=plot.y_range, x_range=plot.x_range,
            src=source, padding=padding
        ), code=f"""
            const data = src.data;
            const ts = data.timestamp;
            const fields = [{fields_js}];
            let min_v = Infinity, max_v = -Infinity;
            for (let i = 0; i < ts.length; i++) {{
                if (ts[i] >= x_range.start && ts[i] <= x_range.end) {{
                    for (let f of fields) {{
                        const v = data[f][i];
                        if (v < min_v) min_v = v;
                        if (v > max_v) max_v = v;
                    }}
                }}
            }}
            if (min_v !== Infinity) {{
                const pad = (max_v - min_v) * padding;
                y_range.start = min_v - pad;
                y_range.end = max_v + pad;
            }}
        """)
        plot.x_range.js_on_change('start', callback)
        plot.x_range.js_on_change('end', callback)

# =============================================================================
# STICKY LABEL
# =============================================================================
class StickyLabel:
    """Метка, привязанная к краю viewport."""
    
    @staticmethod
    def create_right(plot, y_value, text, color, y_range_name=None):
        kwargs = dict(
            x=plot.x_range.end, y=y_value,
            text=f" {text} ", text_font_size='10px',
            text_color=color, text_align='right',
            x_offset=-4, y_offset=-6,
            border_line_color=color, border_line_alpha=0.5,
            background_fill_color='#ffffff', background_fill_alpha=0.9,
        )
        if y_range_name:
            kwargs['y_range_name'] = y_range_name
        label = Label(**kwargs)
        plot.add_layout(label)
        callback = CustomJS(args=dict(label=label, xr=plot.x_range), 
                           code="label.x = xr.end;")
        plot.x_range.js_on_change('end', callback)
        return label
    
    @staticmethod
    def create_left(plot, y_value, text, color):
        label = Label(
            x=plot.x_range.start, y=y_value,
            text=f" {text} ", text_font_size='10px',
            text_color=color, text_align='left',
            x_offset=4, y_offset=-6,
            border_line_color=color, border_line_alpha=0.5,
            background_fill_color='#ffffff', background_fill_alpha=0.9,
        )
        plot.add_layout(label)
        callback = CustomJS(args=dict(label=label, xr=plot.x_range), 
                           code="label.x = xr.start;")
        plot.x_range.js_on_change('start', callback)
        return label

# =============================================================================
# CANDLESTICK
# =============================================================================
class Candlestick:
    """Рендеринг свечей."""
    DAY_MS = 24 * 60 * 60 * 1000
    
    @staticmethod
    def render(plot, source, width_ratio=0.6):
        width = width_ratio * Candlestick.DAY_MS
        plot.segment('timestamp', 'low', 'timestamp', 'high',
                    source=source, color='color', line_width=1)
        plot.vbar('timestamp', width, 'close', 'open',
                 source=source, fill_color='color', line_color='color')
```

**Критерий успеха:**
```python
from bokeh_utils import CrosshairSync, AutoScaleY, Candlestick
# Должно импортироваться без ошибок
```

---

## 📅 ДЕНЬ 2: Strike Chart Provider

### Задача 2.1: Создать `strike_chart_provider.py`

**Файл:** `model/test1/strike_chart_provider.py`

**Ключевые отличия от оригинала:**
1. Возвращает `bokeh.layouts.column`, а не HTML
2. Нет `file_html()`, нет CDN injection
3. Toggle через внешние callbacks (не внутри)

**Структура:**
```python
"""
Strike Chart Provider для Panel.
Возвращает Bokeh layout, не HTML.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Tuple, List, Any

from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, Range1d, Span, HoverTool
from bokeh.layouts import column

from panel_constants import COLORS, GREEK_ORDER, GREEK_CONFIG, CHART_CONFIG
from bokeh_utils import CrosshairSync, AutoScaleY, StickyLabel, Candlestick


class StrikeChartProvider:
    """
    Провайдер Strike Chart для Panel.
    
    Использование в Panel:
        provider = StrikeChartProvider(df_ohlc, df_spot, df_greeks)
        layout = provider.get_layout()
        pane = pn.pane.Bokeh(layout)
    """
    
    def __init__(
        self,
        df_ohlc: pd.DataFrame,
        df_spot: pd.DataFrame,
        df_greeks: Dict[str, pd.DataFrame],
        title: str = "BTC $55,000 CALL",
        visible_greeks: List[str] = None
    ):
        self.df_ohlc = df_ohlc
        self.df_spot = df_spot
        self.df_greeks = df_greeks
        self.title = title
        self.visible_greeks = visible_greeks or GREEK_ORDER.copy()
        
        # Создаём sources
        self._create_sources()
        
        # Создаём figures
        self._create_figures()
    
    def _create_sources(self):
        """Конвертация DataFrame в ColumnDataSource."""
        # Цвет свечей
        colors = [
            COLORS['call'] if self.df_ohlc['close'].iloc[i] >= self.df_ohlc['open'].iloc[i]
            else COLORS['put']
            for i in range(len(self.df_ohlc))
        ]
        
        self.src_ohlc = ColumnDataSource(dict(
            timestamp=self.df_ohlc['timestamp'].tolist(),
            open=self.df_ohlc['open'].tolist(),
            high=self.df_ohlc['high'].tolist(),
            low=self.df_ohlc['low'].tolist(),
            close=self.df_ohlc['close'].tolist(),
            color=colors,
        ))
        
        self.src_spot = ColumnDataSource(dict(
            timestamp=self.df_spot['timestamp'].tolist(),
            value=self.df_spot['value'].tolist(),
        ))
        
        self.src_greeks = {}
        for key, df in self.df_greeks.items():
            self.src_greeks[key] = ColumnDataSource(dict(
                timestamp=df['timestamp'].tolist(),
                value=df['value'].tolist(),
            ))
    
    def _create_figures(self):
        """Создание Bokeh figures."""
        cfg = CHART_CONFIG
        
        # X Range (shared)
        x_min = min(self.src_ohlc.data['timestamp'])
        x_max = max(self.src_ohlc.data['timestamp'])
        delta = (x_max - x_min) * 0.02
        self.x_range = Range1d(start=x_min - delta, end=x_max + delta)
        
        # Main figure (candles + spot)
        self.p_main = self._create_main_figure()
        
        # Greek figures
        self.greek_figures = {}
        for key in GREEK_ORDER:
            self.greek_figures[key] = self._create_greek_figure(key)
        
        # Crosshair sync
        all_plots = [self.p_main] + list(self.greek_figures.values())
        self.crosshair_spans = CrosshairSync.create_spans(all_plots)
        
        move_cb = CrosshairSync.create_move_callback(self.crosshair_spans)
        hide_cb = CrosshairSync.create_hide_callback(self.crosshair_spans)
        for p in all_plots:
            hover = HoverTool(tooltips=None, mode='vline', callback=move_cb)
            p.add_tools(hover)
            p.js_on_event('mouseleave', hide_cb)
    
    def _create_main_figure(self) -> figure:
        """Создание главного графика со свечами."""
        cfg = CHART_CONFIG
        
        lo = min(self.src_ohlc.data['low'])
        hi = max(self.src_ohlc.data['high'])
        pad = (hi - lo) * 0.12
        
        p = figure(
            x_axis_type='datetime',
            x_range=self.x_range,
            y_range=Range1d(lo - pad, hi + pad),
            height=400,
            sizing_mode='stretch_width',
            tools='pan,wheel_zoom,reset',
            toolbar_location=None,
            background_fill_color=COLORS['bg'],
            min_border_left=cfg['min_border_left'],
            min_border_right=cfg['min_border_right'],
        )
        
        # Свечи
        Candlestick.render(p, self.src_ohlc)
        
        # Автомасштабирование
        AutoScaleY.attach(p, self.src_ohlc, ['high', 'low'])
        
        # Price line
        last_close = self.src_ohlc.data['close'][-1]
        p.add_layout(Span(location=last_close, dimension='width',
                         line_color=COLORS['call'], line_dash='dotted'))
        StickyLabel.create_left(p, last_close, f'{last_close:.2f}', COLORS['text'])
        
        p.xaxis.visible = False
        p.grid.grid_line_alpha = cfg['grid_alpha']
        
        return p
    
    def _create_greek_figure(self, key: str) -> figure:
        """Создание графика грека."""
        cfg = CHART_CONFIG
        color = GREEK_CONFIG[key]['color']
        
        vals = self.src_greeks[key].data['value']
        vmin, vmax = min(vals), max(vals)
        pad = (vmax - vmin) * 0.15 if vmax != vmin else 1
        
        p = figure(
            x_axis_type='datetime',
            x_range=self.x_range,
            y_range=Range1d(vmin - pad, vmax + pad),
            height=100,
            sizing_mode='stretch_width',
            tools='',
            toolbar_location=None,
            background_fill_color=COLORS['bg'],
            min_border_left=cfg['min_border_left'],
            min_border_right=cfg['min_border_right'],
        )
        
        # Заливка + линия
        p.varea(x='timestamp', y1='value', y2=0, source=self.src_greeks[key],
               fill_color=color, fill_alpha=0.2)
        p.line('timestamp', 'value', source=self.src_greeks[key],
              color=color, line_width=2)
        
        # Price line
        last_val = vals[-1]
        p.add_layout(Span(location=last_val, dimension='width',
                         line_color=color, line_dash='dotted'))
        
        # Автомасштабирование
        AutoScaleY.attach(p, self.src_greeks[key], ['value'])
        
        # Стиль
        p.xaxis.visible = False
        p.yaxis.axis_label = GREEK_CONFIG[key]['label']
        p.yaxis.axis_label_text_color = color
        p.grid.grid_line_alpha = cfg['grid_alpha']
        
        return p
    
    def get_layout(self) -> column:
        """Возвращает Bokeh layout для Panel pane."""
        plots = [self.p_main]
        for key in GREEK_ORDER:
            if key in self.visible_greeks:
                self.greek_figures[key].visible = True
                self.greek_figures[key].height = 100
            else:
                self.greek_figures[key].visible = False
                self.greek_figures[key].height = 0
            plots.append(self.greek_figures[key])
        
        # Последний график показывает X axis
        for p in plots[:-1]:
            p.xaxis.visible = False
        plots[-1].xaxis.visible = True
        
        return column(*plots, sizing_mode='stretch_both')
    
    def set_visible_greeks(self, visible: List[str]):
        """Обновляет видимость греков (для Panel callbacks)."""
        self.visible_greeks = visible
    
    def get_sources(self) -> Dict[str, ColumnDataSource]:
        """Возвращает sources для обновления данных."""
        return {
            'ohlc': self.src_ohlc,
            'spot': self.src_spot,
            **{f'greek_{k}': v for k, v in self.src_greeks.items()}
        }


# =============================================================================
# ТЕСТ
# =============================================================================
def generate_test_data(n_points: int = 100):
    """Генерация тестовых данных."""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=n_points, freq='D')
    
    spot = 50000 + np.cumsum(np.random.normal(100, 400, n_points))
    iv = np.clip(60 + np.cumsum(np.random.normal(0, 1.2, n_points)), 30, 100)
    
    base_price = 100 + iv * 5 + np.random.normal(0, 20, n_points)
    opens, highs, lows, closes = [], [], [], []
    prev = base_price[0]
    for i in range(n_points):
        c = base_price[i]
        h = max(prev, c) + abs(np.random.normal(0, 10))
        l = min(prev, c) - abs(np.random.normal(0, 10))
        opens.append(prev)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        prev = c
    
    df_ohlc = pd.DataFrame({
        'timestamp': dates, 'open': opens, 'high': highs,
        'low': lows, 'close': closes
    })
    df_spot = pd.DataFrame({'timestamp': dates, 'value': spot.tolist()})
    df_greeks = {
        'iv': pd.DataFrame({'timestamp': dates, 'value': iv.tolist()}),
        'theta': pd.DataFrame({'timestamp': dates, 'value': (-25 - iv/8).tolist()}),
        'delta': pd.DataFrame({'timestamp': dates, 'value': np.clip(0.4 + 0.1*np.random.randn(n_points), 0, 1).tolist()}),
        'gamma': pd.DataFrame({'timestamp': dates, 'value': (0.001 + 0.0001*np.random.randn(n_points)).tolist()}),
        'vega': pd.DataFrame({'timestamp': dates, 'value': (80 + 10*np.random.randn(n_points)).tolist()}),
    }
    return df_ohlc, df_spot, df_greeks


if __name__ == '__main__':
    from bokeh.io import show
    
    print("Generating test data...")
    df_ohlc, df_spot, df_greeks = generate_test_data()
    
    print("Creating provider...")
    provider = StrikeChartProvider(df_ohlc, df_spot, df_greeks)
    
    print("Getting layout...")
    layout = provider.get_layout()
    
    print("Opening in browser...")
    show(layout)
```

**Критерий успеха:**
```bash
cd /Users/user/work/Python/derebit_download1/model/test1
source ../../.venv/bin/activate
python strike_chart_provider.py
# Должен открыться браузер с графиком без ошибок
```

---

## 📅 ДЕНЬ 3: Smile & Surface Providers

### Задача 3.1: Создать `smile_chart_provider.py`

**Файл:** `model/test1/smile_chart_provider.py`

```python
"""
Smile Chart Provider для Panel (Plotly).
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, List, Optional

from panel_constants import COLORS, GREEK_ORDER, GREEK_CONFIG


class SmileChartProvider:
    """
    Провайдер Smile Chart для Panel (Plotly).
    
    Использование в Panel:
        provider = SmileChartProvider(dte_data)
        fig = provider.get_figure()
        pane = pn.pane.Plotly(fig)
    """
    
    def __init__(
        self,
        dte_data: Dict[int, pd.DataFrame] = None,
        spot: float = 50000,
        visible_greeks: List[str] = None
    ):
        self.spot = spot
        self.visible_greeks = visible_greeks or ['iv']
        
        if dte_data is None:
            self.dte_data = self._generate_data()
        else:
            self.dte_data = dte_data
    
    def _generate_data(self) -> Dict[int, pd.DataFrame]:
        """Генерация тестовых данных."""
        from scipy.stats import norm
        
        dtes = [7, 30, 90]
        strikes = np.linspace(self.spot * 0.7, self.spot * 1.3, 25)
        moneyness = np.log(strikes / self.spot)
        
        result = {}
        for dte in dtes:
            T = dte / 365.0
            base_iv = 50 + 10 / np.sqrt(T + 0.1)
            iv = np.clip(base_iv + 40 * moneyness**2 - 8 * moneyness, 20, 150)
            
            sigma = iv / 100
            d1 = (np.log(self.spot / strikes) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
            
            result[dte] = pd.DataFrame({
                'strike': strikes,
                'iv': iv,
                'delta': norm.cdf(d1),
                'gamma': norm.pdf(d1) / (self.spot * sigma * np.sqrt(T)) * 10000,
                'theta': -(self.spot * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) / 365,
                'vega': self.spot * np.sqrt(T) * norm.pdf(d1) / 100,
            })
        
        return result
    
    def get_figure(self, greek_key: str = 'iv') -> go.Figure:
        """Возвращает Plotly figure для одного грека."""
        fig = go.Figure()
        
        color = GREEK_CONFIG[greek_key]['color']
        label = GREEK_CONFIG[greek_key]['label']
        
        # Разные оттенки для DTE
        dtes = sorted(self.dte_data.keys())
        for i, dte in enumerate(dtes):
            df = self.dte_data[dte]
            opacity = 1.0 - i * 0.2
            
            fig.add_trace(go.Scatter(
                x=df['strike'],
                y=df[greek_key],
                mode='lines+markers',
                name=f'{dte}D',
                line=dict(color=color, width=2),
                marker=dict(size=5),
                opacity=opacity
            ))
        
        # Spot line
        fig.add_vline(x=self.spot, line_dash='dash', line_color=COLORS['spot'],
                     annotation_text=f"Spot ${self.spot:,.0f}")
        
        fig.update_layout(
            title=f"Volatility Smile - {label}",
            xaxis_title="Strike",
            yaxis_title=label,
            template='plotly_white',
            legend=dict(orientation='h', yanchor='bottom', y=1.02),
            margin=dict(l=50, r=20, t=60, b=50),
        )
        
        return fig
    
    def get_grid_figures(self) -> Dict[str, go.Figure]:
        """Возвращает dict figures для всех видимых греков."""
        return {key: self.get_figure(key) for key in self.visible_greeks}


if __name__ == '__main__':
    print("Creating provider...")
    provider = SmileChartProvider()
    
    print("Getting figure...")
    fig = provider.get_figure('iv')
    
    print("Showing...")
    fig.show()
```

---

### Задача 3.2: Создать `surface_chart_provider.py`

**Файл:** `model/test1/surface_chart_provider.py`

```python
"""
Surface Chart Provider для Panel (Plotly 3D).
"""

import numpy as np
import plotly.graph_objects as go
from typing import Dict, Any, List

from panel_constants import COLORS, GREEK_ORDER, GREEK_CONFIG


class SurfaceChartProvider:
    """
    Провайдер 3D Surface Chart для Panel (Plotly).
    
    Использование в Panel:
        provider = SurfaceChartProvider()
        fig = provider.get_figure('iv')
        pane = pn.pane.Plotly(fig)
    """
    
    def __init__(
        self,
        data: Dict[str, Any] = None,
        spot: float = 50000,
        visible_greeks: List[str] = None
    ):
        self.spot = spot
        self.visible_greeks = visible_greeks or ['iv']
        self.data = data if data else self._generate_data()
    
    def _generate_data(self) -> Dict[str, Any]:
        """Генерация 3D поверхности."""
        import math
        
        n_strikes, n_dtes = 40, 15
        strikes = np.linspace(self.spot * 0.6, self.spot * 1.4, n_strikes)
        dtes = np.linspace(1, 120, n_dtes)
        
        S_mesh, T_mesh = np.meshgrid(strikes, dtes)
        T_years = T_mesh / 365.0
        
        moneyness = np.log(S_mesh / self.spot)
        iv = np.clip(50 + 60 * moneyness**2 + 5 / np.sqrt(T_years + 0.05), 15, 180)
        
        v = iv / 100.0
        sqrt_T = np.sqrt(np.maximum(T_years, 1e-10))
        d1 = (np.log(self.spot / S_mesh) + 0.5 * v**2 * T_years) / (v * sqrt_T)
        
        def norm_pdf(x): return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)
        def norm_cdf(x): return 0.5 * (1 + np.vectorize(math.erf)(x / np.sqrt(2)))
        
        return {
            'strikes': strikes.tolist(),
            'dtes': dtes.tolist(),
            'iv': iv.tolist(),
            'delta': norm_cdf(d1).tolist(),
            'gamma': (norm_pdf(d1) / (self.spot * v * sqrt_T) * 10000).tolist(),
            'theta': (-(self.spot * norm_pdf(d1) * v) / (2 * sqrt_T) / 365).tolist(),
            'vega': (self.spot * sqrt_T * norm_pdf(d1) / 100).tolist(),
        }
    
    def get_figure(self, greek_key: str = 'iv') -> go.Figure:
        """Возвращает Plotly 3D figure."""
        color = GREEK_CONFIG[greek_key]['color']
        label = GREEK_CONFIG[greek_key]['label']
        
        fig = go.Figure(data=[go.Surface(
            z=self.data[greek_key],
            x=self.data['strikes'],
            y=self.data['dtes'],
            colorscale=[[0, 'rgba(255,255,255,0.1)'], [1, color]],
            showscale=True,
            opacity=0.9,
            colorbar=dict(title=label)
        )])
        
        fig.update_layout(
            title=f"3D {label} Surface",
            scene=dict(
                xaxis_title='Strike',
                yaxis_title='DTE',
                zaxis_title=label,
                camera=dict(eye=dict(x=1.6, y=1.6, z=1.2))
            ),
            template='plotly_white',
            margin=dict(l=0, r=0, b=0, t=40),
        )
        
        return fig
    
    def get_grid_figures(self) -> Dict[str, go.Figure]:
        """Возвращает dict figures для всех видимых греков."""
        return {key: self.get_figure(key) for key in self.visible_greeks}


if __name__ == '__main__':
    print("Creating provider...")
    provider = SurfaceChartProvider()
    
    print("Getting figure...")
    fig = provider.get_figure('iv')
    
    print("Showing...")
    fig.show()
```

---

## 📅 ДЕНЬ 4: Автотесты

### Задача 4.1: Создать `test_providers.py`

**Файл:** `model/test1/test_providers.py`

```python
"""
Автотесты для провайдеров графиков.
"""

import pytest
import pandas as pd
import numpy as np


class TestPanelConstants:
    def test_colors_exist(self):
        from panel_constants import COLORS
        assert 'iv' in COLORS
        assert 'theta' in COLORS
        assert COLORS['iv'] == '#9B59B6'
    
    def test_greek_config(self):
        from panel_constants import GREEK_CONFIG, GREEK_ORDER
        assert len(GREEK_ORDER) == 5
        for key in GREEK_ORDER:
            assert key in GREEK_CONFIG
            assert 'symbol' in GREEK_CONFIG[key]
            assert 'color' in GREEK_CONFIG[key]


class TestBokehUtils:
    def test_imports(self):
        from bokeh_utils import CrosshairSync, AutoScaleY, Candlestick
        assert CrosshairSync is not None


class TestStrikeChartProvider:
    @pytest.fixture
    def test_data(self):
        from strike_chart_provider import generate_test_data
        return generate_test_data(n_points=50)
    
    def test_creation(self, test_data):
        from strike_chart_provider import StrikeChartProvider
        df_ohlc, df_spot, df_greeks = test_data
        provider = StrikeChartProvider(df_ohlc, df_spot, df_greeks)
        assert provider is not None
    
    def test_layout(self, test_data):
        from strike_chart_provider import StrikeChartProvider
        df_ohlc, df_spot, df_greeks = test_data
        provider = StrikeChartProvider(df_ohlc, df_spot, df_greeks)
        layout = provider.get_layout()
        assert layout is not None
        assert len(layout.children) == 6  # main + 5 greeks
    
    def test_sources(self, test_data):
        from strike_chart_provider import StrikeChartProvider
        df_ohlc, df_spot, df_greeks = test_data
        provider = StrikeChartProvider(df_ohlc, df_spot, df_greeks)
        sources = provider.get_sources()
        assert 'ohlc' in sources
        assert 'spot' in sources
        assert 'greek_iv' in sources


class TestSmileChartProvider:
    def test_creation(self):
        from smile_chart_provider import SmileChartProvider
        provider = SmileChartProvider()
        assert provider is not None
    
    def test_figure(self):
        from smile_chart_provider import SmileChartProvider
        provider = SmileChartProvider()
        fig = provider.get_figure('iv')
        assert fig is not None
        assert len(fig.data) >= 3  # 3 DTE lines


class TestSurfaceChartProvider:
    def test_creation(self):
        from surface_chart_provider import SurfaceChartProvider
        provider = SurfaceChartProvider()
        assert provider is not None
    
    def test_figure(self):
        from surface_chart_provider import SurfaceChartProvider
        provider = SurfaceChartProvider()
        fig = provider.get_figure('iv')
        assert fig is not None
        assert len(fig.data) == 1  # 1 surface


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
```

**Команда запуска:**
```bash
cd /Users/user/work/Python/derebit_download1/model/test1
source ../../.venv/bin/activate
pytest test_providers.py -v
```

---

## 📅 ДЕНЬ 5: Интеграция в Panel

### Задача 5.1: Обновить `model_panel/views/strike_view.py`

**Изменения:**
```python
# Добавить импорт
import sys
sys.path.insert(0, '/Users/user/work/Python/derebit_download1/model/test1')
from strike_chart_provider import StrikeChartProvider

# В методе _render_chart():
def _render_chart(self):
    # ... получение данных ...
    
    provider = StrikeChartProvider(
        df_ohlc=ohlc_df,
        df_spot=base_df,
        df_greeks=greeks_df,
        visible_greeks=self.state.visible_charts
    )
    
    layout = provider.get_layout()
    return pn.pane.Bokeh(layout, sizing_mode='stretch_both')
```

### Задача 5.2: Добавить Toggle виджеты

**В Panel view:**
```python
self.iv_toggle = pn.widgets.Toggle(value=True, name='IV', button_type='default')
self.theta_toggle = pn.widgets.Toggle(value=True, name='Θ', button_type='default')
# ... остальные

@param.depends('iv_toggle.value', watch=True)
def _update_visible_greeks(self):
    visible = []
    if self.iv_toggle.value: visible.append('iv')
    if self.theta_toggle.value: visible.append('theta')
    # ...
    self.state.visible_charts = visible
```

---

## ✅ Критерии Успеха

### Визуальные (ОБЯЗАТЕЛЬНО):
- [ ] Свечи зелёные (#76D7C4) вверх, красные (#FF8787) вниз
- [ ] Цвета греков: IV=#9B59B6, Θ=#E67E22, Δ=#3498DB, Γ=#F1C40F, ν=#1ABC9C
- [ ] Toggle кнопки переключают видимость
- [ ] Crosshair синхронизирован между графиками
- [ ] Y-axis автомасштабируется при pan/zoom X
- [ ] Price lines и sticky labels на месте

### Функциональные:
- [ ] `python strike_chart_provider.py` открывает браузер без ошибок
- [ ] `pytest test_providers.py` - все тесты зелёные
- [ ] `panel serve app.py` - графики отображаются

### Performance:
- [ ] Render time < 1000ms для Strike Chart
- [ ] Нет memory leaks при toggle

---

## 🔙 Rollback План

Если что-то пошло не так:

1. **Git restore:**
   ```bash
   git checkout main -- model_panel/views/strike_view.py
   ```

2. **Fallback на iframe:**
   ```python
   # В strike_view.py
   from model.test1.strike_chart import StrikeChart
   chart = StrikeChart(...)
   return pn.pane.HTML(f'<iframe srcdoc="{chart.to_html()}">')
   ```

3. **Удаление новых файлов:**
   ```bash
   rm model/test1/*_provider.py
   rm model/test1/panel_constants.py
   rm model/test1/bokeh_utils.py
   ```

---

## 📝 Changelog

| Дата | Версия | Изменения |
|------|--------|-----------|
| 2026-02-04 | 2.0 | Полностью переписан план с конкретикой |
