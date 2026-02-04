import os
import sys

# Добавляем текущую директорию в путь, чтобы импорты работали
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_data import generate_strike_data, generate_smile_data, generate_surface_data
from strike_chart import StrikeChart
from smile_chart import SmileChart
from surface_chart import SurfaceChart

def generate():
    # 1. Strike Chart
    df_ohlc, df_spot, df_greeks = generate_strike_data()
    strike = StrikeChart(df_ohlc, df_spot, df_greeks, title="BTC-55000-CALL Precision V11")
    strike_path = os.path.abspath("strike_test.html")
    strike.save(strike_path)
    print(f"Strike Chart generated: {strike_path}")

    # 2. Smile Chart
    smile_data = generate_smile_data()
    smile = SmileChart(smile_data, title="BTC Volatility Smile Precision V11")
    smile_path = os.path.abspath("smile_test.html")
    with open(smile_path, 'w', encoding='utf-8') as f:
        f.write(smile.to_html())
    print(f"Smile Chart generated: {smile_path}")

    # 3. Surface Chart
    surface_data = generate_surface_data()
    surface = SurfaceChart(surface_data, title="BTC 3D Surface Precision V11")
    surface_path = os.path.abspath("surface_test.html")
    with open(surface_path, 'w', encoding='utf-8') as f:
        f.write(surface.to_html())
    print(f"Surface Chart generated: {surface_path}")

if __name__ == "__main__":
    generate()
