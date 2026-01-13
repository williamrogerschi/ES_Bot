import pandas as pd
import numpy as np
from datetime import datetime, timedelta

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
    
    def load_from_ibkr(self, bars):
        """Load historical bars from IBKR into DataFrame"""
        self.data = pd.DataFrame([{
            'timestamp': bar.date,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume
        } for bar in bars])
    
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

