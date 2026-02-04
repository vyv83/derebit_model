"""
test_data.py — Единый источник тестовых данных для графиков.
Генерирует синтетические данные, максимально приближенные к реальным рыночным условиям.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Any

def norm_pdf(x):
    return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)

def norm_cdf(x):
    # Аппроксимация для CDF
    return 0.5 * (1 + np.vectorize(lambda v: np.sign(v) * np.sqrt(1 - np.exp(-2 * v**2 / np.pi)))(x))

def generate_strike_data(n_points: int = 200, spot_base: float = 50000) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, pd.DataFrame]]:
    """
    Генерирует данные для Strike Chart (свечи + греки).
    """
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=n_points, freq='D')
    
    # Spot (BTC) - базовый актив
    spot = spot_base + np.cumsum(np.random.normal(100, 400, n_points))
    
    # IV 30-100% - волатильность
    iv = np.clip(60 + np.cumsum(np.random.normal(0, 1.2, n_points)), 30, 100)
    
    # Option OHLC - цены опциона
    strike = spot_base + 5000
    intrinsic = np.maximum(spot - strike, 0)
    time_decay = 1 - np.arange(n_points) / n_points
    base_price = intrinsic * 0.2 + iv * 10 * time_decay + 100
    
    opens, highs, lows, closes = [], [], [], []
    prev = base_price[0]
    for i in range(n_points):
        c = base_price[i] + np.random.normal(0, 15)
        h = max(prev, c) + abs(np.random.normal(0, 12))
        l = min(prev, c) - abs(np.random.normal(0, 12))
        opens.append(prev)
        highs.append(h)
        lows.append(l)
        closes.append(c)
        prev = c
    
    df_ohlc = pd.DataFrame({
        'timestamp': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
    })
    
    df_spot = pd.DataFrame({
        'timestamp': dates,
        'value': spot.tolist(),
    })
    
    # Греки
    df_greeks = {
        'iv': pd.DataFrame({'timestamp': dates, 'value': iv.tolist()}),
        'theta': pd.DataFrame({'timestamp': dates, 'value': (-25 - iv/8 + np.random.normal(0, 3, n_points)).tolist()}),
        'delta': pd.DataFrame({'timestamp': dates, 'value': np.clip(0.4 + 0.15*np.sin(np.arange(n_points)/10) + 0.05*np.random.randn(n_points), 0, 1).tolist()}),
        'gamma': pd.DataFrame({'timestamp': dates, 'value': (0.001 + 0.0003*np.cos(np.arange(n_points)/15) + 0.00005*np.random.randn(n_points)).tolist()}),
        'vega': pd.DataFrame({'timestamp': dates, 'value': (80 + 25*np.sin(np.arange(n_points)/20) + 5*np.random.randn(n_points)).tolist()}),
    }
    
    return df_ohlc, df_spot, df_greeks

def generate_smile_data(spot: float = 50000, dtes: list = None) -> Dict[int, pd.DataFrame]:
    """
    Генерирует данные для Smile Chart (улыбка волатильности).
    """
    if dtes is None:
        dtes = [7, 30, 90]
    
    strikes = np.linspace(spot * 0.7, spot * 1.3, 25)
    moneyness = np.log(strikes / spot)
    
    result = {}
    for dte in dtes:
        T = dte / 365.0
        base_iv = 50 + 10 / np.sqrt(T + 0.1)
        iv = np.clip(base_iv + 40 * moneyness**2 - 8 * moneyness, 20, 150)
        
        sigma = iv / 100
        d1 = (np.log(spot / strikes) + (0.05 + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        
        result[dte] = pd.DataFrame({
            'strike': strikes,
            'iv': iv,
            'delta': norm_cdf(d1),
            'gamma': norm_pdf(d1) / (spot * sigma * np.sqrt(T)) * 10000,
            'theta': -(spot * norm_pdf(d1) * sigma) / (2 * np.sqrt(T)) / 365,
            'vega': spot * np.sqrt(T) * norm_pdf(d1) / 100,
        })
    
    return result

def generate_surface_data(spot: float = 50000, n_strikes: int = 40, n_dtes: int = 15) -> Dict[str, Any]:
    """
    Генерирует данные для Surface Chart (3D поверхность).
    """
    strikes = np.linspace(spot * 0.6, spot * 1.4, n_strikes)
    dtes = np.linspace(1, 120, n_dtes)
    
    S_mesh, T_mesh = np.meshgrid(strikes, dtes)
    T_years = T_mesh / 365.0
    
    # IV Surface
    moneyness = np.log(S_mesh / spot)
    iv_surface = 50 + 60 * moneyness**2 + 5 / np.sqrt(T_years + 0.05)
    iv_surface = np.clip(iv_surface, 15, 180)
    
    # Greeks
    v = iv_surface / 100.0
    sqrt_T = np.sqrt(np.maximum(T_years, 1e-10))
    d1 = (np.log(spot / S_mesh) + 0.5 * v**2 * T_years) / (v * sqrt_T)
    
    delta = norm_cdf(d1)
    gamma = norm_pdf(d1) / (spot * v * sqrt_T) * 10000
    theta = -(spot * norm_pdf(d1) * v) / (2 * sqrt_T) / 365
    vega = spot * sqrt_T * norm_pdf(d1) / 100
    
    return {
        'strikes': strikes.tolist(),
        'dtes': dtes.tolist(),
        'iv': iv_surface.tolist(),
        'delta': delta.tolist(),
        'gamma': gamma.tolist(),
        'theta': theta.tolist(),
        'vega': vega.tolist(),
        'spot': spot
    }

if __name__ == "__main__":
    # Быстрый тест генерации
    df_ohlc, df_spot, df_greeks = generate_strike_data()
    print(f"Strike Data: OHLC shape {df_ohlc.shape}, Spot shape {df_spot.shape}")
    
    smile_data = generate_smile_data()
    print(f"Smile Data: Generated for {list(smile_data.keys())} DTEs")
    
    surface_data = generate_surface_data()
    print(f"Surface Data: Strikes={len(surface_data['strikes'])}, DTEs={len(surface_data['dtes'])}")
    print("✅ Test data generation successful.")
