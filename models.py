"""
Data models for ES Futures Grid Trading Strategy
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class TrendState(Enum):
    STRONG_BULLISH = "strong_bullish"
    MODERATE_BULLISH = "moderate_bullish"
    SIDEWAYS = "sideways"
    MODERATE_BEARISH = "moderate_bearish"
    STRONG_BEARISH = "strong_bearish"


@dataclass
class Position:
    side: str  # 'long' or 'short'
    entry_price: float
    size: float
    stop_loss: float
    take_profit: float
    trailing_stop: Optional[float]
    entry_time: datetime
    grid_level: float
    order_id: Optional[int] = None


@dataclass
class StrategyConfig:
    # Grid settings
    base_grid_pct: float = 0.10          # ~7 pts on ES
    max_positions: int = 5
    use_volatility_grid: bool = True
    lookback_for_anchor: int = 20
    max_anchor_distance_grids: int = 3   # Cap anchor at N grid widths from price
    
    # ATR settings
    atr_length: int = 14
    atr_multiplier: float = 1.5
    
    # RSI settings
    rsi_length: int = 14
    rsi_overbought: int = 70
    rsi_oversold: int = 30
    
    # MA settings
    short_ma_length: int = 20
    long_ma_length: int = 50
    super_long_ma_length: int = 200
    
    # MACD settings
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    
    # Risk management
    stop_loss_pct: float = 0.15          # ~10 pts
    take_profit_pct: float = 0.20        # ~14 pts
    trailing_stop_pct: float = 0.10      # ~7 pts
    use_trailing_stop: bool = True       # Enable trailing stop
    max_loss_per_day_pct: float = 2.0    # $2k on $100k
    
    # Time-based exit
    time_based_exit: bool = True
    max_holding_hours: int = 48
    
    # Position sizing
    use_risk_based_position: bool = True
    risk_per_trade_pct: float = 1.0
    max_leverage: float = 3.0
    
    # Account
    initial_equity: float = 100000.0
    
    # ES-specific: Trend confirmation
    trend_confirmation_bars: int = 3     # Bars needed to confirm trend change
    trend_cooldown_minutes: int = 5      # Ignore trend changes after entry
    use_trend_reversal_exit: bool = False  # Disabled for ES (too choppy)
    
    # Entry RSI thresholds (can be loosened for testing)
    entry_rsi_bearish: float = 60        # RSI > this for shorts in bearish
    entry_rsi_bullish: float = 40        # RSI < this for longs in bullish
    entry_rsi_sideways_short: float = 70 # RSI > this for shorts in sideways
    entry_rsi_sideways_long: float = 30  # RSI < this for longs in sideways