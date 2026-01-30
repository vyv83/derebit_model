"""
Options Analytics Service
==========================
Main orchestrator for options analytics operations.

Combines Greeks calculation and strike generation services
for comprehensive options analysis.
"""

from typing import Dict, List, Any, Optional
import pandas as pd
from datetime import datetime

from .greeks_calculation_service import GreeksCalculationService
from .strike_generation_service import StrikeGenerationService


class OptionsAnalyticsService:
    """
    Главный orchestrator для опционной аналитики.
    
    Координирует работу всех сервисов для предоставления
    комплексного анализа опционов.
    
    Example:
        >>> analytics = OptionsAnalyticsService(greeks_service, strikes_service)
        >>> board = analytics.generate_options_board(
        ...     market_state={...},
        ...     expiration_date='2024-02-01',
        ...     is_call=True
        ... )
    """
    
    def __init__(
        self,
        greeks_service: GreeksCalculationService,
        strikes_service: StrikeGenerationService
    ):
        """
        Инициализация главного сервиса.
        
        Args:
            greeks_service: Сервис расчета Greeks
            strikes_service: Сервис генерации страйков
        """
        self.greeks = greeks_service
        self.strikes = strikes_service
    
    def generate_options_board(
        self,
        market_state: Dict[str, Any],
        expiration_date: str,
        anchor_spot: float,
        anchor_iv: float,
        is_call: bool = True,
        price_history: Optional[List[float]] = None,
        iv_history: Optional[List[float]] = None
    ) -> pd.DataFrame:
        """
        Генерирует полную доску опционов с Greeks.
        
        Args:
            market_state: Market features (spot, iv_atm, returns, etc.)
            expiration_date: Дата экспирации
            anchor_spot: Spot при рождении
            anchor_iv: IV при рождении
            is_call: Call или Put опционы
            price_history: История цен (опционально)
            iv_history: История IV (опционально)
            
        Returns:
            DataFrame с полной доской опционов и Greeks
        """
        # Step 1: Generate strikes
        strikes = self.strikes.generate_strikes_for_expiration(
            current_spot=market_state['spot'],
            expiration_date=expiration_date,
            anchor_spot=anchor_spot,
            anchor_iv=anchor_iv,
            price_history=price_history,
            iv_history=iv_history
        )
        
        # Step 2: Calculate Greeks for all strikes
        birth_date, birth_dte = self.strikes.get_birth_info(expiration_date)
        # TODO: Calculate actual current DTE from dates
        dte_days = birth_dte  # Simplified
        
        greeks_df = self.greeks.calculate_full_greeks(
            market_state=market_state,
            strikes=strikes,
            dte_days=dte_days,
            is_call=is_call
        )
        
        return greeks_df
    
    def get_available_expirations(self, current_date: datetime):
        """
        Получает список доступных экспираций.
        
        Args:
            current_date: Текущая дата
            
        Returns:
            List экспираций
        """
        return self.strikes.get_expirations(current_date)
