"""
Magnet Filtering Module
========================
Applies magnet snapping to align strikes to stable grid positions.

Magnets filter strikes based on historical price layers and time to expiration,
ensuring stability and reducing strike proliferation.
"""

import numpy as np
from typing import Set, List
from dataclasses import dataclass

from .config import CONFIG
from .grid_engine import GridEngine


def get_current_min_step(current_dte: int) -> int:
    """
    Определяет минимальный шаг магнита на основе DTE.
    
    Args:
        current_dte: Days To Expiration
        
    Returns:
        Минимальный шаг (1, 2, или 4)
    """
    if current_dte > CONFIG.MAGNET_THRESHOLD_LONG:
        return CONFIG.MAGNET_STEP_LONG
    elif current_dte > CONFIG.MAGNET_THRESHOLD_MID:
        return CONFIG.MAGNET_STEP_MID
    else:
        return CONFIG.MAGNET_STEP_SHORT


@dataclass
class LayerBoundaries:
    """Границы слоев для фильтрации."""
    l1_low: int
    l1_high: int
    l2_low: int
    l2_high: int
    l3_low: int
    l3_high: int


def compute_layer_boundaries(
    price_history: List[float],
    current_day: int
) -> LayerBoundaries:
    """
    Вычисляет границы слоев (Layer 1/2/3) на основе истории цен.
    
    Args:
        price_history: История цен до current_day
        current_day: Текущий день
        
    Returns:
        LayerBoundaries с низом/верхом каждого слоя
        
    Note:
        Layer 1 = недавняя история (последние 30 дней)
        Layer 2 = средняя история (30-180 дней назад)
        Layer 3 = старая история (>180 дней назад)
    """
   # Индексы начала окон
    day_recent_start = max(0, current_day - CONFIG.LAYER_WINDOW_RECENT + 1)
    day_medium_start = max(0, current_day - CONFIG.LAYER_WINDOW_MEDIUM + 1)
    
    # Numpy arrays для быстрого min/max
    prices_arr = np.array(price_history[:current_day+1])
    
    # Layer 1: недавняя история
    if day_recent_start <= current_day:
        h_recent, l_recent = prices_arr[day_recent_start:].max(), prices_arr[day_recent_start:].min()
        idx_h, idx_l = GridEngine.find_index(h_recent), GridEngine.find_index(l_recent)
        price_range = h_recent - l_recent
        buf_dol = price_range * CONFIG.LAYER1_BUFFER_PCT if price_range > 0 else h_recent * 0.01
        idx_h_b = GridEngine.find_index(h_recent + buf_dol)
        idx_l_b = GridEngine.find_index(l_recent - buf_dol)
        buf = max(2, ((idx_h_b - idx_h) + (idx_l - idx_l_b)) // 2)
        l1_low, l1_high = idx_l - buf, idx_h + buf
    else:
        l1_low = l1_high = -1
    
    # Layer 2: средняя история
    if day_medium_start < day_recent_start:
        h_medium, l_medium = prices_arr[day_medium_start:day_recent_start].max(), prices_arr[day_medium_start:day_recent_start].min()
        idx_h, idx_l = GridEngine.find_index(h_medium), GridEngine.find_index(l_medium)
        price_range = h_medium - l_medium
        buf_dol = price_range * CONFIG.LAYER2_BUFFER_PCT if price_range > 0 else h_medium * 0.02
        idx_h_b = GridEngine.find_index(h_medium + buf_dol)
        idx_l_b = GridEngine.find_index(l_medium - buf_dol)
        buf = max(2, ((idx_h_b - idx_h) + (idx_l - idx_l_b)) // 2)
        l2_low, l2_high = idx_l - buf, idx_h + buf
    else:
        l2_low = l2_high = -1
    
    # Layer 3: старая история
    if day_medium_start > 0:
        h_old, l_old = prices_arr[:day_medium_start].max(), prices_arr[:day_medium_start].min()
        l3_low, l3_high = GridEngine.find_index(l_old), GridEngine.find_index(h_old)
    else:
        l3_low = l3_high = -1
    
    return LayerBoundaries(l1_low, l1_high, l2_low, l2_high, l3_low, l3_high)


def apply_magnet_filter(
    new_raw_indices: Set[int],
    boundaries: LayerBoundaries,
    step_l1: int,
    step_l2: int,
    step_l3: int
) -> Set[int]:
    """
    Применяет магнитную фильтрацию к новым индексам.
    
    Args:
        new_raw_indices: Новые сырые индексы для фильтрации
        boundaries: Границы слоев
        step_l1: Шаг для Layer 1
        step_l2: Шаг для Layer 2
        step_l3: Шаг для Layer 3
        
    Returns:
        Set одобренных (магнитированных) индексов
        
    Note:
        Использует numpy для векторизации вычислений.
    """
    if not new_raw_indices:
        return set()
    
    # Конвертируем в numpy array
    new_raw_arr = np.array(list(new_raw_indices), dtype=np.int32)
    
    # Создаем маски для каждого слоя
    mask_l1 = (new_raw_arr >= boundaries.l1_low) & (new_raw_arr <= boundaries.l1_high)
    mask_l2 = (new_raw_arr >= boundaries.l2_low) & (new_raw_arr <= boundaries.l2_high) & ~mask_l1
    mask_l3 = ~(mask_l1 | mask_l2)
    
    # Применяем магнитное округление для каждого слоя
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


def filter_new_strikes_only(
    new_raw_indices: Set[int],
    price_history: List[float],
    current_day: int,
    birth_dte: int
) -> Set[int]:
    """
    Фильтрует ТОЛЬКО новые страйки через магнит.
    
    Args:
        new_raw_indices: Новые сырые индексы (не из предыдущей доски)
        price_history: История цен
        current_day: Текущий день
        birth_dte: DTE при рождении
        
    Returns:
        Set одобренных новых индексов
        
    Note:
        Старые страйки защищены персистентностью в generate_daily_board.
    """
    # Early exit если нет новых индексов
    if not new_raw_indices:
        return set()
    
    # Вычисляем шаги
    current_dte = birth_dte - current_day
    min_step = get_current_min_step(current_dte)
    
    step_l1 = min_step
    step_l2 = max(CONFIG.LAYER2_MIN_STEP, min_step)
    step_l3 = max(CONFIG.LAYER3_MIN_STEP, min_step)
    
    # Вычисляем границы слоев
    boundaries = compute_layer_boundaries(price_history, current_day)
    
    # Применяем магнитную фильтрацию
    approved = apply_magnet_filter(new_raw_indices, boundaries, step_l1, step_l2, step_l3)
    
    return approved
