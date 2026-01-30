"""
Neural Options Analytics - Panel Application
============================================
Main entry point for the Panel application.
Replicates the Dash application functionality.
"""

import panel as pn
import param
import logging
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure local modules are importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Panel extensions
pn.extension('plotly', 'tabulator', sizing_mode='stretch_width')

# Load CSS
CSS_PATH = os.path.join(BASE_DIR, 'assets', 'styles.css')
if os.path.exists(CSS_PATH):
    pn.config.raw_css.append(open(CSS_PATH).read())
    logger.info("Loaded styles.css")

# Import application components
from state import AppState
from components import HeaderComponent, TimeDeckComponent, ExpirationsComponent, ChartControlsComponent
from views import SmileView, SurfaceView, BoardView, StrikeView


class NeuralOptionsApp(pn.viewable.Viewer):
    """
    Main application class.
    Assembles all components and manages layout.
    """
    
    def __init__(self, **params):
        super().__init__(**params)
        
        # Initialize state
        logger.info("Initializing AppState...")
        self.state = AppState()
        
        # Initialize components
        logger.info("Initializing components...")
        self.header = HeaderComponent(self.state)
        self.expirations = ExpirationsComponent(self.state)
        self.time_deck = TimeDeckComponent(self.state)
        self.chart_controls = ChartControlsComponent(self.state)
        
        # Initialize views
        logger.info("Initializing views...")
        self.smile_view = SmileView(self.state)
        self.surface_view = SurfaceView(self.state)
        self.board_view = BoardView(self.state)
        self.strike_view = StrikeView(self.state)
        
        # Main tabs
        self.tabs = pn.Tabs(
            ('Smile', self.smile_view),
            ('Board', self.board_view),
            ('Surface', self.surface_view),
            ('Strike Chart', self._strike_tab_content()),
            tabs_location='above',
            css_classes=['main-tabs'],
            dynamic=True
        )
        
        # Watch tab changes
        self.tabs.param.watch(self._on_tab_change, 'active')
        
        # Watch state active_tab for programmatic changes
        self.state.param.watch(self._on_state_tab_change, 'active_tab')
        
        logger.info("Application initialized successfully")
    
    def _strike_tab_content(self):
        """Create Strike tab content with chart controls."""
        return pn.Column(
            pn.Row(
                self.chart_controls,
                css_classes=['chart-controls-container'],
                sizing_mode='stretch_width'
            ),
            self.strike_view,
            sizing_mode='stretch_both'
        )
    
    def _on_tab_change(self, event):
        """Handle tab changes from UI."""
        tab_names = ['Smile', 'Board', 'Surface', 'Strike Chart']
        if event.new < len(tab_names):
            new_tab = tab_names[event.new]
            if self.state.active_tab != new_tab:
                self.state.active_tab = new_tab
                
                # Set default strike when switching to Strike Chart
                if new_tab == 'Strike Chart' and not self.state.selected_strike:
                    self.state.set_default_strike()
    
    def _on_state_tab_change(self, event):
        """Handle programmatic tab changes from state."""
        tab_names = ['Smile', 'Board', 'Surface', 'Strike Chart']
        if event.new in tab_names:
            new_idx = tab_names.index(event.new)
            if self.tabs.active != new_idx:
                self.tabs.active = new_idx
    
    def __panel__(self):
        # Main content area - FULL WIDTH, no margins
        main_content = pn.Column(
            # Header row
            self.header,
            
            # Expirations selector
            self.expirations,
            
            # Main tabs with charts
            self.tabs,
            
            sizing_mode='stretch_both',
            css_classes=['main-container'],
            margin=0,  # NO margins - full width
        )
        
        # Control dock (fixed at bottom via CSS)
        control_dock = pn.Row(
            self.time_deck,
            css_classes=['control-dock'],
            sizing_mode='stretch_width',
            margin=0,
        )
        
        # Full page layout
        return pn.Column(
            main_content,
            control_dock,
            sizing_mode='stretch_both',
            margin=0,
            styles={'background-color': '#F5F7F9', 'min-height': '100vh'}
        )


def create_app():
    """Create and return the application."""
    return NeuralOptionsApp()


# For panel serve
app = create_app()

# Servable
app.servable(title="Neural Options Analytics")
