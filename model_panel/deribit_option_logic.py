"""
STRIKES UTILS - FINAL PROPER VERSION
====================================
Wrapper for strikes module with backward compatibility.

Now uses modular strikes package instead of monolithic engine.
"""

from typing import List, Optional

# Import from new modular strikes package
#  Note: Using relative import since this file is in model/ directory
try:
    # Try relative import first (when called from within model package)
    from .strikes import (
        ContractDNA,
        GridEngine,
        simulate_board_evolution,
        parabolic_distribution_cached,
        CONFIG,
        # Re-export expiration functions for backward compatibility
        get_last_friday,
        round_to_nice_tick,
        generate_deribit_expirations,
        get_birth_date,
        calculate_time_layers
    )
except ImportError:
    # Fallback to absolute import (when called as model.deribit_option_logic)
    from strikes import (
        ContractDNA,
        GridEngine,
        simulate_board_evolution,
        parabolic_distribution_cached,
        CONFIG,
        get_last_friday,
        round_to_nice_tick,
        generate_deribit_expirations,
        get_birth_date,
        calculate_time_layers
    )



# ==============================================================================
# ГЕНЕРАЦИЯ СТРАЙКОВ (V5 ULTIMATE)
# ==============================================================================

def generate_deribit_strikes(
    current_spot: float,
    current_dte: int,
    anchor_spot: float,
    anchor_vol: float,
    birth_dte: int,
    historical_ranges: List = None,
    coincidence_count: int = 1,
    price_history: Optional[List[float]] = None,
    iv_history: Optional[List[float]] = None
) -> List[int]:
    """
    Основная точка входа для генерации страйков.
    Использует V5 Accumulation если есть история, иначе Fallback Parabolic.
    """
    # 1. ПРАВИЛЬНЫЙ ПУТЬ: Полноценная V5 симуляция
    if price_history is not None and iv_history is not None and len(price_history) > 0:
        dna = ContractDNA(anchor_spot, anchor_vol, birth_dte)
        current_day = len(price_history) - 1
        
        final_indices, _ = simulate_board_evolution(
            dna=dna, price_history=price_history, iv_history=iv_history, target_day=current_day
        )
        
        table = GridEngine.generate_table()
        return sorted([int(table[idx]) for idx in final_indices if idx < len(table)])

    # 2. FALLBACK: Одиночный расчет (если истории нет)
    center_idx = GridEngine.find_index(current_spot)
    raw_indices = parabolic_distribution_cached(
        center_idx, round(current_spot, 2), round(anchor_vol, 4), current_dte
    )
    
    # Выбор шага магнита
    if current_dte > CONFIG.MAGNET_THRESHOLD_LONG: step = CONFIG.MAGNET_STEP_LONG
    elif current_dte > CONFIG.MAGNET_THRESHOLD_MID: step = CONFIG.MAGNET_STEP_MID
    else: step = CONFIG.MAGNET_STEP_SHORT
    
    filtered = {(idx // step) * step for idx in raw_indices}
    table = GridEngine.generate_table()
    return sorted([int(table[idx]) for idx in filtered if idx < len(table)])
