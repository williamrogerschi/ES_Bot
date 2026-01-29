# trades.py
import asyncio

class TradeStrategy:
    def __init__(self, broker, strong_threshold=0.25):
        """
        broker: your IBKRBroker instance
        strong_threshold: fraction from high/low to define strong bar (0.25 = top/bottom 25%)
        """
        self.broker = broker
        self.strong_threshold = strong_threshold
        self.epsilon = 1e-6  # for floating point tolerance

    async def run(self):
        async for bar in self.broker.stream_closed_bars():
            o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]
            bar_range = h - l
            if bar_range <= 0:
                continue

            close_pct = (c - l) / bar_range
            print(f"[BAR] {bar['time']} H:{h} L:{l} C:{c} Range:{bar_range:.2f} Close%:{close_pct:.2f}")
            print("DEBUG: close_pct computed as", close_pct)

            # Strong bullish bar → BUY
            if close_pct >= 1 - self.strong_threshold - self.epsilon:
                limit_price = round(c - 0.05, 2)  # slight adjustment below close
                print(f"[ENTRY] Strong bullish bar → BUY Limit: {limit_price}")
                self.broker.place_limit_order_no_wait("BUY", 1, limit_price)

            # Strong bearish bar → SELL
            elif close_pct <= self.strong_threshold + self.epsilon:
                limit_price = round(c + 0.05, 2)  # slight adjustment above close
                print(f"[ENTRY] Strong bearish bar → SELL Limit: {limit_price}")
                self.broker.place_limit_order_no_wait("SELL", 1, limit_price)
