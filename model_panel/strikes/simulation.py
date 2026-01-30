"""
Board Simulation Module
========================
Simulates the evolution of strike boards over time with accumulation strategy.

Implements incremental strike generation from contract birth through expiration.
"""

from typing import List, Set, Tuple, Optional
from dataclasses import dataclass, field

from .grid_engine import GridEngine
from .distributions import parabolic_distribution
from .magnets import filter_new_strikes_only


@dataclass
class ContractDNA:
    """
    Неизменные параметры контракта при рождении.
    
    Attributes:
        anchor_spot: Цена спота при рождении контракта
        anchor_iv: Implied Volatility при рождении
        birth_dte: Days To Expiration при рождении
        anchor_table_index: Индекс anchor_spot в базовой таблице
    """
    anchor_spot: float
    anchor_iv: float
    birth_dte: int
    anchor_table_index: int = field(init=False)
    
    def __post_init__(self):
        """Вычисляет anchor_table_index после инициализации."""
        object.__setattr__(self, 'anchor_table_index', GridEngine.find_index(self.anchor_spot))


def generate_accumulated_strikes_stateless(
    dna: ContractDNA,
    price_history: List[float],
    iv_history: List[float],
    current_day: int
) -> Set[int]:
    """
    Генерирует ВСЕ накопленные сырые страйки с дня рождения до текущего дня.
    
    Args:
        dna: ДНК контракта
        price_history: История цен [day_0, ..., day_current]
        iv_history: История IV [day_0, ..., day_current]
        current_day: Номер текущего дня (0 = рождение)
        
    Returns:
        Set всех сырых индексов страйков
        
    Note:
        Функция stateless: одинаковые входы дают одинаковый результат.
        Используется для api compatibility и ad-hoc запросов.
    """
    all_raw_indices = set()
    
    for day in range(0, current_day + 1):
        dte_on_day = dna.birth_dte - day
        spot_on_day = price_history[day]
        iv_on_day = iv_history[day]
        center_on_day = GridEngine.find_index(spot_on_day)
        
        daily_indices = parabolic_distribution(center_on_day, spot_on_day, iv_on_day, dte_on_day)
        all_raw_indices.update(daily_indices)
    
    return all_raw_indices


def generate_daily_board(
    dna: ContractDNA,
    price_history: List[float],
    iv_history: List[float],
    current_day: int,
    previous_final_strikes: Optional[Set[int]] = None
) -> Set[int]:
    """
    Генерирует финальную доску страйков для текущего дня.
    
    Args:
        dna: ДНК контракта
        price_history: История цен [0..current_day]
        iv_history: История IV [0..current_day]
        current_day: Номер текущего дня (0 = рождение)
        previous_final_strikes: Финальная доска предыдущего дня
        
    Returns:
        Set индексов финальной доски
        
    Note:
        Stateless: одинаковые входы дают одинаковый результат.
        Персистентность: previous_final_strikes никогда не удаляются.
    """
    # Накопление всех сырых страйков
    all_raw_indices = generate_accumulated_strikes_stateless(
        dna, price_history, iv_history, current_day
    )
    
    # Определяем новые
    if previous_final_strikes is None:
        previous_final_strikes = set()
    
    new_raw_indices = all_raw_indices - previous_final_strikes
    
    # Фильтруем новые
    new_approved = filter_new_strikes_only(
        new_raw_indices,
        price_history,
        current_day,
        dna.birth_dte
    )
    
    # Гарантия персистентности
    final_board = previous_final_strikes | new_approved
    
    return final_board


def simulate_board_evolution(
    dna: ContractDNA,
    price_history: List[float],
    iv_history: List[float],
    target_day: int
) -> Tuple[Set[int], List[Set[int]]]:
    """
    Симулирует эволюцию доски с incremental accumulation (O(N) вместо O(N²)).
    
    Args:
        dna: ДНК контракта
        price_history: История цен [0..target_day]
        iv_history: История IV [0..target_day]
        target_day: Финальный день симуляции
        
    Returns:
        (final_board, history): финальная доска и список досок по дням
        
    Note:
        Это ОСНОВНАЯ функция для production использования.
        Использует incremental accumulation для максимальной скорости.
    """
    history = []
    previous_final = None
    accumulated_raw = set()  # Инкрементальное накопление
    
    for day in range(0, target_day + 1):
        # Добавляем ТОЛЬКО текущий день к накопленным
        dte_on_day = dna.birth_dte - day
        spot_on_day = price_history[day]
        iv_on_day = iv_history[day]
        center_on_day = GridEngine.find_index(spot_on_day)
        
        daily_indices = parabolic_distribution(center_on_day, spot_on_day, iv_on_day, dte_on_day)
        accumulated_raw.update(daily_indices)
        
        # Фильтрация
        if previous_final is None:
            previous_final = set()
        
        new_raw_indices = accumulated_raw - previous_final
        
        new_approved = filter_new_strikes_only(
            new_raw_indices,
            price_history[:day+1],
            day,
            dna.birth_dte
        )
        
        current_board = previous_final | new_approved
        
        history.append(current_board)
        previous_final = current_board
    
    return previous_final, history
