class DataHandler:
    def __init__(self, ib, contract, bar_size="1 min", duration="2 D"):
        self.ib = ib
        self.contract = contract
        self.bar_size = bar_size
        self.duration = duration

    async def load_history(self):
        bars = await self.ib.reqHistoricalDataAsync(
            self.contract,
            endDateTime='',
            durationStr=self.duration,
            barSizeSetting=self.bar_size,
            whatToShow='TRADES',
            useRTH=False,
            formatDate=1
        )
        print(f"✓ Loaded {len(bars)} bars from IBKR")
        return bars
