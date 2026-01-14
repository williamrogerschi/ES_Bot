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
        self.position = 0
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

        print("Bot is now running...\n")

        # Subscribe to live bars (1-min)
        async for bar in self.broker.stream_live_bars(bar_size="1 min"):
            price = bar['close']

            # Check stop loss / take profit
            if self.position != 0:
                exit_signal = self.risk_manager.check_exit(self.entry_price, price, self.position)
                if exit_signal:
                    print(f"Closed position at {price} due to {exit_signal}")
                    self.position = 0
                    self.entry_price = None
                    print(f"[Price: ${price} | Position: {self.position}]")
                    continue

            # Generate signal if flat
            if self.position == 0:
                action = self.strategy.generate_signal(self.broker.recent_bars)
                if action == 'BUY':
                    self.position = 1
                    self.entry_price = price
                    print(f"Opened LONG position at {price}")
                elif action == 'SELL':
                    self.position = -1
                    self.entry_price = price
                    print(f"Opened SHORT position at {price}")

            # Print status
            print(f"[Price: ${price} | Position: {self.position}]")

        await self.broker.disconnect_async()

if __name__ == "__main__":
    bot = ESBot()
    asyncio.run(bot.start())
