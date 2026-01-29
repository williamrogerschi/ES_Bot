# ibkrBroker.py
from ib_insync import IB, Future, LimitOrder
import asyncio
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")

class IBKRBroker:
    def __init__(self, symbol="ES"):
        self.ib = IB()
        self.symbol = symbol
        self.contract = None

        # 1-min bar builder
        self.current_bar = None
        self.current_minute = None

    # -------------------- Connection --------------------
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
        details.sort(key=lambda d: d.contract.lastTradeDateOrContractMonth)
        self.contract = details[0].contract
        print(f"✓ Front-month contract: {self.contract.localSymbol}")

    # -------------------- Limit orders --------------------
    def place_limit_order_no_wait(self, action, quantity, price):
        """Submit a simple limit order immediately."""
        order = LimitOrder(action, quantity, price)
        order.tif = "GTC"
        order.outsideRth = True
        trade = self.ib.placeOrder(self.contract, order)
        print(f"[ORDER] Submitted {action} LIMIT @ {price}")
        return trade

    # -------------------- Build 1-min bars from market data --------------------
    async def stream_1m_bars_from_mktdata(self):
        ticker = self.ib.reqMktData(self.contract, "", False, False)

        try:
            while True:
                await ticker.updateEvent

                if ticker.last is None:
                    continue

                # Convert UTC tick to Central
                tick_time = ticker.time.astimezone(CENTRAL)
                minute = tick_time.replace(second=0, microsecond=0)
                price = ticker.last

                # First tick ever
                if self.current_bar is None:
                    self.current_minute = minute
                    self.current_bar = {
                        "time": minute,
                        "open": price,
                        "high": price,
                        "low": price,
                        "close": price,
                    }
                    continue

                # New minute → yield previous bar
                if minute > self.current_minute:
                    yield self.current_bar  # yield closed bar
                    self.current_minute = minute
                    self.current_bar = {
                        "time": minute,
                        "open": price,
                        "high": price,
                        "low": price,
                        "close": price,
                    }
                    continue

                # Update current bar
                self.current_bar["high"] = max(self.current_bar["high"], price)
                self.current_bar["low"] = min(self.current_bar["low"], price)
                self.current_bar["close"] = price

        finally:
            self.ib.cancelMktData(self.contract)

    # -------------------- Strategy-facing API --------------------
    async def stream_closed_bars(self):
        """Yields every closed bar (1-min) as a dict."""
        async for bar in self.stream_1m_bars_from_mktdata():
            yield bar
