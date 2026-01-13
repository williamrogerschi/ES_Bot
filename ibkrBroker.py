from ib_insync import IB, Future
import pandas as pd
from datetime import datetime

class IBKRBroker:
    def __init__(self, symbol="ES", paper=True):
        self.ib = IB()
        self.symbol = symbol
        self.paper = paper
        self.contract = None
        self.historical_data = pd.DataFrame()
        self.connected = False

    def connect(self, host='127.0.0.1', port=7497):
        self.connected = self.ib.connect(host, port, clientId=1)
        if self.connected:
            print(f"✓ Connected to IBKR on port {port} (Paper={self.paper})")
        else:
            print(f"❌ Failed to connect to IBKR")
        return self.connected

    def get_front_month_contract(self):
        contract = Future(symbol=self.symbol, exchange="CME")
        details = self.ib.reqContractDetails(contract)
        if not details:
            print("⚠ No front-month contract found")
            return None
        # Sort by lastTradeDateOrContractMonth
        sorted_details = sorted(details, key=lambda x: x.contract.lastTradeDateOrContractMonth)
        self.contract = sorted_details[0].contract
        print(f"✓ Front-month contract: {self.contract.localSymbol} ({self.contract.lastTradeDateOrContractMonth})")
        return self.contract

    def get_historical_bars(self, duration="2 D", bar_size="5 mins", what_to_show="TRADES"):
        if not self.contract:
            self.get_front_month_contract()
        if not self.contract:
            return pd.DataFrame()

        # Corrected duration string format
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

    def get_latest_price(self):
        if not self.historical_data.empty:
            return self.historical_data['close'].iloc[-1]
        return None

    def disconnect(self):
        self.ib.disconnect()
        print("✓ Disconnected from IBKR")
