# main.py
import asyncio
from strategy import GridStrategy
from models import StrategyConfig
from broker import IBKRBroker

# =============================================================================
# SELECT MODE: "scalp" or "grid"
# =============================================================================
MODE = "scalp"
# =============================================================================


async def main():
    broker = IBKRBroker(symbol="ES")
    
    # ===== STRATEGY CONFIGURATIONS =====
    if MODE == "scalp":
        # -----------------------------------------------------------------
        # SCALP MODE: Single contract, trailing stop, quick exits
        # Best for: Capturing quick moves, letting winners run
        # -----------------------------------------------------------------
        config = StrategyConfig(
            # Grid settings
            base_grid_pct=0.10,
            max_positions=1,
            use_volatility_grid=True,
            
            # ATR settings
            atr_length=14,
            atr_multiplier=1.5,
            
            # RSI settings
            rsi_length=14,
            rsi_overbought=70,
            rsi_oversold=30,
            
            # MA settings
            short_ma_length=20,
            long_ma_length=50,
            super_long_ma_length=200,
            
            # MACD settings
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            
            # Risk management - tighter for scalping
            stop_loss_pct=0.12,       # ~8 pts
            take_profit_pct=0.18,     # ~12 pts
            use_trailing_stop=True,
            trailing_stop_pct=0.07,   # ~5 pts
            max_loss_per_day_pct=1.0,
            
            # Time-based exit
            time_based_exit=True,
            max_holding_hours=4,
            
            # Position sizing
            use_risk_based_position=False,
            risk_per_trade_pct=1.0,
            max_leverage=3.0,
            
            # Account
            initial_equity=100000.0
        )
        print("\n" + "="*60)
        print("📈 MODE: SCALP")
        print("   • 1 contract max")
        print("   • Trailing stop enabled")
        print("   • SL: ~8 pts | TP: ~12 pts | Trail: ~5 pts")
        print("="*60)
        
    elif MODE == "grid":
        # -----------------------------------------------------------------
        # GRID MODE: Multiple positions, no trailing, wider stops
        # Best for: Averaging into positions, mean reversion
        # -----------------------------------------------------------------
        config = StrategyConfig(
            # Grid settings
            base_grid_pct=0.12,
            max_positions=3,
            use_volatility_grid=True,
            
            # ATR settings
            atr_length=14,
            atr_multiplier=1.5,
            
            # RSI settings
            rsi_length=14,
            rsi_overbought=70,
            rsi_oversold=30,
            
            # MA settings
            short_ma_length=20,
            long_ma_length=50,
            super_long_ma_length=200,
            
            # MACD settings
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            
            # Risk management - wider for grid
            stop_loss_pct=0.40,       # ~28 pts - covers all 3 entries
            take_profit_pct=0.25,     # ~17 pts
            use_trailing_stop=False,  # No trailing for grid
            trailing_stop_pct=0.0,
            max_loss_per_day_pct=2.0,
            
            # Time-based exit
            time_based_exit=True,
            max_holding_hours=8,
            
            # Position sizing
            use_risk_based_position=False,
            risk_per_trade_pct=1.0,
            max_leverage=3.0,
            
            # Account
            initial_equity=100000.0
        )
        print("\n" + "="*60)
        print("📊 MODE: GRID")
        print("   • 3 contracts max")
        print("   • No trailing stop")
        print("   • SL: ~28 pts | TP: ~17 pts")
        print("="*60)
    
    else:
        raise ValueError(f"Unknown MODE: {MODE}. Use 'scalp' or 'grid'")
    
    try:
        # ===== CONNECT TO IBKR =====
        await broker.connect_async(host="127.0.0.1", port=7497, client_id=10)
        await broker.get_front_month_contract_async()
        
        # Initialize strategy
        strategy = GridStrategy(broker=broker, config=config)
        
        # ===== WARM UP WITH HISTORICAL DATA =====
        print("\n" + "="*60)
        print("Loading historical data for indicator warm-up...")
        print("="*60)
        
        historical_bars = await broker.get_historical_bars(duration="1 D", bar_size="1 min")
        
        if historical_bars:
            print(f"\nProcessing {len(historical_bars)} historical bars...")
            
            for bar in historical_bars:
                strategy.bars.append(bar)
                strategy.last_price = bar['close']
                
                # Reset daily P&L tracking
                current_day = bar['time'].day
                if strategy.last_reset_day != current_day:
                    strategy.daily_pnl = 0.0
                    strategy.last_reset_day = current_day
            
            # Calculate indicators after loading all bars
            if strategy.indicators.calculate_all(strategy.bars):
                strategy.current_trend = strategy._determine_trend()
                strategy.grid_levels = strategy._calculate_grid_levels()
                
                ind = strategy.indicators.cache
                print(f"\n✓ Indicators ready!")
                print(f"  Bars loaded: {len(strategy.bars)}")
                print(f"  Last price: {strategy.last_price:.2f}")
                print(f"  Trend: {strategy.current_trend.value}")
                print(f"  RSI: {ind['rsi']:.1f}")
                print(f"  ATR: {ind['atr']:.2f}")
                print(f"  MACD: {ind['macd']['macd']:.2f} / Signal: {ind['macd']['signal']:.2f}")
                print(f"  MA: {ind['short_ma']:.2f} / {ind['long_ma']:.2f} / {ind['super_long_ma']:.2f}")
            else:
                print(f"⚠️ Still need more bars. Have {len(strategy.bars)}, need ~{config.super_long_ma_length}")
        else:
            print("⚠️ No historical data loaded. Strategy will warm up with live bars.")
        
        # ===== DISPLAY ACCOUNT INFO =====
        print("\n" + "-"*60)
        account_value = broker.get_account_value()
        buying_power = broker.get_buying_power()
        current_position = broker.get_position()
        print(f"Account Value: ${account_value:,.2f}")
        print(f"Buying Power: ${buying_power:,.2f}")
        print(f"Current Position: {current_position} contracts")
        print("-"*60)
        
        # ===== START LIVE STREAMING =====
        print("\n" + "="*60)
        print("Starting live 1-minute bar stream...")
        print(f"Strategy is now ACTIVE ({MODE.upper()} mode)")
        print("="*60 + "\n")
        
        async for bar in broker.stream_1m_bars():
            await strategy.on_new_bar(bar)
            
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("Stopped by user.")
        print("="*60)
        
        # Final summary
        if 'strategy' in locals():
            print(f"\nFinal Summary ({MODE.upper()} mode):")
            print(f"  Daily P&L: {strategy.daily_pnl:+.2f}")
            print(f"  Open Positions: {strategy.position_count}")
            print(f"  Equity: {strategy.equity:.2f}")
            
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await broker.disconnect_async()


if __name__ == "__main__":
    asyncio.run(main())