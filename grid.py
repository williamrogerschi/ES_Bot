# grid.py
import asyncio
from ib_insync import LimitOrder

class GridStrategy:
    def __init__(self, broker, grid_spacing=1, quantity=1):
        self.broker = broker
        self.grid_spacing = grid_spacing
        self.quantity = quantity
        self.active_buy = None
        self.active_sell = None

    async def start(self):
        """
        Start the oscillating grid.
        """
        price = self.broker.partial_bar['close'] if self.broker.partial_bar else 0
        if not price:
            print("⚠ Waiting for initial price...")
            while not self.broker.partial_bar:
                await asyncio.sleep(0.1)
            price = self.broker.partial_bar['close']

        await self._place_initial_orders(price)

        # Main loop
        while True:
            await asyncio.sleep(0.1)
            await self._check_fills()

    async def _place_initial_orders(self, price):
        """
        Place one buy below and one sell above the current price.
        """
        buy_price = price - self.grid_spacing
        sell_price = price + self.grid_spacing

        self.active_buy = await self.broker.place_limit_order("BUY", self.quantity, buy_price)
        self.active_sell = await self.broker.place_limit_order("SELL", self.quantity, sell_price)

        print(f"✓ Placed initial buy at {buy_price}, sell at {sell_price}")

    async def _check_fills(self):
        """
        Check if either order filled and update the counter order.
        """
        # Buy filled
        if self.active_buy and self.active_buy.isDone() and self.active_buy.orderStatus.status == "Filled":
            filled_price = self.active_buy.order.lmtPrice
            print(f"Order filled: BUY {self.quantity} @ {filled_price}")

            # Cancel existing sell
            if self.active_sell:
                await self.broker.cancel_order(self.active_sell)
                self.active_sell = None

            # Place new sell for profit-taking
            new_sell_price = filled_price + self.grid_spacing
            self.active_sell = await self.broker.place_limit_order("SELL", self.quantity, new_sell_price)
            self.active_buy = None

        # Sell filled
        if self.active_sell and self.active_sell.isDone() and self.active_sell.orderStatus.status == "Filled":
            filled_price = self.active_sell.order.lmtPrice
            print(f"Order filled: SELL {self.quantity} @ {filled_price}")

            # Cancel existing buy
            if self.active_buy:
                await self.broker.cancel_order(self.active_buy)
                self.active_buy = None

            # Place new buy for profit-taking
            new_buy_price = filled_price - self.grid_spacing
            self.active_buy = await self.broker.place_limit_order("BUY", self.quantity, new_buy_price)
            self.active_sell = None
