# ibkrBroker.py
from ib_insync import IB, Future
import pandas as pd
from datetime import datetime
import asyncio

class IBKRBroker:
    def __init__(self, symbol="ES"):
        self.ib = IB()
        self.symbol = symbol
        self.contract = None
        self.recent_bars = pd.DataFrame()
        self.connected = False

    async def connect_async(self, host='127.0.0.1', port=7497):
        try:
            self.connected = await self.ib.connectAsync(host, port, clientId=1)
            print("✓ Connected to IBKR")
            return self.connected
        except Exception as e:
            print(f"API connection failed: {e}")
            return False

    async def disconnect_async(self):
        self.ib.disconnect()
        print("✓ Disconnected from IBKR")

    async def get_front_month_contract_async(self):
        contract = Future(symbol=self.symbol, exchange="CME")
        details = await self.ib.reqContractDetailsAsync(contract)
        if not details:
            print("⚠ No front-month contract found")
            return False

        sorted_details = sorted(details, key=lambda x: x.contract.lastTradeDateOrContractMonth)
        self.contract = sorted_details[0].contract
        print(f"✓ Front-month contract: {self.contract.localSymbol} ({self.contract.lastTradeDateOrContractMonth})")
        return True

    async def stream_live_bars(self, bar_size="1 min", what_to_show="TRADES"):
        """
        Stream live bars indefinitely.
        """
        if not self.contract:
            raise ValueError("Contract not loaded")

        # Subscribe to IBKR bars
        bars = self.ib.reqRealTimeBars(self.contract, barSize=bar_size, whatToShow=what_to_show, useRTH=True)
        self.recent_bars = pd.DataFrame()

        while True:
            await asyncio.sleep(1)
            df = pd.DataFrame([{
                'timestamp': bar.time,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            } for bar in bars])

            if not df.empty:
                df.sort_values('timestamp', inplace=True)
                df.reset_index(drop=True, inplace=True)
                self.recent_bars = df
                yield df.iloc[-1]  # yield last bar only
