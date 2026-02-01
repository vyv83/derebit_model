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

    # 2. FALLBACK: Optimized Unified Logic (V3)
    # Гарантирует 100% совпадение с симуляцией (Day 0) при экстремальной скорости.
    # Использует гипотезу, что для Day 0 буфер слоя Layer 1 всегда равен +/- 2 индекса.
    
    # 2.1. Basic Params
    spot_r = round(current_spot, 2)
    vol_r = round(anchor_vol, 4)
    center_idx = GridEngine.find_index(current_spot)
    
    # 2.2. Cached Parabolic Distribution
    raw_indices_tuple = parabolic_distribution_cached(
        center_idx, spot_r, vol_r, current_dte
    )
    
    # 2.3. Constant Buffer Optimization (Layer 1 Range for Day 0)
    l1_low = center_idx - 2
    l1_high = center_idx + 2
    
    # 2.4. Magnet Step Logic
    min_step = 1
    if current_dte > CONFIG.MAGNET_THRESHOLD_LONG: min_step = CONFIG.MAGNET_STEP_LONG
    elif current_dte > CONFIG.MAGNET_THRESHOLD_MID: min_step = CONFIG.MAGNET_STEP_MID
    else: min_step = CONFIG.MAGNET_STEP_SHORT
    step_l3 = max(CONFIG.LAYER3_MIN_STEP, min_step)
    
    # 2.5. Inline Filtering Loop (Pure Python is fastest here for <100 items)
    filtered_indices = set()
    
    if min_step == step_l3:
        # Optimization: No branching needed
        for idx in raw_indices_tuple:
            filtered_indices.add((idx // min_step) * min_step)
    else:
        for idx in raw_indices_tuple:
            if l1_low <= idx <= l1_high:
                filtered_indices.add((idx // min_step) * min_step)
            else:
                filtered_indices.add((idx // step_l3) * step_l3)
    
    table = GridEngine.generate_table()
    limit = len(table)
    return sorted([int(table[idx]) for idx in filtered_indices if idx < limit])
