"""
Data models for ES Futures Grid Trading Strategy
"""

from dataclasses import dataclass
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
    order_id: Optional[int] = None

    # Native IB order tracking
    stop_order_id: Optional[int] = None
    tp_order_id: Optional[int] = None

    # Trailing stop state
    trailing_activated: bool = False
    highest_price: Optional[float] = None  # For long positions
    lowest_price: Optional[float] = None   # For short positions


@dataclass
class PendingOrder:
    """Tracks a pending limit order waiting for fill."""
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
    tick_size: float = 0.25              # ES tick size

    # Grid settings
    base_grid_pct: float = 0.10
    max_positions: int = 1
    use_volatility_grid: bool = True
    max_anchor_distance_grids: int = 3
    lookback_for_anchor: int = 20

    # ATR settings
    atr_length: int = 14
    atr_multiplier: float = 1.5

    # RSI settings
    rsi_length: int = 14
    rsi_overbought: int = 70
    rsi_oversold: int = 30

    # RSI entry thresholds
    entry_rsi_bearish: float = 55.0         # CHANGED: was 60, lowered to catch more entries
    entry_rsi_bullish: float = 45.0         # CHANGED: was 40, raised to catch more entries
    entry_rsi_sideways_short: float = 70.0  # RESTORED: was 65 in current, back to old 70
    entry_rsi_sideways_long: float = 30.0   # RESTORED: was 35 in current, back to old 30

    # MA settings
    short_ma_length: int = 20
    long_ma_length: int = 50
    super_long_ma_length: int = 200

    # MACD settings
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Trend confirmation
    trend_confirmation_bars: int = 3        # RESTORED: was 2 in current, back to old 3

    # Risk management - points-based (used by current strategy.py)
    stop_loss_pts: float = 8.0
    take_profit_pts: float = 12.0
    trailing_activation_pts: float = 5.0
    trailing_distance_pts: float = 5.0

    # Risk management - pct-based (used by entry order sizing, aligned to pts targets)
    stop_loss_pct: float = 0.117          # ~8 pts at 6860
    take_profit_pct: float = 0.175        # ~12 pts at 6860
    use_trailing_stop: bool = True
    trailing_stop_pct: float = 0.073      # ~5 pts at 6860

    max_loss_per_day_pct: float = 2.0       # RESTORED: was 1.0, back to old 2.0

    # Trend reversal exit
    use_trend_reversal_exit: bool = False   # RESTORED: was True in current, back to old False
    trend_cooldown_minutes: int = 5

    # Time-based exit
    time_based_exit: bool = True
    max_holding_hours: int = 4              # Keep current: 4 hour max hold

    # Position sizing
    use_risk_based_position: bool = False
    risk_per_trade_pct: float = 1.0
    max_leverage: float = 3.0

    # Account
    initial_equity: float = 100000.0


# =============================================================================
# CONFIG PRESETS
# =============================================================================

def get_scalp_config() -> StrategyConfig:
    """Single position, faster entries, tight risk. Good for trending opens."""
    return StrategyConfig(
        max_positions=1,
        base_grid_pct=0.08,
        use_volatility_grid=True,
        atr_multiplier=1.2,
        max_anchor_distance_grids=2,
        stop_loss_pct=0.12,
        take_profit_pct=0.18,
        trailing_stop_pct=0.07,
        trailing_activation_pts=5.0,
        use_trailing_stop=True,
        max_loss_per_day_pct=1.0,
        trend_confirmation_bars=2,
        use_trend_reversal_exit=False,
        entry_rsi_bearish=55.0,
        entry_rsi_bullish=45.0,
        entry_rsi_sideways_short=70.0,
        entry_rsi_sideways_long=30.0,
    )


def get_grid_config() -> StrategyConfig:
    """Multiple positions, wider spacing, no trailing. Good for ranging markets."""
    return StrategyConfig(
        max_positions=3,
        base_grid_pct=0.12,
        use_volatility_grid=True,
        atr_multiplier=1.5,
        max_anchor_distance_grids=3,
        stop_loss_pct=0.40,
        take_profit_pct=0.25,
        trailing_stop_pct=0.0,
        use_trailing_stop=False,
        max_loss_per_day_pct=2.0,
        trend_confirmation_bars=3,
        use_trend_reversal_exit=False,
        entry_rsi_bearish=60.0,
        entry_rsi_bullish=40.0,
        entry_rsi_sideways_short=70.0,
        entry_rsi_sideways_long=30.0,
    )


# Preset registry
CONFIG_PRESETS = {
    'scalp': get_scalp_config,
    'grid': get_grid_config,
}