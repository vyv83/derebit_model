# 📋 ПЛАН МИГРАЦИИ: Dash → Panel

> **Версия:** FINAL  
> **Дата:** 2026-01-30  

---

# 1. СТРУКТУРА ПРОЕКТА

## 1.1 Исходная структура (Dash)

```
model/
├── model_analytics_app.py      # 694 строки - главное приложение + 13 callbacks
├── daily_data_provider.py      # 118 строк
├── option_timeseries_provider.py # 241 строка
├── deribit_option_logic.py     # 90 строк
├── config/
│   ├── theme.py                # 95 строк - CUSTOM_CSS, apply_chart_theme()
│   └── dashboard_config.py     # 52 строки - RISK_FREE_RATE=0.0, SUBPLOT_CONFIG
├── core/
│   └── black_scholes.py        # 175 строк
├── ui/
│   ├── components.py           # 98 строк - build_control_dock()
│   └── layout_builder.py       # 211 строк - LayoutBuilder class
├── charts/
│   ├── base_chart.py           # 77 строк - BaseChartBuilder ABC
│   ├── smile_chart.py          # 113 строк - render_smile_chart()
│   ├── surface_chart.py        # 55 строк - render_surface_chart()
│   ├── board_renderer.py       # 240 строк - BoardRenderer class
│   └── strike_chart.py         # 423 строки - StrikeChartBuilder class
├── services/
│   └── greeks_calculation_service.py  # 155 строк
├── ml/
│   ├── model_wrapper.py        # 143 строки - OptionModel class
│   └── model_architecture.py
└── strikes/                    # 7 файлов - генерация страйков
```

## 1.2 Целевая структура (Panel)

```
model_panel/
├── MIGRATION_PLAN.md           # Этот файл
├── app.py                      # Главная точка входа
├── state.py                    # AppState(param.Parameterized)
├── daily_data_provider.py      # КОПИЯ
├── option_timeseries_provider.py # КОПИЯ
├── deribit_option_logic.py     # КОПИЯ
├── config/                     # КОПИЯ
├── core/                       # КОПИЯ
├── services/                   # КОПИЯ
├── ml/                         # КОПИЯ
├── strikes/                    # КОПИЯ
├── components/
│   ├── header.py               # Заголовок + Currency + Period + KPIs
│   ├── expirations.py          # CheckButtonGroup
│   ├── time_deck.py            # Slider + ◀ ▶ кнопки
│   ├── chart_controls.py       # Toggle IV/Theta
│   └── board_grid.py           # Tabulator
├── views/
│   ├── smile_view.py
│   ├── board_view.py
│   ├── surface_view.py
│   └── strike_view.py
└── assets/
    └── styles.css
```

---

# 2. ГРАФ ЗАВИСИМОСТЕЙ

```
┌─────────────┐
│  currency   │──────┐
└─────────────┘      │
                     ▼
┌─────────────┐  ┌──────────────────┐
│   period    │─▶│   timestamps[]   │
└─────────────┘  └────────┬─────────┘
                          │
┌─────────────┐           ▼
│ btn-play/   │──▶ ┌─────────────┐
│ btn-back    │    │ time_index  │ (ЦИКЛИЧНО: end→0, 0→end)
└─────────────┘    └──────┬──────┘
                          │
                          ▼
                  ┌─────────────────┐
                  │  market_state   │
                  └────────┬────────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
   ┌────────────┐  ┌───────────────┐  ┌──────────────┐
   │   KPIs     │  │ dte_options   │  │time_display  │
   └────────────┘  └───────┬───────┘  └──────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │ selected_dtes  │ (STICKY: сохранять если валидно)
                  └────────┬───────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  predictions   │ (для ВСЕХ экспираций!)
                  └────────┬───────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
   ┌────────────┐  ┌─────────────┐  ┌──────────────┐
   │ Smile Tab  │  │ Board Tab   │  │ Surface Tab  │
   │(Calls only)│  │(Calls+Puts) │  │(Calls only)  │
   └────────────┘  └──────┬──────┘  └──────────────┘
                          │
                          │ grid click → парсинг _c/_p суффикса
                          ▼
                  ┌────────────────┐
                  │selected_strike │ (или auto-default при tab switch)
                  └────────┬───────┘
                           │
                           ▼
                  ┌────────────────┐    ┌────────────────┐
                  │  Strike Tab    │◀───│ visible_charts │
                  │ (5 состояний)  │    │ ['theta']      │
                  └────────────────┘    └────────────────┘
```

---

# 3. STATE MANAGEMENT

## 3.1 dcc.Store → param Mapping

| Dash Store | Panel param | Default |
|------------|-------------|---------|
| `market-state-store` | `market_state = param.Dict({})` | `{}` |
| `prediction-results-store` | `predictions = param.List([])` | `[]` |
| `timestamps-store` | `timestamps = param.List([])` | `[]` |
| `board-active-tab-store` | `board_active_tab = param.String(None, allow_None=True)` | `None` |
| `previous-dte-selection-store` | `_previous_dtes = param.List([])` | `[]` |
| `selected-strike-store` | `selected_strike = param.Dict(None, allow_None=True)` | `None` |
| `chart-sublots-selector` | `visible_charts = param.List(['theta'])` | `['theta']` |

## 3.2 AppState Class

```python
class AppState(param.Parameterized):
    # Selectors
    currency = param.Selector(default='BTC', objects=['BTC', 'ETH'])
    period = param.Selector(default='2024', objects=['2021','2022','2023','2024','2025'])
    
    # Time navigation
    timestamps = param.List(default=[])
    time_index = param.Integer(default=0)
    
    # Market data
    market_state = param.Dict(default={})
    predictions = param.List(default=[])
    
    # Expirations
    dte_options = param.List(default=[])
    selected_dtes = param.List(default=[])
    _previous_dtes = param.List(default=[])
    
    # Board
    board_active_tab = param.String(default=None, allow_None=True)
    
    # Strike Chart
    selected_strike = param.Dict(default=None, allow_None=True)
    visible_charts = param.List(default=['theta'])
    
    # Active tab
    active_tab = param.Selector(default='Smile', objects=['Smile', 'Board', 'Surface', 'Strike Chart'])
```

---

# 4. CALLBACKS → WATCHERS

## 4.1 Callback #1: Update Periods

```python
# Dash
@callback(Output("period-selector", "options"), Input("currency-selector", "value"))
def update_periods(currency): ...

# Panel
@param.depends('currency', watch=True)
def _update_periods(self):
    self.param.period.objects = ['2021', '2022', '2023', '2024', '2025']
```

## 4.2 Callback #2: Time Slider + Navigation (ОБЪЕДИНЁННЫЙ)

**Dash:** Один callback с ctx.triggered для определения источника

```python
@callback(
    [Output('time-slider', 'min'), Output('time-slider', 'max'),
     Output('time-slider', 'value'), Output('time-slider', 'marks'),
     Output('time-slider', 'disabled'), Output('timestamps-store', 'data')],
    [Input("currency-selector", "value"), Input("period-selector", "value"),
     Input('btn-play', 'n_clicks'), Input('btn-back', 'n_clicks')],
    [State('time-slider', 'value'), State('time-slider', 'max')]
)
def update_time_slider_logic(currency, period, play_clicks, back_clicks, current_val, max_val):
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id in ['btn-play', 'btn-back']:
        # Циклическая навигация
        if trigger_id == 'btn-play':
            new_val = (current_val + 1) if current_val < max_val else 0
        else:
            new_val = (current_val - 1) if current_val > 0 else max_val
        return [dash.no_update] * 2 + [new_val] + [dash.no_update] * 3
    
    # Реконфигурация timestamps
    ...
```

**Panel:** Три раздельных watcher

```python
@param.depends('currency', 'period', watch=True)
def _reconfigure_timestamps(self):
    all_dates = self.provider.get_date_range()
    year_dates = all_dates[all_dates.year == int(self.period)]
    self.timestamps = [d.strftime("%Y-%m-%d") for d in year_dates]
    self.time_index = 0

def on_play_click(self, event):
    max_val = len(self.timestamps) - 1
    self.time_index = 0 if self.time_index >= max_val else self.time_index + 1

def on_back_click(self, event):
    max_val = len(self.timestamps) - 1
    self.time_index = max_val if self.time_index <= 0 else self.time_index - 1
```

## 4.3 Callback #3: Update Market State

```python
# Dash
@callback(
    [Output("market-state-store", "data"), Output("kpi-spot", "children"), 
     Output("kpi-atm-iv", "children"), Output("kpi-hv", "children"),
     Output("time-display", "children")],
    [Input("time-slider", "value"), Input("timestamps-store", "data")]
)
def update_market_state(slider_idx, timestamps):
    # Type coercion защита
    idx = 0
    if slider_idx is not None:
        try:
            idx = int(slider_idx)
        except:
            idx = 0
    if idx >= len(timestamps):
        idx = 0
    ...

# Panel
@param.depends('time_index', 'timestamps', watch=True)
def _update_market_state(self):
    if not self.timestamps:
        return
    idx = min(self.time_index, len(self.timestamps) - 1)
    target_ts = self.timestamps[idx]
    self.market_state = self.provider.get_market_state(pd.to_datetime(target_ts))
```

## 4.4 Callback #4: STICKY DTE Selection

```python
# Dash
@callback(
    [Output("dte-selector", "options"), Output("dte-selector", "value")],
    [Input("market-state-store", "data")],
    [State("dte-selector", "value")]
)
def update_expiration_options(market_state, current_values):
    # STICKY: сохраняем если валидно
    valid_options = [opt['value'] for opt in options]
    new_values = [v for v in current_values if v in valid_options]
    if not new_values:
        new_values = [options[i]['value'] for i in range(min(3, len(options)))]
    return options, new_values

# Panel
@param.depends('market_state', watch=True)
def _update_dte_options(self):
    # ... generate new_options ...
    valid_values = [opt['value'] for opt in new_options]
    kept_values = [v for v in self.selected_dtes if v in valid_values]
    if not kept_values and new_options:
        kept_values = [new_options[i]['value'] for i in range(min(3, len(new_options)))]
    self.dte_options = new_options
    self.selected_dtes = kept_values
```

## 4.5 Callback #5: Run Model Inference

```python
# Dash - predictions для ВСЕХ экспираций (не только selected!)
all_exps = generate_deribit_expirations(current_date)
for exp, cnt in all_exps:
    dte = (exp - current_date).days
    if dte <= 0: continue
    result = model.predict(market_state, strikes, dte, is_call=True)
    result['type'] = 'call'
    # ... аналогично для puts ...
```

## 4.6 Callback #9: Auto-activate Board Subtab (SET DIFFERENCE)

```python
# Dash
@callback(
    [Output('board-active-tab-store', 'data', allow_duplicate=True),
     Output('previous-dte-selection-store', 'data')],
    Input('dte-selector', 'value'),
    [State('board-active-tab-store', 'data'),
     State('previous-dte-selection-store', 'data')],
    prevent_initial_call=True
)
def auto_activate_board_subtab(selected_dtes, current_active, previous_dtes):
    previous_set = set(previous_dtes) if previous_dtes else set()
    current_set = set(selected_dtes)
    newly_added = current_set - previous_set  # SET DIFFERENCE!
    
    if newly_added:
        new_active = list(newly_added)[0]
        return new_active, selected_dtes
    return dash.no_update, selected_dtes

# Panel
@param.depends('selected_dtes', watch=True)
def _auto_activate_board_subtab(self):
    previous_set = set(self._previous_dtes)
    current_set = set(self.selected_dtes)
    newly_added = current_set - previous_set
    
    if newly_added:
        self.board_active_tab = list(newly_added)[0]
    self._previous_dtes = list(self.selected_dtes)
```

## 4.7 Callback #7: Grid Click (PATTERN MATCHING)

```python
# Dash - Pattern matching ID
id={'type': 'options-grid', 'date': date_str}

@callback(
    [Output('selected-strike-store', 'data', allow_duplicate=True),
     Output('main-tabs', 'active_tab', allow_duplicate=True)],
    Input({'type': 'options-grid', 'date': ALL}, 'cellClicked'),
    ...
)
def handle_grid_click(cell_clicked_list, ...):
    col_id = clicked_cell.get('colId')
    
    # Игнорируем strike_price
    if col_id == 'strike_price':
        return dash.no_update, dash.no_update
    
    # Определяем тип по суффиксу
    if col_id.endswith('_c'):
        option_type = 'call'
    elif col_id.endswith('_p'):
        option_type = 'put'
    
    # Парсим JSON из prop_id для получения exp_date
    triggered_id = ctx.triggered[0]['prop_id']
    grid_id = json.loads(id_part)
    exp_date = grid_id.get('date')

# Panel - on_click с замыканием
def create_board_grid(self, df, exp_date, atm_strike):
    table = pn.widgets.Tabulator(value=df, ...)
    
    def on_cell_click(event):
        col = event.column
        if col == 'strike_price':
            return
        
        option_type = 'call' if col.endswith('_c') else 'put'
        strike = df.iloc[event.row]['strike_price']
        
        self.state.selected_strike = {
            'strike': strike,
            'type': option_type,
            'exp_date': exp_date  # Из замыкания!
        }
        self.state.active_tab = 'Strike Chart'
    
    table.on_click(on_cell_click)
    return table
```

## 4.8 Callbacks #11-12: Toggle Buttons (ДВУСТОРОННЯЯ СИНХРОНИЗАЦИЯ)

```python
# Dash: 2 callback
# 1. Clicks → Store
@callback(Output("chart-sublots-selector", "data"), 
          [Input("btn-toggle-iv", "n_clicks"), Input("btn-toggle-theta", "n_clicks")], ...)
          
# 2. Store → Button Visuals
@callback([Output("btn-toggle-iv", "style"), Output("btn-toggle-iv", "children"), ...],
          [Input("chart-sublots-selector", "data")])

# Panel: Один класс с watchers
class ChartControlsComponent(param.Parameterized):
    visible_charts = param.List(default=['theta'])
    
    def __init__(self, **params):
        super().__init__(**params)
        self.btn_iv = pn.widgets.Button(name='VOL OFF')
        self.btn_theta = pn.widgets.Button(name='THETA ON')
        
        self.btn_iv.on_click(self._toggle_iv)
        self.btn_theta.on_click(self._toggle_theta)
        self.param.watch(self._update_button_visuals, 'visible_charts')
    
    def _toggle_iv(self, event):
        if 'iv' in self.visible_charts:
            self.visible_charts = [c for c in self.visible_charts if c != 'iv']
        else:
            self.visible_charts = self.visible_charts + ['iv']
    
    def _update_button_visuals(self, event=None):
        is_iv_active = 'iv' in self.visible_charts
        self.btn_iv.name = f'VOL {"ON" if is_iv_active else "OFF"}'
        # ... stylesheets ...
```

---

# 5. КОМПОНЕНТЫ - ДЕТАЛИ

## 5.1 Currency Selector

| Dash | Panel |
|------|-------|
| `dbc.RadioItems` | `pn.widgets.RadioButtonGroup` |
| `btn btn-sm btn-outline-primary rounded-pill` | CSS override |
| `style={"gap": "3px"}` | CSS |

## 5.2 Period Selector

| Dash | Panel |
|------|-------|
| `dbc.Select(size="sm")` | `pn.widgets.Select(width=100)` |
| `borderRadius: 20px, height: 24px, fontSize: 11px` | CSS |

## 5.3 Time Slider

| Dash | Panel | Решение |
|------|-------|---------|
| `dcc.Slider` с marks | `pn.widgets.IntSlider` | Кастомный SliderWithMarks |
| `marks={0: 'Jan', 12: 'Feb', ...}` | НЕТ marks | HTML overlay |
| `updatemode='drag'` | По умолчанию | ОК |

```python
class SliderWithMarks(pn.viewable.Viewer):
    @param.depends('timestamps')
    def _generate_marks_html(self):
        marks = []
        for i, ts in enumerate(self.timestamps):
            dt = pd.to_datetime(ts)
            if dt.day == 1:  # Только 1-й день месяца!
                pct = i * 100 / (len(self.timestamps) - 1)
                marks.append(f'<span style="left:{pct}%">{dt.strftime("%b")}</span>')
        return pn.pane.HTML(f'<div class="slider-marks">{"".join(marks)}</div>')
```

## 5.4 Navigation Buttons ◀ ▶

| Dash | Panel |
|------|-------|
| `dbc.Button("◀", color="light")` | `pn.widgets.Button(name="◀", button_type='light')` |
| `borderRadius: 50%, width: 35px, height: 35px` | CSS |
| **Циклическая навигация** | on_click handler |

## 5.5 Expirations Checklist

| Dash | Panel |
|------|-------|
| `dbc.Checklist(inline=True)` | `pn.widgets.CheckButtonGroup` |
| `scrollbarWidth: none` | CSS `.no-scrollbar` |
| `flexWrap: nowrap` | CSS |
| **STICKY selection** | watcher logic |

## 5.6 Main Tabs

| Dash | Panel |
|------|-------|
| `dbc.Tabs` | `pn.Tabs` |
| `active_tab="tab-smile"` | Первый элемент |
| `label_style={"fontSize": "13px", "fontWeight": "500"}` | CSS |

## 5.7 Board Subtabs

| Dash | Panel |
|------|-------|
| `dbc.Tabs` внутри Board | `pn.Tabs` с `dynamic=True` |
| `label_style={"fontSize": "12px", "fontWeight": "400"}` | МЕНЬШЕ чем main! |

## 5.8 KPI Bar

| Элемент | Стили |
|---------|-------|
| Контейнер | `height: 52px, marginLeft: auto, border: 1px solid #E0E6ED` |
| PRICE | `minWidth: 120px, border-end` |
| IV ATM, HV 30D | `minWidth: 90px, border-end` |
| Label | `fontSize: 11px, fontWeight: 600, letterSpacing: 0.05em, textTransform: uppercase` |
| Value | `fontSize: 16px, fontWeight: 800, lineHeight: 1` |

## 5.9 Toggle Buttons

| Состояние | Border | Color |
|-----------|--------|-------|
| IV active | `#9B59B6` | `#9B59B6` |
| THETA active | `#E67E22` | `#E67E22` |
| Inactive | `#ced4da` | `#7F8C8D` |

Общие стили: `padding: 1px 10px, height: 24px, borderRadius: 4px, fontSize: 10px`

Label structure: `<span style="fontSize: 9px, opacity: 0.7">VOL </span><span style="fontWeight: 800">ON</span>`

---

# 6. VIEWS - ДЕТАЛИ

## 6.1 Smile Chart

- **Только Calls** (puts не показываются)
- Фильтрация по `selected_dtes`
- Cubic spline интерполяция (`make_interp_spline(x, y, k=3)`)
- Fallback: если < 4 точек → линия вместо spline
- Fallback: если spline fails → простая линия
- Actual points: `showlegend=False`
- Spot line: `vline` с annotation

## 6.2 Surface Chart

- **Только Calls**
- **НЕТ фильтрации** по selected_dtes (все данные)
- `go.Scatter3d` (НЕ go.Surface!) — это точки
- `marker=dict(size=3, colorscale='Viridis', opacity=0.8)`
- `margin=dict(l=0, r=0, b=0, t=40)` — отличается!

## 6.3 Board View

- **Calls И Puts**
- Tabs для каждой экспирации
- Фильтрация по `selected_dtes`
- AG Grid / Tabulator с d3.format
- ATM row highlighting: `backgroundColor: #FEF9E7`
- Click handler с col_id суффиксом `_c`/`_p`
- `board_renderer` создаётся КАЖДЫЙ раз (не singleton)

### Column Definitions

```python
columns = [
    # Call side
    {'field': 'vega_c', 'width': 90, 'format': ',.2f'},
    {'field': 'theta_c', 'width': 90, 'format': ',.2f'},
    {'field': 'gamma_c', 'width': 120, 'format': ',.6f'},
    {'field': 'delta_c', 'width': 90, 'format': ',.2f', 'color': '#76D7C4'},
    {'field': 'mark_iv_c', 'width': 80, 'format': ',.1f'},
    {'field': 'price_c', 'width': 145, 'format': ',.3f', 'bold': True},
    
    # Strike (center)
    {'field': 'strike_price', 'width': 120, 
     'style': {'fontWeight': 800, 'textAlign': 'center', 
               'backgroundColor': '#F8F9F9', 'fontSize': '16px',
               'borderLeft': '2px solid #D5D8DC', 'borderRight': '2px solid #D5D8DC'}},
    
    # Put side
    {'field': 'price_p', ...},
    # ... mirror of call side
]
```

## 6.4 Strike Chart (5 СОСТОЯНИЙ)

| # | Условие | UI |
|---|---------|-----|
| 1 | `not market_state` | "System initializing..." |
| 2 | `not selected_strike` | "Click on any Call or Put..." |
| 3 | Missing strike/type/exp_date | "Invalid Selection" |
| 4 | `ohlc_df.empty` | "No historical data..." |
| 5 | OK | Candlestick график |

### OHLC Generation (СИНТЕТИЧЕСКИЕ ДАННЫЕ!)

```python
for date_str in timestamps_store:
    if date > current_dt or date > exp_dt:
        continue
    
    state = provider.get_market_state(date)
    result = model.predict(market_state=state, strikes=[strike], dte_days=dte)
    iv = result['mark_iv'].iloc[0] / 100.0
    
    greeks = black_scholes_safe(S=spot, K=strike, T=T, r=0.0, sigma=iv)
    
    # FAKE OHLC: open = previous close
    prices_data.append({'price': greeks['price'], 'iv': iv*100, 'theta': greeks['theta']})
```

### Subplot Configuration

```python
SUBPLOT_CONFIG = {
    'iv': {'label': 'VOL', 'title': 'IV (%)', 'color': '#9B59B6', 'data_col': 'iv'},
    'theta': {'label': 'THETA', 'title': 'Theta ($)', 'color': '#E67E22', 'data_col': 'theta'}
}
```

---

# 7. СТИЛИ

## 7.1 assets/styles.css

```css
/* ========== FONTS ========== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ========== GLOBAL ========== */
:root {
    --background: #F5F7F9;
    --card-bg: #FFFFFF;
    --text-primary: #2C3E50;
    --text-secondary: #7F8C8D;
    --accent-call: #76D7C4;
    --accent-put: #FF8787;
    --accent-iv: #9B59B6;
    --accent-theta: #E67E22;
    --border-color: #E0E6ED;
}

body {
    background-color: var(--background);
    font-family: 'Inter', sans-serif;
    min-height: 100vh;
}

/* ========== CONTAINER ========== */
.main-container {
    max-width: 1800px;
    padding-bottom: 100px;  /* Space for control dock */
}

/* ========== CONTROL DOCK ========== */
.control-dock {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    background-color: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
    border-top: 1px solid #E0E0E0;
    padding: 15px 40px;
    z-index: 1000;
}

/* ========== SCROLLBAR HIDE ========== */
.no-scrollbar {
    overflow-x: auto;
    white-space: nowrap;
    scrollbar-width: none;
    -ms-overflow-style: none;
}
.no-scrollbar::-webkit-scrollbar {
    display: none;
}

/* ========== ROUNDED PILLS ========== */
.rounded-pill .bk-btn {
    border-radius: 20px !important;
    padding: 2px 12px !important;
    font-size: 10px !important;
}

/* ========== NAVIGATION BUTTONS ========== */
.nav-button .bk-btn {
    border-radius: 50% !important;
    width: 35px !important;
    height: 35px !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

/* ========== KPI BAR ========== */
.kpi-bar {
    display: flex;
    align-items: center;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    border: 1px solid var(--border-color);
    height: 52px;
    margin-left: auto;
}

.kpi-item {
    padding: 0 12px;
    min-width: 90px;
}
.kpi-item:first-child { min-width: 120px; }
.kpi-item:not(:last-child) { border-right: 1px solid var(--border-color); }

.kpi-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.kpi-value {
    font-size: 16px;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1;
}

/* ========== CHART CONTROLS ========== */
.chart-controls {
    position: absolute;
    top: 25px;
    left: 35px;
    z-index: 100;
}

/* ========== TOGGLE BUTTONS ========== */
.toggle-btn {
    padding: 1px 10px !important;
    height: 24px !important;
    border-radius: 4px !important;
    font-size: 10px !important;
    background-color: rgba(255,255,255,0.8) !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
}

/* ========== CARD ========== */
.card {
    background-color: var(--card-bg);
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    border: none;
    padding: 12px 20px;
    margin-bottom: 10px;
}

/* ========== CHART ========== */
.chart-container {
    height: calc(100vh - 280px);
    min-height: 500px;
}

/* ========== TABS ========== */
.bk-tab {
    font-size: 13px !important;
    padding: 6px 12px !important;
    font-weight: 500 !important;
}

/* Board subtabs - smaller */
.board-subtabs .bk-tab {
    font-size: 12px !important;
    padding: 5px 10px !important;
    font-weight: 400 !important;
}

/* ========== TABULATOR ATM ROW ========== */
.tabulator-row.atm-row {
    background-color: #FEF9E7 !important;
}

/* ========== AG GRID HEADER ========== */
.ag-theme-alpine .ag-header-cell {
    font-size: 11px !important;
}

/* ========== SLIDER MARKS ========== */
.slider-marks {
    position: relative;
    height: 25px;
    margin-top: -5px;
}
.slider-marks span {
    position: absolute;
    transform: translateX(-50%);
    font-size: 10px;
    color: var(--text-secondary);
}
```

---

# 8. EDGE CASES

## 8.1 Type Coercion

```python
# Slider value может быть None или string
idx = 0
if slider_idx is not None:
    try:
        idx = int(slider_idx)
    except:
        idx = 0
if idx >= len(timestamps):
    idx = 0
```

## 8.2 Fallbacks Chain

```python
# vol
vol = market_state.get('Real_IV_ATM', market_state.get('HV_30d', 0.80))

# anchor_state
if anchor_state:
    anchor_spot = anchor_state['underlying_price']
else:
    anchor_spot = spot

# hist_ranges
if not hist_ranges:
    hist_ranges = [('daily', spot, spot)]
```

## 8.3 Strike Selection Sources

1. `handle_grid_click` — клик на Board
2. `set_default_strike` — автоматически при переходе на Strike tab (prevent_initial_call=False!)

## 8.4 visible_charts Default

```python
# Два места с одинаковым default
dcc.Store(id="chart-sublots-selector", data=['theta'])

if not isinstance(current_list, list):
    current_list = ['theta']
```

---

# 9. ФАЙЛЫ БЕЗ ИЗМЕНЕНИЙ

```bash
cp model/daily_data_provider.py model_panel/
cp model/option_timeseries_provider.py model_panel/
cp model/deribit_option_logic.py model_panel/
cp -r model/config model_panel/
cp -r model/core model_panel/
cp -r model/services model_panel/
cp -r model/ml model_panel/
cp -r model/strikes model_panel/
```

**Изменить пути:**
```python
# Было
model_path = os.path.join(BASE_DIR, '../best_multitask_svi.pth')

# Стало
model_path = os.path.join(BASE_DIR, '../best_multitask_svi.pth')  # Оставить как есть
```

---

# 10. ЧЕКЛИСТ

## Инфраструктура
- [ ] Структура папок
- [ ] Скопировать файлы
- [ ] assets/styles.css
- [ ] Подключить Inter font
- [ ] state.py с AppState

## Компоненты
- [ ] components/header.py
- [ ] components/expirations.py (STICKY logic)
- [ ] components/time_deck.py (циклическая навигация, SliderWithMarks)
- [ ] components/chart_controls.py (двусторонняя синхронизация)
- [ ] components/board_grid.py (on_click с замыканием, ATM highlighting)

## Views
- [ ] views/smile_view.py (spline + fallbacks, только Calls)
- [ ] views/surface_view.py (Scatter3d, все DTEs)
- [ ] views/board_view.py (Tabs, Calls+Puts, d3.format → Tabulator)
- [ ] views/strike_view.py (5 состояний, subplots)

## Логика
- [ ] 3 watcher для time slider
- [ ] STICKY selection для экспираций
- [ ] Auto-activate board subtab
- [ ] Grid click → selected_strike → tab switch
- [ ] Toggle buttons синхронизация
- [ ] predictions для ВСЕХ экспираций

## Стили
- [ ] Control dock с blur
- [ ] Scrollbar hide
- [ ] Rounded pills
- [ ] KPI bar с разделителями
- [ ] Chart height: calc(100vh - 280px)
- [ ] Board subtabs < main tabs

## Edge Cases
- [ ] Type coercion
- [ ] Vol fallback chain
- [ ] Empty timestamps
- [ ] ATM strike calculation

---

# 11. ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ (POST-IMPLEMENTATION)

> Проблемы выявлены при тестировании Panel приложения 2026-01-30

## 11.1 LAYOUT & SIZING

### Проблема 1: Панель не на весь экран по ширине
**Источник в Dash:** `layout_builder.py:205`
```python
dbc.Container([...], fluid=True, style={"maxWidth": "1800px", ...})
```
**Решение Panel:** Убрать `margin=(0, 20)` из main_content, использовать `sizing_mode='stretch_width'`

### Проблема 2: Time slider узкий
**Источник в Dash:** `components.py:60`
```python
dbc.Col([...slider...], width=10),
dbc.Col([...buttons...], width=2)
```
**Решение Panel:** Bootstrap row 10/2 split → Panel `pn.Row` с 83%/17% или `pn.FlexBox`

### Проблема 3: Control dock не fixed
**Источник в Dash:** `components.py:87-97`
```python
style={
    "position": "fixed", 
    "bottom": "0", 
    "left": "0", 
    "width": "100%",
    "padding": "15px 40px",
    "zIndex": "1000"
}
```
**Решение Panel:** Использовать `pn.Template` с sidebar=False или CSS `position: fixed`

### Проблема 4: Высота расходуется впустую
**Источник в Dash:** `theme.py:29`
```python
GLOBAL_CHART_STYLE = {"height": "calc(100vh - 280px)", "minHeight": "500px"}
```
**Решение Panel:** Применить `min_height=500` и `sizing_mode='stretch_both'` к chart panes

## 11.2 TYPOGRAPHY & SPACING

### Проблема 5: Большие контролы и шрифты
**Источник в Dash:**
- Header: `fontSize: 16px` (title), `fontSize: 10px` (labels)
- Tabs: `fontSize: 13px, padding: 6px 12px`
- Expirations: `fontSize: 10px`
- Control dock: `fontSize: 10px`

**Решение Panel:** Обновить CSS с ТОЧНЫМИ размерами

### Проблема 6: Большие шрифты в таблице
**Источник в Dash:** `board_renderer.py:198-199`
```python
dashGridOptions={
    "headerHeight": 28,
    "rowHeight": 35,
    ...
}
```
**Решение Panel:** `pn.widgets.Tabulator(height=35, header_filters=False)`, CSS для font-size

### Проблема 7: Страйки не жирные
**Источник в Dash:** `board_renderer.py:89-97`
```python
{'field': 'strike_price', 'headerName': 'STRIKE', 'width': 120, 
 'cellStyle': {
     'fontWeight': '800', 
     'textAlign': 'center', 
     'backgroundColor': '#F8F9F9', 
     'fontSize': '16px',
     'borderLeft': '2px solid #D5D8DC', 
     'borderRight': '2px solid #D5D8DC'
 }}
```
**Решение Panel:** Tabulator formatters + CSS selectors для strike column

## 11.3 DATA & LOGIC

### Проблема 8: 0 день не имеет графика
**Анализ:** DTE = 0 пропускается в `_generate_ohlc_data`:
```python
dte = (exp_dt - date).days
if dte <= 0:  # <-- 0 пропускается!
    continue
```
**Решение:** Изменить на `if dte < 0:` ИЛИ показывать placeholder "Option expired today"

### Проблема 9: ATM row не выделен
**Источник в Dash:** `board_renderer.py:201-208`
```python
dashGridOptions={
    "getRowStyle": {
        "styleConditions": [
            {
                "condition": f"params.data.strike_price == {atm_strike}",
                "style": {"backgroundColor": "#FEF9E7"}
            }
        ]
    }
}
```
**Решение Panel:** Tabulator `row_content` callback или CSS + class assignment

## 11.4 UI BEHAVIOR

### Проблема 10: При добавлении экспирации панель расширяется
**Анализ:** Tabs перерисовываются и меняют layout
**Решение:** `pn.Tabs(..., dynamic=True)` и фиксированный `min_height` для chart container

## 11.5 CSS DISCREPANCIES

| Элемент | Dash | Panel (текущий) | Исправить |
|---------|------|-----------------|-----------|
| Title | `fontSize: 16px` | CSS override | ✓ |
| Subtitle | `fontSize: 10px` | CSS override | ✓ |
| Currency btn | `btn-sm rounded-pill px-2 py-0` | Button default | ✓ |
| Period select | `height: 24px, fontSize: 11px` | Select default | ✓ |
| Tab labels | `fontSize: 13px, padding: 6px 12px` | `bk-tab` default | ✓ |
| Expiration pills | `fontSize: 10px` | CheckButtonGroup | ✓ |
| Control dock padding | `15px 40px` | Row margin | ✓ |
| Nav buttons | `35x35, border-radius: 50%` | Button default | ✓ |

---

# 12. КРИТИЧЕСКИЙ АНАЛИЗ СКРИНШОТОВ (2026-01-30 14:53)

## Оценка текущего состояния: 2.8/10 ❌

| Скрин | Элемент | Проблема | Оценка |
|-------|---------|----------|--------|
| 1 | Header | BTC/ETH кнопки огромные, много пустоты, слишком высокие контролы | 3/10 |
| 2 | KPI Bar | Большой gap между label и value, высота ячеек завышена | 4/10 |
| 3 | Board | Черные стрелки (row_content!), большие ячейки, нет ATM highlighting, дрыгание при timeline | 2/10 |
| 4 | Expirations | Не pill-style, нет gap между кнопками, не закруглены | 3/10 |
| 5 | Chart Toggle | Кнопки на всю ширину, огромные, некрасивые | 2/10 |

## Причины проблем:

### 1. Черные стрелочки в таблице
**Причина:** Использовал `row_content=row_style` в Tabulator - это добавляет expand arrows!
**Решение:** Удалить `row_content`, использовать `stylesheets` для ATM highlighting

### 2. Дрыгание таблицы при timeline
**Причина:** Tabulator пересоздается при каждом изменении данных, что вызывает flickering
**Решение:** 
- Использовать `Tabulator.patch()` вместо пересоздания
- Добавить `configuration={'renderVerticalBuffer': 300}` для буферизации
- Использовать `min_height` для стабильного layout

### 3. Кнопки не pill-style  
**Источник в Dash:** `label_class_name="btn btn-sm btn-outline-primary rounded-pill px-2 py-0"`
- `rounded-pill` = border-radius: 50rem (очень закругленные)
- `btn-sm` = height ~24px, font-size 10px
- `px-2 py-0` = padding: 0 8px

### 4. Toggle кнопки на всю ширину
**Источник в Dash:** `style={"padding": "1px 10px", "height": "24px", "borderRadius": "4px", "fontSize": "10px"}`
- Очень компактные
- Фиксированная ширина
- marginRight: "5px" между ними

---

# 13. ДЕТАЛЬНЫЙ ПЛАН ИСПРАВЛЕНИЙ v2

## Фаза 1: Board View Fix (КРИТИЧНО)
1. [x] Убрать `row_content` из Tabulator (убирает черные стрелки)
2. [ ] Использовать `style_data` callback для ATM highlighting
3. [ ] Уменьшить row height до 28px, header до 24px
4. [ ] Font-size 11px через stylesheets
5. [ ] Для предотвращения дрыгания: использовать `patch()` или фиксированный min_height

## Фаза 2: Button Styling (все кнопки в приложении)
**Единый стиль кнопок:**
```css
.pill-button .bk-btn {
    border-radius: 50rem !important;  /* Pill shape */
    padding: 0 8px !important;
    height: 22px !important;
    font-size: 10px !important;
    border: 1px solid #007bff !important;
    background: white !important;
}
.pill-button.active .bk-btn {
    background: #007bff !important;
    color: white !important;
}
```

Применить к:
1. [ ] Currency selector (BTC/ETH)
2. [ ] Expirations selector (pill buttons)
3. [ ] Toggle buttons (VOL/THETA) - компактные, не на всю ширину

## Фаза 3: Header Compactness
1. [ ] Уменьшить общую высоту header row
2. [ ] Убрать лишний padding вокруг title
3. [ ] KPI bar: уменьшить gap между label/value

## Фаза 4: Toggle Buttons Style
**Из оригинального Dash кода:**
```python
style = {
    "padding": "1px 10px", 
    "height": "24px", 
    "borderRadius": "4px", 
    "fontSize": "10px",
    "border": f"1px solid {color if active else '#ced4da'}",
    "backgroundColor": "rgba(255,255,255,0.8)",
    "boxShadow": "0 2px 4px rgba(0,0,0,0.05)",
    "marginRight": "5px"
}
```

## Фаза 5: Expirations Pills
1. [ ] Закругленные pill-style
2. [ ] Gap 3px между кнопками
3. [ ] Font-size 10px
4. [ ] Height 22-24px

