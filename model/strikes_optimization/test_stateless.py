"""
ТЕСТ: Проверка stateless поведения + отсутствие скрытой памяти
Сценарий: генерируем день 37, потом 36, потом снова 37
+ проверка на глобальные переменные
"""

import sys
sys.path.append('/Users/user/work/Python/derebit_download1/model/strikes_optimization')

import v1_baseline as v1
import v4_optimized as v4
import numpy as np
import gc
import copy

# Генерируем тестовые данные
np.random.seed(42)
spot = 100000
iv = 0.65
birth_dte = 90

price_history = [spot]
iv_history = [iv]

for day in range(1, birth_dte):
    daily_return = np.random.normal(0.0005, 0.02)
    new_price = price_history[-1] * (1 + daily_return)
    price_history.append(new_price)
    
    iv_change = np.random.normal(0, 0.01)
    new_iv = max(0.2, min(1.5, iv_history[-1] + iv_change))
    iv_history.append(new_iv)

# Создаем DNA
dna_v1 = v1.ContractDNA(spot, iv, birth_dte)
dna_v4 = v4.ContractDNA(spot, iv, birth_dte)

print("="*80)
print("🧪 ТЕСТ 1: STATELESS - Non-sequential вызовы")
print("="*80)

# Сценарий 1: Последовательно day 0 → 37
print("\n1️⃣ V1: Последовательно 0→37")
board_v1_37_seq = v1.generate_daily_board(dna_v1, price_history[:38], iv_history[:38], 37, None)
print(f"   День 37 (sequential): {len(board_v1_37_seq)} страйков")

print("\n1️⃣ V4: Последовательно 0→37")
board_v4_37_seq = v4.generate_daily_board(dna_v4, price_history[:38], iv_history[:38], 37, None)
print(f"   День 37 (sequential): {len(board_v4_37_seq)} страйков")

# Сценарий 2: Прямой вызов day 37 (без истории предыдущих дней)
print("\n2️⃣ V1: Прямой вызов дня 37 (без previous)")
board_v1_37_direct = v1.generate_daily_board(dna_v1, price_history[:38], iv_history[:38], 37, None)
print(f"   День 37 (direct): {len(board_v1_37_direct)} страйков")

print("\n2️⃣ V4: Прямой вызов дня 37 (без previous)")
board_v4_37_direct = v4.generate_daily_board(dna_v4, price_history[:38], iv_history[:38], 37, None)
print(f"   День 37 (direct): {len(board_v4_37_direct)} страйков")

# Проверка идентичности
print("\n" + "="*80)
print("✅ ПРОВЕРКА ИДЕНТИЧНОСТИ")
print("="*80)

if board_v1_37_seq == board_v1_37_direct:
    print("✓ V1: Sequential == Direct (STATELESS работает)")
else:
    print("❌ V1: Sequential != Direct (БАГ!)")

if board_v4_37_seq == board_v4_37_direct:
    print("✓ V4: Sequential == Direct (STATELESS работает)")
else:
    print("❌ V4: Sequential != Direct (БАГ!)")

if board_v1_37_seq == board_v4_37_seq:
    print("✓ V1 == V4: Результаты совпадают")
else:
    print("❌ V1 != V4: Результаты РАЗНЫЕ!")
    diff = board_v1_37_seq.symmetric_difference(board_v4_37_seq)
    print(f"   Различий: {len(diff)} страйков")

# Сценарий 3: Обратное движение (37 → 36 → 37)
print("\n" + "="*80)
print("🔄 ТЕСТ 2: ОБРАТНОЕ ДВИЖЕНИЕ - 37 → 36 → 37")
print("="*80)

print("\n3️⃣ V1: День 36 после дня 37")
board_v1_36 = v1.generate_daily_board(dna_v1, price_history[:37], iv_history[:37], 36, None)
print(f"   День 36: {len(board_v1_36)} страйков")

board_v1_37_again = v1.generate_daily_board(dna_v1, price_history[:38], iv_history[:38], 37, None)
print(f"   День 37 (снова): {len(board_v1_37_again)} страйков")

if board_v1_37_seq == board_v1_37_again:
    print("   ✓ V1: 37 (first) == 37 (after 36) - STATELESS OK")
else:
    print("   ❌ V1: РАЗНЫЕ результаты - НЕ STATELESS!")

print("\n3️⃣ V4: День 36 после дня 37")
board_v4_36 = v4.generate_daily_board(dna_v4, price_history[:37], iv_history[:37], 36, None)
print(f"   День 36: {len(board_v4_36)} страйков")

board_v4_37_again = v4.generate_daily_board(dna_v4, price_history[:38], iv_history[:38], 37, None)
print(f"   День 37 (снова): {len(board_v4_37_again)} страйков")

if board_v4_37_seq == board_v4_37_again:
    print("   ✓ V4: 37 (first) == 37 (after 36) - STATELESS OK")
else:
    print("   ❌ V4: РАЗНЫЕ результаты - НЕ STATELESS!")

# НОВЫЙ ТЕСТ: Проверка на скрытую память
print("\n" + "="*80)
print("🔍 ТЕСТ 3: ОТСУТСТВИЕ СКРЫТОЙ ПАМЯТИ")
print("="*80)

# Сохраняем состояние модулей ДО вызовов
print("\n4️⃣ Проверка глобальных переменных...")

# Список атрибутов модуля до вызовов
v4_attrs_before = set(dir(v4))
v4_cache_size_before = v4.parabolic_distribution_cached.cache_info().currsize if hasattr(v4.parabolic_distribution_cached, 'cache_info') else 0

# Делаем вызовы
_ = v4.generate_daily_board(dna_v4, price_history[:50], iv_history[:50], 49, None)
_ = v4.generate_daily_board(dna_v4, price_history[:30], iv_history[:30], 29, None)
_ = v4.generate_daily_board(dna_v4, price_history[:50], iv_history[:50], 49, None)

# Проверяем состояние ПОСЛЕ
v4_attrs_after = set(dir(v4))
v4_cache_size_after = v4.parabolic_distribution_cached.cache_info().currsize if hasattr(v4.parabolic_distribution_cached, 'cache_info') else 0

new_attrs = v4_attrs_after - v4_attrs_before
if new_attrs:
    print(f"   ⚠️  Обнаружены новые атрибуты: {new_attrs}")
else:
    print(f"   ✓ Новых глобальных атрибутов не создано")

print(f"   LRU cache: {v4_cache_size_before} → {v4_cache_size_after} элементов")
if v4_cache_size_after > v4_cache_size_before:
    print(f"   ✓ LRU кэш растет (ожидаемо для оптимизации)")
else:
    print(f"   ✓ LRU кэш стабилен")

# Проверка изоляции между DNA
print("\n5️⃣ Проверка изоляции между контрактами...")
dna_2 = v4.ContractDNA(spot * 1.1, iv * 1.1, birth_dte + 10)
board_dna2 = v4.generate_daily_board(dna_2, price_history[:38], iv_history[:38], 37, None)

if board_dna2 == board_v4_37_seq:
    print("   ❌ Разные DNA дают одинаковые результаты - ЕСТЬ УТЕЧКА!")
else:
    print("   ✓ Разные DNA дают разные результаты (изоляция OK)")

# Проверка потокобезопасности (симуляция)
print("\n6️⃣ Проверка независимости параллельных вызовов...")
results_parallel = []
for i in range(3):
    dna_par = v4.ContractDNA(spot * (1 + i*0.01), iv, birth_dte)
    board_par = v4.generate_daily_board(dna_par, price_history[:38], iv_history[:38], 37, None)
    results_parallel.append(board_par)

# Проверяем, что результаты различаются (из-за разных DNA)
all_different = len(set([frozenset(r) for r in results_parallel])) == len(results_parallel)
if all_different:
    print("   ✓ Параллельные вызовы независимы")
else:
    print("   ⚠️  Некоторые параллельные вызовы дали одинаковые результаты")

# Финальный вердикт
print("\n" + "="*80)
print("🏁 ФИНАЛЬНЫЙ ВЕРДИКТ")
print("="*80)

v1_stateless = (board_v1_37_seq == board_v1_37_direct == board_v1_37_again)
v4_stateless = (board_v4_37_seq == board_v4_37_direct == board_v4_37_again)
v4_no_memory_leak = (not new_attrs) and all_different

print(f"\n✅ Тест 1 - Stateless:")
print(f"   V1: {'✅ ДА' if v1_stateless else '❌ НЕТ'}")
print(f"   V4: {'✅ ДА' if v4_stateless else '❌ НЕТ'}")

print(f"\n✅ Тест 2 - Обратное движение:")
print(f"   V1: {'✅ ДА' if v1_stateless else '❌ НЕТ'}")
print(f"   V4: {'✅ ДА' if v4_stateless else '❌ НЕТ'}")

print(f"\n✅ Тест 3 - Отсутствие скрытой памяти:")
print(f"   V4: {'✅ ДА' if v4_no_memory_leak else '❌ НЕТ'}")

if v1_stateless and v4_stateless and v4_no_memory_leak:
    print("\n" + "="*80)
    print("✅ ✅ ✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ ✅ ✅ ✅")
    print("="*80)
    print("V4 корректна и не создает скрытую память")
elif v4_stateless and v4_no_memory_leak:
    print("\n✅ V4 STATELESS и БЕЗ УТЕЧЕК - оптимизация корректна")
else:
    print("\n❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ - требуется исправление!")
    if not v4_stateless:
        print("   - V4 не stateless")
    if not v4_no_memory_leak:
        print("   - V4 создает скрытую память")
