# grid.py
import asyncio
from datetime import datetime, timedelta

class GridStrategy:
    def __init__(self, broker, trader, scalp_points=1.0, min_bar_range=0.5):
        self.broker = broker
        self.trader = trader
        self.scalp_points = scalp_points
        self.min_bar_range = min_bar_range
        self.active_trade = None

    async def start(self):
        async for bars in self.broker.stream_tick_bars():
            if bars.empty:
                continue

            last_bar = bars.iloc[-1]
            h, l, c = last_bar.open, last_bar.high, last_bar.low, last_bar.close
            bar_range = h - l
            close_pct = (c - l) / bar_range if bar_range > 0 else 0

            # Skip if already active trade
            if self.active_trade:
                continue

            if bar_range < self.min_bar_range:
                continue

            # Strong long bar
            if close_pct >= 0.95:
                limit_price = c - 0.25
                print(f"[ENTRY] Strong CLOSED bar → BUY Close:{c} Limit:{limit_price}")
                trade = self.trader.place_limit_order_no_wait("BUY", 1, limit_price)
                self.active_trade = trade
                await self.trader.place_take_profit("BUY", limit_price, self.scalp_points)

            # Strong short bar
            elif close_pct <= 0.05:
                limit_price = c + 0.25
                print(f"[ENTRY] Strong CLOSED bar → SELL Close:{c} Limit:{limit_price}")
                trade = self.trader.place_limit_order_no_wait("SELL", 1, limit_price)
                self.active_trade = trade
                await self.trader.place_take_profit("SELL", limit_price, self.scalp_points)

            # Reset after trade
            self.active_trade = None
