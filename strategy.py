# strategy.py
import pandas as pd

class MovingAverageCrossoverStrategy:
    def __init__(self, short_window=2, long_window=5):
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(self, bars: pd.DataFrame):
        if len(bars) < self.long_window:
            return "HOLD"

        bars = bars.copy()
        bars["short_ma"] = bars["close"].rolling(self.short_window).mean()
        bars["long_ma"] = bars["close"].rolling(self.long_window).mean()

        # Check crossover in the last row
        if bars["short_ma"].iloc[-2] <= bars["long_ma"].iloc[-2] and bars["short_ma"].iloc[-1] > bars["long_ma"].iloc[-1]:
            return "BUY"
        elif bars["short_ma"].iloc[-2] >= bars["long_ma"].iloc[-2] and bars["short_ma"].iloc[-1] < bars["long_ma"].iloc[-1]:
            return "SELL"
        else:
            return "HOLD"
