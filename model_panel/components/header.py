"""
Header Component
================
Application header with title, currency/period selectors, and KPI bar.
"""

import panel as pn
import param


class HeaderComponent(pn.viewable.Viewer):
    """Header row with title, selectors, and KPIs."""
    
    def __init__(self, state, **params):
        super().__init__(**params)
        self.state = state
        
        # Currency selector
        self.currency_selector = pn.widgets.RadioButtonGroup(
            name='Currency',
            options=['BTC', 'ETH'],
            value=state.currency,
            button_type='default',
            css_classes=['currency-selector']
        )
        self.currency_selector.link(state, value='currency')
        
        # Period selector  
        self.period_selector = pn.widgets.Select(
            name='Period',
            options=['2021', '2022', '2023', '2024', '2025'],
            value=state.period,
            width=100,
            css_classes=['period-selector']
        )
        self.period_selector.link(state, value='period')
        
        # Link state KPIs to display
        state.param.watch(self._update_kpis, ['kpi_spot', 'kpi_atm_iv', 'kpi_hv'])
    
    def _update_kpis(self, event):
        """Update KPI displays when state changes."""
        self._kpi_spot_value.object = self.state.kpi_spot
        self._kpi_iv_value.object = self.state.kpi_atm_iv
        self._kpi_hv_value.object = self.state.kpi_hv
    
    @param.depends()
    def _build_kpi_bar(self):
        """Build the KPI bar with PRICE, IV ATM, HV 30D."""
        # PRICE
        self._kpi_spot_value = pn.pane.HTML(
            self.state.kpi_spot,
            css_classes=['kpi-value']
        )
        kpi_price = pn.Column(
            pn.pane.HTML('<div class="kpi-label">PRICE</div>'),
            self._kpi_spot_value,
            css_classes=['kpi-item'],
            margin=0
        )
        
        # IV ATM
        self._kpi_iv_value = pn.pane.HTML(
            self.state.kpi_atm_iv,
            css_classes=['kpi-value']
        )
        kpi_iv = pn.Column(
            pn.pane.HTML('<div class="kpi-label">IV ATM</div>'),
            self._kpi_iv_value,
            css_classes=['kpi-item'],
            margin=0
        )
        
        # HV 30D
        self._kpi_hv_value = pn.pane.HTML(
            self.state.kpi_hv,
            css_classes=['kpi-value']
        )
        kpi_hv = pn.Column(
            pn.pane.HTML('<div class="kpi-label">HV 30D</div>'),
            self._kpi_hv_value,
            css_classes=['kpi-item'],
            margin=0
        )
        
        return pn.Row(
            kpi_price, kpi_iv, kpi_hv,
            css_classes=['kpi-bar'],
            margin=0
        )
    
    def __panel__(self):
        # Title section - compact
        title_section = pn.Column(
            pn.pane.HTML('<h1 class="app-title">NEURAL OPTIONS ANALYTICS</h1>'),
            pn.pane.HTML('<p class="app-subtitle">Hybrid NN+BS Greeks Engine</p>'),
            margin=0,
            styles={'line-height': '1.2'}
        )
        
        # Currency selector with label
        currency_section = pn.Column(
            pn.pane.HTML('<label class="selector-label">CURRENCY</label>'),
            self.currency_selector,
            margin=(0, 10, 0, 0)
        )
        
        # Period selector with label
        period_section = pn.Column(
            pn.pane.HTML('<label class="selector-label">PERIOD</label>'),
            self.period_selector,
            margin=(0, 10, 0, 0)
        )
        
        # Spacer to push KPIs to right
        spacer = pn.Spacer(sizing_mode='stretch_width')
        
        return pn.Row(
            title_section,
            currency_section,
            period_section,
            spacer,
            self._build_kpi_bar(),
            css_classes=['header-row'],
            sizing_mode='stretch_width',
            margin=(5, 0)  # Compact vertical margin
        )
