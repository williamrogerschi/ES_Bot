# ibkrBroker.py
from ib_insync import IB, Future
import pandas as pd
from datetime import datetime

class IBKRBroker:
    def __init__(self, symbol="ES"):
        self.ib = IB()
        self.symbol = symbol
        self.contract = None
        self.historical_data = pd.DataFrame()
        self.connected = False

    def connect(self, host='127.0.0.1', port=7497):
        self.connected = self.ib.connect(host, port, clientId=1)
        if self.connected:
            print(f"✓ Connected to IBKR")
        else:
            print(f"❌ Failed to connect")
        return self.connected

    def get_front_month_contract(self):
        contract = Future(symbol=self.symbol, exchange="CME")
        details = self.ib.reqContractDetails(contract)
        if not details:
            print("⚠ No front-month contract found")
            return None

        # Pick the earliest lastTradeDateOrContractMonth
        sorted_details = sorted(details, key=lambda x: x.contract.lastTradeDateOrContractMonth)
        self.contract = sorted_details[0].contract
        print(f"✓ Front-month contract: {self.contract.localSymbol} ({self.contract.lastTradeDateOrContractMonth})")
        return self.contract

    def get_historical_bars(self, duration="2 D", bar_size="1 min", what_to_show="TRADES"):
        if not self.contract:
            if not self.get_front_month_contract():
                return pd.DataFrame()

        try:
            bars = self.ib.reqHistoricalData(
                self.contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=False,
                formatDate=1
            )
        except Exception as e:
            print(f"⚠ Failed to fetch historical bars: {e}")
            return pd.DataFrame()

        if not bars:
            print("⚠ No bars returned from IBKR")
            return pd.DataFrame()

        df = pd.DataFrame([{
            'timestamp': bar.date if isinstance(bar.date, datetime) else datetime.strptime(bar.date, "%Y%m%d %H:%M:%S"),
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume
        } for bar in bars])

        df.sort_values('timestamp', inplace=True)
        df.reset_index(drop=True, inplace=True)
        self.historical_data = df
        print(f"✓ Loaded {len(df)} historical bars from IBKR")
        return df

    def disconnect(self):
        self.ib.disconnect()
        print("✓ Disconnected from IBKR")
