"""
Time Deck Component
===================
Time slider with marks overlay and navigation buttons.
Implements cyclic navigation (end→0, 0→end).
"""

import panel as pn
import param
import pandas as pd


class TimeDeckComponent(pn.viewable.Viewer):
    """
    Time control dock with:
    - Time label and display
    - Slider with month marks
    - ◀ ▶ navigation buttons
    """
    
    def __init__(self, state, **params):
        super().__init__(**params)
        self.state = state
        
        # Time display
        self.time_display = pn.pane.HTML(
            self.state.time_display,
            css_classes=['time-display']
        )
        state.param.watch(self._update_time_display, 'time_display')
        
        # Slider
        self.slider = pn.widgets.IntSlider(
            name='',
            start=0,
            end=max(1, len(state.timestamps) - 1),
            value=state.time_index,
            show_value=False,
            sizing_mode='stretch_width',
            css_classes=['time-slider']
        )
        
        # Link slider to state
        self.slider.link(state, value='time_index', bidirectional=True)
        
        # Watch for timestamp changes to update slider bounds
        state.param.watch(self._update_slider_bounds, 'timestamps')
        
        # Navigation buttons
        self.btn_back = pn.widgets.Button(
            name='◀',
            button_type='light',
            width=35,
            height=35,
            css_classes=['nav-button']
        )
        self.btn_back.on_click(state.on_back_click)
        
        self.btn_play = pn.widgets.Button(
            name='▶',
            button_type='light', 
            width=35,
            height=35,
            css_classes=['nav-button']
        )
        self.btn_play.on_click(state.on_play_click)
    
    def _update_time_display(self, event):
        """Update time display when state changes."""
        self.time_display.object = self.state.time_display
    
    def _update_slider_bounds(self, event):
        """Update slider bounds when timestamps change."""
        if not self.state.timestamps:
            self.slider.end = 1
            self.slider.value = 0
            self.slider.disabled = True
        else:
            self.slider.end = len(self.state.timestamps) - 1
            self.slider.disabled = False
    
    def _generate_marks_html(self):
        """Generate HTML overlay for slider marks (first day of each month)."""
        if not self.state.timestamps:
            return ''
        
        marks = []
        total = len(self.state.timestamps)
        
        for i, ts in enumerate(self.state.timestamps):
            dt = pd.to_datetime(ts)
            if dt.day == 1:  # Only first day of month
                pct = (i * 100 / (total - 1)) if total > 1 else 0
                marks.append(
                    f'<span style="left:{pct:.1f}%">{dt.strftime("%b")}</span>'
                )
        
        return f'<div class="slider-marks">{"".join(marks)}</div>'
    
    @param.depends('state.timestamps')
    def _marks_overlay(self):
        """Create marks overlay pane."""
        return pn.pane.HTML(
            self._generate_marks_html(),
            sizing_mode='stretch_width',
            margin=(-5, 0, 0, 0)
        )
    
    def __panel__(self):
        # Time label row - compact
        time_label_row = pn.Row(
            pn.pane.HTML('<span class="time-label">TIME SNAPSHOT SELECTOR</span>'),
            self.time_display,
            margin=(0, 0, 3, 0)
        )
        
        # Slider with marks - stretch to fill
        slider_section = pn.Column(
            self.slider,
            self._marks_overlay,
            sizing_mode='stretch_width',
            margin=0
        )
        
        # Navigation buttons - compact
        nav_buttons = pn.Row(
            self.btn_back,
            self.btn_play,
            css_classes=['nav-buttons'],
            margin=(0, 0, 0, 15),
            align='center'
        )
        
        # Main layout - flex grow for slider section
        return pn.Row(
            pn.Column(
                time_label_row,
                slider_section,
                sizing_mode='stretch_width',
                margin=0,
                styles={'flex': '1 1 auto', 'min-width': '0'}  # Flex grow
            ),
            nav_buttons,
            sizing_mode='stretch_width',
            css_classes=['control-dock-inner'],
            styles={'width': '100%'}
        )
