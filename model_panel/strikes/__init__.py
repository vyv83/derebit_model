"""
Strikes Package
================
Modular Deribit strikes generation engine (V5 Ultimate).

This package implements the complete strikes generation algorithm:
1. Config - All calibration parameters
2. GridEngine - Adaptive strike grid foundation
3. Distributions - Parabolic (volatility-based) distribution
4. Magnets - Layer-based filtering and snapping
5. Simulation - Contract evolution over time
6. Expirations - Deribit-standard expiration logic

Public API
----------
Primary Functions:
- simulate_board_evolution(): Main production interface
- generate_deribit_expirations(): Generate expiration dates
- get_birth_date(): Calculate contract birth date

Classes:
- ContractDNA: Immutable contract parameters
- GridEngine: Strike grid generator
- AlgoConfig: Configuration dataclass

Configuration:
- CONFIG: Global configuration instance

Example
-------
>>> from strikes import ContractDNA, simulate_board_evolution, CONFIG
>>> 
>>> # Define contract DNA
>>> dna = ContractDNA(
...     anchor_spot=100000.0,  # BTC at 100k
...     anchor_iv=0.75,         # 75% IV
...     birth_dte=90            # 3 months to expiration
... )
>>> 
>>> # Simulate evolution
>>> final_board, history = simulate_board_evolution(
...     dna=dna,
...     price_history=[100000, 101000, 99000, ...],
...     iv_history=[0.75, 0.76, 0.74, ...],
...     target_day=30
... )
>>> 
>>> # Convert indices to strike prices
>>> from strikes import GridEngine
>>> table = GridEngine.generate_table()
>>> strikes = [table[idx] for idx in final_board]
"""

# ===== Configuration =====
from .config import AlgoConfig, CONFIG

# ===== Core Components =====
from .grid_engine import GridEngine
from .distributions import parabolic_distribution, parabolic_distribution_cached
from .magnets import (
    get_current_min_step,
    LayerBoundaries,
    compute_layer_boundaries,
    apply_magnet_filter,
    filter_new_strikes_only
)
from .simulation import (
    ContractDNA,
    generate_accumulated_strikes_stateless,
    generate_daily_board,
    simulate_board_evolution
)
from .expirations import (
    get_last_friday,
    round_to_nice_tick,
    generate_deribit_expirations,
    get_birth_date,
    calculate_time_layers
)

# ===== Public API =====
__all__ = [
    # Configuration
    'AlgoConfig',
    'CONFIG',
    
    # Grid Engine
    'GridEngine',
    
    # Distributions
    'parabolic_distribution',
    'parabolic_distribution_cached',
    
    # Magnets
    'get_current_min_step',
    'LayerBoundaries',
    'compute_layer_boundaries',
    'apply_magnet_filter',
    'filter_new_strikes_only',
    
    # Simulation
    'ContractDNA',
    'generate_accumulated_strikes_stateless',
    'generate_daily_board',
    'simulate_board_evolution',
    
    # Expirations
    'get_last_friday',
    'round_to_nice_tick',
    'generate_deribit_expirations',
    'get_birth_date',
    'calculate_time_layers',
]

__version__ = '5.0.0'
__author__ = 'Deribit Options Analytics Team'
