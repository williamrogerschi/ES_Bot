# ibkrBroker.py
from ib_insync import IB, Future, LimitOrder
from zoneinfo import ZoneInfo
import asyncio

CENTRAL = ZoneInfo("America/Chicago")


class IBKRBroker:
    def __init__(self, symbol="ES"):
        self.ib = IB()
        self.symbol = symbol
        self.contract = None
        self.last_price = None

    async def connect_async(self, host="127.0.0.1", port=7497):
        await self.ib.connectAsync(host, port, clientId=1)
        print("✓ Connected to IBKR")

    async def get_front_month_contract_async(self):
        contract = Future(symbol=self.symbol, exchange="CME")
        details = await self.ib.reqContractDetailsAsync(contract)
        details.sort(key=lambda d: d.contract.lastTradeDateOrContractMonth)
        self.contract = details[0].contract
        print(f"✓ Front-month contract: {self.contract.localSymbol}")

    # --------------------------------------------------
    # REAL-TIME TICKS (reqMktData)
    # --------------------------------------------------
    async def stream_ticks(self):
        ticker = self.ib.reqMktData(self.contract, "", False, False)

        try:
            while True:
                await ticker.updateEvent

                if ticker.last is None:
                    continue

                price = float(ticker.last)
                self.last_price = price
                yield price

        finally:
            self.ib.cancelMktData(self.contract)

    # --------------------------------------------------
    # ORDERS
    # --------------------------------------------------
    def place_limit_order_no_wait(self, action, qty, price):
        order = LimitOrder(action, qty, price)
        order.tif = "GTC"
        order.outsideRth = True
        trade = self.ib.placeOrder(self.contract, order)
        print(f"[ORDER] {action} {qty} @ {price}")
        return trade
