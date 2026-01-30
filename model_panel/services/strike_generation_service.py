"""
Strike Generation Service
==========================
Coordinates strike generation and expiration logic.

Provides high-level interface for strike board generation using the modular strikes package.
"""

from typing import List, Tuple, Optional
from datetime import datetime

from strikes import (
    ContractDNA,
    GridEngine,
    simulate_board_evolution,
    generate_deribit_expirations,
    get_birth_date,
    calculate_time_layers
)


class StrikeGenerationService:
    """
    Service для генерации страйков и управления экспирациями.
    
    Инкапсулирует сложность strikes package и предоставляет простой API.
    
    Example:
        >>> service = StrikeGenerationService()
        >>> strikes = service.generate_strikes_for_expiration(
        ...     current_spot=100000,
        ...     expiration_date='2024-02-01',
        ...     price_history=[...],
        ...     iv_history=[...]
        ... )
    """
    
    def __init__(self):
        """Инициализация сервиса."""
        pass
    
    def generate_strikes_for_expiration(
        self,
        current_spot: float,
        expiration_date: str,
        anchor_spot: float,
        anchor_iv: float,
        price_history: Optional[List[float]] = None,
        iv_history: Optional[List[float]] = None
    ) -> List[int]:
        """
        Генерирует страйки для заданной экспирации.
        
        Args:
            current_spot: Текущая цена спота
            expiration_date: Дата экспирации (str YYYY-MM-DD)
            anchor_spot: Spot при рождении контракта
            anchor_iv: IV при рождении контракта
            price_history: Опциональная история цен (для V5 accumulation)
            iv_history: Опциональная история IV
            
        Returns:
            List целых цен страйков
            
        Note:
            Использует V5 Accumulation если история доступна,
            иначе Parabolic distribution.
        """
        # Calculate birth date and DTE
        birth_date, birth_dte = get_birth_date(expiration_date)
        
        # If history available, use full V5 simulation
        if price_history and iv_history and len(price_history) > 0:
            dna = ContractDNA(
                anchor_spot=anchor_spot,
                anchor_iv=anchor_iv,
                birth_dte=birth_dte
            )
            
            current_day = len(price_history) - 1
            final_indices, _ = simulate_board_evolution(
                dna=dna,
                price_history=price_history,
                iv_history=iv_history,
                target_day=current_day
            )
            
            # Convert indices to strikes
            table = GridEngine.generate_table()
            return sorted([int(table[idx]) for idx in final_indices if idx < len(table)])
        
        # Fallback: single-day parabolic
        from strikes import parabolic_distribution_cached, CONFIG
        
        current_dte = birth_dte  # Simplified for fallback
        center_idx = GridEngine.find_index(current_spot)
        
        raw_indices = parabolic_distribution_cached(
            center_idx,
            round(current_spot, 2),
            round(anchor_iv, 4),
            current_dte
        )
        
        # Apply magnet snapping based on DTE
        if current_dte > CONFIG.MAGNET_THRESHOLD_LONG:
            step = CONFIG.MAGNET_STEP_LONG
        elif current_dte > CONFIG.MAGNET_THRESHOLD_MID:
            step = CONFIG.MAGNET_STEP_MID
        else:
            step = CONFIG.MAGNET_STEP_SHORT
        
        filtered = {(idx // step) * step for idx in raw_indices}
        table = GridEngine.generate_table()
        return sorted([int(table[idx]) for idx in filtered if idx < len(table)])
    
    def get_expirations(self, current_date: datetime) -> List[Tuple[datetime, int]]:
        """
        Генерирует стандартный набор Deribit экспираций.
        
        Args:
            current_date: Текущая дата
            
        Returns:
            List[(expiration_date, coincidence_count)]
            где coincidence_count = количество типов на эту дату
        """
        return generate_deribit_expirations(current_date)
    
    def get_birth_info(self, expiration_date: str) -> Tuple[datetime, int]:
        """
        Получает информацию о дате рождения контракта.
        
        Args:
            expiration_date: Дата экспирации (str)
            
        Returns:
            (birth_date, lead_days): дата рождения и lead time
        """
        return get_birth_date(expiration_date)
    
    def get_time_layers(
        self,
        current_date: str,
        birth_date: str
    ) -> List[Tuple[str, datetime, datetime]]:
        """
        Формирует слои истории для аналитики.
        
        Args:
            current_date: Текущая дата
            birth_date: Дата рождения контракта
            
        Returns:
            List[(layer_name, start_date, end_date)]
        """
        return calculate_time_layers(current_date, birth_date)
