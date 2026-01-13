from esBot import TradingBot

# Create the bot
bot = TradingBot()

# Initialize: connect to IBKR and load historical bars
bot.initialize()

# Show first and last 5 bars
print("\nFirst 5 bars:")
print(bot.data_handler.data.head())

print("\nLast 5 bars:")
print(bot.data_handler.data.tail())

# Show status before running any cycle
print("\nBot Status BEFORE cycle:")
print(bot.get_status())

# Run a single strategy cycle (like one live bar)
bot.is_running = True  # manually set to True so the cycle can run
bot.run_strategy_cycle()

# Show status after cycle
print("\nBot Status AFTER cycle:")
print(bot.get_status())
