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
        
        # Navigation buttons with icons - NARROWER
        nav_button_css = """
        .bk-btn {
            border: none !important;
            background: transparent !important;
            color: #888888 !important;
            font-size: 16px !important;
            padding: 0px !important; /* Removed padding for narrow look */
            box-shadow: none !important;
            border-radius: 4px !important;
            transition: all 0.15s ease !important;
            min-width: 0 !important; /* Allow narrow width */
        }
        .bk-btn:hover {
            color: #444444 !important;
            background: rgba(0, 0, 0, 0.05) !important;
        }
        .bk-btn:active {
            color: #222222 !important;
            background: rgba(0, 0, 0, 0.1) !important;
        }
        """

        self.btn_back = pn.widgets.Button(
            icon='chevron-left',
            icon_size='1.3em',
            button_type='light',
            width=20, # Much narrower
            height=35,
            stylesheets=[nav_button_css]
        )
        self.btn_back.on_click(state.on_back_click)
        
        self.btn_play = pn.widgets.Button(
            icon='chevron-right',
            icon_size='1.3em',
            button_type='light', 
            width=20, # Much narrower
            height=35,
            stylesheets=[nav_button_css]
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
                    f'<span style="left:{pct:.1f}%">{dt.strftime("%m")}</span>'
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
        # 1. Date Section - Fixed width, Left aligned
        date_section = pn.Row(
            self.time_display,
            width=80, # Fixed width to prevent collapsing
            align='center',
            margin=(5, 5, 0, 5), # Lowered MORE (was 2)
            sizing_mode='fixed' 
        )

        # 2. Slider Section - Takes all remaining space
        slider_section = pn.Column(
            self.slider,
            self._marks_overlay,
            sizing_mode='stretch_width',
            margin=(7, 5, 0, 5), # Reverted to 7 (was 12)
        )
        
        # 3. Navigation Buttons - Fixed width, Right aligned, Tight
        nav_buttons = pn.Row(
            self.btn_back,
            self.btn_play,
            width=50, # Narrow fixed width container
            align='center',
            margin=(0, 5, 0, 0),
            sizing_mode='fixed',
            styles={'gap': '0px'} # Force 0 gap
        )
        
        # Main Layout
        return pn.Row(
            date_section,
            slider_section,
            nav_buttons,
            sizing_mode='stretch_width',
            css_classes=['control-dock-inner'],
            styles={
                'width': '100%', 
                'align-items': 'center', # Vertical centering
                'justify-content': 'space-between' # Distribute elements
            },
            margin=(0, 0, 0, 0) # Reverted top margin to lower the frame height
        )
