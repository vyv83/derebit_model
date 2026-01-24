"""
Greeks Calculation Service
===========================
Orchestrates hybrid Neural Network + Black-Scholes approach for Greeks calculation.

This service combines:
- Neural Network predictions (IV, Delta, Vega)
- Black-Scholes analytics (Gamma, Theta, Price)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any

from core.black_scholes import black_scholes_safe


class GreeksCalculationService:
    """
    Service для расчета Greeks с использованием гибридного подхода.
    
    Архитектура:
    - NN → IV, Delta, Vega (обучена на рыночных данных)
    - BS → Gamma, Theta, Price (аналитические формулы)
    
    Example:
        >>> service = GreeksCalculationService(option_model)
        >>> results = service.calculate_full_greeks(
        ...     market_state={'spot': 100000, 'iv_atm': 0.75, ...},
        ...     strikes=[95000, 100000, 105000],
        ...     dte_days=30,
        ...     is_call=True
        ... )
    """
    
    def __init__(self, neural_network_model):
        """
        Инициализация сервиса.
        
        Args:
            neural_network_model: Экземпляр OptionModel для предсказаний
        """
        self.model = neural_network_model
    
    def calculate_full_greeks(
        self,
        market_state: Dict[str, Any],
        strikes: List[float],
        dte_days: int,
        is_call: bool = True,
        risk_free_rate: float = 0.0
    ) -> pd.DataFrame:
        """
        Рассчитывает полный набор Greeks для списка страйков.
        
        Args:
            market_state: Словарь с market features (spot, iv_atm, returns, etc.)
            strikes: Список цен страйков
            dte_days: Days To Expiration
            is_call: True для call опционов, False для put
            risk_free_rate: Безрисковая ставка (по умолчанию 0.0 для крипты)
            
        Returns:
            DataFrame с колонками:
            - strike: Цена страйка
            - iv: Implied Volatility (из NN)
            - delta: Delta (из NN)
            - vega: Vega (из NN)
            - gamma: Gamma (из BS) ← более точная
            - theta: Theta (из BS)
            - price: Теоретическая цена (из BS)
            - moneyness: S/K
            
        Note:
            Гибридный подход обоснован тестированием:
            - Gamma: MAE = 0.000004 (BS в 4.5x лучше чем NN)
            - Theta: MAPE = 28.10% (BS корректна для крипты)
            - IV, Delta, Vega: NN обучена на реальных рыночных данных
        """
        # Шаг 1: Получить NN предсказания (IV, Delta, Vega)
        nn_predictions = self.model.predict(
            market_state=market_state,
            strikes=strikes,
            dte_days=dte_days,
            is_call=is_call
        )
        
        # Шаг 2: Prepare results list
        results = []
        spot = market_state['spot']
        
        # Шаг 3: Для каждого страйка рассчитать BS Greeks
        for i, strike in enumerate(strikes):
            # NN outputs
            iv = nn_predictions['mark_iv'][i]
            delta = nn_predictions['delta'][i]
            vega = nn_predictions['vega'][i]
            
            # BS calculation с NN IV
            dte_years = max(1/365.0, dte_days / 365.0)
            
            bs_result = black_scholes_safe(
                S=spot,
                K=strike,
                T=dte_years,
                r=risk_free_rate,
                sigma=iv / 100.0,
                option_type='call' if is_call else 'put'
            )
            
            # Combine results
            results.append({
                'strike': strike,
                'iv': iv,
                'delta': delta,  # NN
                'vega': vega,    # NN
                'gamma': bs_result['gamma'],   # BS ← более точная
                'theta': bs_result['theta'],   # BS
                'price': bs_result['price'],   # BS
                'moneyness': spot / strike if strike > 0 else 0
            })
        
        return pd.DataFrame(results)
    
    def calculate_single_strike(
        self,
        market_state: Dict[str, Any],
        strike: float,
        dte_days: int,
        is_call: bool = True,
        risk_free_rate: float = 0.0
    ) -> Dict[str, float]:
        """
        Рассчитывает Greeks для одного страйка.
        
        Args:
            market_state: Словарь с market features
            strike: Цена страйка
            dte_days: Days To Expiration
            is_call: True для call, False для put
            risk_free_rate: Безрисковая ставка
            
        Returns:
            Dict с Greeks для одного страйка
        """
        df = self.calculate_full_greeks(
            market_state=market_state,
            strikes=[strike],
            dte_days=dte_days,
            is_call=is_call,
            risk_free_rate=risk_free_rate
        )
        
        return df.iloc[0].to_dict()
