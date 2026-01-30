"""
Services Package
================
Business logic services for options analytics.

This package provides high-level services that orchestrate
various components of the options analytics system.

Services:
---------
- GreeksCalculationService: Hybrid NN+BS Greeks calculation
- StrikeGenerationService: Strike board generation
- OptionsAnalyticsService: Main orchestrator

Example:
--------
>>> from services import GreeksCalculationService, StrikeGenerationService
>>> from services import OptionsAnalyticsService
>>> 
>>> # Initialize services
>>> greeks_service = GreeksCalculationService(model)
>>> strikes_service = StrikeGenerationService()
>>> analytics = OptionsAnalyticsService(greeks_service, strikes_service)
>>> 
>>> # Generate full board
>>> board = analytics.generate_options_board(
...     market_state={'spot': 100000, ...},
...     expiration_date='2024-02-01',
...     anchor_spot=95000,
...     anchor_iv=0.75
... )
"""

from .greeks_calculation_service import GreeksCalculationService
from .strike_generation_service import StrikeGenerationService
from .options_analytics_service import OptionsAnalyticsService

__all__ = [
    'GreeksCalculationService',
    'StrikeGenerationService',
    'OptionsAnalyticsService',
]

__version__ = '1.0.0'
