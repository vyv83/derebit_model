"""
Parabolic Distribution Module
==============================
Generates strike indices using parabolic (volatility-based) distribution.

Strikes are dense around ATM and sparse at the wings, with density
controlled by volatility and time to expiration.
"""

import numpy as np
from functools import lru_cache
from typing import List, Tuple

from .config import CONFIG
from .grid_engine import GridEngine


@lru_cache(maxsize=512)  # ✅ BOUNDED для контроля памяти
def parabolic_distribution_cached(
    center_index: int,
    current_spot: float,
    current_iv: float,
    current_dte: int
) -> Tuple[int, ...]:
    """
    Генерирует индексы страйков в параболическом распределении (кэшированная).
    
    Args:
        center_index: Индекс центрального страйка (ATM)
        current_spot: Текущая цена спота (округленная)
        current_iv: Текущая IV (округленная)
        current_dte: Days To Expiration
        
    Returns:
        Tuple индексов (hashable для LRU кэша)
        
    Note:
        Параметры округляются перед кэшированием для лучшего hit rate.
        Bounded cache (maxsize=512) предотвращает неограниченный рост памяти.
    """
    # Расчет теоретических границ
    years = max(1/365.0, current_dte / 365.0)
    time_factor = years ** CONFIG.PARABOLA_SIGMA_TIME_POWER
    iv_factor = current_iv ** CONFIG.PARABOLA_IV_POWER
    sigma_move = iv_factor * time_factor
    
    price_down = current_spot * np.exp(-CONFIG.PARABOLA_SIGMA_MULTIPLIER * sigma_move)
    price_up = current_spot * np.exp(CONFIG.PARABOLA_SIGMA_MULTIPLIER * sigma_move)
    
    # Конвертация в индексы
    index_down = GridEngine.find_index(price_down)
    index_up = GridEngine.find_index(price_up)
    
    range_down = center_index - index_down
    range_up = index_up - center_index
    max_range = max(range_down, range_up)
    
    # Базовый шаг в центре
    dte_normalized = current_dte / 365.0
    base_skip = max(1, int(1 + CONFIG.PARABOLA_DTE_DENSITY_MULTIPLIER * dte_normalized))
    
    indices = set()
    indices.add(center_index)
    
    # Функция расчета шага (растет при удалении от центра)
    def get_skip(distance_from_center: int) -> int:
        if max_range == 0:
            return base_skip
        norm_dist = distance_from_center / max_range
        factor = 1 + CONFIG.PARABOLA_STEEPNESS * (norm_dist ** CONFIG.PARABOLA_POWER)
        return max(1, int(base_skip * factor))
    
    # Генерация вниз
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
    
    # Генерация вверх
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


def parabolic_distribution(
    center_index: int,
    current_spot: float,
    current_iv: float,
    current_dte: int
) -> List[int]:
    """
    Обертка для parabolic_distribution_cached с округлением параметров.
    
    Args:
        center_index: Индекс центрального страйка
        current_spot: Текущая цена спота
        current_iv: Текущая IV
        current_dte: Days To Expiration
        
    Returns:
        List индексов страйков
        
    Note:
        Округление параметров улучшает cache hit rate.
    """
    current_spot_rounded = round(current_spot, 2)
    current_iv_rounded = round(current_iv, 4)
    result_tuple = parabolic_distribution_cached(
        center_index, current_spot_rounded, current_iv_rounded, current_dte
    )
    return list(result_tuple)
