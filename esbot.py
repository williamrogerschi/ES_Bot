# esBot.py
import asyncio
from ibkrBroker import IBKRBroker
from grid import GridStrategy

async def main():
    # Initialize broker
    broker = IBKRBroker()
    print(f"Connecting to IBKR at 127.0.0.1:7497 (clientId=1)")
    try:
        await broker.connect_async()
        print("IBKR connected and contract resolved.")
    except Exception as e:
        print("API connection failed:", e)
        return

    # Get front-month contract
    try:
        success = await broker.get_front_month_contract_async()
        if not success:
            print("Failed to resolve front-month contract.")
            await broker.disconnect_async()
            return
    except Exception as e:
        print("Error fetching contract:", e)
        await broker.disconnect_async()
        return

    # Initialize grid strategy
    strategy = GridStrategy(
        broker=broker,
        grid_spacing=1.0,      # 1 point spacing for scalping
        scalp_points=1.0,      # Target 1 point profit
        min_bar_range=0.5      # Minimum bar range to consider strong
    )

    # Start the strategy
    try:
        await strategy.start()
    except Exception as e:
        print("Strategy failed:", e)
    finally:
        # Disconnect cleanly
        await broker.disconnect_async()
        print("Bot shut down cleanly.")

if __name__ == "__main__":
    asyncio.run(main())
