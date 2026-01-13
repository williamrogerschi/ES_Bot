from ib_insync import *

class IBKRBroker:
    def __init__(self, paper=True):
        self.paper = paper
        self.ib = IB()
        self.connected = False

def connect(self):
    port = 7497 if self.paper else 7496

    try:
        self.ib.connect(
            host='127.0.0.1',
            port=port,
            clientId=1,
            timeout=5
        )
    except Exception as e:
        print("❌ IBKR connection failed:", e)
        return False

    if not self.ib.isConnected():
        print("❌ IBKR not connected (no API Ready)")
        return False

    self.connected = True
    print(f"✓ Connected to IBKR on port {port} (Paper={self.paper})")
    return True

def get_historical_bars(self, symbol="ES", duration="2 D", bar_size="5 mins"):
    contract = Future(
        symbol=symbol,
        lastTradeDateOrContractMonth='',
        exchange='CME',
        currency='USD'
    )

    self.ib.qualifyContracts(contract)

    bars = self.ib.reqHistoricalData(
        contract,
        endDateTime='',
        durationStr=duration,
        barSizeSetting=bar_size,
        whatToShow='TRADES',
        useRTH=False,
        formatDate=1
    )

    return bars



    def get_account_balance(self):
        account = self.ib.managedAccounts()[0]
        values = self.ib.accountValues(account)
        for v in values:
            if v.tag == 'AvailableFunds':
                return float(v.value)
        return 0.0

    def place_order(self, action, quantity, symbol, price):
        contract = Future(
            symbol='ES',
            lastTradeDateOrContractMonth='202503',
            exchange='CME',
            currency='USD'
        )

        self.ib.qualifyContracts(contract)

        order = MarketOrder(action, quantity)
        trade = self.ib.placeOrder(contract, order)

        trade.filledEvent += lambda t: print(
            f"\n{'='*50}\n"
            f"ORDER EXECUTED: {action} {quantity} {symbol}\n"
            f"{'='*50}\n"
        )

        return trade
