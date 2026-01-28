# ibkrBroker.py
from ib_insync import IB, Future
import pandas as pd
from datetime import datetime, timedelta
import asyncio

class IBKRBroker:
    def __init__(self, symbol="ES"):
        self.ib = IB()
        self.symbol = symbol
        self.contract = None
        self.bars = pd.DataFrame(columns=["time", "open", "high", "low", "close"])
        self.tick_buffer = []
        self.current_bar_start = None
        self.bar_interval = timedelta(minutes=1)
        self.tick_sub = None

    async def connect_async(self, host="127.0.0.1", port=7497):
        await self.ib.connectAsync(host, port, clientId=1)
        print("✓ Connected to IBKR")

    async def disconnect_async(self):
        if self.ib.isConnected():
            self.ib.disconnect()
            print("✓ Disconnected from IBKR")

    async def get_front_month_contract_async(self):
        contract = Future(symbol=self.symbol, exchange="CME")
        details = await self.ib.reqContractDetailsAsync(contract)
        if not details:
            print("⚠ No contract found")
            return False

        details.sort(key=lambda x: x.contract.lastTradeDateOrContractMonth)
        self.contract = details[0].contract
        print(f"✓ Front-month contract: {self.contract.localSymbol}")
        return True

    async def stream_tick_bars(self):
        """
        Streams tick data and builds 1-minute bars.
        """
        self.tick_sub = self.ib.reqMktData(self.contract, "", False, False)

        def process_tick(tick):
            last_price = getattr(tick, "last", None)
            if last_price is None:
                return

            now = datetime.now()

            # Start new bar if needed
            if self.current_bar_start is None:
                self.current_bar_start = now.replace(second=0, microsecond=0)

            if now >= self.current_bar_start + self.bar_interval:
                # Close current bar
                if self.tick_buffer:
                    high = max(self.tick_buffer)
                    low = min(self.tick_buffer)
                    close = self.tick_buffer[-1]

                    bar_data = {
                        "time": self.current_bar_start,
                        "high": high,
                        "low": low,
                        "close": close
                    }

                    self.bars = pd.concat(
                        [self.bars, pd.DataFrame([bar_data])],
                        ignore_index=True
                    )
                    print(f"[BAR] {self.current_bar_start} H:{high} L:{low} C:{close}")

                # Reset for next bar
                self.current_bar_start = now.replace(second=0, microsecond=0)
                self.tick_buffer = [last_price]
            else:
                self.tick_buffer.append(last_price)

        self.tick_sub.updateEvent += process_tick

        try:
            while True:
                await asyncio.sleep(0.1)
                yield self.bars
        finally:
            if self.tick_sub:
                self.ib.cancelMktData(self.tick_sub)
