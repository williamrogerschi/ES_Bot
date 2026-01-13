import pandas as pd
from datetime import datetime

class DataHandler:
    def __init__(self, symbol="ES"):
        self.symbol = symbol
        self.data = pd.DataFrame()

    def load_from_ibkr(self, bars):
        if bars is None or len(bars) == 0:
            self.data = pd.DataFrame(columns=['timestamp','open','high','low','close','volume'])
            print("⚠ No bars received from IBKR")
            return self.data

        df = pd.DataFrame([{
            'timestamp': bar['timestamp'] if isinstance(bar['timestamp'], datetime) else datetime.strptime(bar['timestamp'], "%Y%m%d %H:%M:%S"),
            'open': bar['open'],
            'high': bar['high'],
            'low': bar['low'],
            'close': bar['close'],
            'volume': bar['volume']
        } for bar in bars.to_dict('records')])

        df.sort_values('timestamp', inplace=True)
        df.reset_index(drop=True, inplace=True)
        self.data = df
        print(f"✓ Loaded {len(self.data)} bars from IBKR")
        return df

    def get_latest_price(self):
        if len(self.data) > 0:
            return self.data['close'].iloc[-1]
        return None
