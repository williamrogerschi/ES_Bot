# broker.py
from ib_insync import IB, Future, util
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import deque

CENTRAL = ZoneInfo("America/Chicago")
UTC = ZoneInfo("UTC")

class IBKRBroker:
    def __init__(self, symbol="ES"):
        util.startLoop()  # only needed if running in Jupyter/script without event loop
        self.ib = IB()
        self.symbol = symbol
        self.contract = None
        
        # For 1-min aggregation
        self._current_1min = None
        self._last_start = None
        self._bar_queue = asyncio.Queue()           # completed 1-min bars go here
        self._rt_bars = None

    async def connect_async(self, host="127.0.0.1", port=7497, client_id=10):
        await self.ib.connectAsync(host, port, clientId=client_id)
        print(f"✓ Connected to IBKR (paper) - clientId={client_id}")

    async def disconnect_async(self):
        if self.ib.isConnected():
            self.ib.disconnect()
            print("✓ Disconnected from IBKR")

    async def get_front_month_contract_async(self):
        template = Future(symbol=self.symbol, exchange="CME", currency="USD")
        details = await self.ib.reqContractDetailsAsync(template)
        if not details:
            raise ValueError(f"No contract found for {self.symbol}")
        
        details.sort(key=lambda d: d.contract.lastTradeDateOrContractMonth)
        self.contract = details[0].contract
        
        # Important: qualify so we have full contract info
        await self.ib.qualifyContractsAsync(self.contract)
        print(f"✓ Front-month contract: {self.contract.localSymbol}  expiry={self.contract.lastTradeDateOrContractMonth}")

    def _on_rt_bar(self, bars, has_new_bar: bool):
        """RealTimeBarList updateEvent callback"""
        if not bars:
            return
        
        bar = bars[-1]                  # latest 5-second bar
        dt = bar.time                   # already datetime.datetime (UTC, naive)
        
        # Make it timezone-aware (UTC)
        dt_utc = dt.replace(tzinfo=UTC)
        
        # Round down to start of the minute
        minute_start = dt_utc.replace(second=0, microsecond=0)

        if self._last_start != minute_start:
            # New minute → push completed previous bar if any
            if self._current_1min is not None:
                asyncio.create_task(self._bar_queue.put(dict(self._current_1min)))
            
            # Begin new 1-min aggregation
            self._current_1min = {
                "time": minute_start,       # now timezone-aware UTC
                "open": bar.open_,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume
            }
            self._last_start = minute_start
        else:
            # Update current minute bar
            self._current_1min["high"]  = max(self._current_1min["high"],  bar.high)
            self._current_1min["low"]   = min(self._current_1min["low"],   bar.low)
            self._current_1min["close"] = bar.close
            self._current_1min["volume"] += bar.volume

    async def stream_1m_bars(self):
        if not self.contract:
            raise RuntimeError("Contract not set. Run get_front_month_contract_async() first.")

        self._rt_bars = self.ib.reqRealTimeBars(
            contract=self.contract,
            barSize=5,                  # ONLY 5 is supported
            whatToShow="TRADES",
            useRTH=False
        )

        self._rt_bars.updateEvent += self._on_rt_bar
        print("→ Subscribed to 5-second real-time bars (aggregating to 1 min)")

        try:
            while True:
                bar = await self._bar_queue.get()
                yield bar
        finally:
            if self._rt_bars:
                # Fixed: cancel using the RealTimeBarList object, not the contract
                self.ib.cancelRealTimeBars(self._rt_bars)
                self._rt_bars.updateEvent -= self._on_rt_bar
            print("→ Real-time bars cancelled")