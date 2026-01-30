"""
Black-Scholes Option Pricing
=============================
Complete Black-Scholes implementation with all Greeks.
"""

import numpy as np
from scipy.stats import norm


def black_scholes_safe(S, K, T, r, sigma, option_type='call'):
    """
    Black-Scholes pricing с полным набором Greeks
    
    ⚠️ ИСПОЛЬЗУЙТЕ r=0.0 для криптовалютных опционов!
    
    Parameters:
    -----------
    S : float
        Spot price (текущая цена актива)
    K : float
        Strike price
    T : float
        Time to expiration в ГОДАХ (30 дней = 30/365 = 0.0822)
    r : float
        Risk-free rate (0.0 для крипты, ~0.04-0.05 для акций)
    sigma : float
        Implied volatility в долях (70% = 0.70, НЕ 70!)
    option_type : str
        'call' или 'put'
    
    Returns:
    --------
    dict: {
        'price': Теоретическая цена опциона,
        'delta': Delta,
        'gamma': Gamma,
        'vega': Vega (per 1% IV change),
        'theta': Theta (daily decay в $),
        'rho': Rho (per 1% rate change)
    }
    
    Examples:
    ---------
    >>> greeks = black_scholes_safe(45000, 50000, 30/365, 0.0, 0.72, 'call')
    >>> print(f"Price: ${greeks['price']:.2f}, Gamma: {greeks['gamma']:.8f}")
    """
    
    # ========================================
    # Обработка экспирированных опционов
    # ========================================
    if T <= 0:
        intrinsic = max(0, S - K) if option_type == 'call' else max(0, K - S)
        return {
            'price': intrinsic,
            'delta': 1.0 if (option_type == 'call' and S > K) else 0.0,
            'gamma': 0.0,
            'vega': 0.0,
            'theta': 0.0,
            'rho': 0.0
        }
    
    # ========================================
    # Safety: защита от малых T и некорректных sigma
    # ========================================
    MIN_TIME_HOURS = 1.0
    T_safe = max(T, MIN_TIME_HOURS / 24 / 365)
    
    if sigma <= 0:
        sigma_safe = 0.05  # Минимум 5%
    elif sigma > 5.0:
        sigma_safe = 5.0   # Максимум 500%
    else:
        sigma_safe = sigma
    
    # Валидация входных параметров
    if S <= 0 or K <= 0:
        raise ValueError(f"Spot ({S}) и Strike ({K}) должны быть > 0")
    
    # ========================================
    # Вычисление d1, d2
    # ========================================
    try:
        d1 = (np.log(S / K) + (r + 0.5 * sigma_safe**2) * T_safe) / (sigma_safe * np.sqrt(T_safe))
        d2 = d1 - sigma_safe * np.sqrt(T_safe)
    except (ValueError, ZeroDivisionError, FloatingPointError):
        intrinsic = max(0, S - K) if option_type == 'call' else max(0, K - S)
        return {
            'price': intrinsic,
            'delta': 0.0,
            'gamma': 0.0,
            'vega': 0.0,
            'theta': 0.0,
            'rho': 0.0
        }
    
    # Клампинг для защиты от overflow
    d1 = np.clip(d1, -10, 10)
    d2 = np.clip(d2, -10, 10)
    
    # ========================================
    # PRICE
    # ========================================
    if option_type == 'call':
        price = S * norm.cdf(d1) - K * np.exp(-r * T_safe) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * T_safe) * norm.cdf(-d2) - S * norm.cdf(-d1)
    
    price = max(price, 0.0)
    
    # ========================================
    # DELTA
    # ========================================
    if option_type == 'call':
        delta = norm.cdf(d1)
    else:
        delta = norm.cdf(d1) - 1
    
    # ========================================
    # GAMMA (одинаковая для call/put)
    # ========================================
    gamma = norm.pdf(d1) / (S * sigma_safe * np.sqrt(T_safe))
    
    # ========================================
    # VEGA (одинаковая для call/put)
    # ========================================
    # Per 1% IV change
    vega = S * norm.pdf(d1) * np.sqrt(T_safe) / 100
    
    # ========================================
    # THETA (daily)
    # ========================================
    if option_type == 'call':
        theta_annual = (
            - (S * norm.pdf(d1) * sigma_safe) / (2 * np.sqrt(T_safe))
            - r * K * np.exp(-r * T_safe) * norm.cdf(d2)
        )
    else:
        theta_annual = (
            - (S * norm.pdf(d1) * sigma_safe) / (2 * np.sqrt(T_safe))
            + r * K * np.exp(-r * T_safe) * norm.cdf(-d2)
        )
    
    theta_daily = theta_annual / 365.0
    
    # ========================================
    # RHO
    # ========================================
    if option_type == 'call':
        rho = K * T_safe * np.exp(-r * T_safe) * norm.cdf(d2) / 100
    else:
        rho = -K * T_safe * np.exp(-r * T_safe) * norm.cdf(-d2) / 100
    
    # ========================================
    # Финальная валидация
    # ========================================
    if np.isnan(price) or np.isinf(price):
        price = max(0, S - K) if option_type == 'call' else max(0, K - S)
    
    # Проверка Greeks на NaN/Inf
    delta = 0.0 if (np.isnan(delta) or np.isinf(delta)) else delta
    gamma = 0.0 if (np.isnan(gamma) or np.isinf(gamma)) else gamma
    vega = 0.0 if (np.isnan(vega) or np.isinf(vega)) else vega
    theta_daily = 0.0 if (np.isnan(theta_daily) or np.isinf(theta_daily)) else theta_daily
    rho = 0.0 if (np.isnan(rho) or np.isinf(rho)) else rho
    
    return {
        'price': price,
        'delta': delta,
        'gamma': gamma,
        'vega': vega,
        'theta': theta_daily,
        'rho': rho
    }
