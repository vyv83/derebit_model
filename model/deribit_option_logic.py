"""
STRIKES UTILS - FINAL PROPER VERSION
====================================
1. Экспирации: Оригинальная логика (Стабильно)
2. Страйки: V5 Ultimate (Accumulation, Parabolic, Magnet)
3. Конфигурация: Единый центр в strikes_v5_core.py
"""

import numpy as np
import calendar
from datetime import datetime, timedelta
import pandas as pd
from typing import Tuple, List, Optional
import deribit_strikes_engine as v5

# ==============================================================================
# 1. ЭКСПИРАЦИИ (БИРЖЕВАЯ ЛОГИКА)
# ==============================================================================

def get_last_friday(year: int, month: int) -> datetime:
    """Возвращает дату последней пятницы месяца."""
    last_day = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day)
    offset = (last_date.weekday() - 4) % 7
    return last_date - timedelta(days=offset)

def round_to_nice_tick(value: float) -> float:
    """Округление к биржевым тикам (nice numbers)."""
    if value <= 1e-9: return 0.0
    magnitude = 10 ** np.floor(np.log10(value))
    normalized = value / magnitude
    
    if normalized < 1.485: nice = 1.0
    elif normalized < 2.2275: nice = 2.0
    elif normalized < 3.7125: nice = 2.5
    elif normalized < 7.425: nice = 5.0
    else: nice = 10.0
    
    result = nice * magnitude
    return round(result) if result >= 1 else round(result, -int(np.floor(np.log10(result))) + 2)

def generate_deribit_expirations(current_date: datetime) -> List[Tuple[datetime, int]]:
    """Генерирует стандартный набор экспираций Deribit."""
    curr = current_date.replace(hour=8, minute=0, second=0, microsecond=0)
    exp_counts = {} 

    # Dailies
    for i in range(4):
        d = curr + timedelta(days=i)
        exp_counts.setdefault(d, set()).add('daily')

    # Weeklies
    days_to_fri = (4 - curr.weekday() + 7) % 7
    if days_to_fri == 0 and curr.hour >= 8: days_to_fri = 7 
    first_friday = curr + timedelta(days=days_to_fri)
    for i in range(4):
        d = first_friday + timedelta(weeks=i)
        exp_counts.setdefault(d, set()).add('weekly')

    # Monthlies
    for i in range(3):
        m = (curr.month + i - 1) % 12 + 1
        y = curr.year + (curr.month + i - 1) // 12
        d = get_last_friday(y, m).replace(hour=8, minute=0, second=0, microsecond=0)
        if d >= curr: exp_counts.setdefault(d, set()).add('monthly')

    # Quarterlies
    for i in range(24): 
        m = (curr.month + i - 1) % 12 + 1
        if m in [3, 6, 9, 12]:
            y = curr.year + (curr.month + i - 1) // 12
            d = get_last_friday(y, m).replace(hour=8, minute=0, second=0, microsecond=0)
            if d >= curr and d <= curr + timedelta(days=365):
                exp_counts.setdefault(d, set()).add('quarterly')

    sorted_dates = sorted(exp_counts.keys())[:24]
    return [(d, len(exp_counts[d])) for d in sorted_dates]

def get_birth_date(exp_date) -> Tuple[datetime, int]:
    """Определяет теоретическую дату рождения контракта (Lead Time)."""
    if isinstance(exp_date, str): exp_date = datetime.strptime(exp_date, "%Y-%m-%d")
    is_friday = (exp_date.weekday() == 4)
    
    if not is_friday: lead = 3
    else:
        lf = get_last_friday(exp_date.year, exp_date.month)
        is_last = (exp_date.date() == lf.date())
        if not is_last: lead = 28
        else: lead = 365 if exp_date.month in [3, 6, 9, 12] else 90
    
    return exp_date - timedelta(days=lead), lead

def calculate_time_layers(current_date, birth_date) -> List[Tuple[str, datetime, datetime]]:
    """Формирует слои истории для аналитики."""
    if isinstance(current_date, str): current_date = pd.to_datetime(current_date)
    if isinstance(birth_date, str): birth_date = pd.to_datetime(birth_date)
    
    # Берем настройки из единого конфига V5
    cfg = v5.CONFIG
    layers = []
    
    t_d = current_date - timedelta(days=cfg.DAILY_LOOKBACK)
    t_w = current_date - timedelta(days=cfg.WEEKLY_LOOKBACK)
    t_m = current_date - timedelta(days=cfg.MONTHLY_LOOKBACK)
    
    # Слой Recent
    s_recent = max(birth_date, t_d)
    layers.append(('recent', s_recent, current_date))
    
    # Слой Medium
    if t_d > birth_date:
        s_medium = max(birth_date, t_w)
        if s_medium < t_d: layers.append(('medium', s_medium, t_d))
        
    # Слой Old
    if t_w > birth_date:
        s_old = max(birth_date, t_m)
        if s_old < t_w: layers.append(('old', s_old, t_w))
    
    return layers

# ==============================================================================
# 2. ГЕНЕРАЦИЯ СТРАЙКОВ (V5 ULTIMATE)
# ==============================================================================

def generate_deribit_strikes(
    current_spot: float,
    current_dte: int,
    anchor_spot: float,
    anchor_vol: float,
    birth_dte: int,
    historical_ranges: List = None,
    coincidence_count: int = 1,
    price_history: Optional[List[float]] = None,
    iv_history: Optional[List[float]] = None
) -> List[int]:
    """
    Основная точка входа для генерации страйков.
    Использует V5 Accumulation если есть история, иначе Fallback Parabolic.
    """
    # 1. ПРАВИЛЬНЫЙ ПУТЬ: Полноценная V5 симуляция
    if price_history is not None and iv_history is not None and len(price_history) > 0:
        dna = v5.ContractDNA(anchor_spot, anchor_vol, birth_dte)
        current_day = len(price_history) - 1
        
        final_indices, _ = v5.simulate_board_evolution(
            dna=dna, price_history=price_history, iv_history=iv_history, target_day=current_day
        )
        
        table = v5.GridEngine.generate_table()
        return sorted([int(table[idx]) for idx in final_indices if idx < len(table)])

    # 2. FALLBACK: Одиночный расчет (если истории нет)
    center_idx = v5.GridEngine.find_index(current_spot)
    raw_indices = v5.parabolic_distribution_cached(
        center_idx, round(current_spot, 2), round(anchor_vol, 4), current_dte
    )
    
    # Выбор шага магнита
    if current_dte > v5.CONFIG.MAGNET_THRESHOLD_LONG: step = v5.CONFIG.MAGNET_STEP_LONG
    elif current_dte > v5.CONFIG.MAGNET_THRESHOLD_MID: step = v5.CONFIG.MAGNET_STEP_MID
    else: step = v5.CONFIG.MAGNET_STEP_SHORT
    
    filtered = {(idx // step) * step for idx in raw_indices}
    table = v5.GridEngine.generate_table()
    return sorted([int(table[idx]) for idx in filtered if idx < len(table)])
