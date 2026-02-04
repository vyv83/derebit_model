"""
ФАЙЛ: strike_chart.py (test2)
ОПИСАНИЕ: Strike Chart - Свечи + Греки. 
ПРИНЦИП: PIXEL PERFECT (V11 Final + Zoom Fix).
"""

import pandas as pd
import numpy as np
import time
import os
from typing import Dict, List, Tuple, Optional, Any

from bokeh.plotting import figure
from bokeh.models import (
    ColumnDataSource, HoverTool, Span, Range1d, LinearAxis, 
    Label, Div, BasicTicker, NumeralTickFormatter, DatetimeTickFormatter,
    CustomJS, Toggle, WheelZoomTool, PanTool, ResetTool
)
from bokeh.layouts import column, row, Spacer
from bokeh.embed import file_html
from bokeh.resources import CDN

# Импорты нашей дизайн-системы
from bokeh_components import (
    ChartTheme, GreekConfig, CONFIG, COLORS, GREEK_ORDER, GREEK_SYMBOLS,
    GREEK_LABELS, GREEK_FORMATS, HeightCalculator, UIFactory, TogglePanel, PANEL_STYLE
)
from bokeh_workarounds import (
    CrosshairSync, AutoScaleY, StickyLabel, LayoutFixer,
    SharedAxisPlot, Candlestick, SmartBounds, WindowResize, SafeModelAccess
)

class StrikeChart:
    def __init__(self, df_ohlc, df_spot, df_greeks, title="BTC-USD Option", visible_greeks=None):
        self.title = title
        self.src_ohlc, self.src_spot, self.src_greeks = self._prepare_sources(df_ohlc, df_spot, df_greeks)
        ts = self.src_ohlc.data['timestamp']
        self.x_range = SmartBounds.create_x_range(min(ts), max(ts), padding=0.003)
        self.p_main = self._create_main_plot()
        self.p_greeks = self._create_greek_plots()
        self.p_axis = SharedAxisPlot.create(self.x_range, self.src_ohlc, height=25)
        self._setup_interactions()
        self.layout = self._finalize_layout()

    def _prepare_sources(self, df_ohlc, df_spot, df_greeks):
        colors = [ChartTheme.CANDLE_UP if close >= open_ else ChartTheme.CANDLE_DOWN for open_, close in zip(df_ohlc['open'], df_ohlc['close'])]
        src_ohlc = ColumnDataSource({**{k: df_ohlc[k].tolist() for k in df_ohlc.columns}, 'color': colors})
        src_spot = ColumnDataSource({'timestamp': df_spot['timestamp'].tolist(), 'value': df_spot['value'].tolist()})
        src_greeks_cds = {key: ColumnDataSource({'timestamp': df_greeks[key]['timestamp'].tolist(), 'value': df_greeks[key]['value'].tolist()}) for key in GREEK_ORDER if key in df_greeks}
        return src_ohlc, src_spot, src_greeks_cds

    def _create_main_plot(self):
        lo, hi = min(self.src_ohlc.data['low']), max(self.src_ohlc.data['high'])
        pad = (hi - lo) * CONFIG.ohlc_y_padding
        p = figure(x_axis_type='datetime', x_range=self.x_range, y_range=Range1d(lo - pad, hi + pad), height=400, sizing_mode='stretch_width', tools='', toolbar_location=None, background_fill_color=ChartTheme.BG, min_border_left=CONFIG.min_border_left, min_border_right=CONFIG.min_border_right, min_border_top=10, min_border_bottom=0)
        
        # Tools Fix (Multi-component Zoom & Drag)
        wheel_zoom = WheelZoomTool(maintain_focus=False)
        p.add_tools(wheel_zoom, PanTool(), ResetTool())
        p.toolbar.active_scroll = wheel_zoom
        
        Candlestick.render(p, self.src_ohlc, CONFIG.candle_width_ratio)
        
        # Axis Styling (Gray #CCCCCC)
        p.yaxis[0].axis_label = 'Option Price ($)'
        p.yaxis[0].axis_label_text_color = ChartTheme.TEXT_SECONDARY
        p.yaxis[0].major_label_text_color = ChartTheme.TEXT_SECONDARY
        p.yaxis[0].major_label_text_font_size = '7pt'
        p.yaxis[0].axis_label_text_font_size = '8pt'
        p.yaxis[0].axis_label_text_font_style = 'bold'
        p.yaxis[0].axis_line_color = COLORS['axis']
        p.yaxis[0].major_tick_line_color = COLORS['axis']
        p.yaxis[0].minor_tick_line_color = None
        p.yaxis[0].major_tick_in, p.yaxis[0].major_tick_out = 2, 2
        p.yaxis[0].ticker = BasicTicker(desired_num_ticks=5)

        # Spot Axis (Right)
        s_vals = self.src_spot.data['value']
        smin, smax = min(s_vals), max(s_vals)
        spad = (smax - smin) * CONFIG.spot_y_padding
        p.extra_y_ranges = {'spot': Range1d(smin - spad, smax + spad)}
        spot_axis = LinearAxis(y_range_name='spot', axis_label='Spot $')
        spot_axis.axis_label_text_color = ChartTheme.TEXT_SECONDARY
        spot_axis.major_label_text_color = ChartTheme.TEXT_SECONDARY
        spot_axis.major_label_text_font_size = '7pt'
        spot_axis.axis_label_text_font_size = '8pt'
        spot_axis.axis_label_text_font_style = 'bold'
        spot_axis.axis_line_color = COLORS['axis']
        spot_axis.major_tick_line_color = COLORS['axis']
        spot_axis.minor_tick_line_color = None
        spot_axis.major_tick_in, spot_axis.major_tick_out = 2, 2
        spot_axis.ticker = BasicTicker(desired_num_ticks=4)
        p.add_layout(spot_axis, 'right')
        
        p.line('timestamp', 'value', source=self.src_spot, color=ChartTheme.SPOT, line_width=1.5, line_dash='dashed', y_range_name='spot')
        
        last_close, last_spot = self.src_ohlc.data['close'][-1], self.src_spot.data['value'][-1]
        p.add_layout(Span(location=last_close, dimension='width', line_color=ChartTheme.CANDLE_UP, line_dash='dotted', line_width=1.5))
        p.add_layout(Span(location=last_spot, dimension='width', line_color=ChartTheme.SPOT, line_dash='dotted', line_width=1, y_range_name='spot'))
        
        StickyLabel.create_left(p, last_close, f'{last_close:.2f}', ChartTheme.TEXT_SECONDARY)
        StickyLabel.create_right(p, last_spot, f'{last_spot:.0f}', ChartTheme.TEXT_SECONDARY, y_range_name='spot')
        
        AutoScaleY.attach_to_plot(p, self.src_ohlc, ['high', 'low'], CONFIG.autoscale_padding)
        AutoScaleY.attach_to_extra_y_range(p, 'spot', self.src_spot, ['value'], CONFIG.spot_y_padding)
        p.xaxis.visible = False
        p.grid.grid_line_alpha = ChartTheme.GRID_ALPHA
        p.grid.grid_line_color = COLORS['grid']
        p.outline_line_color = None
        return p

    def _create_greek_plots(self):
        plots = {}
        for key in GREEK_ORDER:
            if key not in self.src_greeks: continue
            src = self.src_greeks[key]
            vals = src.data['value']
            vmin, vmax = min(vals), max(vals)
            pad = (vmax - vmin) * CONFIG.greek_y_padding if vmax != vmin else 1
            color = ChartTheme.get_greek_color(key)
            
            p = figure(x_axis_type='datetime', x_range=self.x_range, y_range=Range1d(vmin - pad, vmax + pad), height=80, sizing_mode='stretch_width', tools='', toolbar_location=None, background_fill_color=ChartTheme.BG, min_border_left=CONFIG.min_border_left, min_border_right=45, min_border_top=3, min_border_bottom=0)
            
            # Tools Sync Fix
            p.add_tools(WheelZoomTool(maintain_focus=False), PanTool())
            
            p.varea(x='timestamp', y1='value', y2=0, source=src, fill_color=color, fill_alpha=ChartTheme.AREA_FILL_ALPHA)
            p.line('timestamp', 'value', source=src, color=color, line_width=2.5)
            
            # Left Axis
            p.yaxis.axis_line_color = COLORS['axis']
            p.yaxis.major_tick_line_color = COLORS['axis']
            p.yaxis.minor_tick_line_color = None
            p.yaxis.major_tick_in, p.yaxis.major_tick_out = 2, 2
            p.yaxis.major_label_text_font_size = '7pt'
            p.yaxis.major_label_text_color = '#888888'
            p.yaxis.ticker = BasicTicker(desired_num_ticks=4)
            p.yaxis.formatter = NumeralTickFormatter(format=GREEK_FORMATS.get(key, '0.0'))
            
            # Right Axis (Label Only)
            p.extra_y_ranges = {"label_range": p.y_range}
            label_axis = LinearAxis(y_range_name="label_range", axis_label=GREEK_LABELS.get(key, key.upper()))
            label_axis.axis_label_text_color = color
            label_axis.axis_label_text_font_size = '8pt'
            label_axis.axis_label_text_font_style = 'bold'
            label_axis.major_label_text_font_size = '0pt'
            label_axis.major_tick_line_color = COLORS['axis']
            label_axis.major_tick_in, label_axis.major_tick_out = 2, 2
            label_axis.minor_tick_line_color = None
            label_axis.axis_line_color = COLORS['axis']
            p.add_layout(label_axis, 'right')
            
            last_val = vals[-1]
            p.add_layout(Span(location=last_val, dimension='width', line_color=color, line_dash='dotted', line_width=1.5))
            StickyLabel.create_right(p, last_val, GreekConfig.format_value(key, last_val), color)
            AutoScaleY.attach_to_plot(p, src, ['value'], CONFIG.greek_y_padding)
            p.xaxis.visible = False
            p.grid.grid_line_alpha = ChartTheme.GRID_ALPHA
            p.grid.grid_line_color = COLORS['grid']
            p.outline_line_color = None
            plots[key] = p
        return plots

    def _setup_interactions(self):
        self.toggles = TogglePanel.create_toggles()
        self.controls_div = TogglePanel.create_html_controls(self.toggles)
        self.all_plots = [self.p_main] + [self.p_greeks[k] for k in GREEK_ORDER if k in self.p_greeks] + [self.p_axis]
        self.all_spans = CrosshairSync.create_spans(self.all_plots, color=ChartTheme.CROSSHAIR)
        self.legend_div = Div(text=f'<div style="{PANEL_STYLE}"><span>...</span></div>', sizing_mode='stretch_width', styles={'margin-left': '20px'})
        
        hover_cb = CustomJS(args=dict(spans=self.all_spans, legend=self.legend_div, src_ohlc=self.src_ohlc, src_spot=self.src_spot, src_iv=self.src_greeks.get('iv'), src_theta=self.src_greeks.get('theta'), src_delta=self.src_greeks.get('delta'), src_gamma=self.src_greeks.get('gamma'), src_vega=self.src_greeks.get('vega'), colors={'call':COLORS['call'], 'put':COLORS['put'], 'spot':COLORS['spot'], 'iv':COLORS['iv'], 'theta':COLORS['theta'], 'delta':COLORS['delta'], 'gamma':COLORS['gamma'], 'vega':COLORS['vega']}, style=PANEL_STYLE, toggles=self.toggles), 
            code="""
            const geometry = cb_data.geometry; if (!geometry) return; const x = geometry.x;
            for (let i = 0; i < spans.length; i++) { spans[i].location = x; if (i === 0 || i === spans.length - 1) spans[i].visible = true; else spans[i].visible = toggles[i-1].active; }
            const ts = src_ohlc.data.timestamp; let idx = 0, minDist = Infinity;
            for (let i = 0; i < ts.length; i++) { let d = Math.abs(ts[i] - x); if (d < minDist) { minDist = d; idx = i; } }
            const o = src_ohlc.data.open[idx].toFixed(2), h = src_ohlc.data.high[idx].toFixed(2), l = src_ohlc.data.low[idx].toFixed(2), c = src_ohlc.data.close[idx].toFixed(2), s = src_spot.data.value[idx].toFixed(0);
            let html = `<div style="${style}">`;
            html += `<span style="color:${colors.call}; font-weight:700;">O:${o} H:${h} L:${l} C:${c}</span>`;
            html += `<span style="color:${colors.spot}; font-weight:700;">Spot: $${s}</span>`;
            const gks = ['iv','theta','delta','gamma','vega']; const syms = {iv:'IV', theta:'Θ', delta:'Δ', gamma:'Γ', vega:'ν'}; const srcs = {iv:src_iv, theta:src_theta, delta:src_delta, gamma:src_gamma, vega:src_vega};
            for (let i=0; i<5; i++) { let k = gks[i]; if (srcs[k] && toggles[i].active) { let val = srcs[k].data.value[idx]; let fmt = (k==='gamma') ? val.toFixed(6) : (k==='delta' ? val.toFixed(4) : val.toFixed(2)); if (k==='iv') fmt += '%'; html += `<span style="color:${colors[k]}; font-weight:600;">${syms[k]}:${fmt}</span>`; } }
            html += `</div>`; legend.text = html;
            """)
        hide_cb = CrosshairSync.create_hide_callback(self.all_spans)
        show_cb = CustomJS(args=dict(spans=self.all_spans), code="for (let s of spans) s.visible = true;")
        for p in self.all_plots:
            p.add_tools(HoverTool(tooltips=None, mode='vline', callback=hover_cb))
            p.js_on_event('mouseleave', hide_cb)
            p.js_on_event('mouseenter', show_cb)
        
        update_html_cb = TogglePanel.create_update_callback(self.controls_div, self.toggles)
        for t in self.toggles: t.js_on_change('active', update_html_cb)

    def _finalize_layout(self):
        greek_plots = [self.p_greeks[k] for k in GREEK_ORDER if k in self.p_greeks]
        # Manual configuration to avoid LayoutFixer's aggressive resets
        all_plots = [self.p_main] + greek_plots + [self.p_axis]
        for p in all_plots:
            p.min_border_left = CONFIG.min_border_left
            p.min_border_right = CONFIG.min_border_right
            p.margin = 0
            p.min_border_top = 0
            if p == self.p_axis:
                p.min_border_bottom = 25 # Pushes axis labels UP
            else:
                p.min_border_bottom = 0
                p.xaxis.visible = False

        # JS Manager for precise height control
        layout_manager = CustomJS(args=dict(main=self.p_main, greeks=greek_plots, axis=self.p_axis, toggles=self.toggles), 
            code="""
            window.updateLayout = () => {
                const overhead = 55;
                const axisH = 25;
                const totalH = window.innerHeight - overhead - axisH;
                if (totalH < 200) return;
                
                let activeGreeks = []; 
                for (let i = 0; i < greeks.length; i++) { 
                    const act = toggles[i].active; 
                    greeks[i].visible = act; 
                    if (act) activeGreeks.push(greeks[i]); 
                }
                
                const count = activeGreeks.length; 
                let greekArea = 0; 
                for (let i = 0; i < count; i++) { greekArea += 0.25 / Math.pow(2, i); }
                
                let mainH = (count === 0) ? totalH : Math.floor(totalH * (1 - greekArea));
                main.height = mainH; 
                let remH = totalH - mainH;
                for (let i = 0; i < count; i++) { 
                    let h = (i === count - 1) ? remH : Math.floor(remH / (count - i)); 
                    activeGreeks[i].height = h; 
                    remH -= h; 
                }
                axis.height = axisH;
                window.dispatchEvent(new Event('resize')); // Force bokeh layout recompute
            };
            if (!window._obs) { 
                window._obs = new ResizeObserver(window.updateLayout); 
                window._obs.observe(document.body); 
            }
            window.updateLayout();
            """)
        for t in self.toggles: t.js_on_change('active', layout_manager)
        self.p_main.js_on_change('inner_width', layout_manager)
        
        control_panel = row(self.controls_div, Spacer(width=20), self.legend_div, sizing_mode='stretch_width', styles={'align-items': 'center', 'height': '46px', 'padding': '0 10px', 'background': '#fff', 'border-bottom': '1px solid #eee'})
        chart_stack = column(self.p_main, *greek_plots, self.p_axis, sizing_mode='stretch_both', spacing=0)
        
        layout = column(control_panel, chart_stack, row(self.toggles, visible=False), sizing_mode='stretch_both')
        return layout

    def to_html(self):
        extra_head = f"<style>* {{ font-family: 'SF Mono', Monaco, monospace !important; }} html, body {{ margin: 0; padding: 0; width: 100vw; height: 100vh; overflow: hidden; background: #fff; }} .bk-root {{ height: 100vh !important; width: 100vw !important; }} .bk-tooltip {{ font-variant-numeric: tabular-nums; }}</style>{WindowResize.get_init_script()}{SafeModelAccess.get_toggle_function_script()}"
        html = file_html(self.layout, CDN, self.title)
        return html.replace('</head>', f'{extra_head}</head>')

    def save(self, filepath):
        with open(filepath, 'w', encoding='utf-8') as f: f.write(self.to_html())
        return filepath
