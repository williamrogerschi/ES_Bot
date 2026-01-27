# ibkrBroker.py
from ib_insync import IB, Future, MarketOrder, LimitOrder, Trade
import pandas as pd
import asyncio

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
        return True

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
        future = asyncio.get_event_loop().create_future()

        def on_filled(t):
            if not future.done():
                future.set_result(True)
                print(f"Market order filled: {t.order.action} {t.order.totalQuantity} @ market")

        trade.filledEvent += on_filled
        try:
            await future
        except asyncio.CancelledError:
            print("Market order waiting cancelled")
        finally:
            trade.filledEvent -= on_filled
        return trade

    async def place_limit_order(self, action, quantity, price):
        """
        Places a limit order safely and waits asynchronously until filled.
        """
        order = LimitOrder(action, quantity, price)
        order.tif = "GTC"
        order.outsideRth = True
        trade = self.ib.placeOrder(self.contract, order)
        self.active_orders[trade.order.orderId] = trade

        future = asyncio.get_event_loop().create_future()

        def on_filled(t):
            if not future.done():
                future.set_result(True)
                print(f"Order filled: {t.order.action} {t.order.totalQuantity} @ {t.order.lmtPrice}")

        trade.filledEvent += on_filled
        trade.cancelledEvent += lambda t: print(f"Order cancelled: {t}")

        try:
            await future  # wait asynchronously until filled
        except asyncio.CancelledError:
            print("Order waiting cancelled")
        finally:
            trade.filledEvent -= on_filled
            if trade.order.orderId in self.active_orders:
                del self.active_orders[trade.order.orderId]

        return trade

    async def cancel_order(self, trade: Trade):
        if trade and trade.isActive():
            self.ib.cancelOrder(trade.order)
            if trade.order.orderId in self.active_orders:
                del self.active_orders[trade.order.orderId]

    async def stream_live_bars(self, bar_size=1):
        """
        Async generator yielding only fully closed bars.
        """
        bars = self.ib.reqRealTimeBars(self.contract, bar_size, "TRADES", False)
        last_time = None  # track last printed bar

        try:
            while True:
                await bars.updateEvent
                bar = bars[-1]

                # Update partial bar
                self.partial_bar = {
                    "time": bar.time,
                    "open": bar.open_,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close
                }

                # Only consider the bar closed if its timestamp is new
                if bar.time != last_time:
                    last_time = bar.time
                    # Append closed bar to recent_bars
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

                    # Print closed bar
                    bar_range = bar.high - bar.low
                    close_percent = (bar.close - bar.low) / bar_range if bar_range != 0 else 0
                    print(f"[BAR] O:{bar.open_} H:{bar.high} L:{bar.low} C:{bar.close} "
                        f"Range:{bar_range:.2f} Close%:{close_percent:.2f}")

                    yield self.recent_bars, self.partial_bar

        finally:
            # Cleanup
            if self.ib.isConnected():
                self.ib.cancelRealTimeBars(bars)

