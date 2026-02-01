"""
Expirations Component
=====================
CheckButtonGroup for selecting expiration dates.
Implements STICKY selection logic.
"""

import panel as pn
import param


class ExpirationsComponent(pn.viewable.Viewer):
    """Expiration date selector with horizontal scrolling and sticky selection."""
    
    def __init__(self, state, **params):
        super().__init__(**params)
        self.state = state
        
        button_css = """
        /* Focus state - remove default outline */
        .bk-btn:focus {
            outline: none !important;
            box-shadow: none !important;
        }

        /* Default state - Convex 3D effect */
        .bk-btn {
            border-radius: 20px !important;
            padding: 0 10px !important;
            height: 24px !important;
            font-size: 11px !important;
            font-weight: 500 !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            line-height: 1 !important;
            transition: all 0.2s ease;
            margin: 0 2px !important;
            border: 1px solid #e0e0e0 !important;
            color: #495057 !important;
            background-color: white !important;
            box-shadow: rgba(50, 50, 93, 0.15) 0px 2px 4px -1px, rgba(0, 0, 0, 0.1) 0px 1px 2px -1px !important;
        }

        /* Hover state - Lift up */
        .bk-btn:hover:not(.bk-active) {
            transform: translateY(-1px);
            box-shadow: rgba(50, 50, 93, 0.2) 0px 4px 8px -2px, rgba(0, 0, 0, 0.15) 0px 2px 4px -2px !important;
            background-color: #f8f9fa !important;
        }

        /* Active state - Concave/Pressed effect */
        .bk-btn.bk-active {
            background-color: #007bff !important;
            border-color: #007bff !important;
            color: white !important;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.2) !important;
            transform: translateY(0);
        }
        """

        # Create CheckButtonGroup
        self.selector = pn.widgets.CheckButtonGroup(
            name='Expirations',
            options=[],
            value=[],
            button_type='light',
            button_style='outline',
            stylesheets=[button_css],
            align='center'
        )
        
        # Watch state for option changes
        state.param.watch(self._update_options, 'dte_options')
        state.param.watch(self._update_value, 'selected_dtes')
        
        # Link selector changes back to state
        self.selector.param.watch(self._on_selection_change, 'value')
        
        # Initial update
        self._update_options(None)
        self._update_value(None)
    
    def _update_options(self, event):
        """Update available options from state."""
        if not self.state.dte_options:
            self.selector.options = []
            return
        
        # Convert to format expected by CheckButtonGroup
        # {label: value}
        options = {opt['label']: opt['value'] for opt in self.state.dte_options}
        self.selector.options = options
    
    def _update_value(self, event):
        """Update selected values from state."""
        # Only update if different to avoid loops
        if set(self.selector.value) != set(self.state.selected_dtes):
            self.selector.value = self.state.selected_dtes
    
    def _on_selection_change(self, event):
        """Handle user selection changes."""
        # Only update state if different to avoid loops
        if set(event.new) != set(self.state.selected_dtes):
            self.state.selected_dtes = list(event.new)
    
    def __panel__(self):
        # Frame container with scrolling and centering
        return pn.Row(
            self.selector,
            styles={
                'border': '1px solid #e0e0e0',
                'border-radius': '8px',
                'padding': '4px 6px',
                'background': '#ffffff',
                'box-shadow': '0 1px 3px rgba(0,0,0,0.05)',
                'overflow-x': 'auto',
                'min-width': '0' # Enable flex shrinking
            },
            sizing_mode='stretch_width',
            margin=(0, 0, 8, 0),
            align='center',
            height=36
        )
