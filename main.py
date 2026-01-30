# main.py
import asyncio
from broker import IBKRBroker
from strategy import GridStrategy

async def main():
    broker = IBKRBroker(symbol="ES")
    
    try:
        await broker.connect_async(host="127.0.0.1", port=7497, client_id=10)
        await broker.get_front_month_contract_async()
        
        strategy = GridStrategy(broker=broker)
        
        print("\nStarting 1-minute bar stream + strategy...\n")
        
        async for bar in broker.stream_1m_bars():
            # Feed bar to strategy
            await strategy.on_new_bar(bar)
            
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await broker.disconnect_async()

if __name__ == "__main__":
    asyncio.run(main())