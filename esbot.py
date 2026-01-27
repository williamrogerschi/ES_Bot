# esBot.py
import asyncio
from ibkrBroker import IBKRBroker
from grid import GridStrategy

async def main():
    broker = IBKRBroker("ES")
    await broker.connect_async()

    # Get front-month contract
    success = await broker.get_front_month_contract_async()
    if not success:
        return

    # Wait for initial price bar
    async for bars, partial in broker.stream_live_bars(bar_size=1):
        if partial:
            break

    # Start grid strategy
    grid = GridStrategy(broker, grid_spacing=1, quantity=1)
    await grid.start()

    await broker.disconnect_async()

if __name__ == "__main__":
    asyncio.run(main())
