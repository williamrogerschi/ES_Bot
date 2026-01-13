"""
ES Automated Trading Bot
Simple Moving Average Crossover Strategy with TP/SL and PnL
"""

import time
import numpy as np
from datetime import datetime

from dataHandler import DataHandler
from strategy import Strategy
from riskManager import RiskManager
from ibkrBroker import IBKRBroker
from visualizer import Visualizer


class TradingBot:
    """Main trading bot orchestrator"""

    def __init__(self):
        self.data_handler = DataHandler(symbol="ES")
        self.strategy = Strategy(fast_period=10, slow_period=30)
        self.risk_manager = RiskManager(stop_loss_points=20, take_profit_points=30, max_position_size=1)
        self.broker = IBKRBroker(paper=True)
        self.visualizer = Visualizer(self.strategy)

        self.is_running = False
        self.trade_log = []

    def initialize(self):
        """Initialize the bot"""
        print("Initializing ES Futures Trading Bot...")
        print(f"Strategy: Moving Average Crossover (10/30)")
        print(f"Symbol: ES Futures")
        print(f"Mode: Paper Trading\n")

        # Connect to broker
        if not self.broker.connect():
            print("Failed to connect to broker")
            return False

        # Load initial mock data
        print("Loading historical data...")

        # If IBKR is connected, load real historical ES bars
        if self.broker.connected:
            bars = self.broker.get_historical_bars(symbol="ES", duration="2 D", bar_size="5 mins")
            self.data_handler.load_from_ibkr(bars)
            print(f"✓ Loaded {len(self.data_handler.data)} bars from IBKR")
        else:
            # Fallback: generate mock data
            self.data_handler.generate_mock_data(periods=100, interval_minutes=5)
            print(f"✓ Loaded {len(self.data_handler.data)} bars (mock data)")



        return True

    def run_strategy_cycle(self):
        """Run one cycle of the strategy"""

        data = self.strategy.calculate_signals(self.data_handler.data)

        if self.strategy.position == 0:
            action, price = self.strategy.check_entry_exit(data)

            if action:
                position_size = self.risk_manager.calculate_position_size(
                    self.broker.get_account_balance(),
                    price
                )

                # Place order
                self.broker.place_order(action, position_size, "ES", price)

                # Log entry with LONG/SHORT
                position_type = "LONG" if action == "BUY" else "SHORT"
                print(f"\n{'='*50}")
                print(f"ORDER EXECUTED: {action} {position_size} ES @ ${price:.2f} | Position: {position_type}")
                print(f"{'='*50}\n")

                # Update state
                self.strategy.position = 1 if action == "BUY" else -1
                self.risk_manager.entry_price = price

                self.trade_log.append({
                    "timestamp": datetime.now(),
                    "action": action,
                    "price": price,
                    "size": position_size
                })

        if self.strategy.position != 0:
            current_price = self.data_handler.get_latest_price()
            exit_reason = self.risk_manager.check_exit(current_price, self.strategy.position)

            if exit_reason:
                exit_action = "SELL" if self.strategy.position == 1 else "BUY"

                # Calculate PnL in points
                if self.strategy.position == 1:  # LONG
                    pnl_points = current_price - self.risk_manager.entry_price
                elif self.strategy.position == -1:  # SHORT
                    pnl_points = self.risk_manager.entry_price - current_price

                # Convert points to $ (ES = $50 per point)
                pnl_dollars = pnl_points * 50

                # Print exit info
                print(f"\n⚠ EXIT ({exit_reason}) at ${current_price:.2f}")
                print(f"{'='*50}")
                print(f"ORDER EXECUTED: {exit_action} 1 ES @ ${current_price:.2f} | PnL: ${pnl_dollars:.2f}")
                print(f"{'='*50}\n")

                # Place the order
                self.broker.place_order(exit_action, 1, "ES", current_price)

                # Reset position
                self.strategy.position = 0
                self.risk_manager.entry_price = None

        self.visualizer.plot(data)

    def start(self, run_once=False):
        """Start the trading bot"""
        if not self.initialize():
            return

        self.is_running = True
        print("Bot is now running...\n")
        print("=" * 60)

        cycle_count = 0

        try:
            while self.is_running:
                cycle_count += 1
                current_price = self.data_handler.get_latest_price()
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                print(f"[{current_time}] Cycle {cycle_count} | Price: ${current_price:.2f} | Position: {self.strategy.position}")

                # Run one cycle
                self.run_strategy_cycle()

                # Simulate new bar every 5 cycles
                if cycle_count % 5 == 0:
                    last_price = self.data_handler.get_latest_price()
                    new_price = last_price * (1 + np.random.normal(0, 0.002))
                    self.data_handler.add_bar(
                        open_price=last_price,
                        high=new_price * 1.001,
                        low=new_price * 0.999,
                        close=new_price,
                        volume=np.random.randint(100, 1000)
                    )

                if run_once:
                    break

                time.sleep(2)

        except KeyboardInterrupt:
            print("\nBot stopped by user")
            self.stop()

    def stop(self):
        """Stop the trading bot"""
        self.is_running = False
        print("\n" + "=" * 60)
        print("TRADING SESSION SUMMARY")
        print("=" * 60)
        print(f"Total trades: {len(self.trade_log)}")
        print(f"Account balance: ${self.broker.get_account_balance():.2f}")

        if self.trade_log:
            print("\nTrade Log:")
            for trade in self.trade_log:
                print(f"  {trade['timestamp'].strftime('%H:%M:%S')} - {trade['action']} @ ${trade['price']:.2f}")

    def get_status(self):
        """Get current bot status"""
        return {
            "is_running": self.is_running,
            "current_position": self.strategy.position,
            "account_balance": self.broker.get_account_balance(),
            "total_trades": len(self.trade_log)
        }


if __name__ == "__main__":
    bot = TradingBot()
    bot.start(run_once=False)
