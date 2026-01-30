# grid.py
import math

class GridStrategy:
    def __init__(self, broker, grid_size=10.0):
        """
        grid_size: ES points between grid levels
        """
        self.broker = broker
        self.grid_size = grid_size
        self.last_grid_price = None

    async def run(self):
        async for price in self.broker.stream_ticks():
            if self.last_grid_price is None:
                self.last_grid_price = price
                print(f"[GRID INIT] {price}")
                continue

            move = price - self.last_grid_price

            # PRICE MOVED UP → SELL GRID
            if move >= self.grid_size:
                sell_price = math.floor(price / self.grid_size) * self.grid_size
                print(f"[GRID SELL] price={price} sell={sell_price}")
                self.broker.place_limit_order_no_wait("SELL", 1, sell_price)
                self.last_grid_price = price

            # PRICE MOVED DOWN → BUY GRID
            elif move <= -self.grid_size:
                buy_price = math.ceil(price / self.grid_size) * self.grid_size
                print(f"[GRID BUY] price={price} buy={buy_price}")
                self.broker.place_limit_order_no_wait("BUY", 1, buy_price)
                self.last_grid_price = price
