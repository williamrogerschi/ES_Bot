# bot.py
import asyncio
from ibkrBroker import IBKRBroker
from grid import GridStrategy

async def main():
    broker = IBKRBroker()
    await broker.connect_async()
    await broker.get_front_month_contract_async()

    grid = GridStrategy(broker, grid_size=1.0)
    await grid.run()

asyncio.run(main())
