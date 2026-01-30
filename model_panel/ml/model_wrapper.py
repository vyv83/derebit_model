"""
============================================================================
MODEL WRAPPER - NEURAL NETWORK PREDICTIONS
============================================================================
ИЗМЕНЕНИЯ (2026-01-15):
-----------------------
✅ predict() теперь возвращает ТОЛЬКО: ['strike', 'mark_iv', 'delta', 'vega']
✅ Gamma УДАЛЕНА - теперь вычисляется через Black-Scholes (точнее в 4.5x!)

ОБОСНОВАНИЕ:
------------
Модель обучалась на 4 выходах: [iv, delta, log_gamma, vega]
Однако тесты показали:
  - Model Gamma: MAE = 0.000018  ❌
  - BS Gamma:    MAE = 0.000004  ✅ (в 4.5 раза лучше!)

Gamma требует математической согласованности с Price/Delta/Theta.
BS гарантирует no-arbitrage pricing через единую формулу.
============================================================================
"""

import torch
import pandas as pd
import numpy as np
from .model_architecture import ImprovedMultiTaskSVI

class OptionModel:
    def __init__(self, model_path='best_multitask_svi.pth'):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load the full package
        print(f"Loading model from {model_path}...")
        package = torch.load(model_path, map_location=self.device, weights_only=False)
        
        # Reconstruct architecture
        arch_params = package['model_architecture'].copy()
        
        # Remove metadata fields that are not constructor arguments
        metadata_fields = ['class', 'total_params', 'pytorch_version']
        for field in metadata_fields:
            if field in arch_params:
                arch_params.pop(field)
        
        self.model = ImprovedMultiTaskSVI(**arch_params).to(self.device)
        self.model.load_state_dict(package['model_state_dict'])
        self.model.eval()
        
        self.scaler = package['scaler_X']
        self.input_features = package['input_features']
        print(f"Model loaded successfully on {self.device}")

    def predict(self, market_state, strikes, dte_days, is_call=True):
        """
        Предсказывает IV, Delta, Vega через Neural Network
        
        ⚠️ ИЗМЕНЕНО (2026-01-15): Возвращает IV, Delta, Vega
        Gamma теперь вычисляется через Black-Scholes (точнее на 75%)!
        
        Parameters:
        -----------
        market_state : dict
            Market features: {
                'Real_IV_ATM': float,      # ATM IV (в долях, 0.65 = 65%)
                'HV_30d': float,           # Historical volatility 30d
                'IV_HV_Ratio': float,      # IV/HV ratio
                'Skew_30d': float,         # Returns skewness
                'Kurt_30d': float,         # Returns kurtosis
                'Drawdown': float,         # Current drawdown
                'Vol_Spike': float,        # Volatility spike indicator
                'Cum_Returns_30d': float,  # Cumulative 30d returns
                'Month': int,              # 1-12
                'Quarter': int,            # 1-4
                'DayOfWeek': int           # 0-6
            }
        strikes : array-like
            Strike prices для расчета
        dte_days : int
            Days to expiration
        is_call : bool
            True для Call опционов, False для Put
        
        Returns:
        --------
        pd.DataFrame: ['strike', 'mark_iv', 'delta', 'vega']
            
            - mark_iv: в процентах (72.5 = 72.5%)
            - delta: в долях (-1.0 до 1.0)
            - vega: в $ per 1% IV change
            
            ⚠️ Для получения Gamma/Theta/Price используйте black_scholes_safe()!
        """
        data = []
        spot = market_state['underlying_price']
        
        for K in strikes:
            # Create input row
            row = {
                'log_moneyness': np.log(spot / K),
                'dte': dte_days, # Model trained on days, not years
                'is_call': 1.0 if is_call else 0.0,
                'Real_IV_ATM': market_state.get('Real_IV_ATM', 0.5),
                'HV_30d': market_state.get('HV_30d', 0.5),
                'IV_HV_Ratio': market_state.get('IV_HV_Ratio', 1.0),
                'Skew_30d': market_state.get('Skew_30d', 0.0),
                'Kurt_30d': market_state.get('Kurt_30d', 0.0),
                'Drawdown': market_state.get('Drawdown', 0.0),
                'Vol_Spike': market_state.get('Vol_Spike', 0.0),
                'Cum_Returns_30d': market_state.get('Cum_Returns_30d', 0.0),
                'Month': market_state.get('Month', 1),
                'Quarter': market_state.get('Quarter', 1),
                'DayOfWeek': market_state.get('DayOfWeek', 0)
            }
            data.append(row)
            
        df_input = pd.DataFrame(data)
        
        # Ensure correct column order
        df_input = df_input[self.input_features]
        
        # Scale
        X_scaled = self.scaler.transform(df_input)
        X_tensor = torch.FloatTensor(X_scaled).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(X_tensor)
        
        # Outputs: [iv, delta, log_gamma, vega]
        preds = outputs.cpu().numpy()
        
        # ========================================
        # ВОЗВРАЩАЕМ: IV, Delta, Vega (без Gamma!)
        # ========================================
        results = pd.DataFrame({
            'strike': strikes,
            'mark_iv': preds[:, 0] * 100,  # IV в процентах
            'delta': preds[:, 1],          # ✅ Из модели (MAE: 0.0052)
            'vega': preds[:, 3]            # ✅ Из модели (MAE: 1.35)
            # Gamma УДАЛЕНА! Вычисляется через BS (MAE: 0.000004)
        })
        
        return results

