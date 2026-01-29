# ibkrBroker.py
from ib_insync import IB, Future, LimitOrder
import pandas as pd
from datetime import timezone
from zoneinfo import ZoneInfo
import asyncio

CENTRAL = ZoneInfo("America/Chicago")

class IBKRBroker:
    def __init__(self, symbol="ES"):
        self.ib = IB()
        self.symbol = symbol
        self.contract = None
        self.recent_bars = pd.DataFrame(columns=["time", "open", "high", "low", "close"])
        self.last_time = None  # last bar time for stream_closed_bars

    async def connect_async(self, host="127.0.0.1", port=7497):
        await self.ib.connectAsync(host, port, clientId=1)
        print("✓ Connected to IBKR")

    async def disconnect_async(self):
        if self.ib.isConnected():
            self.ib.disconnect()
            print("✓ Disconnected from IBKR")

    async def get_front_month_contract_async(self):
        """
        Dynamically fetch the front-month ES contract.
        """
        contract = Future(symbol=self.symbol, exchange="CME")
        details = await self.ib.reqContractDetailsAsync(contract)
        if not details:
            raise RuntimeError("No contract found")
        # Sort by nearest expiry
        details.sort(key=lambda d: d.contract.lastTradeDateOrContractMonth)
        self.contract = details[0].contract
        print(f"✓ Front-month contract: {self.contract.localSymbol}")

    # ------------------------------------------------------------------
    # Stream 1-minute bars from TWS
    # ------------------------------------------------------------------
    async def stream_closed_bars(self):
        """
        Async generator yielding each fully closed 1-minute bar.
        Bars come from historical data with keepUpToDate=True, so they match TWS charts.
        """
        bars = await self.ib.reqHistoricalDataAsync(
            self.contract,
            endDateTime="",
            durationStr="2 D",
            barSizeSetting="1 min",
            whatToShow="TRADES",
            useRTH=False,
            keepUpToDate=True
        )

        while True:
            await bars.updateEvent  # wait for new data
            if not bars:
                continue

            bar = bars[-1]

            # Convert IBKR UTC datetime to Central
            bar_time = bar.date.replace(tzinfo=timezone.utc).astimezone(CENTRAL)

            # Skip if bar hasn’t changed
            if self.last_time == bar_time:
                continue

            self.last_time = bar_time

            bar_dict = {
                "time": bar_time,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
            }

            # Optionally append to recent_bars
            self.recent_bars = pd.concat([self.recent_bars, pd.DataFrame([bar_dict])], ignore_index=True)

            yield bar_dict

    # ------------------------------------------------------------------
    # Trade API
    # ------------------------------------------------------------------
    def place_limit_order_no_wait(self, action, quantity, price):
        """
        Immediately submit a limit order without awaiting fills.
        """
        if self.contract is None:
            raise ValueError("Contract not set")
        order = LimitOrder(action, quantity, price)
        order.tif = "GTC"
        order.outsideRth = True
        trade = self.ib.placeOrder(self.contract, order)
        print(f"[ORDER] Submitted {action} LIMIT @ {price}")
        return trade
