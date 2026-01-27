# grid.py
import asyncio

class GridStrategy:
    def __init__(self, broker, grid_spacing=1.0, scalp_points=1.0, min_bar_range=0.5):
        self.broker = broker
        self.grid_spacing = grid_spacing
        self.scalp_points = scalp_points
        self.min_bar_range = min_bar_range
        self.active_trade = None

    async def start(self):
        async for bars, partial in self.broker.stream_live_bars():
            last_bar = bars.iloc[-1]
            o, h, l, c = last_bar.open, last_bar.high, last_bar.low, last_bar.close
            bar_range = h - l
            close_pct = (c - l) / bar_range if bar_range > 0 else 0

            print(f"[BAR] O:{o} H:{h} L:{l} C:{c} Range:{bar_range} Close%:{close_pct:.2f}")

            # Skip if there is already an active trade
            if self.active_trade:
                continue

            # Only consider strong bars with minimum range
            if bar_range < self.min_bar_range:
                continue

            # Strong long bar (close near high)
            if close_pct >= 0.95:
                limit_price = c - 0.05  # slightly below close
                print(f"Strong bar detected: BUY at {c}, placing limit at {limit_price}")
                self.active_trade = await self.broker.place_limit_order("BUY", 1, limit_price)
                # After fill, place take profit
                await self._place_take_profit("BUY", self.active_trade.order.lmtPrice)

            # Strong short bar (close near low)
            elif close_pct <= 0.05:
                limit_price = c + 0.05  # slightly above close
                print(f"Strong bar detected: SELL at {c}, placing limit at {limit_price}")
                self.active_trade = await self.broker.place_limit_order("SELL", 1, limit_price)
                await self._place_take_profit("SELL", self.active_trade.order.lmtPrice)

    async def _place_take_profit(self, action, entry_price):
        if action == "BUY":
            tp_price = entry_price + self.scalp_points
            print(f"Placing take profit SELL at {tp_price}")
            await self.broker.place_limit_order("SELL", 1, tp_price)
        else:
            tp_price = entry_price - self.scalp_points
            print(f"Placing take profit BUY at {tp_price}")
            await self.broker.place_limit_order("BUY", 1, tp_price)

        self.active_trade = None  # reset for next trade
