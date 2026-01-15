"""
OPTIMIZED VERSION v4 - Iteration 3 (FINAL)
РЕВОЛЮЦИОННАЯ ОПТИМИЗАЦИЯ:
13. TRUE INCREMENTAL ACCUMULATION - не пересчитываем весь цикл каждый день!
    Храним промежуточные результаты накопления, добавляем только новый день

Это КАРДИНАЛЬНО меняет сложность:
- Baseline: O(N²) - day 90 = 90 iterations
- V4: O(N) - day 90 = 1 iteration (только новый день!)
"""

import numpy as np
from typing import List, Set, Tuple, Optional, Dict
from functools import lru_cache

# Config (unchanged)
class AlgoConfig:
    GRID_STEP_LOW_MULTIPLIER = 0.025
    GRID_STEP_HIGH_MULTIPLIER = 0.050
    GRID_THRESHOLD_LOW = 2.0
    GRID_THRESHOLD_HIGH = 5.0
    
    PARABOLA_SIGMA_MULTIPLIER = 1.4
    PARABOLA_SIGMA_TIME_POWER = 0.2
    PARABOLA_IV_POWER = 2.0
    PARABOLA_DTE_DENSITY_MULTIPLIER = 1.0
    PARABOLA_STEEPNESS = 15.0
    PARABOLA_POWER = 1.2
    
    MAGNET_THRESHOLD_LONG = 180
    MAGNET_THRESHOLD_MID = 30
    MAGNET_STEP_LONG = 4
    MAGNET_STEP_MID = 2
    MAGNET_STEP_SHORT = 1
    
    LAYER_WINDOW_RECENT = 30
    LAYER_WINDOW_MEDIUM = 180
    LAYER1_BUFFER_PCT = 0.05
    LAYER2_BUFFER_PCT = 0.15
    LAYER2_MIN_STEP = 2
    LAYER3_MIN_STEP = 4


# GridEngine (unchanged)
class GridEngine:
    _table_cache = None
    
    @staticmethod
    def get_step(price):
        if price <= 1e-9:
            return 0.000001
        
        exponent = np.floor(np.log10(price))
        magnitude = 10 ** exponent
        normalized = round(price / magnitude, 6)
        
        if normalized < AlgoConfig.GRID_THRESHOLD_LOW:
            return magnitude * AlgoConfig.GRID_STEP_LOW_MULTIPLIER
        elif normalized < AlgoConfig.GRID_THRESHOLD_HIGH:
            return magnitude * AlgoConfig.GRID_STEP_HIGH_MULTIPLIER
        else:
            return magnitude * AlgoConfig.GRID_STEP_HIGH_MULTIPLIER
    
    @classmethod
    def generate_table(cls, min_price=100, max_price=5000000):
        if cls._table_cache is not None:
            return cls._table_cache
        
        strikes = []
        first_step = cls.get_step(min_price)
        current = np.ceil(min_price / first_step) * first_step
        current = float(f"{current:.8g}")
        
        while current <= max_price:
            strikes.append(current)
            step = cls.get_step(current)
            current += step
            current = float(f"{current:.8g}")
            
            if len(strikes) > 100000:
                break
        
        cls._table_cache = strikes
        return strikes
    
    @classmethod
    def find_index(cls, price):
        table = cls.generate_table()
        idx = np.searchsorted(table, price)
        
        if idx == 0:
            return 0
        elif idx == len(table):
            return len(table) - 1
        else:
            if abs(table[idx-1] - price) < abs(table[idx] - price):
                return idx - 1
            else:
                return idx


class ContractDNA:
    def __init__(self, anchor_spot, anchor_iv, birth_dte):
        self.anchor_spot = anchor_spot
        self.anchor_iv = anchor_iv
        self.birth_dte = birth_dte
        self.anchor_table_index = GridEngine.find_index(anchor_spot)


# Parabolic (from v2/v3)
@lru_cache(maxsize=1024)
def parabolic_distribution_cached(center_index, current_spot, current_iv, current_dte):
    years = max(1/365.0, current_dte / 365.0)
    
    time_factor = years ** AlgoConfig.PARABOLA_SIGMA_TIME_POWER
    iv_factor = current_iv ** AlgoConfig.PARABOLA_IV_POWER
    sigma_move = iv_factor * time_factor
    
    price_down = current_spot * np.exp(-AlgoConfig.PARABOLA_SIGMA_MULTIPLIER * sigma_move)
    price_up = current_spot * np.exp(AlgoConfig.PARABOLA_SIGMA_MULTIPLIER * sigma_move)
    
    index_down = GridEngine.find_index(price_down)
    index_up = GridEngine.find_index(price_up)
    
    range_down = center_index - index_down
    range_up = index_up - center_index
    max_range = max(range_down, range_up)
    
    dte_normalized = current_dte / 365.0
    base_skip = max(1, int(1 + AlgoConfig.PARABOLA_DTE_DENSITY_MULTIPLIER * dte_normalized))
    
    indices = set()
    indices.add(center_index)
    
    def get_skip(distance_from_center):
        if max_range == 0:
            return base_skip
        norm_dist = distance_from_center / max_range
        factor = 1 + AlgoConfig.PARABOLA_STEEPNESS * (norm_dist ** AlgoConfig.PARABOLA_POWER)
        return max(1, int(base_skip * factor))
    
    current_idx = center_index
    table_size = len(GridEngine.generate_table())
    max_iterations = 10000
    
    iteration = 0
    while iteration < max_iterations:
        distance_from_center = center_index - current_idx
        if distance_from_center >= range_down:
            break
        skip = get_skip(distance_from_center)
        current_idx -= skip
        if current_idx >= 0:
            indices.add(current_idx)
        else:
            break
        iteration += 1
    
    current_idx = center_index
    iteration = 0
    while iteration < max_iterations:
        distance_from_center = current_idx - center_index
        if distance_from_center >= range_up:
            break
        skip = get_skip(distance_from_center)
        current_idx += skip
        if current_idx < table_size:
            indices.add(current_idx)
        else:
            break
        iteration += 1
    
    return tuple(sorted(indices))


def parabolic_distribution(center_index, current_spot, current_iv, current_dte):
    current_spot_rounded = round(current_spot, 2)
    current_iv_rounded = round(current_iv, 4)
    result_tuple = parabolic_distribution_cached(
        center_index, current_spot_rounded, current_iv_rounded, current_dte
    )
    return list(result_tuple)


# ==============================================================================
# 🔥 REVOLUTIONARY: TRUE INCREMENTAL ACCUMULATION
# ==============================================================================

def generate_accumulated_strikes_stateless(
    dna: ContractDNA,
    price_history: List[float],
    iv_history: List[float],
    current_day: int
) -> Set[int]:
    """
    🔥 OPTIMIZATION 13: Это wrapper для совместимости.
    Внутри accumulate_from_scratch идет обычное накопление
    """
    # Для stateless API мы все равно должны пересчитывать с нуля
    # НО это используется только для verify, не в production simulate_board_evolution
    all_raw_indices = set()
    
    for day in range(0, current_day + 1):
        dte_on_day = dna.birth_dte - day
        spot_on_day = price_history[day]
        iv_on_day = iv_history[day]
        center_on_day = GridEngine.find_index(spot_on_day)
        
        daily_indices = parabolic_distribution(center_on_day, spot_on_day, iv_on_day, dte_on_day)
        all_raw_indices.update(daily_indices)
    
    return all_raw_indices


# Filter (from v3 - vectorized)
def get_current_min_step(current_dte):
    if current_dte > AlgoConfig.MAGNET_THRESHOLD_LONG:
        return AlgoConfig.MAGNET_STEP_LONG
    elif current_dte > AlgoConfig.MAGNET_THRESHOLD_MID:
        return AlgoConfig.MAGNET_STEP_MID
    else:
        return AlgoConfig.MAGNET_STEP_SHORT


def filter_new_strikes_only(
    new_raw_indices: Set[int],
    price_history: List[float],
    current_day: int,
    birth_dte: int
) -> Set[int]:
    """Vectorized filter from v3"""
    if not new_raw_indices:
        return set()
    
    current_dte = birth_dte - current_day
    min_step = get_current_min_step(current_dte)
    
    step_l1 = min_step
    step_l2 = max(AlgoConfig.LAYER2_MIN_STEP, min_step)
    step_l3 = max(AlgoConfig.LAYER3_MIN_STEP, min_step)
    
    prices_arr = np.array(price_history[:current_day+1])
    
    day_recent_start = max(0, current_day - AlgoConfig.LAYER_WINDOW_RECENT + 1)
    day_medium_start = max(0, current_day - AlgoConfig.LAYER_WINDOW_MEDIUM + 1)
    
    if day_recent_start <= current_day:
        h_recent, l_recent = prices_arr[day_recent_start:].max(), prices_arr[day_recent_start:].min()
    else:
        h_recent = l_recent = None
    
    if day_medium_start < day_recent_start:
        h_medium, l_medium = prices_arr[day_medium_start:day_recent_start].max(), prices_arr[day_medium_start:day_recent_start].min()
    else:
        h_medium = l_medium = None
    
    if day_medium_start > 0:
        h_old, l_old = prices_arr[:day_medium_start].max(), prices_arr[:day_medium_start].min()
    else:
        h_old = l_old = None
    
    if h_recent is not None:
        idx_h, idx_l = GridEngine.find_index(h_recent), GridEngine.find_index(l_recent)
        price_range = h_recent - l_recent
        buf_dol = price_range * AlgoConfig.LAYER1_BUFFER_PCT if price_range > 0 else h_recent * 0.01
        idx_h_b = GridEngine.find_index(h_recent + buf_dol)
        idx_l_b = GridEngine.find_index(l_recent - buf_dol)
        buf = max(2, ((idx_h_b - idx_h) + (idx_l - idx_l_b)) // 2)
        l1_low, l1_high = idx_l - buf, idx_h + buf
    else:
        l1_low = l1_high = -1
    
    if h_medium is not None:
        idx_h, idx_l = GridEngine.find_index(h_medium), GridEngine.find_index(l_medium)
        price_range = h_medium - l_medium
        buf_dol = price_range * AlgoConfig.LAYER2_BUFFER_PCT if price_range > 0 else h_medium * 0.02
        idx_h_b = GridEngine.find_index(h_medium + buf_dol)
        idx_l_b = GridEngine.find_index(l_medium - buf_dol)
        buf = max(2, ((idx_h_b - idx_h) + (idx_l - idx_l_b)) // 2)
        l2_low, l2_high = idx_l - buf, idx_h + buf
    else:
        l2_low = l2_high = -1
    
    if h_old is not None:
        l3_low, l3_high = GridEngine.find_index(l_old), GridEngine.find_index(h_old)
    else:
        l3_low = l3_high = -1
    
    new_raw_arr = np.array(list(new_raw_indices), dtype=np.int32)
    
    mask_l1 = (new_raw_arr >= l1_low) & (new_raw_arr <= l1_high)
    mask_l2 = (new_raw_arr >= l2_low) & (new_raw_arr <= l2_high) & ~mask_l1
    mask_l3 = ~(mask_l1 | mask_l2)
    
    approved = set()
    
    if mask_l1.any():
        snapped_l1 = (new_raw_arr[mask_l1] // step_l1) * step_l1
        approved.update(snapped_l1.tolist())
    
    if mask_l2.any():
        snapped_l2 = (new_raw_arr[mask_l2] // step_l2) * step_l2
        approved.update(snapped_l2.tolist())
    
    if mask_l3.any():
        snapped_l3 = (new_raw_arr[mask_l3] // step_l3) * step_l3
        approved.update(snapped_l3.tolist())
    
    return approved


# Main orchestrator (unchanged for API compatibility)
def generate_daily_board(
    dna: ContractDNA,
    price_history: List[float],
    iv_history: List[float],
    current_day: int,
    previous_final_strikes: Optional[Set[int]] = None
) -> Set[int]:
    all_raw_indices = generate_accumulated_strikes_stateless(
        dna, price_history, iv_history, current_day
    )
    
    if previous_final_strikes is None:
        previous_final_strikes = set()
    
    new_raw_indices = all_raw_indices - previous_final_strikes
    
    new_approved = filter_new_strikes_only(
        new_raw_indices,
        price_history,
        current_day,
        dna.birth_dte
    )
    
    final_board = previous_final_strikes | new_approved
    
    return final_board


# ==============================================================================
# 🚀 REVOLUTIONARY: INCREMENTAL EVOLUTION
# ==============================================================================

def simulate_board_evolution(
    dna: ContractDNA,
    price_history: List[float],
    iv_history: List[float],
    target_day: int
) -> Tuple[Set[int], List[Set[int]]]:
    """
    🔥 OPTIMIZATION 13 APPLIED HERE: Инкрементальное накопление
    
    Вместо пересчета всего с нуля каждый день:
    - Храним accumulated_raw (накопленные сырые индексы)
    - Каждый день добавляем ТОЛЬКО новый день
    - Complexity: O(N) вместо O(N²)!
    """
    history = []
    previous_final = None
    accumulated_raw = set()  # 🔥 Храним накопленные сырые индексы
    
    for day in range(0, target_day + 1):
        # 🔥 INCREMENTAL: добавляем только текущий день!
        dte_on_day = dna.birth_dte - day
        spot_on_day = price_history[day]
        iv_on_day = iv_history[day]
        center_on_day = GridEngine.find_index(spot_on_day)
        
        daily_indices = parabolic_distribution(center_on_day, spot_on_day, iv_on_day, dte_on_day)
        accumulated_raw.update(daily_indices)  # Добавляем к накопленным
        
        # Определяем НОВЫЕ (не из предыдущей финальной доски)
        if previous_final is None:
            previous_final = set()
        
        new_raw_indices = accumulated_raw - previous_final
        
        # Фильтруем новые
        new_approved = filter_new_strikes_only(
            new_raw_indices,
            price_history[:day+1],
            day,
            dna.birth_dte
        )
        
        # Финальная доска
        current_board = previous_final | new_approved
        
        history.append(current_board)
        previous_final = current_board
    
    return previous_final, history
