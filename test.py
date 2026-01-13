from ib_insync import IB

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=99)

print("Connected:", ib.isConnected())
