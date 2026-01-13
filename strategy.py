import pandas as pd

class MovingAverageCrossoverStrategy:
    def __init__(self, fast_period=10, slow_period=30):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.position = 0
        self.name = "Moving Average Crossover"

    def calculate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        if data.empty or 'close' not in data.columns:
            return data

        data['MA_fast'] = data['close'].rolling(window=self.fast_period, min_periods=1).mean()
        data['MA_slow'] = data['close'].rolling(window=self.slow_period, min_periods=1).mean()

        data['signal'] = 0
        data.loc[data['MA_fast'] > data['MA_slow'], 'signal'] = 1
        data.loc[data['MA_fast'] < data['MA_slow'], 'signal'] = -1

        self.position = data['signal'].iloc[-1]
        return data
