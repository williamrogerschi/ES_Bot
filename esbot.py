# esBot.py (quick test)
import asyncio
from ibkrBroker import IBKRBroker

async def main():
    broker = IBKRBroker()
    await broker.connect_async()
    await broker.get_front_month_contract_async()

    async for bar in broker.stream_closed_bars():
        o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]
        ts = bar["time"]
        bar_range = h - l
        close_pct = (c - l) / bar_range if bar_range > 0 else 0
        print(f"[BAR] {ts} H:{h} L:{l} C:{c} Range:{bar_range:.2f} Close%:{close_pct:.2f}")

asyncio.run(main())
