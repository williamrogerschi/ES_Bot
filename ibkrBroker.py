from ib_insync import IB, Future, MarketOrder
import pandas as pd

class IBKRBroker:
    def __init__(self, symbol="ES"):
        self.ib = IB()
        self.symbol = symbol
        self.contract = None
        self.recent_bars = pd.DataFrame(columns=["time", "open", "high", "low", "close"])
        self.partial_bar = None  # store real-time price info for immediate execution

    async def connect_async(self, host="127.0.0.1", port=7497):
        await self.ib.connectAsync(host, port, clientId=1)
        print("✓ Connected to IBKR")
        return True

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
        print(f"✓ Front-month contract: {self.contract.localSymbol} ({self.contract.lastTradeDateOrContractMonth})")
        return True

    async def place_market_order(self, action, quantity):
        order = MarketOrder(action, quantity)
        order.tif = "GTC"
        order.outsideRth = True
        trade = self.ib.placeOrder(self.contract, order)
        await trade.filledEvent
        return trade

    async def stream_live_bars(self):
        """Streams live 5-second bars but updates partial price for real-time execution."""
        bars = self.ib.reqRealTimeBars(self.contract, 5, "TRADES", False)
        try:
            while True:
                await bars.updateEvent
                bar = bars[-1]

                # Update partial bar (latest real-time price)
                self.partial_bar = {
                    "time": bar.time,
                    "open": bar.open_,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close
                }

                # Only add fully closed 1-minute bars to recent_bars
                # Here we assume each bar is 1 minute; adjust if using 5-second bar aggregation
                # Use bar.time as indicator of completion
                if len(self.recent_bars) == 0 or bar.time != self.recent_bars['time'].iloc[-1]:
                    self.recent_bars = pd.concat([self.recent_bars, pd.DataFrame([{
                        "time": bar.time,
                        "open": bar.open_,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close
                    }])], ignore_index=True)

                yield self.partial_bar  # real-time price for immediate execution
        finally:
            self.ib.cancelRealTimeBars(bars)
