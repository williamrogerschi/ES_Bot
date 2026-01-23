# esBot.py
import asyncio
from ibkrBroker import IBKRBroker
from strategy import MovingAverageCrossoverStrategy
from riskManager import RiskManager

class ESBot:
    def __init__(self):
        self.broker = IBKRBroker()
        self.strategy = MovingAverageCrossoverStrategy()
        self.risk_manager = RiskManager(stop_points=2, target_points=4)

        self.position = 0          # 1 = long, -1 = short
        self.entry_price = None

    async def start(self):
        # Connect to IBKR
        if not await self.broker.connect_async():
            print("Failed to connect to IBKR")
            return

        # Load front-month contract
        if not await self.broker.get_front_month_contract_async():
            print("No contract loaded")
            return

        print("\nBot is now running...\n")

        try:
            async for bar in self.broker.stream_live_bars():
                price = bar["close"]  # latest real-time price

                # --- EXIT LOGIC ---
                if self.position != 0:
                    exit_signal = self.risk_manager.check_exit(
                        self.entry_price, price, self.position
                    )
                    if exit_signal:
                        action = "SELL" if self.position == 1 else "BUY"
                        trade = await self.broker.place_market_order(action, 1)
                        fill_price = trade.fills[-1].execution.price
                        print(f"EXIT {exit_signal} @ {fill_price}")
                        self.position = 0
                        self.entry_price = None
                        continue

                # --- ENTRY LOGIC ---
                if self.position == 0 and len(self.broker.recent_bars) >= self.strategy.long_window:
                    signal = self.strategy.generate_signal(self.broker.recent_bars)
                    if signal in ("BUY", "SELL"):
                        trade = await self.broker.place_market_order(signal, 1)
                        fill_price = trade.fills[-1].execution.price
                        self.position = 1 if signal == "BUY" else -1
                        self.entry_price = fill_price
                        side = "LONG" if self.position == 1 else "SHORT"
                        print(f"ENTER {side} @ {fill_price}")

                # --- DEBUG PRINT ---
                last_bars = self.broker.recent_bars.tail(self.strategy.long_window)
                short_ma = last_bars['close'].rolling(self.strategy.short_window).mean().iloc[-1]
                long_ma = last_bars['close'].rolling(self.strategy.long_window).mean().iloc[-1]
                print(f"[Price: {price} | Position: {self.position} | MA short: {short_ma:.2f} | MA long: {long_ma:.2f}]")

        finally:
            await self.broker.disconnect_async()


if __name__ == "__main__":
    asyncio.run(ESBot().start())
