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