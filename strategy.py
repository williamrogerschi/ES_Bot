# strategy.py
import asyncio
from collections import deque
import math
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")

class GridStrategy:
    def __init__(self, broker):
        self.broker = broker
        
        # ── Config (tune these) ───────────────────────────────
        self.base_grid_pct     = 0.8          # %
        self.atr_mult          = 1.5
        self.atr_length        = 14
        self.max_positions     = 5
        self.stop_loss_pct     = 2.0
        self.take_profit_pct   = 3.0
        
        # State
        self.bars = deque(maxlen=200)               # enough for ATR + some history
        self.positions = []                         # list of dicts: {'side':, 'entry':, ...}
        self.last_price = None

    def compute_atr(self):
        if len(self.bars) <= self.atr_length:
            return None
        
        trs = []
        for i in range(1, len(self.bars)):
            h, l, pc = self.bars[i]['high'], self.bars[i]['low'], self.bars[i-1]['close']
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        
        return sum(trs[-self.atr_length:]) / self.atr_length

    def get_grid_size_pct(self, price):
        atr = self.compute_atr()
        if atr is None:
            return self.base_grid_pct
        atr_pct = (atr / price) * 100
        return max(self.base_grid_pct, atr_pct * self.atr_mult)

    async def on_new_bar(self, bar):
        self.bars.append(bar)
        self.last_price = bar['close']
        
        # Convert UTC time → Chicago local time for display
        local_time = bar['time'].astimezone(CENTRAL)
        time_str = local_time.strftime('%H:%M')
        
        print(f"[{time_str}] Close: {bar['close']:.2f}   "
              f"H:{bar['high']:.2f} L:{bar['low']:.2f}")

        atr = self.compute_atr()
        if atr is None:
            print("  Waiting for enough bars to compute ATR...")
            return

        grid_pct = self.get_grid_size_pct(bar['close'])
        print(f"  Grid size: {grid_pct:.3f}%   ATR: {atr:.2f}")

        # Very basic grid visualization (expand to real logic later)
        buys = [bar['close'] * (1 - grid_pct/100 * i) for i in range(1, self.max_positions + 1)]
        sells = [bar['close'] * (1 + grid_pct/100 * i) for i in range(1, self.max_positions + 1)]

        print(f"  Potential buy levels:  {[f'{x:.2f}' for x in buys]}")
        print(f"  Potential sell levels: {[f'{x:.2f}' for x in sells]}")

        # TODO: add real entry logic (check if low/high crossed level + trend filter)
        # TODO: add position management (SL/TP/trailing/time exit)
        # TODO: broker.place_order(...) when ready — start with limit orders!

        # Example placeholder detection
        if bar['low'] <= buys[0]:
            print("  → BUY grid level touched!")
            # await self.broker.ib.placeOrder(...)  # uncomment when confident

        if bar['high'] >= sells[0]:
            print("  → SELL grid level touched!")