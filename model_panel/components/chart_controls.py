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
        
        # Create toggle buttons - COMPACT style
        self.btn_iv = pn.widgets.Button(
            name=self._get_button_label('iv'),
            button_type='light',
            width=70,  # Compact width
            css_classes=['toggle-btn', 'toggle-btn-iv', self._get_active_class('iv')]
        )
        
        self.btn_theta = pn.widgets.Button(
            name=self._get_button_label('theta'),
            button_type='light',
            width=85,  # Compact width
            css_classes=['toggle-btn', 'toggle-btn-theta', self._get_active_class('theta')]
        )
        
        # Click handlers
        self.btn_iv.on_click(self._toggle_iv)
        self.btn_theta.on_click(self._toggle_theta)
        
        # Watch state for changes
        state.param.watch(self._update_button_visuals, 'visible_charts')
    
    def _get_button_label(self, key):
        """Get button label with ON/OFF status."""
        config = SUBPLOT_CONFIG[key]
        is_active = key in self.state.visible_charts
        return f"{config['label']} {'ON' if is_active else 'OFF'}"
    
    def _get_active_class(self, key):
        """Get CSS class for active/inactive state."""
        return 'active' if key in self.state.visible_charts else 'inactive'
    
    def _toggle_iv(self, event):
        """Toggle IV visibility."""
        self.state.toggle_iv()
    
    def _toggle_theta(self, event):
        """Toggle Theta visibility."""
        self.state.toggle_theta()
    
    def _update_button_visuals(self, event):
        """Update button labels and styles when state changes."""
        # IV button
        is_iv_active = 'iv' in self.state.visible_charts
        self.btn_iv.name = f"{SUBPLOT_CONFIG['iv']['label']} {'ON' if is_iv_active else 'OFF'}"
        self.btn_iv.css_classes = [
            'toggle-btn', 'toggle-btn-iv', 
            'active' if is_iv_active else 'inactive'
        ]
        
        # Theta button
        is_theta_active = 'theta' in self.state.visible_charts
        self.btn_theta.name = f"{SUBPLOT_CONFIG['theta']['label']} {'ON' if is_theta_active else 'OFF'}"
        self.btn_theta.css_classes = [
            'toggle-btn', 'toggle-btn-theta',
            'active' if is_theta_active else 'inactive'
        ]
    
    def __panel__(self):
        return pn.Row(
            self.btn_iv,
            self.btn_theta,
            css_classes=['chart-controls'],
            margin=0
        )
