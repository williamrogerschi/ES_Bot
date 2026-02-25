# models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class TrendState(Enum):
    STRONG_BULLISH = "strong_bullish"
    MODERATE_BULLISH = "moderate_bullish"
    STRONG_BEARISH = "strong_bearish"
    MODERATE_BEARISH = "moderate_bearish"
    SIDEWAYS = "sideways"


@dataclass
class Position:
    """Tracks an open position with its associated IB orders."""
    side: str  # 'long' or 'short'
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    trailing_stop: Optional[float]
    entry_time: datetime
    grid_level: float
    order_id: Optional[int] = None  # Entry order ID
    
    # Native IB order tracking
    stop_order_id: Optional[int] = None  # IB stop order ID
    tp_order_id: Optional[int] = None    # IB take profit order ID
    
    # Trailing stop state
    trailing_activated: bool = False  # Changed from trailing_active
    highest_price: Optional[float] = None  # For long positions
    lowest_price: Optional[float] = None   # For short positions


@dataclass
class StrategyConfig:
    # Grid settings
    base_grid_pct: float = 0.10
    max_positions: int = 1
    use_volatility_grid: bool = True
    max_anchor_distance_grids: int = 3  # Max grids away from current price for anchor
    
    # Tick size
    tick_size: float = 0.25  # ES tick size
    
    # ATR settings
    atr_length: int = 14
    atr_multiplier: float = 1.5
    
    # RSI settings
    rsi_length: int = 14
    rsi_overbought: int = 70
    rsi_oversold: int = 30
    
    # RSI entry thresholds (separate from trend determination)
    entry_rsi_bearish: float = 60.0       # Short when RSI > this in bearish trend
    entry_rsi_bullish: float = 40.0       # Long when RSI < this in bullish trend
    entry_rsi_sideways_short: float = 65.0  # Short when RSI > this in sideways
    entry_rsi_sideways_long: float = 35.0   # Long when RSI < this in sideways
    
    # MA settings
    short_ma_length: int = 20
    long_ma_length: int = 50
    super_long_ma_length: int = 200
    
    # MACD settings
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    # Trend confirmation
    trend_confirmation_bars: int = 2  # Bars needed to confirm trend change
    
    # Risk management - in POINTS for ES
    stop_loss_pts: float = 8.0        # Hard stop: 8 points
    take_profit_pts: float = 12.0     # Take profit: 12 points
    trailing_activation_pts: float = 5.0  # Activate trailing after +5 pts
    trailing_distance_pts: float = 5.0    # Trail by 5 pts from high/low
    
    # Legacy pct-based (used in current strategy)
    stop_loss_pct: float = 0.12
    take_profit_pct: float = 0.18
    use_trailing_stop: bool = True
    trailing_stop_pct: float = 0.07
    
    max_loss_per_day_pct: float = 1.0
    
    # Trend reversal exit
    use_trend_reversal_exit: bool = True
    trend_cooldown_minutes: int = 5  # Min time before trend reversal exit
    
    # Time-based exit
    time_based_exit: bool = True
    max_holding_hours: int = 4
    
    # Position sizing
    use_risk_based_position: bool = False
    risk_per_trade_pct: float = 1.0
    max_leverage: float = 3.0
    
    # Grid anchor settings
    lookback_for_anchor: int = 20  # bars to look back for swing high/low
    
    # Account
    initial_equity: float = 100000.0


@dataclass
class PendingOrder:
    """Tracks a pending limit order waiting for fill."""
    order_id: int
    side: str  # 'long' or 'short'
    limit_price: float
    size: float  # Added size field
    stop_loss: float
    take_profit: float
    trailing_stop: Optional[float]  # Added trailing_stop field
    submit_time: datetime
    grid_level: float