# esBot.py
import asyncio
from ibkrBroker import IBKRBroker
from trades import TradeStrategy

async def main():
    broker = IBKRBroker()
    await broker.connect_async()
    await broker.get_front_month_contract_async()

    strategy = TradeStrategy(broker, strong_threshold=0.25)
    await strategy.run()

    await broker.disconnect_async()

asyncio.run(main())
