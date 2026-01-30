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
        
        # Create CheckButtonGroup
        self.selector = pn.widgets.CheckButtonGroup(
            name='Expirations',
            options=[],
            value=[],
            button_type='default',
            css_classes=['dte-selector']
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
        return pn.Row(
            self.selector,
            css_classes=['dte-selector-container'],
            sizing_mode='stretch_width',
            margin=0,
            height=34  # Compact height
        )
