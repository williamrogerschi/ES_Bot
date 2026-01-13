# riskManager.py
import pandas as pd

class RiskManager:
    """
    Simple Risk Manager for ES Bot
    Handles Stop-Loss (SL) and Take-Profit (TP) logic
    Works with bar close prices (Option A: last two bars)
    """

    def __init__(self, stop_loss_pct=0.5, take_profit_pct=1.0):
        """
        Initialize risk manager
        :param stop_loss_pct: Stop loss in % of entry price
        :param take_profit_pct: Take profit in % of entry price
        """
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.entry_price = None
        self.position = 0  # 0 = flat, 1 = long, -1 = short

    def set_position(self, position, entry_price):
        """
        Set current position
        :param position: 1 for long, -1 for short, 0 for flat
        :param entry_price: price at which position was opened
        """
        self.position = position
        self.entry_price = entry_price

        if position != 0:
            print(f"Opened {'LONG' if position == 1 else 'SHORT'} position at {entry_price}")

    def check_exit(self, data: pd.DataFrame):
        """
        Check if stop-loss or take-profit is hit based on last two bars
        :param data: pandas DataFrame with at least 'close' column
        :return: True if position should be closed, False otherwise
        """
        if self.position == 0 or data.empty or len(data) < 2:
            return False  # no position or insufficient data

        last_close = data['close'].iloc[-1]
        prev_close = data['close'].iloc[-2]

        # Calculate SL and TP prices
        stop_loss = self.entry_price * (1 - self.stop_loss_pct / 100) if self.position == 1 else \
                    self.entry_price * (1 + self.stop_loss_pct / 100)
        take_profit = self.entry_price * (1 + self.take_profit_pct / 100) if self.position == 1 else \
                      self.entry_price * (1 - self.take_profit_pct / 100)

        # Long position
        if self.position == 1:
            if prev_close < stop_loss <= last_close:
                print(f"Stop-Loss hit: {last_close} <= {stop_loss}")
                self.position = 0
                return True
            elif prev_close < take_profit <= last_close:
                print(f"Take-Profit hit: {last_close} >= {take_profit}")
                self.position = 0
                return True

        # Short position
        if self.position == -1:
            if prev_close > stop_loss >= last_close:
                print(f"Stop-Loss hit: {last_close} >= {stop_loss}")
                self.position = 0
                return True
            elif prev_close > take_profit >= last_close:
                print(f"Take-Profit hit: {last_close} <= {take_profit}")
                self.position = 0
                return True

        return False
