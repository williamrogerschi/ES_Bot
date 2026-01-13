# esBot.py
import time
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

    def start(self):
        if not self.broker.connect():
            print("Failed to connect to IBKR")
            return

        bars = self.broker.get_historical_bars(duration="2 D", bar_size="1 min")
        if bars.empty:
            print("No historical bars to trade")
            return

        print("Bot is now running...\n")

        for idx in range(len(bars)):
            current_bar = bars.iloc[idx]
            price = current_bar['close']

            # Check SL/TP first
            if self.position != 0:
                exit_signal = self.risk_manager.check_exit(self.entry_price, price, self.position)
                if exit_signal:
                    print(f"Closed position at {price} due to {exit_signal}")
                    self.position = 0
                    self.entry_price = None
                    # After closing, skip new signal on same bar
                    print(f"[Price: ${price} | Position: {self.position}]")
                    continue

            # Generate signal only if flat
            if self.position == 0:
                action = self.strategy.generate_signal(bars[:idx+1])
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
            time.sleep(1)  # simulate bar stepping

        self.broker.disconnect()


if __name__ == "__main__":
    bot = ESBot()
    bot.start()
