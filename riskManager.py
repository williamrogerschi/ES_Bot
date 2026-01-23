# riskManager.py
class RiskManager:
    def __init__(self, stop_points=2, target_points=4):
        self.stop_points = stop_points
        self.target_points = target_points

    def check_exit(self, entry_price, current_price, position):
        if position == 1:  # long
            if current_price <= entry_price - self.stop_points:
                return "EXIT_STOP"
            elif current_price >= entry_price + self.target_points:
                return "EXIT_TARGET"
        elif position == -1:  # short
            if current_price >= entry_price + self.stop_points:
                return "EXIT_STOP"
            elif current_price <= entry_price - self.target_points:
                return "EXIT_TARGET"
        return None
