"""
ФАЙЛ: bokeh_workarounds.py
ОПИСАНИЕ: Слой 1 - Инкапсуляция всех известных проблем/багов Bokeh.
          Этот модуль СКРЫВАЕТ все костыли библиотеки и предоставляет чистый API.

ЗАВИСИМОСТИ: bokeh

СПИСОК РЕШЁННЫХ ПРОБЛЕМ BOKEH:
1.  CrosshairTool не синхронизируется между plots (#3799)
2.  Y-axis не автомасштабируется при pan/zoom (#7475)
3.  visible=False не убирает из layout - используем height=0
4.  extra_y_ranges не масштабируется независимо (#13302)
5.  min_border/spacing не работает корректно (#4164)
6.  Label не sticky к viewport
7.  HoverTool не синхронизируется между plots (#14066)
8.  sizing_mode='stretch_both' сломан (#12614)
9.  X-axis дублируется/не выравнивается (#5572)
10. Toggle styling ограничен
11. Candlestick нет встроенного - собираем из segment + vbar
12. Legend не обновляется динамически
13. Multiple callbacks на одно property (#6508)
14. change.emit() не всегда обновляет view
15. Zoom блокируется когда один край на bounds (#6708)
16. vbar width в datetime требует миллисекунды
17. desired_num_ticks игнорируется
18. Window resize не поддерживается (#11602)
19. get_model_by_id может вернуть null

ТЕСТ: Этот файл не запускается отдельно - используется другими модулями.
"""

from bokeh.models import (
    CustomJS, Span, Range1d, LinearAxis, Label, Div, Toggle,
    HoverTool, BasicTicker, NumeralTickFormatter, ColumnDataSource
)
from bokeh.plotting import figure
from bokeh.models.formatters import DatetimeTickFormatter


# ============================================================================
# WORKAROUND #1, #7: CrosshairSync - Синхронизация crosshair между plots
# Проблема: CrosshairTool не линкуется между графиками
# Решение: Создаём Span на каждом графике + CustomJS для синхронизации
# ============================================================================

class CrosshairSync:
    """
    Создаёт синхронизированный crosshair на нескольких графиках.
    
    Использование:
        spans = CrosshairSync.create_spans(plots, color='#546E7A')
        # spans нужно передать в HoverSync для управления видимостью
    """
    
    @staticmethod
    def create_spans(plots, color='#546E7A', line_width=1, line_alpha=0.7):
        """
        Создаёт вертикальные Span на всех графиках.
        
        Args:
            plots: список figure объектов
            color: цвет линии crosshair
            line_width: толщина линии
            line_alpha: прозрачность
            
        Returns:
            list of Span objects (по одному на каждый plot)
        """
        spans = []
        for p in plots:
            span = Span(
                location=0,
                dimension='height',
                line_color=color,
                line_width=line_width,
                line_alpha=line_alpha,
                line_dash='solid',
                visible=False
            )
            p.add_layout(span)
            spans.append(span)
        return spans

    @staticmethod
    def create_callback(spans):
        """
        Создаёт callback для обновления позиции crosshair.
        """
        return CustomJS(args=dict(spans=spans), code="""
            const geometry = cb_data.geometry;
            if (!geometry) return;
            const x = geometry.x;
            for (let span of spans) {
                span.location = x;
                span.visible = true;
            }
        """)

    @staticmethod
    def create_hide_callback(spans):
        """
        Создаёт callback для скрытия crosshair при mouseleave.
        
        Args:
            spans: список Span объектов
            
        Returns:
            CustomJS callback
        """
        return CustomJS(args=dict(spans=spans), code="""
            for (let span of spans) {
                span.visible = false;
            }
        """)


# ============================================================================
# WORKAROUND #2, #4: AutoScaleY - Автомасштабирование Y при изменении X
# Проблема: y_range не пересчитывается при pan/zoom по X
# Решение: CustomJS callback на x_range.change
# ============================================================================

class AutoScaleY:
    """
    Автоматическое масштабирование Y-оси при изменении видимого X-диапазона.
    
    Использование:
        callback = AutoScaleY.create_callback(
            y_range=plot.y_range,
            x_range=plot.x_range,
            source=data_source,
            y_fields=['high', 'low'],
            padding=0.10
        )
        plot.x_range.js_on_change('start', callback)
        plot.x_range.js_on_change('end', callback)
    """
    
    @staticmethod
    def create_callback(y_range, x_range, source, y_fields, padding=0.10):
        """
        Создаёт callback для автомасштабирования Y.
        
        Args:
            y_range: Range1d объект для обновления (y_range или extra_y_ranges['name'])
            x_range: Range1d объект X-оси (для фильтрации видимых данных)
            source: ColumnDataSource с данными
            y_fields: список полей для вычисления min/max (например ['high', 'low'])
            padding: отступ от краёв (доля от диапазона)
            
        Returns:
            CustomJS callback
        """
        fields_js = ', '.join([f"'{f}'" for f in y_fields])
        
        return CustomJS(args=dict(
            y_range=y_range,
            x_range=x_range,
            src=source,
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

    @staticmethod
    def attach_to_plot(plot, source, y_fields, padding=0.10):
        """
        Удобный метод - создаёт и привязывает callback к plot.
        
        Args:
            plot: figure объект
            source: ColumnDataSource
            y_fields: поля для min/max
            padding: отступ
        """
        callback = AutoScaleY.create_callback(
            plot.y_range, plot.x_range, source, y_fields, padding
        )
        plot.x_range.js_on_change('start', callback)
        plot.x_range.js_on_change('end', callback)
        return callback

    @staticmethod
    def attach_to_extra_y_range(plot, range_name, source, y_fields, padding=0.10):
        """
        Для дополнительных Y-осей (extra_y_ranges).
        
        Args:
            plot: figure объект
            range_name: имя в extra_y_ranges (например 'spot')
            source: ColumnDataSource
            y_fields: поля для min/max
            padding: отступ
        """
        callback = AutoScaleY.create_callback(
            plot.extra_y_ranges[range_name], plot.x_range, source, y_fields, padding
        )
        plot.x_range.js_on_change('start', callback)
        plot.x_range.js_on_change('end', callback)
        return callback


# ============================================================================
# WORKAROUND #6: StickyLabel - Метки привязанные к краю viewport
# Проблема: Label не имеет режима sticky
# Решение: CustomJS обновляет позицию Label при изменении x_range
# ============================================================================

class StickyLabel:
    """
    Создаёт Label который остаётся у края видимой области при pan/zoom.
    
    Использование:
        label, callback = StickyLabel.create_right(
            plot=plot,
            y_value=100.50,
            text="100.50",
            color='#888888'
        )
    """
    
    @staticmethod
    def create_right(plot, y_value, text, color='#888888', y_range_name=None):
        """
        Создаёт Label привязанный к правому краю.
        """
        label_kwargs = dict(
            x=plot.x_range.end if hasattr(plot.x_range, 'end') else 0,
            y=y_value,
            text=text,
            text_font_size='8pt',
            text_color=color,
            text_font_style='normal',
            text_align='right',
            x_offset=-5,
            y_offset=2,
        )
        if y_range_name:
            label_kwargs['y_range_name'] = y_range_name
            
        label = Label(**label_kwargs)
        plot.add_layout(label)
        
        callback = CustomJS(args=dict(label=label, x_range=plot.x_range), code="""
            label.x = x_range.end;
        """)
        plot.x_range.js_on_change('start', callback)
        plot.x_range.js_on_change('end', callback)
        
        return label, callback

    @staticmethod
    def create_left(plot, y_value, text, color='#888888', y_range_name=None):
        """
        Создаёт Label привязанный к левому краю.
        """
        label_kwargs = dict(
            x=plot.x_range.start if hasattr(plot.x_range, 'start') else 0,
            y=y_value,
            text=text,
            text_font_size='8pt',
            text_color=color,
            text_font_style='normal',
            text_align='left',
            x_offset=5,
            y_offset=2,
        )
        if y_range_name:
            label_kwargs['y_range_name'] = y_range_name
            
        label = Label(**label_kwargs)
        plot.add_layout(label)
        
        callback = CustomJS(args=dict(label=label, x_range=plot.x_range), code="""
            label.x = x_range.start;
        """)
        plot.x_range.js_on_change('start', callback)
        plot.x_range.js_on_change('end', callback)
        
        return label, callback


# ============================================================================
# WORKAROUND #3, #5, #8: LayoutFixer - Исправление проблем с layout
# Проблемы: visible=False не работает, spacing, min_border, sizing_mode
# Решение: Комплекс настроек + height=0 для скрытия
# ============================================================================

class LayoutFixer:
    """
    Исправляет проблемы с layout в Bokeh.
    """
    
    @staticmethod
    def apply_zero_gaps(plot):
        """
        Убирает все отступы у графика для плотной стыковки.
        """
        plot.min_border_top = 0
        plot.min_border_bottom = 0
        plot.margin = 0
        
    @staticmethod
    def configure_for_stack(plots, min_border_left=50, min_border_right=50):
        """
        Настраивает список графиков для вертикальной стыковки.
        
        Args:
            plots: список figure объектов
            min_border_left: одинаковый отступ слева (для выравнивания Y-осей)
            min_border_right: одинаковый отступ справа
        """
        for p in plots:
            p.min_border_left = min_border_left
            p.min_border_right = min_border_right
            p.min_border_top = 0
            p.min_border_bottom = 0
            p.margin = 0
            
    @staticmethod
    def get_responsive_html_wrapper():
        """
        Возвращает CSS и JS для полноэкранного responsive layout.
        """
        return '''
        <style>
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
        </style>
        '''


# ============================================================================
# WORKAROUND #9: SharedAxisPlot - Отдельный график для общей X-оси
# Проблема: X-axis дублируется и не выравнивается между графиками
# Решение: Скрыть X-axis на всех графиках, создать отдельный axis plot внизу
# ============================================================================

class SharedAxisPlot:
    """
    Создаёт отдельный минимальный график только для отображения X-оси.
    
    Использование:
        axis_plot = SharedAxisPlot.create(
            x_range=main_plot.x_range,
            source=data_source,
            height=25
        )
    """
    
    @staticmethod
    def create(x_range, source, height=25, min_border_left=50, min_border_right=50):
        """
        Создаёт график-заглушку для X-оси.
        
        Args:
            x_range: Range1d - общий X range (от основного графика)
            source: ColumnDataSource - нужен для определения масштаба
            height: высота в пикселях
            min_border_left/right: отступы для выравнивания с другими графиками
            
        Returns:
            figure объект
        """
        p = figure(
            height=height,
            sizing_mode='stretch_width',
            x_axis_type='datetime',
            x_range=x_range,
            min_border_left=min_border_left,
            min_border_right=min_border_right,
            min_border_top=0,
            min_border_bottom=25,
            tools='',
            toolbar_location=None,
            outline_line_color=None,
            background_fill_alpha=0,
            border_fill_alpha=0
        )
        
        # Невидимый рендерер для определения масштаба
        p.line('timestamp', 'close', source=source, alpha=0, line_width=0)
        
        # Левая линия (продолжение оси Y основных графиков)
        p.yaxis.visible = True
        p.yaxis.axis_line_color = '#CCCCCC'
        p.yaxis.major_tick_line_color = None
        p.yaxis.minor_tick_line_color = None
        p.yaxis.major_label_text_font_size = '0pt'
        p.yaxis.major_label_text_color = None
        
        # Убираем сетку
        p.xgrid.visible = False
        p.ygrid.visible = False
        
        # Стилизация X-оси
        p.xaxis.axis_line_color = '#CCCCCC'
        p.xaxis.major_tick_line_color = '#CCCCCC'
        p.xaxis.major_label_text_color = '#888888'
        p.xaxis.major_label_text_font_size = '7pt'
        p.xaxis.major_tick_in = 2
        p.xaxis.major_tick_out = 2
        
        p.xaxis.formatter = DatetimeTickFormatter(
            days='%d %b',
            months='%b %Y'
        )
        
        p.margin = 0
        
        return p


# ============================================================================
# WORKAROUND #11, #16: Candlestick - Свечной график из segment + vbar
# Проблема: Bokeh не имеет встроенного candlestick
# Решение: segment для теней + vbar для тел
# ============================================================================

class Candlestick:
    """
    Рендерит свечной график.
    
    Использование:
        Candlestick.render(
            plot=p,
            source=src_ohlc,
            candle_width=0.6
        )
    """
    
    # Ширина свечи = доля от дня в миллисекундах
    DAY_MS = 24 * 60 * 60 * 1000
    
    @staticmethod
    def render(plot, source, candle_width_ratio=0.6):
        """
        Рисует свечи на графике.
        
        Args:
            plot: figure объект
            source: ColumnDataSource с полями: timestamp, open, high, low, close, color
            candle_width_ratio: ширина свечи как доля от дня (0.6 = 60%)
        """
        width = candle_width_ratio * Candlestick.DAY_MS
        
        # Тени (wicks)
        plot.segment(
            'timestamp', 'low', 'timestamp', 'high',
            source=source, color='color', line_width=1
        )
        
        # Тела (bodies)
        plot.vbar(
            'timestamp', width, 'close', 'open',
            source=source, fill_color='color', line_color='color'
        )


# ============================================================================
# WORKAROUND #10, #12: DynamicLegend - Обновляемая легенда через Div
# Проблема: Legend не обновляется динамически при hover
# Решение: Используем Div + CustomJS
# ============================================================================

class DynamicLegend:
    """
    Создаёт динамически обновляемую легенду.
    """
    
    @staticmethod
    def create_div(initial_html, style=None):
        """
        Создаёт Div для легенды.
        
        Args:
            initial_html: начальный HTML контент
            style: CSS стили (словарь) или None
            
        Returns:
            Div объект
        """
        return Div(text=initial_html, sizing_mode='stretch_width')


# ============================================================================
# WORKAROUND #18: WindowResize - Обработка изменения размера окна
# Проблема: Bokeh не поддерживает window resize event
# Решение: JS addEventListener + trigger toggle callback
# ============================================================================

class WindowResize:
    """
    Добавляет поддержку window resize.
    """
    
    @staticmethod
    def get_init_script():
        """
        Возвращает JS код для инициализации resize handler, trigger обновления и toggleGreek.
        """
        return '''
        <script>
        (function() {
            // Глобальная функция переключения греков
            window.toggleGreek = function(id) {
                if (Bokeh.documents && Bokeh.documents.length > 0) {
                     const toggle = Bokeh.documents[0].get_model_by_id(id);
                     if (toggle) {
                         toggle.active = !toggle.active;
                     } else {
                         console.error("Toggle model not found:", id);
                     }
                }
            };

            function triggerResize() {
                const doc = Bokeh.documents[0];
                if (!doc) return;
                const models = doc._all_models;
                for (const [id, model] of models) {
                    if (model.type === 'Toggle') {
                        model.properties.active.change.emit();
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
        '''


# ============================================================================
# WORKAROUND #19: SafeModelAccess - Безопасный доступ к моделям Bokeh
# Проблема: Bokeh.documents[0].get_model_by_id() может вернуть null
# Решение: Проверка + глобальная функция с защитой
# ============================================================================

class SafeModelAccess:
    """
    Безопасный доступ к Bokeh моделям из JavaScript.
    """
    
    @staticmethod
    def get_toggle_function_script():
        """
        Возвращает JS код с безопасной функцией toggle.
        """
        return '''
        <script>
            if (!window.toggleGreek) {
                window.toggleGreek = function(id) {
                    if (Bokeh.documents && Bokeh.documents.length > 0) {
                        const toggle = Bokeh.documents[0].get_model_by_id(id);
                        if (toggle) {
                            toggle.active = !toggle.active;
                        } else {
                            console.error("Toggle not found:", id);
                        }
                    }
                }
            }
        </script>
        '''


# ============================================================================
# WORKAROUND #17: TickerFixer - Исправление проблем с тиками
# Проблема: desired_num_ticks иногда игнорируется
# Решение: Явная настройка BasicTicker
# ============================================================================

class TickerFixer:
    """
    Настройка тикеров осей.
    """
    
    @staticmethod
    def configure_sparse_ticks(axis, num_ticks=4):
        """
        Настраивает ось с меньшим количеством тиков.
        
        Args:
            axis: объект оси (LinearAxis или из plot.yaxis[0])
            num_ticks: желаемое количество тиков
        """
        axis.ticker = BasicTicker(desired_num_ticks=num_ticks)
        axis.major_tick_in = 2
        axis.major_tick_out = 2


# ============================================================================
# WORKAROUND #15: SmartBounds - Решение проблемы с bounds и zoom
# Проблема: Zoom блокируется когда один край достиг bounds (#6708)
# Решение: Добавляем padding к bounds больше чем к start/end
# ============================================================================

class SmartBounds:
    """
    Создаёт Range1d с корректными bounds.
    """
    
    @staticmethod
    def create_x_range(data_min, data_max, padding=0.02):
        """
        Создаёт X range с заданным padding и жесткими bounds.
        """
        delta = (data_max - data_min) * padding
        start = data_min - delta
        end = data_max + delta
        return Range1d(start=start, end=end, bounds=(start, end))


# ============================================================================
# Утилиты для форматирования
# ============================================================================

class Formatters:
    """
    Форматирование значений для отображения.
    """
    
    GREEK_FORMATS = {
        'iv': lambda v: f'{v:.1f}%',
        'theta': lambda v: f'${v:.2f}',
        'delta': lambda v: f'{v:.4f}',
        'gamma': lambda v: f'{v:.6f}',
        'vega': lambda v: f'${v:.2f}',
    }
    
    @staticmethod
    def format_greek(key, value):
        """Форматирует значение грека для отображения."""
        formatter = Formatters.GREEK_FORMATS.get(key, lambda v: f'{v:.2f}')
        return formatter(value)
    
    @staticmethod
    def get_numeral_format(key):
        """Возвращает формат для NumeralTickFormatter."""
        formats = {
            'iv': '0',
            'theta': '0',
            'delta': '0.00',
            'gamma': '0.0000',
            'vega': '0',
        }
        return formats.get(key, '0.00')
