# trades.py
from ib_insync import MarketOrder, LimitOrder

class Trader:
    def __init__(self, broker):
        self.broker = broker

    async def place_market_order(self, action, quantity):
        order = MarketOrder(action, quantity)
        trade = self.broker.ib.placeOrder(self.broker.contract, order)
        print(f"Submitted {action} MARKET {quantity}")
        return trade

    def place_limit_order_no_wait(self, action, quantity, price):
        order = LimitOrder(action, quantity, price)
        trade = self.broker.ib.placeOrder(self.broker.contract, order)
        print(f"Submitted {action} LIMIT {quantity} @ {price}")
        return trade

    async def place_take_profit(self, action, entry_price, scalp_points=1.0):
        if action == "BUY":
            tp_price = entry_price + scalp_points
            print(f"Placing TAKE-PROFIT SELL @ {tp_price}")
            await self.place_limit_order_no_wait("SELL", 1, tp_price)
        else:
            tp_price = entry_price - scalp_points
            print(f"Placing TAKE-PROFIT BUY @ {tp_price}")
            await self.place_limit_order_no_wait("BUY", 1, tp_price)
