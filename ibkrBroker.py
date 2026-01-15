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

    async def stream_live_bars(self):
        """
        Streams 5-second real-time bars using ib-insync.
        """

        BAR_SECONDS = 5  # IBKR hard limit

        # Request real-time bars (ib-insync style)
        bars = self.ib.reqRealTimeBars(
            self.contract,
            BAR_SECONDS,
            'TRADES',
            False
        )

        try:
            while True:
                # Wait for the next bar update
                await bars.updateEvent

                bar = bars[-1]
                yield {
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'time': bar.time
                }

        finally:
            self.ib.cancelRealTimeBars(bars)
