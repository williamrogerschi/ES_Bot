import time
from ibkrBroker import IBKRBroker
from strategy import MovingAverageCrossoverStrategy
from dataHandler import DataHandler

class TradingBot:
    def __init__(self, symbol="ES"):
        self.symbol = symbol
        self.ibkr = IBKRBroker(symbol=self.symbol, paper=True)
        self.data_handler = DataHandler(symbol=self.symbol)
        self.strategy = MovingAverageCrossoverStrategy()
        self.is_running = False

    def initialize(self):
        if not self.ibkr.connect():
            return False
        contract = self.ibkr.get_front_month_contract()
        bars = self.ibkr.get_historical_bars(duration="2 D", bar_size="5 mins")
        if bars.empty:
            return False
        self.data_handler.load_from_ibkr(bars)
        print("Bot is now running...\n")
        return True

    def run_cycle(self):
        price = self.data_handler.get_latest_price()
        self.strategy.calculate_signals(self.data_handler.data)
        position = self.strategy.position
        print(f"[Price: ${price:.2f} | Position: {position}]")

    def start(self, run_once=False, cycle_delay=5):
        if not self.initialize():
            print("Bot initialization failed. Exiting.")
            return
        self.is_running = True
        while self.is_running:
            self.run_cycle()
            if run_once:
                break
            time.sleep(cycle_delay)

if __name__ == "__main__":
    bot = TradingBot(symbol="ES")
    bot.start(run_once=False, cycle_delay=5)
