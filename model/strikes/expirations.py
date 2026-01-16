"""
Expirations Module
==================
Deribit-standard expiration generation and contract birth date calculation.

Implements exchange-specific logic for daily, weekly, monthly, and quarterly expirations.
"""

import numpy as np
import calendar
import pandas as pd  
from datetime import datetime, timedelta
from typing import Tuple, List

from .config import CONFIG


def get_last_friday(year: int, month: int) -> datetime:
    """
    Возвращает дату последней пятницы месяца.
    
    Args:
        year: Год
        month: Месяц (1-12)
        
    Returns:
        Datetime последней пятницы месяца (8:00 UTC)
    """
    last_day = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day)
    offset = (last_date.weekday() - 4) % 7
    return last_date - timedelta(days=offset)


def round_to_nice_tick(value: float) -> float:
    """
    Округление к биржевым тикам (nice numbers).
    
    Args:
        value: Значение для округления
        
    Returns:
        Округленное значение (1, 2, 2.5, 5, 10 * magnitude)
        
    Note:
        Используется Deribit для "красивых" уровней в цепочках опционов.
    """
    if value <= 1e-9:
        return 0.0
    magnitude = 10 ** np.floor(np.log10(value))
    normalized = value / magnitude
    
    if normalized < 1.485:
        nice = 1.0
    elif normalized < 2.2275:
        nice = 2.0
    elif normalized < 3.7125:
        nice = 2.5
    elif normalized < 7.425:
        nice = 5.0
    else:
        nice = 10.0
    
    result = nice * magnitude
    return round(result) if result >= 1 else round(result, -int(np.floor(np.log10(result))) + 2)


def generate_deribit_expirations(current_date: datetime) -> List[Tuple[datetime, int]]:
    """
    Генерирует стандартный набор экспираций Deribit.
    
    Args:
        current_date: Текущая дата
        
    Returns:
        List[(expiration_date, coincidence_count)]
        где coincidence_count = количество типов экспираций на эту дату
        (daily=1, weekly=1, monthly=1, quarterly=1)
        
    Note:
        Возвращает до 24 ближайших экспираций:
        - 4 daily (каждый день)
        - 4 weekly (следующие 4 пятницы)
        - 3 monthly (последние пятницы ближайших 3 месяцев)
        - Quarterlies (последние пятницы марта, июня, сентября, декабря)
    """
    curr = current_date.replace(hour=8, minute=0, second=0, microsecond=0)
    exp_counts = {} 

    # Dailies: следующие 4 дня
    for i in range(4):
        d = curr + timedelta(days=i)
        exp_counts.setdefault(d, set()).add('daily')

    # Weeklies: следующие 4 пятницы
    days_to_fri = (4 - curr.weekday() + 7) % 7
    if days_to_fri == 0 and curr.hour >= 8:
        days_to_fri = 7  # Если уже пятница после 8:00, берем следующую
    first_friday = curr + timedelta(days=days_to_fri)
    for i in range(4):
        d = first_friday + timedelta(weeks=i)
        exp_counts.setdefault(d, set()).add('weekly')

    # Monthlies: последние пятницы ближайших 3 месяцев
    for i in range(3):
        m = (curr.month + i - 1) % 12 + 1
        y = curr.year + (curr.month + i - 1) // 12
        d = get_last_friday(y, m).replace(hour=8, minute=0, second=0, microsecond=0)
        if d >= curr:
            exp_counts.setdefault(d, set()).add('monthly')

    # Quarterlies: последние пятницы квартальных месяцев (март, июнь, сентябрь, декабрь)
    for i in range(24):  # Ищем в пределах 2 лет
        m = (curr.month + i - 1) % 12 + 1
        if m in [3, 6, 9, 12]:
            y = curr.year + (curr.month + i - 1) // 12
            d = get_last_friday(y, m).replace(hour=8, minute=0, second=0, microsecond=0)
            if d >= curr and d <= curr + timedelta(days=365):
                exp_counts.setdefault(d, set()).add('quarterly')

    sorted_dates = sorted(exp_counts.keys())[:24]
    return [(d, len(exp_counts[d])) for d in sorted_dates]


def get_birth_date(exp_date) -> Tuple[datetime, int]:
    """
    Определяет теоретическую дату рождения контракта (Lead Time).
    
    Args:
        exp_date: Дата экспирации (datetime или str 'YYYY-MM-DD')
        
    Returns:
        (birth_date, lead_days): дата рождения и количество дней lead time
        
    Note:
        Lead time зависит от типа экспирации:
        - Daily: 3 дня
        - Weekly (не последняя пятница месяца): 28 дней (4 недели)
        - Monthly (последняя пятница не-квартального месяца): 90 дней (3 месяца)
        - Quarterly (посл. пятница март/июнь/сент/дек): 365 дней (1 год)
    """
    if isinstance(exp_date, str):
        exp_date = datetime.strptime(exp_date, "%Y-%m-%d")
    
    is_friday = (exp_date.weekday() == 4)
    
    if not is_friday:
        lead = 3  # Daily
    else:
        lf = get_last_friday(exp_date.year, exp_date.month)
        is_last = (exp_date.date() == lf.date())
        if not is_last:
            lead = 28  # Weekly (не последняя пятница)
        else:
            # Последняя пятница
            if exp_date.month in [3, 6, 9, 12]:
                lead = 365  # Quarterly
            else:
                lead = 90  # Monthly
    
    return exp_date - timedelta(days=lead), lead


def calculate_time_layers(current_date, birth_date) -> List[Tuple[str, datetime, datetime]]:
    """
    Формирует слои истории для аналитики.
    
    Args:
        current_date: Current datetime (может быть str или datetime)
        birth_date: Birth datetime (может быть str или datetime)
        
    Returns:
        List[(layer_name, start_date, end_date)]
        
        Layers:
        - 'recent': last DAILY_LOOKBACK days (default 7)
        - 'medium': DAILY_LOOKBACK to WEEKLY_LOOKBACK days ago (default 7-30)
        - 'old': WEEKLY_LOOKBACK to MONTHLY_LOOKBACK days ago (default 30-90)
        
    Note:
        Используется CONFIG.DAILY_LOOKBACK, WEEKLY_LOOKBACK, MONTHLY_LOOKBACK
        для определения границ слоев.
    """
    if isinstance(current_date, str):
        current_date = pd.to_datetime(current_date)
    if isinstance(birth_date, str):
        birth_date = pd.to_datetime(birth_date)
    
    layers = []
    
    t_d = current_date - timedelta(days=CONFIG.DAILY_LOOKBACK)
    t_w = current_date - timedelta(days=CONFIG.WEEKLY_LOOKBACK)
    t_m = current_date - timedelta(days=CONFIG.MONTHLY_LOOKBACK)
    
    # Слой Recent
    s_recent = max(birth_date, t_d)
    layers.append(('recent', s_recent, current_date))
    
    # Слой Medium
    if t_d > birth_date:
        s_medium = max(birth_date, t_w)
        if s_medium < t_d:
            layers.append(('medium', s_medium, t_d))
        
    # Слой Old
    if t_w > birth_date:
        s_old = max(birth_date, t_m)
        if s_old < t_w:
            layers.append(('old', s_old, t_w))
    
    return layers
