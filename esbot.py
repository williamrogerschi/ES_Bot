# esBot.py
import asyncio
from ibkrBroker import IBKRBroker
from trades import Trader
from grid import GridStrategy

async def main():
    # --- Initialize broker ---
    broker = IBKRBroker(symbol="ES")
    try:
        await broker.connect_async()
    except Exception as e:
        print("IBKR connection failed:", e)
        return

    # --- Get front-month contract ---
    try:
        success = await broker.get_front_month_contract_async()
        if not success:
            await broker.disconnect_async()
            return
    except Exception as e:
        print("Contract fetch failed:", e)
        await broker.disconnect_async()
        return

    # --- Initialize Trader and Strategy ---
    trader = Trader(broker)
    strategy = GridStrategy(broker, trader, scalp_points=1.0, min_bar_range=0.5)

    # --- Run strategy ---
    try:
        await strategy.start()
    except Exception as e:
        print("Strategy error:", e)
    finally:
        await broker.disconnect_async()
        print("Bot shut down cleanly.")

if __name__ == "__main__":
    asyncio.run(main())
