from datetime import datetime

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
        
        position_type = "LONG" if action == "BUY" else "SHORT"
        print(f"\n{'='*50}")
        print(f"ORDER EXECUTED: {action} {quantity} {symbol} @ ${price:.2f} | Position: {position_type}")
        print(f"{'='*50}\n")
        
        return order
    
    def get_account_balance(self):
        """Get current account balance"""
        return self.account_balance
    
    def get_positions(self):
        """Get current positions"""
        return self.positions