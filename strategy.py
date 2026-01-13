import pandas as pd

class MovingAverageCrossoverStrategy:
    def __init__(self, fast_period=10, slow_period=30):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.position = 0
        self.name = "Moving Average Crossover"

    def calculate_signal(self, data: pd.DataFrame):
        """Return 1 for long, -1 for short, 0 for hold"""
        if len(data) < self.fast_period:
            return 0
        fast_ma = data['close'].rolling(self.fast_period).mean().iloc[-1]
        slow_ma = data['close'].rolling(self.slow_period).mean().iloc[-1]
        if fast_ma > slow_ma:
            return 1
        elif fast_ma < slow_ma:
            return -1
        return 0
