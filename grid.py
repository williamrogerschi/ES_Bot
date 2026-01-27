# grid.py (dynamic first order only)
import asyncio

class GridStrategy:
    def __init__(self, broker, grid_spacing=1, quantity=1, ma_period=3):
        self.broker = broker
        self.grid_spacing = grid_spacing
        self.quantity = quantity
        self.ma_period = ma_period
        self.active_order = None

    async def start(self):
        """
        Start the dynamic grid: place only one first order based on bias.
        """
        # Wait for initial price
        while not self.broker.partial_bar:
            await asyncio.sleep(0.1)
        price = self.broker.partial_bar['close']

        # Determine first order dynamically
        first_order = self._determine_first_order()
        await self._place_first_order(price, first_order)

        # Main loop
        while True:
            await asyncio.sleep(0.1)
            await self._check_fill()

    def _determine_first_order(self):
        """
        Look at recent bars and moving average to decide BUY or SELL.
        """
        if len(self.broker.recent_bars) < self.ma_period:
            return "BUY"  # default if not enough bars

        recent_close = self.broker.recent_bars['close'].iloc[-self.ma_period:]
        ma = recent_close.mean()
        current_price = self.broker.partial_bar['close']

        if current_price > ma:
            return "SELL"
        else:
            return "BUY"

    async def _place_first_order(self, price, first_order):
        """
        Place only the first order (dynamic).
        """
        if first_order == "BUY":
            order_price = price - self.grid_spacing
        else:
            order_price = price + self.grid_spacing

        self.active_order = await self.broker.place_limit_order(first_order, self.quantity, order_price)
        print(f"✓ Placed first {first_order} order at {order_price}")

    async def _check_fill(self):
        """
        Check if the active order is filled. If so, place the counter-order.
        """
        if self.active_order and self.active_order.isDone() and self.active_order.orderStatus.status == "Filled":
            filled_price = self.active_order.order.lmtPrice
            action = "SELL" if self.active_order.order.action == "BUY" else "BUY"
            new_price = filled_price + self.grid_spacing if action == "SELL" else filled_price - self.grid_spacing

            print(f"Order filled: {self.active_order.order.action} {self.quantity} @ {filled_price}")
            self.active_order = await self.broker.place_limit_order(action, self.quantity, new_price)
            print(f"Placed counter {action} order at {new_price}")
