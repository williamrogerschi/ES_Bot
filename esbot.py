import time
from ibkrBroker import IBKRBroker
from dataHandler import DataHandler
from strategy import MovingAverageCrossoverStrategy
from riskManager import RiskManager
import pandas as pd

bot_name = "ES Trading Bot"
symbol = "ES"

# Initialize modules
ibkr = IBKRBroker(symbol=symbol, paper=True)
data_handler = DataHandler(symbol)
strategy = MovingAverageCrossoverStrategy()
risk_manager = RiskManager()

print(f"Initializing {bot_name}...")
print(f"Strategy: {strategy.name}")
print(f"Mode: {'Paper Trading'}\n")

# Connect
if not ibkr.connect():
    print("❌ IBKR connection failed. Exiting.")
    exit()

# Load historical bars
bars = ibkr.get_historical_bars(duration="2 D", bar_size="5 mins")
if bars.empty:
    print("❌ No historical bars received. Exiting.")
    exit()

data_handler.load_from_ibkr(bars)

# Main loop (simulating live bars)
cycle = 1
while True:
    bar = data_handler.get_next_bar()
    if bar is None:
        print("✓ Reached end of historical data. Stopping simulation.")
        break

    # Append bar to dataframe for strategy
    df = data_handler.data.iloc[:data_handler.index]
    signal = strategy.calculate_signal(df)

    # Check and update position
    trade_occurred = risk_manager.update_position(signal)
    if trade_occurred:
        if signal == 1:
            print(f"Opened LONG position at {bar['close']}")
        elif signal == -1:
            print(f"Opened SHORT position at {bar['close']}")
        else:
            print(f"Closed position at {bar['close']}")

    # Print status
    print(f"[{cycle}] Price: ${bar['close']} | Position: {risk_manager.position}")
    cycle += 1
    time.sleep(1)  # simulate 1-second delay between bars

ibkr.disconnect()
