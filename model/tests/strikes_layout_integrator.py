
from bokeh.models import CustomJS, DatetimeTickFormatter, ColumnDataSource
from bokeh.plotting import figure
from bokeh.layouts import column

def create_integrated_axis_plot(shared_x_range, config, colors, source):
    """
    Создает статичный график оси времени, стилизованный под основной проект.
    """
    # Высота оси 25px - компактный вариант
    axis_h = 25 
    
    p = figure(
        height=axis_h,
        sizing_mode='stretch_width',
        x_axis_type='datetime',
        x_range=shared_x_range,
        min_border_left=config.min_border_left,
        min_border_right=config.min_border_right,
        min_border_top=0,
        min_border_bottom=25, # Ровно столько, чтобы влезли метки дат
        tools='',
        toolbar_location=None,
        outline_line_color=None,
        background_fill_alpha=0,
        border_fill_alpha=0
    )
    
    # Невидимый рендерер по реальным данным - заставляет ось появиться в нужном масштабе
    p.line('timestamp', 'close', source=source, alpha=0, line_width=0)
    
    # Левая линия (продолжение оси Y)
    p.yaxis.visible = True
    p.yaxis.axis_line_color = '#CCCCCC'
    p.yaxis.major_tick_line_color = None
    p.yaxis.minor_tick_line_color = None
    p.yaxis.major_label_text_font_size = '0pt'
    p.yaxis.major_label_text_color = None
    p.xgrid.visible = False
    p.ygrid.visible = False
    
    # Цвета осей из test_bokeh.py (обычно #CCCCCC)
    axis_color = '#CCCCCC' 
    p.xaxis.axis_line_color = axis_color
    p.xaxis.major_tick_line_color = axis_color
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

def get_layout_manager_js(main_plot, greek_plots, toggles, status_div, fixed_overhead, axis_height):
    """
    Возвращает JS-коллбэк для управления высотами.
    Не содержит стилей, только математику распределения пикселей.
    """
    return CustomJS(
        args=dict(
            main_plot=main_plot,
            greek_plots=greek_plots,
            toggles=toggles,
            status_div=status_div,
            FIXED_H=fixed_overhead,
            AXIS_H=axis_height
        ),
        code="""
        const totalH = window.innerHeight - FIXED_H - AXIS_H;
        
        const activeIdxs = [];
        for (let i = 0; i < toggles.length; i++) {
            if (toggles[i].active) activeIdxs.push(i);
        }
        const count = activeIdxs.length;
        
        // Расчет доли греков по формуле
        let greekPct = 0;
        for (let i = 0; i < count; i++) {
            greekPct += 0.25 / Math.pow(2, i);
        }
        
        // Главный график
        let mainH = (count === 0) ? totalH : Math.floor(totalH * (1 - greekPct));
        main_plot.height = mainH;
        main_plot.change.emit();
        
        // Греки
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
        
        // Обновление статуса (текст можно настроить снаружи)
        if (status_div) {
            status_div.text = `<div style="padding:5px 10px; font-family:sans-serif; font-size:11px; color:#666;">` +
                             `Active Greeks: <b>${count}</b></div>`;
        }
        """
    )

def finalize_layout(main_plot, greek_plots, axis_plot, other_components=None):
    """
    Собирает финальный stack и обнуляет отступы для всех элементов.
    """
    all_plots = [main_plot] + list(greek_plots) + [axis_plot]
    chart_stack = column(*all_plots, sizing_mode='stretch_both', spacing=0)
    
    # Обнуляем margin у всех графиков для идеальной стыковки
    for p in all_plots:
        p.margin = 0
        p.min_border_bottom = 0
        p.min_border_top = 0
        # Скрываем оси только на графиках данных
        if p != axis_plot:
            p.xaxis.visible = False
        else:
            p.xaxis.visible = True
            p.min_border_bottom = 25 # Чуть выше, чтобы не обрезало снизу
        
    chart_stack.margin = 0
    return chart_stack
