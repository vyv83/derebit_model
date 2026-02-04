"""
ФАЙЛ: bokeh_workarounds.py (test2)
ОПИСАНИЕ: Слой воркаундов для Bokeh. Все 19 фиксов сохранены.
ПРИНЦИП: PIXEL PERFECT.
"""

from bokeh.models import (
    CustomJS, Span, Range1d, LinearAxis, Label, Div, Toggle,
    HoverTool, BasicTicker, NumeralTickFormatter, ColumnDataSource
)
from bokeh.plotting import figure
from bokeh.models.formatters import DatetimeTickFormatter

class CrosshairSync:
    @staticmethod
    def create_spans(plots, color='#546E7A', line_width=1, line_alpha=0.7):
        spans = []
        for p in plots:
            span = Span(location=0, dimension='height', line_color=color,
                        line_width=line_width, line_alpha=line_alpha, visible=False)
            p.add_layout(span)
            spans.append(span)
        return spans

    @staticmethod
    def create_callback(spans):
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
        return CustomJS(args=dict(spans=spans), code="""
            for (let span of spans) span.visible = false;
        """)

class AutoScaleY:
    @staticmethod
    def create_callback(y_range, x_range, source, y_fields, padding=0.10):
        fields_js = ', '.join([f"'{f}'" for f in y_fields])
        return CustomJS(args=dict(y_range=y_range, x_range=x_range, src=source, padding=padding), 
            code=f"""
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

    @staticmethod
    def attach_to_plot(plot, source, y_fields, padding=0.10):
        cb = AutoScaleY.create_callback(plot.y_range, plot.x_range, source, y_fields, padding)
        plot.x_range.js_on_change('start', cb)
        plot.x_range.js_on_change('end', cb)

    @staticmethod
    def attach_to_extra_y_range(plot, range_name, source, y_fields, padding=0.10):
        cb = AutoScaleY.create_callback(plot.extra_y_ranges[range_name], plot.x_range, source, y_fields, padding)
        plot.x_range.js_on_change('start', cb)
        plot.x_range.js_on_change('end', cb)

class StickyLabel:
    @staticmethod
    def create_right(plot, y_value, text, color='#888888', y_range_name=None):
        kwargs = dict(x=plot.x_range.end, y=y_value, text=f" {text} ", text_font_size='10px',
                      text_color=color, text_align='right', x_offset=-4, y_offset=-6,
                      border_line_color=color, border_line_alpha=0.5,
                      background_fill_color='#ffffff', background_fill_alpha=0.9)
        if y_range_name: kwargs['y_range_name'] = y_range_name
        label = Label(**kwargs)
        plot.add_layout(label)
        cb = CustomJS(args=dict(label=label, x_range=plot.x_range), code="label.x = x_range.end;")
        plot.x_range.js_on_change('end', cb)
        return label

    @staticmethod
    def create_left(plot, y_value, text, color='#888888'):
        label = Label(x=plot.x_range.start, y=y_value, text=f" {text} ", text_font_size='10px',
                      text_color=color, text_align='left', x_offset=4, y_offset=-6,
                      border_line_color=color, border_line_alpha=0.5,
                      background_fill_color='#ffffff', background_fill_alpha=0.9)
        plot.add_layout(label)
        cb = CustomJS(args=dict(label=label, x_range=plot.x_range), code="label.x = x_range.start;")
        plot.x_range.js_on_change('start', cb)
        return label

class SharedAxisPlot:
    @staticmethod
    def create(x_range, source, height=25, min_border_left=50, min_border_right=50):
        p = figure(height=height, sizing_mode='stretch_width', x_axis_type='datetime',
                   x_range=x_range, min_border_left=min_border_left, min_border_right=min_border_right,
                   min_border_top=0, min_border_bottom=25, tools='', toolbar_location=None,
                   outline_line_color=None, background_fill_alpha=0, border_fill_alpha=0)
        p.line('timestamp', 'close', source=source, alpha=0)
        p.yaxis.visible = True
        p.yaxis.axis_line_color = '#CCCCCC'
        p.yaxis.major_tick_line_color = '#CCCCCC'
        p.yaxis.minor_tick_line_color = None
        p.yaxis.major_label_text_font_size = '0pt'
        p.yaxis.major_label_text_color = None
        p.yaxis.major_tick_in = 2
        p.yaxis.major_tick_out = 2
        
        p.xgrid.visible = False
        p.ygrid.visible = False
        
        p.xaxis.axis_line_color = '#CCCCCC'
        p.xaxis.major_tick_line_color = '#CCCCCC'
        p.xaxis.major_label_text_font_size = '7pt'
        p.xaxis.major_label_text_color = '#888888'
        p.xaxis.major_tick_in = 2
        p.xaxis.major_tick_out = 2
        p.xaxis.formatter = DatetimeTickFormatter(days='%d %b', months='%b %Y')
        p.margin = 0
        return p

class WindowResize:
    @staticmethod
    def get_init_script():
        return """
        <script>
        window.addEventListener('resize', function() {
            if (window.Bokeh) {
                for (let doc of Bokeh.documents) {
                    doc.compute_layout();
                }
            }
        });
        </script>
        """

class SafeModelAccess:
    @staticmethod
    def get_toggle_function_script():
        return """
        <script>
        window.toggleGreek = function(id) {
            for (let doc of Bokeh.documents) {
                let m = doc.get_model_by_id(id);
                if (m) {
                    m.active = !m.active;
                    break;
                }
            }
        };
        </script>
        """

class Candlestick:
    DAY_MS = 24 * 60 * 60 * 1000
    @staticmethod
    def render(plot, source, candle_width_ratio=0.6):
        width = candle_width_ratio * Candlestick.DAY_MS
        plot.segment('timestamp', 'low', 'timestamp', 'high', source=source, color='color', line_width=1)
        plot.vbar('timestamp', width, 'close', 'open', source=source, fill_color='color', line_color='color')

class SmartBounds:
    @staticmethod
    def create_x_range(data_min, data_max, padding=0.02):
        delta = (data_max - data_min) * padding
        return Range1d(start=data_min - delta, end=data_max + delta, bounds=(data_min - delta, data_max + delta))

class LayoutFixer:
    @staticmethod
    def configure_for_stack(plots, min_border_left=50, min_border_right=50):
        for p in plots:
            p.min_border_left, p.min_border_right = min_border_left, min_border_right
            p.min_border_top, p.min_border_bottom, p.margin = 0, 0, 0
