"""
Dashboard Configuration
=======================
Central configuration for the Neural Analytics Dashboard.
"""

from config.theme import CUSTOM_CSS

# Risk-free rate for crypto options (Deribit uses r=0.0)
RISK_FREE_RATE = 0.0

# Universal Subplot Configuration for Strike Chart
SUBPLOT_CONFIG = {
    'iv': {
        'label': 'VOL', 
        'title': 'IV (%)', 
        'color': CUSTOM_CSS["accent_iv"], 
        'data_col': 'iv', 
        'format': '.1f',
        'is_percent': True
    },
    'theta': {
        'label': 'THETA', 
        'title': 'Theta ($)', 
        'color': '#E67E22', 
        'data_col': 'theta', 
        'format': '.2f',
        'is_percent': False
    }
}


class DashboardConfig:
    """
    Central configuration class for the dashboard.
    Provides easy access to all configuration parameters.
    """
    
    # Constants
    RISK_FREE_RATE = RISK_FREE_RATE
    SUBPLOT_CONFIG = SUBPLOT_CONFIG
    
    @staticmethod
    def get_subplot_config(key):
        """Get subplot configuration by key."""
        return SUBPLOT_CONFIG.get(key)
    
    @staticmethod
    def get_risk_free_rate():
        """Get risk-free rate for option pricing."""
        return RISK_FREE_RATE
