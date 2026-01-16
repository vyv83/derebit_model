"""
Grid Engine Module
==================
Adaptive strike grid generation with logarithmic step sizing.

The GridEngine provides a foundation table of all possible strikes
with steps that grow proportionally to price level.
"""

import numpy as np
from typing import List, Optional

from .config import CONFIG


class GridEngine:
    """
    Базовая сетка страйков с адаптивным шагом.
    
    Генерирует таблицу всех возможных страйков с шагом, который растет
    пропорционально цене актива. Кэширует результат для переиспользования.
    
    Example:
        >>> GridEngine.find_index(100000)  # BTC at 100k
        571
        >>> table = GridEngine.generate_table()
        >>> table[571]
        100000.0
    """
    _table_cache: Optional[List[float]] = None
    
    @staticmethod
    def get_step(price: float) -> float:
        """
        Вычисляет адаптивный шаг для заданной цены.
        
        Args:
            price: Цена актива
            
        Returns:
            Размер шага для этого уровня цен
            
        Note:
            Шаг растет логарифмически с ценой для обеспечения
            одинаковой относительной плотности на всех уровнях.
        """
        if price <= 1e-9:
            return 0.000001
        
        exponent = np.floor(np.log10(price))
        magnitude = 10 ** exponent
        normalized = round(price / magnitude, 6)
        
        if normalized < CONFIG.GRID_THRESHOLD_LOW:
            return magnitude * CONFIG.GRID_STEP_LOW_MULTIPLIER
        elif normalized < CONFIG.GRID_THRESHOLD_HIGH:
            return magnitude * CONFIG.GRID_STEP_HIGH_MULTIPLIER
        else:
            return magnitude * CONFIG.GRID_STEP_HIGH_MULTIPLIER
    
    @classmethod
    def generate_table(cls, min_price: float = 100, max_price: float = 5000000) -> List[float]:
        """
        Генерирует полную таблицу страйков (кэшируется).
        
        Args:
            min_price: Минимальная цена
            max_price: Максимальная цена
            
        Returns:
            Список всех страйков в диапазоне
            
        Note:
            Результат кэшируется в _table_cache для переиспользования.
            Максимум 100k элементов для ограничения памяти.
        """
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
    def find_index(cls, price: float) -> int:
        """
        Находит индекс ближайшего страйка для заданной цены.
        
        Args:
            price: Цена для поиска
            
        Returns:
            Индекс ближайшего страйка в таблице
            
        Example:
            >>> GridEngine.find_index(100500)
            572  # Индекс ближайшего страйка
        """
        table = cls.generate_table()
        idx = np.searchsorted(table, price)
        
        if idx == 0:
            return 0
        elif idx == len(table):
            return len(table) - 1
        else:
            # Выбираем ближайший
            if abs(table[idx-1] - price) < abs(table[idx] - price):
                return idx - 1
            else:
                return idx
