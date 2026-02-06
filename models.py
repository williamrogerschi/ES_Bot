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
class PendingOrder:
    """Track orders that have been submitted but not yet filled."""
    order_id: int
    side: str  # 'long' or 'short'
    limit_price: float
    size: float
    stop_loss: float
    take_profit: float
    trailing_stop: Optional[float]
    submit_time: datetime
    grid_level: float


@dataclass
class StrategyConfig:
    # Instrument settings
    tick_size: float = 0.25              # ES/NQ = 0.25, CL = 0.01, GC = 0.10
    
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


# =============================================================================
# CONFIG PRESETS
# =============================================================================

def get_scalp_config() -> StrategyConfig:
    """
    Single contract scalper with trailing stop.
    - 1 position max
    - Tight SL/TP
    - Trailing stop enabled
    - Quick entries/exits
    """
    return StrategyConfig(
        # Single position
        max_positions=1,
        
        # Grid (still used for entry levels)
        base_grid_pct=0.08,              # ~5.5 pts on ES
        use_volatility_grid=True,
        atr_multiplier=1.2,
        max_anchor_distance_grids=2,
        
        # Tight risk management
        stop_loss_pct=0.12,              # ~8 pts
        take_profit_pct=0.18,            # ~12 pts
        trailing_stop_pct=0.07,          # ~5 pts
        use_trailing_stop=True,
        max_loss_per_day_pct=1.0,        # $1k on $100k
        
        # Faster trend response
        trend_confirmation_bars=2,
        use_trend_reversal_exit=False,
        
        # Standard entries
        entry_rsi_bearish=60,
        entry_rsi_bullish=40,
        entry_rsi_sideways_short=70,
        entry_rsi_sideways_long=30,
    )


def get_grid_config() -> StrategyConfig:
    """
    Multi-position grid trading without trailing stop.
    - Up to 3 positions
    - Wider SL to accommodate grid levels
    - No trailing stop (let grid work)
    - Fixed TP for all positions
    """
    return StrategyConfig(
        # Multiple positions
        max_positions=3,
        
        # Grid spacing
        base_grid_pct=0.12,              # ~8 pts on ES
        use_volatility_grid=True,
        atr_multiplier=1.5,
        max_anchor_distance_grids=3,
        
        # Wider risk management (SL must cover grid levels)
        stop_loss_pct=0.40,              # ~28 pts (covers 3 grid levels)
        take_profit_pct=0.25,            # ~17 pts
        trailing_stop_pct=0.0,           # Not used
        use_trailing_stop=False,         # DISABLED for grid
        max_loss_per_day_pct=2.0,        # $2k on $100k
        
        # Slower trend response (grid needs stability)
        trend_confirmation_bars=3,
        use_trend_reversal_exit=False,
        
        # Standard entries
        entry_rsi_bearish=60,
        entry_rsi_bullish=40,
        entry_rsi_sideways_short=70,
        entry_rsi_sideways_long=30,
    )


# Preset registry
CONFIG_PRESETS = {
    'scalp': get_scalp_config,
    'grid': get_grid_config,
}