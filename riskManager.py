class RiskManager:
    def __init__(self):
        self.position = 0  # current position

    def update_position(self, signal):
        """Adjust position according to signal"""
        if signal != self.position:
            self.position = signal
            return True  # indicates a trade happened
        return False
