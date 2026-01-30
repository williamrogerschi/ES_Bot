# strategy.py
import asyncio
from collections import deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum

CENTRAL = ZoneInfo("America/Chicago")
UTC = ZoneInfo("UTC")


class TrendState(Enum):
    STRONG_BULLISH = "strong_bullish"
    MODERATE_BULLISH = "moderate_bullish"
    STRONG_BEARISH = "strong_bearish"
    MODERATE_BEARISH = "moderate_bearish"
    SIDEWAYS = "sideways"


@dataclass
class Position:
    side: str
    entry_price: float
    entry_time: datetime
    size: float
    stop_loss: float
    take_profit: float
    trailing_stop: float
    order_id: Optional[int] = None


@dataclass
class StrategyConfig:
    # Grid settings
    base_grid_pct: float = 0.10
    max_positions: int = 5
    use_volatility_grid: bool = True
    
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
    
    # Momentum
    momentum_length: int = 10
    
    # Risk management
    stop_loss_pct: float = 0.15
    take_profit_pct: float = 0.25
    use_trailing_stop: bool = True
    trailing_stop_pct: float = 0.07
    max_loss_per_day_pct: float = 2.0
    
    # Time-based exit
    time_based_exit: bool = True
    max_holding_hours: int = 48
    
    # Position sizing
    use_risk_based_position: bool = True
    risk_per_trade_pct: float = 1.0
    max_leverage: float = 3.0
    
    # Account
    initial_equity: float = 100000.0
    
    # Grid anchor settings
    lookback_for_anchor: int = 20


class Indicators:
    """Calculate all technical indicators from bar data."""
    
    @staticmethod
    def sma(closes: List[float], period: int) -> Optional[float]:
        if len(closes) < period:
            return None
        return sum(closes[-period:]) / period
    
    @staticmethod
    def ema(closes: List[float], period: int) -> Optional[float]:
        if len(closes) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema = closes[0]
        
        for price in closes[1:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    @staticmethod
    def atr(bars: List[Dict], period: int) -> Optional[float]:
        if len(bars) < period + 1:
            return None
        
        trs = []
        for i in range(1, len(bars)):
            high = bars[i]['high']
            low = bars[i]['low']
            prev_close = bars[i-1]['close']
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        
        return sum(trs[-period:]) / period
    
    @staticmethod
    def rsi(closes: List[float], period: int) -> Optional[float]:
        if len(closes) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i] - closes[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        if len(gains) < period:
            return None
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def macd(closes: List[float], fast: int, slow: int, signal: int) -> Optional[Dict]:
        if len(closes) < slow + signal:
            return None
        
        fast_ema = Indicators.ema(closes, fast)
        slow_ema = Indicators.ema(closes, slow)
        
        if fast_ema is None or slow_ema is None:
            return None
        
        macd_line = fast_ema - slow_ema
        
        macd_values = []
        for i in range(signal + slow, len(closes) + 1):
            subset = closes[:i]
            fe = Indicators.ema(subset, fast)
            se = Indicators.ema(subset, slow)
            if fe and se:
                macd_values.append(fe - se)
        
        if len(macd_values) < signal:
            return None
        
        signal_line = sum(macd_values[-signal:]) / signal
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    @staticmethod
    def momentum(closes: List[float], period: int) -> Optional[float]:
        if len(closes) < period + 1:
            return None
        return closes[-1] - closes[-period - 1]
    
    @staticmethod
    def swing_high(bars: List[Dict], lookback: int) -> Optional[float]:
        """Find highest high in lookback period."""
        if len(bars) < lookback:
            return None
        return max(b['high'] for b in list(bars)[-lookback:])
    
    @staticmethod
    def swing_low(bars: List[Dict], lookback: int) -> Optional[float]:
        """Find lowest low in lookback period."""
        if len(bars) < lookback:
            return None
        return min(b['low'] for b in list(bars)[-lookback:])


class GridStrategy:
    def __init__(self, broker, config: Optional[StrategyConfig] = None):
        self.broker = broker
        self.config = config or StrategyConfig()
        
        # Bar history
        max_bars = max(
            self.config.super_long_ma_length,
            self.config.macd_slow + self.config.macd_signal,
            self.config.atr_length,
            self.config.rsi_length,
            self.config.momentum_length,
            self.config.lookback_for_anchor
        ) + 50
        
        self.bars: deque = deque(maxlen=max_bars)
        
        # Position tracking
        self.positions: List[Position] = []
        self.in_trade: bool = False
        self.position_count: int = 0
        
        # Daily P&L tracking
        self.daily_pnl: float = 0.0
        self.last_reset_day: Optional[int] = None
        self.equity: float = self.config.initial_equity
        
        # Current state
        self.last_price: Optional[float] = None
        self.grid_levels: List[float] = []
        self.current_trend: TrendState = TrendState.SIDEWAYS
        self.previous_trend: TrendState = TrendState.SIDEWAYS
        
        # Grid anchor
        self.grid_anchor_price: Optional[float] = None
        self.grid_anchor_time: Optional[datetime] = None
        
        # Indicator cache
        self._indicators: Dict = {}
        
        print(f"Strategy initialized with config:")
        print(f"  Grid: {self.config.base_grid_pct}% base, ATR mult: {self.config.atr_multiplier}")
        print(f"  Max positions: {self.config.max_positions}")
        print(f"  SL: {self.config.stop_loss_pct}%, TP: {self.config.take_profit_pct}%")
        print(f"  Grid anchor lookback: {self.config.lookback_for_anchor} bars")
    
    def _get_closes(self) -> List[float]:
        return [b['close'] for b in self.bars]
    
    def _calculate_indicators(self) -> bool:
        """Calculate all indicators. Returns True if we have enough data."""
        closes = self._get_closes()
        bars_list = list(self.bars)
        
        if len(closes) < self.config.super_long_ma_length:
            return False
        
        self._indicators = {
            'short_ma': Indicators.sma(closes, self.config.short_ma_length),
            'long_ma': Indicators.sma(closes, self.config.long_ma_length),
            'super_long_ma': Indicators.sma(closes, self.config.super_long_ma_length),
            'atr': Indicators.atr(bars_list, self.config.atr_length),
            'rsi': Indicators.rsi(closes, self.config.rsi_length),
            'macd': Indicators.macd(closes, self.config.macd_fast, self.config.macd_slow, self.config.macd_signal),
            'momentum': Indicators.momentum(closes, self.config.momentum_length),
            'swing_high': Indicators.swing_high(bars_list, self.config.lookback_for_anchor),
            'swing_low': Indicators.swing_low(bars_list, self.config.lookback_for_anchor),
        }
        
        required = ['short_ma', 'long_ma', 'atr', 'rsi', 'macd', 'momentum']
        return all(self._indicators.get(k) is not None for k in required)
    
    def _determine_trend(self) -> TrendState:
        """Weighted scoring system for trend determination."""
        ind = self._indicators
        
        short_term_bullish = ind['short_ma'] > ind['long_ma']
        long_term_bullish = ind['long_ma'] > ind['super_long_ma'] if ind['super_long_ma'] else False
        macd_bullish = ind['macd']['macd'] > ind['macd']['signal'] and ind['macd']['macd'] > 0
        rsi_bullish = ind['rsi'] < self.config.rsi_oversold
        momentum_bullish = ind['momentum'] > 0
        
        short_term_bearish = ind['short_ma'] < ind['long_ma']
        long_term_bearish = ind['long_ma'] < ind['super_long_ma'] if ind['super_long_ma'] else False
        macd_bearish = ind['macd']['macd'] < ind['macd']['signal'] and ind['macd']['macd'] < 0
        rsi_bearish = ind['rsi'] > self.config.rsi_overbought
        momentum_bearish = ind['momentum'] < 0
        
        bullish_strength = (
            (20 if short_term_bullish else 0) +
            (30 if long_term_bullish else 0) +
            (20 if macd_bullish else 0) +
            (15 if rsi_bullish else 0) +
            (15 if momentum_bullish else 0)
        )
        
        bearish_strength = (
            (20 if short_term_bearish else 0) +
            (30 if long_term_bearish else 0) +
            (20 if macd_bearish else 0) +
            (15 if rsi_bearish else 0) +
            (15 if momentum_bearish else 0)
        )
        
        if bullish_strength >= 70:
            return TrendState.STRONG_BULLISH
        elif bullish_strength >= 40:
            return TrendState.MODERATE_BULLISH
        elif bearish_strength >= 70:
            return TrendState.STRONG_BEARISH
        elif bearish_strength >= 40:
            return TrendState.MODERATE_BEARISH
        else:
            return TrendState.SIDEWAYS
    
    def _calculate_grid_size(self) -> float:
        """Calculate grid size based on volatility."""
        if not self.config.use_volatility_grid:
            return self.config.base_grid_pct
        
        atr = self._indicators.get('atr')
        if atr is None or self.last_price is None:
            return self.config.base_grid_pct
        
        normalized_atr = (atr / self.last_price) * 100
        return max(self.config.base_grid_pct, normalized_atr * self.config.atr_multiplier)
    
    def _should_reset_grid_anchor(self) -> bool:
        """Determine if grid anchor should be reset."""
        if self.current_trend != self.previous_trend:
            return True
        
        if self.position_count == 0 and self.grid_anchor_price is not None:
            if self.last_price:
                distance_pct = abs(self.last_price - self.grid_anchor_price) / self.grid_anchor_price * 100
                if distance_pct > self.config.base_grid_pct * self.config.max_positions:
                    return True
        
        return False
    
    def _set_grid_anchor(self):
        """Set the grid anchor based on current trend."""
        trend = self.current_trend
        
        if trend in [TrendState.STRONG_BEARISH, TrendState.MODERATE_BEARISH]:
            self.grid_anchor_price = self._indicators.get('swing_high', self.last_price)
        elif trend in [TrendState.STRONG_BULLISH, TrendState.MODERATE_BULLISH]:
            self.grid_anchor_price = self._indicators.get('swing_low', self.last_price)
        else:
            self.grid_anchor_price = self.last_price
        
        self.grid_anchor_time = datetime.now(UTC)
        print(f"  🎯 Grid anchor set @ {self.grid_anchor_price:.2f} ({trend.value})")
    
    def _calculate_grid_levels(self) -> List[float]:
        """Calculate grid levels based on anchored price."""
        grid_size = self._calculate_grid_size()
        anchor = self.grid_anchor_price if self.grid_anchor_price else self.last_price
        
        levels = []
        trend = self.current_trend
        
        if trend in [TrendState.STRONG_BEARISH, TrendState.MODERATE_BEARISH]:
            for i in range(0, self.config.max_positions):
                level = anchor * (1 + (grid_size / 100 * i))
                levels.append(level)
        
        elif trend in [TrendState.STRONG_BULLISH, TrendState.MODERATE_BULLISH]:
            for i in range(0, self.config.max_positions):
                level = anchor * (1 - (grid_size / 100 * i))
                levels.append(level)
        
        else:
            half = self.config.max_positions // 2
            for i in range(0, half + 1):
                levels.append(anchor * (1 + (grid_size / 100 * i)))
            for i in range(1, half + 1):
                levels.append(anchor * (1 - (grid_size / 100 * i)))
        
        return sorted(levels)
    
    def _calculate_position_size(self) -> float:
        """Calculate position size based on risk management."""
        if not self.config.use_risk_based_position:
            return self.equity / self.config.max_positions
        
        risk_amount = self.equity * (self.config.risk_per_trade_pct / 100)
        potential_loss = self.last_price * (self.config.stop_loss_pct / 100)
        
        if potential_loss == 0:
            return 0
        
        calculated_size = risk_amount / potential_loss
        max_size = self.equity * self.config.max_leverage
        
        return min(calculated_size, max_size)
    
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit is exceeded."""
        max_loss = self.equity * (self.config.max_loss_per_day_pct / 100)
        return self.daily_pnl <= -max_loss
    
    def _check_time_based_exit(self, position: Position) -> bool:
        """Check if position should be exited due to time."""
        if not self.config.time_based_exit:
            return False
        
        now = datetime.now(UTC)
        hold_duration = now - position.entry_time
        max_hold = timedelta(hours=self.config.max_holding_hours)
        
        return hold_duration >= max_hold
    
    def _update_trailing_stop(self, position: Position, current_price: float) -> float:
        """Update trailing stop level."""
        if position.side == 'long':
            new_stop = current_price * (1 - self.config.trailing_stop_pct / 100)
            return max(position.trailing_stop, new_stop)
        else:
            new_stop = current_price * (1 + self.config.trailing_stop_pct / 100)
            return min(position.trailing_stop, new_stop) if position.trailing_stop > 0 else new_stop
    
    async def _enter_long(self, price: float, reason: str):
        """Enter a long position."""
        if self.position_count >= self.config.max_positions:
            print(f"  Max positions reached, skipping long entry")
            return
        
        size = self._calculate_position_size()
        stop_loss = price * (1 - self.config.stop_loss_pct / 100)
        take_profit = price * (1 + self.config.take_profit_pct / 100)
        trailing_stop = price * (1 - self.config.trailing_stop_pct / 100)
        
        position = Position(
            side='long',
            entry_price=price,
            entry_time=datetime.now(UTC),
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=trailing_stop
        )
        
        trade = await self.broker.place_limit_order('BUY', 1, price)
        if trade:
            position.order_id = trade.order.orderId
        
        self.positions.append(position)
        self.position_count += 1
        self.in_trade = True
        
        print(f"  ⬆️ LONG ENTRY @ {price:.2f} | Size: {size:.2f} | SL: {stop_loss:.2f} | TP: {take_profit:.2f}")
        print(f"     Reason: {reason}")
    
    async def _enter_short(self, price: float, reason: str):
        """Enter a short position."""
        if self.position_count >= self.config.max_positions:
            print(f"  Max positions reached, skipping short entry")
            return
        
        size = self._calculate_position_size()
        stop_loss = price * (1 + self.config.stop_loss_pct / 100)
        take_profit = price * (1 - self.config.take_profit_pct / 100)
        trailing_stop = price * (1 + self.config.trailing_stop_pct / 100)
        
        position = Position(
            side='short',
            entry_price=price,
            entry_time=datetime.now(UTC),
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=trailing_stop
        )
        
        trade = await self.broker.place_limit_order('SELL', 1, price)
        if trade:
            position.order_id = trade.order.orderId
        
        self.positions.append(position)
        self.position_count += 1
        self.in_trade = True
        
        print(f"  ⬇️ SHORT ENTRY @ {price:.2f} | Size: {size:.2f} | SL: {stop_loss:.2f} | TP: {take_profit:.2f}")
        print(f"     Reason: {reason}")
    
    async def _close_position(self, position: Position, price: float, reason: str):
        """Close a position."""
        pnl = 0.0
        if position.side == 'long':
            pnl = (price - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - price) * position.size
        
        action = 'SELL' if position.side == 'long' else 'BUY'
        await self.broker.place_market_order(action, 1)
        
        self.daily_pnl += pnl
        self.equity += pnl
        self.positions.remove(position)
        self.position_count = max(0, self.position_count - 1)
        
        if len(self.positions) == 0:
            self.in_trade = False
        
        emoji = "✅" if pnl >= 0 else "❌"
        print(f"  {emoji} CLOSE {position.side.upper()} @ {price:.2f} | P&L: {pnl:+.2f} | {reason}")
        print(f"     Daily P&L: {self.daily_pnl:+.2f} | Equity: {self.equity:.2f}")
    
    async def _check_exits(self, bar: Dict):
        """Check all positions for exit conditions."""
        current_price = bar['close']
        high = bar['high']
        low = bar['low']
        
        positions_to_close = []
        
        for position in self.positions:
            exit_reason = None
            exit_price = current_price
            
            if self.config.use_trailing_stop:
                position.trailing_stop = self._update_trailing_stop(position, current_price)
            
            if position.side == 'long':
                if low <= position.stop_loss:
                    exit_reason = "Stop Loss"
                    exit_price = position.stop_loss
                elif high >= position.take_profit:
                    exit_reason = "Take Profit"
                    exit_price = position.take_profit
                elif self.config.use_trailing_stop and low <= position.trailing_stop:
                    exit_reason = "Trailing Stop"
                    exit_price = position.trailing_stop
                elif self.current_trend in [TrendState.STRONG_BEARISH, TrendState.MODERATE_BEARISH]:
                    exit_reason = "Trend Reversal"
                    exit_price = current_price
            
            else:
                if high >= position.stop_loss:
                    exit_reason = "Stop Loss"
                    exit_price = position.stop_loss
                elif low <= position.take_profit:
                    exit_reason = "Take Profit"
                    exit_price = position.take_profit
                elif self.config.use_trailing_stop and high >= position.trailing_stop:
                    exit_reason = "Trailing Stop"
                    exit_price = position.trailing_stop
                elif self.current_trend in [TrendState.STRONG_BULLISH, TrendState.MODERATE_BULLISH]:
                    exit_reason = "Trend Reversal"
                    exit_price = current_price
            
            if exit_reason is None and self._check_time_based_exit(position):
                exit_reason = "Time-Based Exit"
                exit_price = current_price
            
            if exit_reason:
                positions_to_close.append((position, exit_price, exit_reason))
        
        for position, price, reason in positions_to_close:
            await self._close_position(position, price, reason)
    
    async def _check_entries(self, bar: Dict):
        """Check for new entry opportunities."""
        current_price = bar['close']
        high = bar['high']
        low = bar['low']
        open_price = bar['open']
        rsi = self._indicators.get('rsi', 50)
        
        trend = self.current_trend
        
        # In bearish trend, look for short entries
        if trend in [TrendState.STRONG_BEARISH, TrendState.MODERATE_BEARISH] and rsi > 60: #change back to 60
            for level in self.grid_levels:
                # Check if bar crossed UP through the level (for shorting resistance)
                crossed_up = open_price < level <= high
                
                if crossed_up and self.position_count < self.config.max_positions:
                    if not any(abs(p.entry_price - level) < level * 0.001 for p in self.positions):
                        await self._enter_short(level, f"Grid Short ({trend.value}, RSI: {rsi:.1f})")
                        break
        
        # In bullish trend, look for long entries
        elif trend in [TrendState.STRONG_BULLISH, TrendState.MODERATE_BULLISH] and rsi < 40: #change back to 40
            for level in self.grid_levels:
                # Check if bar crossed DOWN through the level (for buying support)
                crossed_down = open_price > level >= low
                
                if crossed_down and self.position_count < self.config.max_positions:
                    if not any(abs(p.entry_price - level) < level * 0.001 for p in self.positions):
                        await self._enter_long(level, f"Grid Long ({trend.value}, RSI: {rsi:.1f})")
                        break
        
        # Sideways market
        elif trend == TrendState.SIDEWAYS:
            if rsi > 70:
                for level in self.grid_levels:
                    crossed_up = open_price < level <= high
                    if crossed_up:
                        if not any(abs(p.entry_price - level) < level * 0.001 for p in self.positions):
                            await self._enter_short(level, f"Sideways Short (RSI: {rsi:.1f})")
                            break
            
            elif rsi < 30:
                for level in self.grid_levels:
                    crossed_down = open_price > level >= low
                    if crossed_down:
                        if not any(abs(p.entry_price - level) < level * 0.001 for p in self.positions):
                            await self._enter_long(level, f"Sideways Long (RSI: {rsi:.1f})")
                            break
    
    async def on_new_bar(self, bar: Dict):
        """Process a new 1-minute bar."""
        self.bars.append(bar)
        self.last_price = bar['close']
        
        # Reset daily P&L at start of new day
        current_day = bar['time'].day
        if self.last_reset_day != current_day:
            if self.last_reset_day is not None:
                print(f"\n📅 New trading day. Previous day P&L: {self.daily_pnl:+.2f}")
            self.daily_pnl = 0.0
            self.last_reset_day = current_day
        
        # Display bar info
        local_time = bar['time'].astimezone(CENTRAL)
        time_str = local_time.strftime('%Y-%m-%d %H:%M')
        print(f"\n[{time_str}] O:{bar['open']:.2f} H:{bar['high']:.2f} L:{bar['low']:.2f} C:{bar['close']:.2f} V:{bar['volume']}")
        
        # Calculate indicators
        if not self._calculate_indicators():
            bars_needed = self.config.super_long_ma_length - len(self.bars)
            print(f"  ⏳ Warming up... need {bars_needed} more bars")
            return
        
        # Store previous trend before updating
        self.previous_trend = self.current_trend
        
        # Determine NEW trend
        self.current_trend = self._determine_trend()
        
        # ===== CHECK ENTRIES WITH OLD GRID FIRST =====
        if self.grid_levels and self.grid_anchor_price:
            await self._check_entries(bar)
        
        # ===== NOW reset grid if needed =====
        if self._should_reset_grid_anchor() or self.grid_anchor_price is None:
            self._set_grid_anchor()
        
        # Calculate grid levels from anchor
        self.grid_levels = self._calculate_grid_levels()
        grid_size = self._calculate_grid_size()
        
        # Display status
        ind = self._indicators
        print(f"  📊 Trend: {self.current_trend.value} | Grid: {grid_size:.3f}%")
        print(f"     RSI: {ind['rsi']:.1f} | MACD: {ind['macd']['macd']:.2f} | ATR: {ind['atr']:.2f}")
        print(f"     MA: {ind['short_ma']:.2f} / {ind['long_ma']:.2f} / {ind['super_long_ma']:.2f}")
        print(f"     Anchor: {self.grid_anchor_price:.2f} | Positions: {self.position_count}/{self.config.max_positions} | Daily P&L: {self.daily_pnl:+.2f}")
        
        # Check daily loss limit
        if self._check_daily_loss_limit():
            print(f"  🛑 MAX DAILY LOSS REACHED - Closing all positions")
            for position in list(self.positions):
                await self._close_position(position, bar['close'], "Max Daily Loss")
            return
        
        # Check exits
        await self._check_exits(bar)
        
        # ===== CHECK ENTRIES AGAIN WITH NEW GRID =====
        await self._check_entries(bar)
        
        # Display grid levels relative to current price
        if self.grid_levels:
            above = [f"{l:.2f}" for l in self.grid_levels if l > self.last_price][:3]
            below = [f"{l:.2f}" for l in sorted(self.grid_levels, reverse=True) if l < self.last_price][:3]
            print(f"     Grid ↑: {above}  Grid ↓: {below}")