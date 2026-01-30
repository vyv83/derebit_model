"""
Chart Controls Component
========================
Toggle buttons for IV and Theta subplots.
Implements two-way synchronization with state.
"""

import panel as pn
import param

# Subplot configuration (from config/dashboard_config.py)
SUBPLOT_CONFIG = {
    'iv': {'label': 'VOL', 'color': '#9B59B6'},
    'theta': {'label': 'THETA', 'color': '#E67E22'}
}


class ChartControlsComponent(pn.viewable.Viewer):
    """
    Toggle buttons for chart subplots (IV, Theta).
    Two-way sync: button clicks → state, state → button visuals.
    """
    
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
            padding: 4px 16px !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            transition: all 0.2s ease;
            margin: 0 4px !important;
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

        # CheckButtonGroup component
        self.toggles = pn.widgets.CheckButtonGroup(
            name='Chart Toggles',
            options=['VOL', 'THETA'],
            value=self._get_current_selection(),
            button_type='light',
            button_style='outline',
            sizing_mode='fixed',
            stylesheets=[button_css],
            align='center'
        )
        
        # Watch for UI changes -> Update State
        self.toggles.param.watch(self._on_toggle_change, 'value')
        
        # Watch state for changes -> Update UI
        state.param.watch(self._update_ui_from_state, 'visible_charts')
    
    def _get_current_selection(self):
        """Convert state set to list of labels."""
        selection = []
        if 'iv' in self.state.visible_charts:
            selection.append('VOL')
        if 'theta' in self.state.visible_charts:
            selection.append('THETA')
        return selection
    
    def _on_toggle_change(self, event):
        """Update state based on toggles (UI -> State)."""
        new_selection = event.new
        
        # Sync IV
        if 'VOL' in new_selection and 'iv' not in self.state.visible_charts:
            self.state.toggle_iv() # Turn ON
        elif 'VOL' not in new_selection and 'iv' in self.state.visible_charts:
            self.state.toggle_iv() # Turn OFF
            
        # Sync Theta
        if 'THETA' in new_selection and 'theta' not in self.state.visible_charts:
            self.state.toggle_theta() # Turn ON
        elif 'THETA' not in new_selection and 'theta' in self.state.visible_charts:
            self.state.toggle_theta() # Turn OFF

    def _update_ui_from_state(self, event):
        """Update UI based on state changes (State -> UI)."""
        # Avoid circular updates if values match
        current_ui_value = set(self.toggles.value)
        new_state_value = set(self._get_current_selection())
        
        if current_ui_value != new_state_value:
            self.toggles.value = list(new_state_value)
    
    def __panel__(self):
        return pn.Row(
            self.toggles,
            styles={
                'border': '1px solid #e0e0e0',
                'border-radius': '8px',
                'padding': '6px 12px',
                'background': '#ffffff',
                'box-shadow': '0 1px 3px rgba(0,0,0,0.05)'
            },
            align='center',
            height=50,
            margin=0
        )
