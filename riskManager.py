class RiskManager:
    """Manages position exits (stop loss & take profit)"""

    def __init__(self, stop_loss_points=20, take_profit_points=30, max_position_size=1):
        self.stop_loss_points = stop_loss_points
        self.take_profit_points = take_profit_points
        self.max_position_size = max_position_size
        self.entry_price = None

    def calculate_position_size(self, account_balance, price):
        """Return position size (for now just max size)"""
        return self.max_position_size

    def check_exit(self, current_price, position):
        """Return exit reason if TP/SL triggered"""
        if self.entry_price is None or position == 0:
            return None

        # LONG
        if position == 1:
            if current_price >= self.entry_price + self.take_profit_points:
                return "TAKE_PROFIT"
            if current_price <= self.entry_price - self.stop_loss_points:
                return "STOP_LOSS"

        # SHORT
        if position == -1:
            if current_price <= self.entry_price - self.take_profit_points:
                return "TAKE_PROFIT"
            if current_price >= self.entry_price + self.stop_loss_points:
                return "STOP_LOSS"

        return None
