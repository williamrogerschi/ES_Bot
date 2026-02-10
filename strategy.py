"""
ES Futures Grid Trading Strategy
Main strategy logic - imports models and indicators
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from models import TrendState, Position, StrategyConfig, PendingOrder
from indicators import Indicators

UTC = ZoneInfo("UTC")
CENTRAL = ZoneInfo("America/Chicago")


class GridStrategy:
    def __init__(self, broker, config: StrategyConfig = None):
        self.broker = broker
        self.config = config or StrategyConfig()
        
        # Price data
        self.bars: List[Dict] = []
        self.last_price: float = 0.0
        
        # Indicators
        self.indicators = Indicators(self.config)
        
        # Trend tracking
        self.current_trend = TrendState.SIDEWAYS
        self.previous_trend = TrendState.SIDEWAYS
        self.confirmed_trend = TrendState.SIDEWAYS
        self.trend_history: List[TrendState] = []
        
        # Grid state
        self.grid_anchor_price: Optional[float] = None
        self.grid_anchor_time: Optional[datetime] = None
        self.grid_levels: List[float] = []
        
        # Position tracking
        self.positions: List[Position] = []
        self.position_count: int = 0
        
        # PENDING ORDER TRACKING - orders submitted but not yet filled
        self.pending_orders: Dict[int, PendingOrder] = {}  # order_id -> PendingOrder
        
        # P&L tracking
        self.equity = self.config.initial_equity
        self.daily_pnl: float = 0.0
        self.last_reset_day: Optional[int] = None
    
    # =========================================================================
    # TICK ROUNDING
    # =========================================================================
    
    def _round_to_tick(self, price: float) -> float:
        """Round price to valid tick increment."""
        return round(price / self.config.tick_size) * self.config.tick_size
    
    # =========================================================================
    # TREND DETERMINATION
    # =========================================================================
    
    def _determine_trend(self) -> TrendState:
        """Determine current trend using weighted scoring.
        
        RSI is NOT used here — it's only for entry timing.
        Trend is based on: MAs (50pts) + MACD (25pts) + Momentum (25pts)
        """
        ind = self.indicators.cache
        
        bullish_score = 0
        bearish_score = 0
        
        # MA alignment (50 points total)
        if ind['short_ma'] > ind['long_ma']:
            bullish_score += 20
        else:
            bearish_score += 20
        
        if ind['long_ma'] > ind['super_long_ma']:
            bullish_score += 30
        else:
            bearish_score += 30
        
        # MACD (25 points)
        macd = ind['macd']
        if macd['macd'] > macd['signal'] and macd['macd'] > 0:
            bullish_score += 25
        elif macd['macd'] < macd['signal'] and macd['macd'] < 0:
            bearish_score += 25
        
        # Momentum (25 points)
        if ind['momentum'] > 0:
            bullish_score += 25
        else:
            bearish_score += 25
        
        # Determine trend state
        if bullish_score >= 70:
            return TrendState.STRONG_BULLISH
        elif bullish_score >= 40:
            return TrendState.MODERATE_BULLISH
        elif bearish_score >= 70:
            return TrendState.STRONG_BEARISH
        elif bearish_score >= 40:
            return TrendState.MODERATE_BEARISH
        else:
            return TrendState.SIDEWAYS
    
    def _get_confirmed_trend(self) -> TrendState:
        """Only change trend after N consecutive bars agree (ES-specific)."""
        self.trend_history.append(self.current_trend)
        
        # Keep only last N readings
        if len(self.trend_history) > self.config.trend_confirmation_bars:
            self.trend_history.pop(0)
        
        # Need full history before confirming changes
        if len(self.trend_history) < self.config.trend_confirmation_bars:
            return self.confirmed_trend
        
        # Check if all recent readings agree
        if all(t == self.trend_history[0] for t in self.trend_history):
            self.confirmed_trend = self.trend_history[0]
        
        return self.confirmed_trend
    
    # =========================================================================
    # GRID MANAGEMENT
    # =========================================================================
    
    def _calculate_grid_size(self) -> float:
        """Calculate grid size, optionally adjusted for volatility."""
        base = self.config.base_grid_pct
        
        if self.config.use_volatility_grid and 'atr' in self.indicators.cache:
            atr = self.indicators.cache['atr']
            atr_pct = (atr / self.last_price) * 100
            return max(base, atr_pct * self.config.atr_multiplier)
        
        return base
    
    def _should_reset_grid_anchor(self) -> bool:
        """Determine if grid anchor should be reset."""
        # Reset if confirmed trend changed
        if self.confirmed_trend != self.previous_trend:
            return True
        
        # Reset if no positions and anchor is stale (> 30 min)
        if self.position_count == 0 and self.grid_anchor_time:
            age = datetime.now(UTC) - self.grid_anchor_time
            if age > timedelta(minutes=30):
                return True
        
        return False
    
    def _set_grid_anchor(self):
        """Set the grid anchor based on confirmed trend with distance cap."""
        trend = self.confirmed_trend
        grid_size = self._calculate_grid_size()
        max_distance = self.last_price * (grid_size / 100) * self.config.max_anchor_distance_grids
        
        if trend in [TrendState.STRONG_BEARISH, TrendState.MODERATE_BEARISH]:
            # Anchor at resistance (swing high) for shorts
            swing = self.indicators.cache.get('swing_high', self.last_price)
            if swing > self.last_price + max_distance:
                self.grid_anchor_price = self.last_price + max_distance
            else:
                self.grid_anchor_price = swing
                
        elif trend in [TrendState.STRONG_BULLISH, TrendState.MODERATE_BULLISH]:
            # Anchor at support (swing low) for longs
            swing = self.indicators.cache.get('swing_low', self.last_price)
            if swing < self.last_price - max_distance:
                self.grid_anchor_price = self.last_price - max_distance
            else:
                self.grid_anchor_price = swing
        else:
            # Sideways: anchor at current price
            self.grid_anchor_price = self.last_price
        
        # Round anchor to valid tick
        self.grid_anchor_price = self._round_to_tick(self.grid_anchor_price)
        
        self.grid_anchor_time = datetime.now(UTC)
        print(f"  🎯 Grid anchor set @ {self.grid_anchor_price:.2f} ({trend.value})")
    
    def _calculate_grid_levels(self) -> List[float]:
        """Calculate grid levels from anchor (all rounded to valid tick)."""
        if not self.grid_anchor_price:
            return []
        
        grid_size = self._calculate_grid_size()
        grid_step = self.last_price * (grid_size / 100)
        # Round step to tick
        grid_step = self._round_to_tick(grid_step)
        levels = []
        
        trend = self.confirmed_trend
        
        if trend in [TrendState.STRONG_BEARISH, TrendState.MODERATE_BEARISH]:
            # Levels at and above anchor for shorts
            for i in range(self.config.max_positions):
                level = self._round_to_tick(self.grid_anchor_price + (i * grid_step))
                levels.append(level)
                
        elif trend in [TrendState.STRONG_BULLISH, TrendState.MODERATE_BULLISH]:
            # Levels at and below anchor for longs
            for i in range(self.config.max_positions):
                level = self._round_to_tick(self.grid_anchor_price - (i * grid_step))
                levels.append(level)
        else:
            # Sideways: levels both directions
            for i in range(self.config.max_positions):
                levels.append(self._round_to_tick(self.grid_anchor_price + ((i + 1) * grid_step)))
                levels.append(self._round_to_tick(self.grid_anchor_price - ((i + 1) * grid_step)))
        
        return sorted(levels)
    
    # =========================================================================
    # POSITION SIZING
    # =========================================================================
    
    def _calculate_position_size(self, entry_price: float) -> float:
        """Calculate position size based on risk."""
        if self.config.use_risk_based_position:
            risk_amount = self.equity * (self.config.risk_per_trade_pct / 100)
            stop_distance = entry_price * (self.config.stop_loss_pct / 100)
            size = risk_amount / stop_distance
        else:
            size = 1.0
        
        # Cap by max leverage
        max_size = (self.equity * self.config.max_leverage) / entry_price
        return min(size, max_size)
    
    # =========================================================================
    # ENTRY LOGIC
    # =========================================================================
    
    async def _check_entries(self, bar: Dict):
        """Check for entry signals on grid levels."""
        # Count both filled positions AND pending orders toward max
        total_orders = self.position_count + len(self.pending_orders)
        if total_orders >= self.config.max_positions:
            return
        
        if not self.grid_levels:
            return
        
        trend = self.confirmed_trend
        rsi = self.indicators.cache.get('rsi', 50)
        
        open_price = bar['open']
        high = bar['high']
        low = bar['low']
        current_price = bar['close']
        
        # Check levels already in use (filled positions + pending orders)
        active_levels = {p.grid_level for p in self.positions}
        active_levels.update({p.grid_level for p in self.pending_orders.values()})
        
        # BEARISH: Look for shorts at resistance
        if trend in [TrendState.STRONG_BEARISH, TrendState.MODERATE_BEARISH]:
            if rsi > self.config.entry_rsi_bearish:
                for level in self.grid_levels:
                    if level in active_levels:
                        continue
                    
                    # Bar crossed up through level
                    crossed_up = open_price < level <= high
                    if crossed_up:
                        await self._enter_short(level, rsi, trend)
                        break
        
        # BULLISH: Look for longs at support
        elif trend in [TrendState.STRONG_BULLISH, TrendState.MODERATE_BULLISH]:
            if rsi < self.config.entry_rsi_bullish:
                for level in self.grid_levels:
                    if level in active_levels:
                        continue
                    
                    # Bar crossed down through level
                    crossed_down = open_price > level >= low
                    if crossed_down:
                        await self._enter_long(level, rsi, trend)
                        break
        
        # SIDEWAYS: Trade both directions with strict RSI
        elif trend == TrendState.SIDEWAYS:
            if rsi > self.config.entry_rsi_sideways_short:
                # Short at upper levels
                for level in self.grid_levels:
                    if level in active_levels or level <= current_price:
                        continue
                    
                    crossed_up = open_price < level <= high
                    if crossed_up:
                        await self._enter_short(level, rsi, trend)
                        break
            
            elif rsi < self.config.entry_rsi_sideways_long:
                # Long at lower levels
                for level in self.grid_levels:
                    if level in active_levels or level >= current_price:
                        continue
                    
                    crossed_down = open_price > level >= low
                    if crossed_down:
                        await self._enter_long(level, rsi, trend)
                        break
    
    async def _enter_long(self, level: float, rsi: float, trend: TrendState):
        """Submit a long entry order (position created only after fill)."""
        # Round to valid tick
        level = self._round_to_tick(level)
        size = self._calculate_position_size(level)
        
        stop_loss = self._round_to_tick(level * (1 - self.config.stop_loss_pct / 100))
        take_profit = self._round_to_tick(level * (1 + self.config.take_profit_pct / 100))
        trailing_stop = self._round_to_tick(level * (1 - self.config.trailing_stop_pct / 100)) if self.config.use_trailing_stop else None
        
        # Place order
        trade = await self.broker.place_limit_order('BUY', 1, level)
        order_id = trade.order.orderId
        
        # Track as PENDING - position created only after fill confirmed
        pending = PendingOrder(
            order_id=order_id,
            side='long',
            limit_price=level,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=trailing_stop,
            submit_time=datetime.now(UTC),
            grid_level=level
        )
        self.pending_orders[order_id] = pending
        
        reason = f"Grid Long ({trend.value}, RSI: {rsi:.1f})"
        print(f"  ⬆️ LONG ORDER @ {level:.2f} | Size: {size:.2f} | SL: {stop_loss:.2f} | TP: {take_profit:.2f}")
        print(f"     Reason: {reason}")
        print(f"     ⏳ Order {order_id} PENDING - awaiting fill confirmation")
    
    async def _enter_short(self, level: float, rsi: float, trend: TrendState):
        """Submit a short entry order (position created only after fill)."""
        # Round to valid tick
        level = self._round_to_tick(level)
        size = self._calculate_position_size(level)
        
        stop_loss = self._round_to_tick(level * (1 + self.config.stop_loss_pct / 100))
        take_profit = self._round_to_tick(level * (1 - self.config.take_profit_pct / 100))
        trailing_stop = self._round_to_tick(level * (1 + self.config.trailing_stop_pct / 100)) if self.config.use_trailing_stop else None
        
        # Place order
        trade = await self.broker.place_limit_order('SELL', 1, level)
        order_id = trade.order.orderId
                
        # Track as PENDING - position created only after fill confirmed
        pending = PendingOrder(
            order_id=order_id,
            side='short',
            limit_price=level,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop=trailing_stop,
            submit_time=datetime.now(UTC),
            grid_level=level
        )
        self.pending_orders[order_id] = pending
        
        reason = f"Grid Short ({trend.value}, RSI: {rsi:.1f})"
        print(f"  ⬇️ SHORT ORDER @ {level:.2f} | Size: {size:.2f} | SL: {stop_loss:.2f} | TP: {take_profit:.2f}")
        print(f"     Reason: {reason}")
        print(f"     ⏳ Order {order_id} PENDING - awaiting fill confirmation")
    
    # =========================================================================
    # PENDING ORDER MANAGEMENT
    # =========================================================================
    
    async def _check_pending_orders(self):
        """Check if any pending orders have been filled or cancelled."""
        if not self.pending_orders:
            return
        
        # Get all open orders from broker
        try:
            open_orders = self.broker.ib.openOrders()
            open_order_ids = {trade.order.orderId for trade in self.broker.ib.openTrades()}
        except:
            open_order_ids = set()
        
        # Check each pending order
        for order_id in list(self.pending_orders.keys()):
            pending = self.pending_orders[order_id]
            
            # Try to find the trade
            trade = None
            for t in self.broker.ib.trades():
                if t.order.orderId == order_id:
                    trade = t
                    break
            
            if trade is None:
                # Order not found - likely expired or cancelled
                print(f"  ⚠️ Order {order_id} not found - removing from pending")
                del self.pending_orders[order_id]
                continue
            
            # Check if filled
            if trade.orderStatus.status == 'Filled' and trade.fills:
                fill_price = trade.fills[-1].execution.price
                
                # Create actual position with FILL price
                position = Position(
                    side=pending.side,
                    entry_price=fill_price,  # Use actual fill price!
                    size=pending.size,
                    stop_loss=pending.stop_loss,
                    take_profit=pending.take_profit,
                    trailing_stop=pending.trailing_stop,
                    entry_time=datetime.now(UTC),
                    grid_level=pending.grid_level,
                    order_id=order_id
                )
                
                self.positions.append(position)
                self.position_count += 1
                del self.pending_orders[order_id]
                
                print(f"  ✅ FILL CONFIRMED: {pending.side.upper()} @ {fill_price:.2f} (order {order_id})")
                print(f"     Position created | SL: {pending.stop_loss:.2f} | TP: {pending.take_profit:.2f}")
            
            # Check if cancelled/expired
            elif trade.orderStatus.status in ['Cancelled', 'ApiCancelled', 'Inactive']:
                print(f"  ❌ Order {order_id} cancelled/expired - removing from pending")
                del self.pending_orders[order_id]
            
            # Still pending - check age
            else:
                age_seconds = (datetime.now(UTC) - pending.submit_time).total_seconds()
                if age_seconds > 120:  # 2 minutes timeout
                    print(f"  ⏰ Order {order_id} timed out after {age_seconds:.0f}s - cancelling")
                    try:
                        self.broker._ib.cancelOrder(trade.order)
                    except:
                        pass
                    del self.pending_orders[order_id]
    
    # =========================================================================
    # EXIT LOGIC
    # =========================================================================
    
    async def _check_exits(self, bar: Dict):
        """Check exit conditions for all positions."""
        current_price = bar['close']
        high = bar['high']
        low = bar['low']
        
        for position in list(self.positions):
            # Check stop loss
            if position.side == 'long' and low <= position.stop_loss:
                await self._close_position(position, position.stop_loss, "Stop Loss")
                continue
            elif position.side == 'short' and high >= position.stop_loss:
                await self._close_position(position, position.stop_loss, "Stop Loss")
                continue
            
            # Check take profit
            if position.side == 'long' and high >= position.take_profit:
                await self._close_position(position, position.take_profit, "Take Profit")
                continue
            elif position.side == 'short' and low <= position.take_profit:
                await self._close_position(position, position.take_profit, "Take Profit")
                continue
            
            # Update trailing stop (only if enabled)
            if self.config.use_trailing_stop and position.trailing_stop is not None:
                if position.side == 'long':
                    new_trailing = current_price * (1 - self.config.trailing_stop_pct / 100)
                    if new_trailing > position.trailing_stop:
                        position.trailing_stop = new_trailing
                    if low <= position.trailing_stop:
                        await self._close_position(position, position.trailing_stop, "Trailing Stop")
                        continue
                else:
                    new_trailing = current_price * (1 + self.config.trailing_stop_pct / 100)
                    if new_trailing < position.trailing_stop:
                        position.trailing_stop = new_trailing
                    if high >= position.trailing_stop:
                        await self._close_position(position, position.trailing_stop, "Trailing Stop")
                        continue
            
            # Trend reversal exit (only if enabled and past cooldown)
            if self.config.use_trend_reversal_exit:
                time_in_trade = (datetime.now(UTC) - position.entry_time).total_seconds() / 60
                if time_in_trade >= self.config.trend_cooldown_minutes:
                    if self._should_exit_on_trend_reversal(position):
                        await self._close_position(position, current_price, "Trend Reversal")
                        continue
            
            # Time-based exit
            if self.config.time_based_exit:
                holding_time = datetime.now(UTC) - position.entry_time
                if holding_time > timedelta(hours=self.config.max_holding_hours):
                    await self._close_position(position, current_price, "Time Exit")
                    continue
    
    def _should_exit_on_trend_reversal(self, position: Position) -> bool:
        """Check if position should exit due to trend reversal."""
        trend = self.confirmed_trend
        
        if position.side == 'long':
            return trend in [TrendState.STRONG_BEARISH, TrendState.MODERATE_BEARISH]
        else:
            return trend in [TrendState.STRONG_BULLISH, TrendState.MODERATE_BULLISH]
    
    async def _close_position(self, position: Position, trigger_price: float, reason: str):
        """Close a position and record P&L."""
        action = 'SELL' if position.side == 'long' else 'BUY'
        
        # Place close order and get actual fill price
        trade = await self.broker.place_market_order(action, 1)
        
        # Wait briefly for fill to register
        await asyncio.sleep(0.3)
        
        # Get actual fill price from trade object
        if trade and trade.fills:
            actual_exit = trade.fills[-1].execution.price
        else:
            # Fallback to trigger price if fill not available
            actual_exit = trigger_price
            print(f"  ⚠️ Fill price not available, using trigger: {trigger_price:.2f}")
        
        # Calculate P&L with actual fill price
        if position.side == 'long':
            pnl = (actual_exit - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - actual_exit) * position.size
        
        self.daily_pnl += pnl
        self.equity += pnl
        
        self.positions.remove(position)
        self.position_count -= 1
        
        print(f"  ❌ CLOSE {position.side.upper()} @ {actual_exit:.2f} (trigger: {trigger_price:.2f}) | P&L: {pnl:+.2f} | {reason}")
        print(f"     Daily P&L: {self.daily_pnl:+.2f} | Equity: {self.equity:.2f}")
    
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit has been hit."""
        max_loss = self.config.initial_equity * (self.config.max_loss_per_day_pct / 100)
        return self.daily_pnl <= -max_loss
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
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
        
        # ===== CHECK PENDING ORDERS FIRST =====
        await self._check_pending_orders()
        
        # Display bar info
        local_time = bar['time'].astimezone(CENTRAL)
        time_str = local_time.strftime('%Y-%m-%d %H:%M')
        print(f"\n[{time_str}] O:{bar['open']:.2f} H:{bar['high']:.2f} L:{bar['low']:.2f} C:{bar['close']:.2f} V:{bar['volume']}")
        
        # Calculate indicators
        if not self.indicators.calculate_all(self.bars):
            bars_needed = self.config.super_long_ma_length - len(self.bars)
            print(f"  ⏳ Warming up... need {bars_needed} more bars")
            return
        
        # Store previous confirmed trend
        self.previous_trend = self.confirmed_trend
        
        # Determine current trend (raw)
        self.current_trend = self._determine_trend()
        
        # Get confirmed trend (requires N consecutive bars)
        self._get_confirmed_trend()
        
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
        ind = self.indicators.cache
        trend_display = f"{self.confirmed_trend.value}"
        if self.current_trend != self.confirmed_trend:
            trend_display += f" (raw: {self.current_trend.value})"
        
        total_orders = self.position_count + len(self.pending_orders)
        print(f"  📊 Trend: {trend_display} | Grid: {grid_size:.3f}%")
        print(f"     RSI: {ind['rsi']:.1f} | MACD: {ind['macd']['macd']:.2f} | ATR: {ind['atr']:.2f}")
        print(f"     MA: {ind['short_ma']:.2f} / {ind['long_ma']:.2f} / {ind['super_long_ma']:.2f}")
        print(f"     Anchor: {self.grid_anchor_price:.2f} | Filled: {self.position_count} | Pending: {len(self.pending_orders)} | Daily P&L: {self.daily_pnl:+.2f}")
        
        # Display pending orders
        for order_id, pending in self.pending_orders.items():
            age_sec = (datetime.now(UTC) - pending.submit_time).total_seconds()
            print(f"     ⏳ PENDING {pending.side.upper()} @ {pending.limit_price:.2f} (order {order_id}, {age_sec:.0f}s)")
        
        # Display open position details
        for pos in self.positions:
            if pos.side == 'long':
                unrealized_pnl = (self.last_price - pos.entry_price) * pos.size
            else:
                unrealized_pnl = (pos.entry_price - self.last_price) * pos.size
            
            active_stop = pos.trailing_stop if self.config.use_trailing_stop and pos.trailing_stop else pos.stop_loss
            print(f"     📍 {pos.side.upper()} @ {pos.entry_price:.2f} | SL: {active_stop:.2f} | TP: {pos.take_profit:.2f} | P&L: ${unrealized_pnl:+.2f}")
        
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