# ibkrBroker.py
from ib_insync import IB, Future, MarketOrder, LimitOrder, Trade
import pandas as pd

class IBKRBroker:
    def __init__(self, symbol="ES"):
        self.ib = IB()
        self.symbol = symbol
        self.contract = None
        self.recent_bars = pd.DataFrame(columns=["time", "open", "high", "low", "close"])
        self.partial_bar = None  # latest real-time price
        self.active_orders = {}  # orderId -> Trade

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
        print(f"✓ Front-month contract: {self.contract.localSymbol} ({self.contract.lastTradeDateOrContractMonth})")
        return True

    async def place_limit_order(self, action, quantity, price):
        order = LimitOrder(action, quantity, price)
        order.tif = "GTC"
        order.outsideRth = True
        trade = self.ib.placeOrder(self.contract, order)
        self.active_orders[trade.order.orderId] = trade
        trade.filledEvent += lambda t: print(f"Order filled: {t.order.action} {t.order.totalQuantity} @ {t.order.lmtPrice}")
        trade.cancelledEvent += lambda t: print(f"Order cancelled: {t}")
        return trade

    async def cancel_order(self, trade: Trade):
        if trade and trade.isActive():
            self.ib.cancelOrder(trade.order)
            if trade.order.orderId in self.active_orders:
                del self.active_orders[trade.order.orderId]

    async def stream_live_bars(self, bar_size=1):
        bars = self.ib.reqRealTimeBars(self.contract, bar_size, "TRADES", False)
        try:
            while True:
                await bars.updateEvent
                bar = bars[-1]
                self.partial_bar = {
                    "time": bar.time,
                    "open": bar.open_,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close
                }

                if len(self.recent_bars) == 0 or bar.time != self.recent_bars['time'].iloc[-1]:
                    self.recent_bars = pd.concat(
                        [self.recent_bars, pd.DataFrame([{
                            "time": bar.time,
                            "open": bar.open_,
                            "high": bar.high,
                            "low": bar.low,
                            "close": bar.close
                        }])],
                        ignore_index=True
                    )

                yield self.recent_bars, self.partial_bar
        finally:
            self.ib.cancelRealTimeBars(bars)
