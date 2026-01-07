"""
ES Automated Trading Bot
Simple Moving Average Crossover Strategy
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedata
import time
import json

class DataHandler:
    """Handles price data fetching and management"""
    
    def __init__(self, symbol="ES"):
        self.symbol = symbol
        self.data = pd.DataFrame()
        
    def generate_mock_data(self, periods=100, interval_minutes=5):
        """Generate mock price data for testing (replace with real broker data later)"""
        start_price = 4500
        dates = [datetime.now() - timedelta(minutes=interval_minutes * i) for i in range(periods)]
        dates.reverse()
        
        # Generate realistic-looking price movement
        np.random.seed(42)
        returns = np.random.normal(0, 0.002, periods)
        prices = [start_price]
        
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        self.data = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': [p * 1.001 for p in prices],
            'low': [p * 0.999 for p in prices],
            'close': prices,
            'volume': np.random.randint(100, 1000, periods)
        })
        
        return self.data
    
    def get_latest_price(self):
        """Get the most recent price"""
        if len(self.data) > 0:
            return self.data['close'].iloc[-1]
        return None
    
    def add_bar(self, open_price, high, low, close, volume):
        """Add new price bar (for live data integration)"""
        new_row = pd.DataFrame({
            'timestamp': [datetime.now()],
            'open': [open_price],
            'high': [high],
            'low': [low],
            'close': [close],
            'volume': [volume]
        })
        self.data = pd.concat([self.data, new_row], ignore_index=True)


class Strategy:
    """Moving Average Crossover Strategy"""
    
    def __init__(self, fast_period=10, slow_period=30):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.position = 0  # 0 = no position, 1 = long, -1 = short
        
    def calculate_signals(self, data):
        """Calculate moving averages and generate signals"""
        data['MA_fast'] = data['close'].rolling(window=self.fast_period).mean()
        data['MA_slow'] = data['close'].rolling(window=self.slow_period).mean()
        
        # Generate signals
        data['signal'] = 0
        data.loc[data['MA_fast'] > data['MA_slow'], 'signal'] = 1  # Long signal
        data.loc[data['MA_fast'] < data['MA_slow'], 'signal'] = -1  # Short signal
        
        return data
    
    def check_entry_exit(self, data):
        """Check if we should enter or exit a position"""
        if len(data) < self.slow_period:
            return None, None  # Not enough data
        
        current_signal = data['signal'].iloc[-1]
        previous_signal = data['signal'].iloc[-2] if len(data) > 1 else 0
        
        # Detect crossover
        if current_signal == 1 and previous_signal != 1 and self.position != 1:
            return "BUY", data['close'].iloc[-1]
        elif current_signal == -1 and previous_signal != -1 and self.position != -1:
            return "SELL", data['close'].iloc[-1]
        
        return None, None


class RiskManager:
    """Manages position sizing and risk"""
    
    def __init__(self, max_position_size=1, stop_loss_points=20):
        self.max_position_size = max_position_size
        self.stop_loss_points = stop_loss_points
        self.entry_price = None
        
    def calculate_position_size(self, account_balance, price):
        """Calculate position size (simplified for now)"""
        return self.max_position_size
    
    def check_stop_loss(self, current_price, position_type):
        """Check if stop loss should be triggered"""
        if self.entry_price is None:
            return False
        
        if position_type == "LONG":
            if current_price <= self.entry_price - self.stop_loss_points:
                return True
        elif position_type == "SHORT":
            if current_price >= self.entry_price + self.stop_loss_points:
                return True
        
        return False


class BrokerInterface:
    """
    Interface for broker connection (abstracted for easy swapping)
    Replace this with actual IBKR, Tradovate, etc. API calls
    """
    
    def __init__(self, paper_trade=True):
        self.paper_trade = paper_trade
        self.account_balance = 50000  # Starting balance for paper trading
        self.positions = []
        self.orders = []
        
    def connect(self):
        """Connect to broker (mock for now)"""
        print("✓ Connected to broker (Paper Trading Mode)")
        return True
    
    def place_order(self, action, quantity, symbol, price):
        """Place an order"""
        order = {
            'timestamp': datetime.now(),
            'action': action,
            'quantity': quantity,
            'symbol': symbol,
            'price': price,
            'status': 'FILLED'  # Mock instant fill
        }
        self.orders.append(order)
        
        print(f"\n{'='*50}")
        print(f"ORDER EXECUTED: {action} {quantity} {symbol} @ ${price:.2f}")
        print(f"{'='*50}\n")
        
        return order
    
    def get_account_balance(self):
        """Get current account balance"""
        return self.account_balance
    
    def get_positions(self):
        """Get current positions"""
        return self.positions


class TradingBot:
    """Main trading bot orchestrator"""
    
    def __init__(self):
        self.data_handler = DataHandler(symbol="ES")
        self.strategy = Strategy(fast_period=10, slow_period=30)
        self.risk_manager = RiskManager(max_position_size=1, stop_loss_points=20)
        self.broker = BrokerInterface(paper_trade=True)
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
        
        # Load initial data
        print("Loading historical data...")
        self.data_handler.generate_mock_data(periods=100, interval_minutes=5)
        print(f"✓ Loaded {len(self.data_handler.data)} bars\n")
        
        return True
    
    def run_strategy_cycle(self):
        """Run one cycle of the strategy"""
        # Calculate indicators
        data_with_signals = self.strategy.calculate_signals(self.data_handler.data)
        
        # Check for entry/exit signals
        action, price = self.strategy.check_entry_exit(data_with_signals)
        
        if action:
            # Calculate position size
            position_size = self.risk_manager.calculate_position_size(
                self.broker.get_account_balance(), 
                price
            )
            
            # Place order
            order = self.broker.place_order(action, position_size, "ES", price)
            
            # Update strategy position
            if action == "BUY":
                self.strategy.position = 1
                self.risk_manager.entry_price = price
            elif action == "SELL":
                self.strategy.position = -1
                self.risk_manager.entry_price = price
            
            # Log trade
            self.trade_log.append({
                'timestamp': datetime.now(),
                'action': action,
                'price': price,
                'position_size': position_size
            })
        
        # Check stop loss
        current_price = self.data_handler.get_latest_price()
        position_type = "LONG" if self.strategy.position == 1 else "SHORT" if self.strategy.position == -1 else None
        
        if position_type and self.risk_manager.check_stop_loss(current_price, position_type):
            exit_action = "SELL" if position_type == "LONG" else "BUY"
            print(f"\n⚠ STOP LOSS TRIGGERED at ${current_price:.2f}")
            self.broker.place_order(exit_action, 1, "ES", current_price)
            self.strategy.position = 0
            self.risk_manager.entry_price = None
    
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
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                current_price = self.data_handler.get_latest_price()
                
                print(f"[{current_time}] Cycle {cycle_count} | Price: ${current_price:.2f} | Position: {self.strategy.position}")
                
                # Run strategy
                self.run_strategy_cycle()
                
                # Simulate new bar (in real version, this would be live data)
                if cycle_count % 5 == 0:  # Add new bar every 5 cycles
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
                
                # Wait before next cycle (in production, this would be your bar interval)
                time.sleep(2)
                
        except KeyboardInterrupt:
            print("\n\nBot stopped by user")
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
            'is_running': self.is_running,
            'current_position': self.strategy.position,
            'account_balance': self.broker.get_account_balance(),
            'total_trades': len(self.trade_log)
        }


# Example usage
if __name__ == "__main__":
    # Create and start the bot
    bot = TradingBot()
    
    # Run for demonstration (in production, remove run_once=True to run continuously)
    bot.start(run_once=False)