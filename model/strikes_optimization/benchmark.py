"""
BENCHMARK SCRIPT - сравнение производительности версий
"""

import time
import numpy as np
from typing import Dict, Any
import sys

# Import all versions
import v1_baseline as v1
import v2_optimized as v2
import v3_optimized as v3
import v4_optimized as v4


def generate_test_data(birth_dte=90, spot=100000, iv=0.65):
    """Генерирует тестовые данные для бенчмарка"""
    np.random.seed(42)
    price_history = [spot]
    iv_history = [iv]
    
    for day in range(1, birth_dte):
        daily_return = np.random.normal(0.0005, 0.02)
        new_price = price_history[-1] * (1 + daily_return)
        price_history.append(new_price)
        
        iv_change = np.random.normal(0, 0.01)
        new_iv = max(0.2, min(1.5, iv_history[-1] + iv_change))
        iv_history.append(new_iv)
    
    return price_history, iv_history


def benchmark_version(version_module, version_name, price_history, iv_history, birth_dte):
    """Бенчмарк одной версии"""
    print(f"\n{'='*80}")
    print(f"🔬 BENCHMARK: {version_name}")
    print(f"{'='*80}")
    
    dna = version_module.ContractDNA(price_history[0], iv_history[0], birth_dte)
    
    # Warmup
    _ = version_module.simulate_board_evolution(dna, price_history[:10], iv_history[:10], 9)
    
    # Actual benchmark
    start_time = time.perf_counter()
    
    final_board, board_history = version_module.simulate_board_evolution(
        dna, price_history, iv_history, birth_dte - 1
    )
    
    elapsed_time = time.perf_counter() - start_time
    
    # Results
    sizes = [len(b) for b in board_history]
    
    results = {
        'version': version_name,
        'time': elapsed_time,
        'final_size': sizes[-1],
        'total_days': len(board_history),
        'board_history': board_history,
        'final_board': final_board
    }
    
    print(f"⏱️  Время выполнения: {elapsed_time:.4f} сек")
    print(f"📊 Финальная доска: {sizes[-1]} страйков")
    print(f"📈 Рост: {sizes[0]} → {sizes[-1]} (+{sizes[-1]-sizes[0]})")
    print(f"🔄 Дней симулировано: {len(board_history)}")
    
    return results


def verify_results_match(results_v1, results_v2):
    """Проверяет, что результаты версий идентичны"""
    print(f"\n{'='*80}")
    print(f"✅ ПРОВЕРКА ИДЕНТИЧНОСТИ РЕЗУЛЬТАТОВ")
    print(f"{'='*80}")
    
    errors = []
    
    # Проверка размера финальной доски
    if results_v1['final_size'] != results_v2['final_size']:
        errors.append(f"❌ Размер финальной доски: v1={results_v1['final_size']} vs v2={results_v2['final_size']}")
    else:
        print(f"✓ Размер финальной доски совпадает: {results_v1['final_size']}")
    
    # Проверка количества дней
    if results_v1['total_days'] != results_v2['total_days']:
        errors.append(f"❌ Количество дней: v1={results_v1['total_days']} vs v2={results_v2['total_days']}")
    else:
        print(f"✓ Количество дней совпадает: {results_v1['total_days']}")
    
    # Проверка содержимого финальной доски
    if results_v1['final_board'] != results_v2['final_board']:
        diff = results_v1['final_board'].symmetric_difference(results_v2['final_board'])
        errors.append(f"❌ Содержимое финальной доски отличается: {len(diff)} различий")
    else:
        print(f"✓ Содержимое финальной доски идентично")
    
    # Проверка истории по дням
    all_days_match = True
    for day in range(results_v1['total_days']):
        if results_v1['board_history'][day] != results_v2['board_history'][day]:
            errors.append(f"❌ День {day}: доски отличаются")
            all_days_match = False
            break
    
    if all_days_match:
        print(f"✓ История досок по всем {results_v1['total_days']} дням идентична")
    
    # Итог
    if errors:
        print(f"\n{'='*80}")
        print(f"❌ ❌ ❌ ОШИБКА: РЕЗУЛЬТАТЫ НЕ СОВПАДАЮТ ❌ ❌ ❌")
        print(f"{'='*80}")
        for error in errors:
            print(error)
        return False
    else:
        print(f"\n{'='*80}")
        print(f"✅ ✅ ✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ ✅ ✅ ✅")
        print(f"{'='*80}")
        return True


def compare_performance(results_v1, results_v2):
    """Сравнивает производительность"""
    print(f"\n{'='*80}")
    print(f"⚡ СРАВНЕНИЕ ПРОИЗВОДИТЕЛЬНОСТИ")
    print(f"{'='*80}")
    
    time_v1 = results_v1['time']
    time_v2 = results_v2['time']
    
    speedup = time_v1 / time_v2
    improvement_pct = (1 - time_v2/time_v1) * 100
    
    print(f"\n📊 Время выполнения:")
    print(f"   V1 (Baseline):  {time_v1:.4f} сек")
    print(f"   V2 (Optimized): {time_v2:.4f} сек")
    print(f"\n🚀 Ускорение: {speedup:.2f}x")
    print(f"📈 Улучшение: {improvement_pct:+.1f}%")
    
    if speedup > 1.0:
        print(f"\n✅ V2 БЫСТРЕЕ на {improvement_pct:.1f}%")
    elif speedup < 1.0:
        print(f"\n❌ V2 МЕДЛЕННЕЕ на {abs(improvement_pct):.1f}%")
    else:
        print(f"\n➖ Одинаковая скорость")
    
    return speedup


def evaluate_optimization(speedup):
    """Оценивает качество оптимизации"""
    print(f"\n{'='*80}")
    print(f"📝 ОЦЕНКА ОПТИМИЗАЦИИ (0-10)")
    print(f"{'='*80}")
    
    if speedup >= 10.0:
        score = 10
        grade = "🏆 ПРЕВОСХОДНО - революционная оптимизация!"
    elif speedup >= 5.0:
        score = 9
        grade = "⭐ ОТЛИЧНО - очень значительное ускорение"
    elif speedup >= 3.0:
        score = 8
        grade = "🌟 ОЧЕНЬ ХОРОШО - существенное улучшение"
    elif speedup >= 2.0:
        score = 7
        grade = "👍 ХОРОШО - заметное ускорение"
    elif speedup >= 1.5:
        score = 6
        grade = "✓ УДОВЛЕТВОРИТЕЛЬНО - видимое улучшение"
    elif speedup >= 1.2:
        score = 5
        grade = "~ ПОСРЕДСТВЕННО - небольшое улучшение"
    elif speedup >= 1.05:
        score = 4
        grade = "⚠️ МИНИМАЛЬНО - почти нет разницы"
    elif speedup >= 0.95:
        score = 3
        grade = "➖ НЕЙТРАЛЬНО - в пределах погрешности"
    elif speedup >= 0.8:
        score = 2
        grade = "⚠️ УХУДШЕНИЕ - стало медленнее"
    else:
        score = 1
        grade = "❌ ДЕГРАДАЦИЯ - значительно медленнее"
    
    print(f"\n🎯 Оценка: {score}/10")
    print(f"📋 Вердикт: {grade}")
    
    return score


def main():
    """Главная функция бенчмарка"""
    print(f"\n{'='*80}")
    print(f"🚀 STRIKE GENERATION OPTIMIZATION BENCHMARK")
    print(f"{'='*80}")
    print(f"Параметры теста: 90-дневный контракт, Spot=$100,000, IV=65%")
    
    price_history, iv_history = generate_test_data(birth_dte=90)
    print(f"\n⏳ Готово: {len(price_history)} дней истории цен")
    
    # Benchmark all versions
    results_v1 = benchmark_version(v1, "V1 - BASELINE", price_history, iv_history, 90)
    results_v2 = benchmark_version(v2, "V2 - LRU Cache + Numpy", price_history, iv_history, 90)
    results_v3 = benchmark_version(v3, "V3 - Vectorization", price_history, iv_history, 90)
    results_v4 = benchmark_version(v4, "V4 - Incremental O(N)", price_history, iv_history, 90)
    
    # Verify all match v1
    all_match = True
    for ver_name, results in [("V2", results_v2), ("V3", results_v3), ("V4", results_v4)]:
        print(f"\n{'='*80}")
        print(f"✅ ПРОВЕРКА {ver_name} vs V1")
        print(f"{'='*80}")
        match = verify_results_match(results_v1, results)
        all_match = all_match and match
    
    if not all_match:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: Результаты не совпадают!")
        sys.exit(1)
    
    # Compare performance
    speedups = {}
    scores = {}
    
    for ver_name, results in [("V2", results_v2), ("V3", results_v3), ("V4", results_v4)]:
        print(f"\n{'='*80}")
        print(f"⚡ {ver_name} vs V1")
        speedups[ver_name] = compare_performance(results_v1, results)
        scores[ver_name] = evaluate_optimization(speedups[ver_name])
    
    # Final comparison
    print(f"\n{'='*80}")
    print(f"🏆 ИТОГОВОЕ СРАВНЕНИЕ")
    print(f"{'='*80}")
    
    versions = [
        ("V1 - Baseline", results_v1['time'], 1.0, "базовая O(N²)"),
        ("V2 - LRU Cache", results_v2['time'], speedups["V2"], f"оценка {scores['V2']}/10"),
        ("V3 - Vectorization", results_v3['time'], speedups["V3"], f"оценка {scores['V3']}/10"),
        ("V4 - Incremental", results_v4['time'], speedups["V4"], f"оценка {scores['V4']}/10 🔥"),
    ]
    
    versions_sorted = sorted(versions, key=lambda x: x[1])
    
    print(f"\n📊 Рейтинг по скорости:")
    for i, (name, time, speedup, note) in enumerate(versions_sorted, 1):
        emoji = "🏆" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f" {emoji} {i}. {name}: {time:.4f} сек ({speedup:.2f}x, {note})")
    
    best = versions_sorted[0]
    print(f"\n🏆 ПОБЕДИТЕЛЬ: {best[0]}")
    print(f"   Время: {best[1]:.4f} сек")
    print(f"   Ускорение: {best[2]:.2f}x относительно baseline")
    
    if best[2] >= 10.0:
        print(f"\n✅ РЕКОМЕНДАЦИЯ: {best[0]} - революционная оптимизация! 🚀")
    elif best[2] >= 7.0:
        print(f"\n✅ РЕКОМЕНДАЦИЯ: {best[0]} обязательна к использованию (отличная оптимизация)")
    elif best[2] >= 3.0:
        print(f"\n✅ РЕКОМЕНДАЦИЯ: Использовать {best[0]} в production (хорошая оптимизация)")
    elif best[2] >= 1.5:
        print(f"\n⚠️  РЕКОМЕНДАЦИЯ: Можно использовать {best[0]}, но выигрыш скромный")
    else:
        print(f"\n❌ РЕКОМЕНДАЦИЯ: Оставить V1, оптимизации не дают большого эффекта")
    
    print(f"\n{'='*80}\n")
    
    return {
        'v2': {'speedup': speedups["V2"], 'score': scores["V2"]},
        'v3': {'speedup': speedups["V3"], 'score': scores["V3"]},
        'v4': {'speedup': speedups["V4"], 'score': scores["V4"]},
        'best': best[0]
    }


if __name__ == "__main__":
    main()
