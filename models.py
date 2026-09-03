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


class MarketRegime(Enum):
    TRENDING_BULLISH = "trending_bullish"
    TRENDING_BEARISH = "trending_bearish"
    RANGING = "ranging"
    UNCERTAIN = "uncertain"


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
    entry_atr: float = 0.0  # ATR at fill time, used for ATR-based trailing


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
    entry_atr: float = 0.0  # ATR captured at order submission, used for ATR-based SL/TP


@dataclass
class StrategyConfig:
    # Instrument settings
    tick_size: float = 0.25

    # Entry mode
    use_grid_entry: bool = True

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

    # -------------------------------------------------------------------------
    # RSI ENTRY THRESHOLDS — restored to original Pine Script logic
    #
    # Core philosophy: mean reversion WITHIN trend, not chasing breakdowns.
    #
    # SHORTS (both bearish states): RSI > 60
    #   Wait for price to bounce back toward overbought in a downtrend,
    #   then fade the exhaustion. Don't short the breakdown — short the rally.
    #
    # LONGS (both bullish states): RSI < 40
    #   Wait for a genuine oversold dip in an uptrend, then buy the bounce.
    #   Don't buy breakouts — buy pullbacks.
    #
    # SIDEWAYS: RSI > 70 short, RSI < 30 long (extreme mean reversion only)
    #
    # RANGING MODE (detected by regime): RSI > 70 short, RSI < 30 long
    #   Uses session high/low as range boundaries.
    # -------------------------------------------------------------------------
    entry_rsi_strong_bearish: float = 60.0   # strong_bearish shorts
    entry_rsi_bearish: float = 60.0          # moderate_bearish shorts
    entry_rsi_bullish: float = 40.0          # all bullish longs (rsi < this)
    entry_rsi_sideways_short: float = 70.0
    entry_rsi_sideways_long: float = 30.0
    use_pullback_entry: bool = False
    rsi_pullback_dip_level: float = 38.0
    # -------------------------------------------------------------------------
    # min_atr_for_pullback_entry — lowered 2.5 -> 1.0 on 2026-08-17.
    # August logs showed median session ATR ~1.5, with the 2.5 gate blocking
    # ~92% of bars and killing 11 of 12 legitimate RSI-turn setups on 8/17
    # before they could even become an order. Backtest replay of those 12
    # setups (filled at signal price) came back 7W/5L, net +13.03 pts.
    # 1.0 sits below the weakest of that day's setups (1.16 ATR) with some
    # room, while still gating out truly dead bars (session floor was 0.54).
    # Revisit if this lets through too much noise once live data comes in.
    # -------------------------------------------------------------------------
    min_atr_for_pullback_entry: float = 1.0
    # -------------------------------------------------------------------------
    # pullback_entry_offset_pts — added 2026-08-18.
    # Pullback entries were submitted as a limit at the exact signal price,
    # which only fills if price ticks back toward the signal bar first. On
    # trending days (8/17, 8/18) that never happened and every signal timed
    # out unfilled. Offsetting the limit through the market makes it
    # marketable — fills near signal price instead of waiting for a
    # retracement that a strong trend may not give.
    # -------------------------------------------------------------------------
    pullback_entry_offset_pts: float = 1.5

    # MA settings
    short_ma_length: int = 20
    long_ma_length: int = 50
    super_long_ma_length: int = 200

    # MACD settings
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Trend confirmation
    trend_confirmation_bars: int = 3

    # Risk management - points-based
    stop_loss_pts: float = 8.0
    take_profit_pts: float = 12.0
    trailing_activation_pts: float = 7.5  # static trail activation — guarantees meaningful profit lock-in
    trailing_distance_pts: float = 1.5  # static trail distance — tight enough to lock in ~4.5pts min

    # Risk management - pct-based
    stop_loss_pct: float = 0.117
    take_profit_pct: float = 0.175
    use_trailing_stop: bool = True
    trailing_stop_pct: float = 0.073

    max_loss_per_day_pct: float = 2.0

    # Trend reversal exit
    use_trend_reversal_exit: bool = False
    trend_cooldown_minutes: int = 5

    # Time-based exit
    time_based_exit: bool = True
    max_holding_hours: int = 4

    # -------------------------------------------------------------------------
    # EOD hard close — added 2026-08-20. Independent of max_holding_hours:
    # a trade can sit well under the holding-hours cap and still be open past
    # market close if it's just grinding sideways. This force-flattens any
    # open position the instant a bar crosses the close time, no exceptions.
    # -------------------------------------------------------------------------
    use_eod_close: bool = False
    eod_close_hour_et: int = 16     # 4:00 PM ET (RTH close)
    eod_close_minute_et: int = 0

    # Position sizing
    use_risk_based_position: bool = False
    risk_per_trade_pct: float = 1.0
    max_leverage: float = 3.0
    contracts_per_trade: int = 1

    # ATR-based position sizing
    atr_high_volatility_threshold: float = 4.5
    contracts_per_trade_high_vol: int = 5

    # ATR-based R:R — when enabled, SL/TP/trail scale with entry ATR
    use_atr_rr: bool = False
    stop_loss_atr_mult: float = 2.0
    take_profit_atr_mult: float = 3.0
    trailing_activation_atr_mult: float = 1.25
    trailing_distance_atr_mult: float = 0.75
    min_stop_loss_pts: float = 8.0   # SL floor — prevents stop shrinking below viable level in low ATR
    # TP floor — added 2026-08-18. Without this, low-ATR sessions hit the SL
    # floor above but let TP shrink freely with ATR, flipping the intended
    # stop_loss_atr_mult:take_profit_atr_mult ratio backwards (observed as
    # low as 1:0.4 reward:risk on 8/18 pullback trades). 0.0 = no floor
    # (default, unaffected unless a preset sets one).
    min_take_profit_pts: float = 0.0

    atr_no_trade_threshold: float = 3.0  # don't enter if ATR below this (market too compressed)

    # -------------------------------------------------------------------------
    # MARKET REGIME DETECTION
    #
    # Classifies the market as TRENDING or RANGING each bar using 4 signals:
    #   1. Trend flip count     — how many times 1m trend changed in last N bars
    #   2. MACD zero-crossings  — how many times MACD crossed zero (oscillating = ranging)
    #   3. ATR compressed       — ATR below threshold = volatility dried up
    #   4. Trend instability    — current trend != confirmed trend
    #
    # Regime = RANGING if 2+ signals fire. TRENDING otherwise.
    #
    # In RANGING mode, entries switch to pure mean reversion:
    #   Short: RSI > 70 AND price in top % of range (near session high)
    #   Long:  RSI < 30 AND price in bottom % of range (near session low)
    # -------------------------------------------------------------------------
    use_regime_detection: bool = True
    regime_lookback_bars: int = 20           # bars for flip/cross counting
    regime_flip_threshold: int = 4           # trend direction flips in lookback = ranging signal

    regime_macd_cross_threshold: int = 2     # MACD zero-crosses in lookback = ranging signal
    regime_atr_threshold: float = 3.5        # ATR below this = compressed = ranging signal
    regime_ranging_rsi_short: float = 70.0   # RSI threshold for ranging shorts (overbought)
    regime_ranging_rsi_long: float = 35.0    # RSI threshold for ranging longs (oversold)
    regime_range_pct_short: float = 0.70     # price must be in top 30% of range to short
    regime_range_pct_long: float = 0.30      # price must be in bottom 30% of range to long
    regime_range_lookback: int = 30          # bars to define the current range
    # -------------------------------------------------------------------------
    # Persistent-trend filter — added 2026-09-03. regime_lookback_bars=20 is
    # short enough that a genuinely sustained directional run (seen live:
    # 12+ consecutive bullish bars, ~18+ min, RSI 50-90 the whole way) can
    # stay locked on RANGING the entire time, since the 5 regime signals only
    # look at the recent short window. That let a ranging-mode mean-reversion
    # SHORT fire directly against real, ongoing buying pressure. This filter
    # is independent of the regime label itself: if enough of the last N raw
    # trend bars are strongly one-directional, block the opposite-direction
    # ranging entry for that bar, regardless of what regime says.
    # Note: an earlier raw-trend veto in ranging mode was removed 8/14 for
    # blocking far more good trades than bad (193 blocks vs 5 real ones) —
    # that version reacted to near-single-bar noise. This one only fires on
    # a genuinely sustained run (10 of the last 15 bars), which is a
    # different, narrower condition — but watch for the same over-blocking
    # failure mode if it starts suppressing too many entries.
    # -------------------------------------------------------------------------
    use_persistent_trend_filter: bool = False
    persistent_trend_lookback: int = 15
    # Threshold validated against the 25 August pattern trades: at 14, the
    # 12 blocked trades were net -9.75 pts (a losing subset) while the 13
    # allowed through went 11W/2L for +60.75 pts — better than the ungated
    # baseline (+51.00 over all 25). Lower thresholds (10-13) blocked a much
    # larger share of genuine winners along with the losers; see chat for
    # the full threshold sweep.
    persistent_trend_threshold: int = 14
    use_grid_stop: bool = False
    grid_stop_buffer_pts: float = 6.0

    # Stop-limit offset (legacy — SL orders now use stop-market)
    stop_limit_offset_pts: float = 4.0

    # Trend-following entry (scalp_aggressive only)
    use_trend_follow_entry: bool = False
    trend_follow_rsi_long: float = 45.0
    trend_follow_rsi_short: float = 55.0
    trend_follow_allow_moderate: bool = False
    post_exit_cooldown_bars: int = 2

    # Session filter
    use_session_filter: bool = False
    session_start_hour: int = 9
    session_start_minute: int = 30
    session_end_hour: int = 12
    session_end_minute: int = 0
    use_5m_filter: bool = False
    use_volume_filter: bool = False
    volume_spike_multiplier: float = 1.5
    volume_lookback: int = 20

    # Session low short filter
    # Blocks shorts when price is too far above session low
    use_session_low_short_filter: bool = False
    session_low_short_buffer: float = 10.0
    session_low_short_hours: float = 2.0

    # Session high long filter (mirrors session low short filter)
    # Blocks longs when price is too close to session high
    use_session_high_long_filter: bool = False
    session_high_long_buffer: float = 10.0
    session_high_long_hours: float = 2.0

    # Account
    initial_equity: float = 100000.0


# =============================================================================
# CONFIG PRESETS
# =============================================================================

def get_scalp_config() -> StrategyConfig:
    return StrategyConfig(
        use_grid_entry=False,
        max_positions=1,
        base_grid_pct=0.08,
        use_volatility_grid=True,
        atr_multiplier=1.2,
        max_anchor_distance_grids=2,
        stop_loss_pct=0.12,
        take_profit_pct=0.18,
        trailing_stop_pct=0.07,
        trailing_activation_pts=7.5,
        trailing_distance_pts=1.5,
        use_trailing_stop=True,
        max_loss_per_day_pct=100.0,
        trend_confirmation_bars=2,
        use_trend_reversal_exit=False,
        entry_rsi_strong_bearish=60.0,
        entry_rsi_bearish=60.0,
        entry_rsi_bullish=40.0,
        entry_rsi_sideways_short=70.0,
        entry_rsi_sideways_long=30.0,
        contracts_per_trade=10,
        atr_high_volatility_threshold=4.5,
        contracts_per_trade_high_vol=5,
        use_atr_rr=True,
        stop_loss_atr_mult=2.0,
        take_profit_atr_mult=3.0,
        trailing_activation_atr_mult=1.25,
        trailing_distance_atr_mult=0.75,
        min_stop_loss_pts=8.0,
        regime_lookback_bars=20,
        use_regime_detection=True,
        regime_ranging_rsi_short=70.0,
        regime_ranging_rsi_long=35.0,
        use_session_filter=True,
        session_start_hour=8,
        session_start_minute=45,
        session_end_hour=14,
        session_end_minute=30,
        use_session_high_long_filter=True,
        session_high_long_buffer=10.0,
        session_high_long_hours=2.0,
        use_session_low_short_filter=True,
        session_low_short_buffer=10.0,
        session_low_short_hours=2.0,
        use_persistent_trend_filter=True,  # added 2026-09-03, see field comment
    )


def get_pullback_config() -> StrategyConfig:
    """No directional bias, both longs and shorts. Waits for a countertrend
    RSI dip/bounce to fail (turn back toward the trend) before entering,
    rather than trend-following the breakout blindly.

    Backtested against April-July logs: profitable in 3 of 4 months, net
    +$67,842.50 over 361 trades. See PULLBACK_STRATEGY_SPEC.md for the full
    evidence. Not yet validated out-of-sample — shadow-log before trusting
    this with real conviction.
    """
    return StrategyConfig(
        use_grid_entry=False,
        use_pullback_entry=True,
        max_positions=1,
        rsi_pullback_dip_level=38.0,
        min_atr_for_pullback_entry=1.0,  # lowered from 2.5 on 2026-08-17, see note above
        # -------------------------------------------------------------------
        # SL/TP — switched from ATR-scaled to plain static on 2026-08-19.
        # At recent ATR (median ~1.5-2.7), 1.5x/2.0x ATR always landed below
        # the SL/TP floors anyway, so the floors were doing 100% of the work
        # and the multipliers were dead weight — two mechanisms, only one
        # ever active, easy to get out of sync (which is exactly what
        # happened: TP floor got added but a stale file kept using the ATR
        # formula). Static values remove the ambiguity entirely.
        # -------------------------------------------------------------------
        use_atr_rr=False,
        stop_loss_pts=8.0,
        take_profit_pts=10.75,  # 8.0 * (2.0/1.5), rounded to nearest ES tick — 1.33:1 R:R
        use_trailing_stop=False,
        use_trend_reversal_exit=False,
        contracts_per_trade=1,
        contracts_per_trade_high_vol=1,  # 2026-08-18: pinned to 1 contract always — clean per-trade
                                          # point data for gauging MES sizing later (multiply by 10)
        post_exit_cooldown_bars=2,
        max_loss_per_day_pct=100.0,  # daily loss limit removed 2026-08-18 — paper trading, want losing trades to play out
        use_eod_close=True,  # force-flatten any open position at 4:00 PM ET, added 2026-08-20
    )


def get_grid_config() -> StrategyConfig:
    return StrategyConfig(
        use_grid_entry=True,
        max_positions=3,
        base_grid_pct=0.12,
        use_volatility_grid=True,
        atr_multiplier=1.5,
        max_anchor_distance_grids=3,
        take_profit_pts=12.0,
        use_trailing_stop=False,
        max_loss_per_day_pct=2.0,
        trend_confirmation_bars=3,
        use_trend_reversal_exit=False,
        entry_rsi_bearish=60.0,
        entry_rsi_bullish=40.0,
        entry_rsi_sideways_short=70.0,
        entry_rsi_sideways_long=30.0,
        contracts_per_trade=3,
        use_grid_stop=True,
        grid_stop_buffer_pts=6.0,
        atr_high_volatility_threshold=4.5,
        contracts_per_trade_high_vol=5,
    )


def get_scalp_robust_config() -> StrategyConfig:
    return StrategyConfig(
        use_grid_entry=False,
        max_positions=1,
        base_grid_pct=0.08,
        use_volatility_grid=True,
        atr_multiplier=1.2,
        max_anchor_distance_grids=2,
        stop_loss_pct=0.12,
        take_profit_pct=0.18,
        trailing_stop_pct=0.07,
        trailing_activation_pts=7.5,
        trailing_distance_pts=1.5,
        use_trailing_stop=True,
        max_loss_per_day_pct=100.0,
        trend_confirmation_bars=2,
        use_trend_reversal_exit=False,
        entry_rsi_strong_bearish=60.0,
        entry_rsi_bearish=60.0,
        entry_rsi_bullish=40.0,
        entry_rsi_sideways_short=70.0,
        entry_rsi_sideways_long=30.0,
        contracts_per_trade=10,
        atr_high_volatility_threshold=4.5,
        contracts_per_trade_high_vol=5,
        use_atr_rr=True,
        stop_loss_atr_mult=2.0,
        take_profit_atr_mult=3.0,
        trailing_activation_atr_mult=1.25,
        trailing_distance_atr_mult=0.75,
        min_stop_loss_pts=8.0,
        use_regime_detection=True,
        regime_ranging_rsi_short=70.0,
        regime_ranging_rsi_long=35.0,
        use_session_filter=True,
        session_start_hour=8,
        session_start_minute=45,
        session_end_hour=12,
        session_end_minute=0,
        use_5m_filter=True,
        use_volume_filter=False,
        volume_spike_multiplier=1.2,
        volume_lookback=50,
        use_session_low_short_filter=True,
        session_low_short_buffer=10.0,
        session_low_short_hours=2.0,
        use_session_high_long_filter=True,
        session_high_long_buffer=10.0,
        session_high_long_hours=2.0,
        use_persistent_trend_filter=True,  # added 2026-09-03, see field comment
    )


CONFIG_PRESETS = {
    'scalp': get_scalp_config,
    'scalp_robust': get_scalp_robust_config,
    'grid': get_grid_config,
    'pullback': get_pullback_config,
}