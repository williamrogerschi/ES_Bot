import pandas as pd

class DataHandler:
    def __init__(self, symbol="ES"):
        self.symbol = symbol
        self.data = pd.DataFrame()
        self.index = 0  # tracks the current “live” bar

    def load_from_ibkr(self, bars):
        if bars is None or len(bars) == 0:
            print("⚠ No bars received")
            self.data = pd.DataFrame(columns=['timestamp','open','high','low','close','volume'])
            return
        self.data = bars.copy()
        self.index = 0
        print(f"✓ Loaded {len(self.data)} bars for simulation")

    def get_next_bar(self):
        """Return the next bar as if it just happened"""
        if self.index >= len(self.data):
            return None
        bar = self.data.iloc[self.index]
        self.index += 1
        return bar

    def get_latest_price(self):
        if self.index == 0:
            return None
        return self.data['close'].iloc[self.index - 1]
