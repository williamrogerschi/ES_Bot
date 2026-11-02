# main.py — ES scalp bot (clientId=10)
import asyncio
import logging
import sys
from datetime import datetime
from strategy import GridStrategy
from models import CONFIG_PRESETS
from broker import IBKRBroker

MODE = "scalp"
CLIENT_ID = 10
SYMBOL = "ES"


class DualWriter:
    """Writes print() output to both console and log file."""
    def __init__(self, console, file):
        self.console = console
        self.file = file

    def write(self, text):
        self.console.write(text)
        self.file.write(text)

    def flush(self):
        self.console.flush()
        self.file.flush()


def setup_logging():
    log_filename = f"es_bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # ONE file handle shared by logging and print(). The old version opened the
    # file twice ('w' for logging, 'a' for print) — two independent write
    # positions on the same file, so logging writes could overwrite print output.
    # buffering=1 = line-buffered, so a crash doesn't lose the last lines.
    log_file_handle = open(log_filename, 'w', encoding='utf-8', buffering=1)

    fmt = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')

    fh = logging.StreamHandler(log_file_handle)   # file: INFO+
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler(sys.stdout)        # console: WARNING+
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = [fh, ch]
    logging.getLogger('ib_insync').setLevel(logging.WARNING)

    sys.stdout = DualWriter(sys.stdout, log_file_handle)
    print(f"Logging to: {log_filename}")
    return log_filename


def print_banner(config):
    """Built from the live config so it can't drift out of date."""
    print("\n" + "=" * 60)
    print("📈 MODE: SCALP")
    print(f"   • Contracts: {config.contracts_per_trade} "
          f"({getattr(config, 'contracts_per_trade_high_vol', config.contracts_per_trade)} when ATR is high)")
    if config.use_atr_rr:
        print(f"   • SL: {config.stop_loss_atr_mult}x ATR (min {config.min_stop_loss_pts} pts) | "
              f"TP: {config.take_profit_atr_mult}x ATR")
    else:
        print(f"   • SL: {config.stop_loss_pts} pts | TP: {config.take_profit_pts} pts")
    if config.use_trailing_stop:
        native = getattr(config, 'use_native_trail', True)
        print(f"   • Trail: activates +{config.trailing_activation_pts} pts, trails "
              f"{config.trailing_distance_pts} pts ({'IBKR-side' if native else 'bar-based'})")
    else:
        print("   • Trailing stop: off")
    # (Persistent-trend banner line removed 2026-11-02: that filter isn't in strategy.py.)
    usd = getattr(config, 'daily_loss_limit_usd', 12000.0)
    if usd and usd > 0:
        print(f"   • Daily loss limit: ${usd:,.0f} (no new entries after)")
    else:
        print(f"   • Daily loss limit: {config.max_loss_per_day_pct}% of equity")
    if getattr(config, 'use_trend_day_lockout', True):
        print(f"   • Trend-day lockout: {getattr(config, 'trend_day_min_move', 30.0):.0f}+ pts from 8:30 open, "
              f"clean >= {getattr(config, 'trend_day_min_clean', 0.5)}, from 9:30 CT")
    if getattr(config, 'use_trend_ride_shadow', True):
        print("   • Trend ride: SHADOW (logged, not traded)")
    print("=" * 60)


async def main():
    log_file = setup_logging()
    config = CONFIG_PRESETS[MODE]()
    broker = IBKRBroker(symbol=SYMBOL)
    strategy = None
    print_banner(config)

    try:
        await broker.connect_async(host="127.0.0.1", port=7497, client_id=CLIENT_ID)
        await broker.get_front_month_contract_async()
        strategy = GridStrategy(broker=broker, config=config)

        print("\n" + "=" * 60)
        print("Loading historical data for indicator warm-up...")
        print("=" * 60)
        historical_bars = await broker.get_historical_bars(duration="1 D", bar_size="1 min")

        if historical_bars:
            print(f"\nProcessing {len(historical_bars)} historical bars...")
            for bar in historical_bars:
                strategy.bars.append(bar)
                strategy.last_price = bar['close']
                if strategy.last_reset_day != bar['time'].day:
                    strategy.daily_pnl = 0.0
                    strategy.last_reset_day = bar['time'].day

            strategy.seed_rth_from_history(historical_bars)

            if strategy.indicators.calculate_all(strategy.bars):
                strategy.current_trend = strategy._determine_trend()
                strategy.grid_levels = strategy._calculate_grid_levels()
                if config.use_5m_filter:
                    strategy.seed_5m_bars(historical_bars)

                ind = strategy.indicators.cache
                print("\nIndicators ready!")
                print(f"  Bars loaded: {len(strategy.bars)}")
                print(f"  Last price: {strategy.last_price:.2f}")
                print(f"  Trend: {strategy.current_trend.value}")
                print(f"  RSI: {ind['rsi']:.1f}")
                print(f"  ATR: {ind['atr']:.2f}")
                print(f"  MACD: {ind['macd']['macd']:.2f} / Signal: {ind['macd']['signal']:.2f}")
                print(f"  MA: {ind['short_ma']:.2f} / {ind['long_ma']:.2f} / {ind['super_long_ma']:.2f}")
                if config.use_5m_filter:
                    print(f"  5m Trend: {strategy.current_trend_5m.value}")
            else:
                print(f"Still need more bars. Have {len(strategy.bars)}, need ~{config.super_long_ma_length}")
        else:
            print("No historical data loaded. Strategy will warm up with live bars.")

        print("\n" + "-" * 60)
        print(f"Account Value: ${broker.get_account_value():,.2f}")
        print(f"Buying Power: ${broker.get_buying_power():,.2f}")
        print(f"Current Position (account-wide): {broker.get_position()} contracts")
        print("-" * 60)

        print("\n" + "=" * 60)
        print("Starting live 1-minute bar stream...")
        print("Strategy is now ACTIVE (SCALP mode)")
        print("=" * 60 + "\n")

        async for bar in broker.stream_1m_bars():
            await strategy.on_new_bar(bar)

    # On Python 3.11+, Ctrl+C inside asyncio.run() arrives as CancelledError,
    # not KeyboardInterrupt — the old handler never fired, so no summary printed.
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n\n" + "=" * 60)
        print("Stopped by user.")
        print("=" * 60)
        if strategy:
            print("\nFinal Summary (SCALP mode):")
            print(f"  Daily P&L: ${strategy.daily_pnl:+,.2f}")
            print(f"  Open Positions: {strategy.position_count}")
            print(f"  Equity: ${strategy.equity:,.2f}")
            print(f"\n  Log saved to: {log_file}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await broker.disconnect_async()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # summary already printed inside main()