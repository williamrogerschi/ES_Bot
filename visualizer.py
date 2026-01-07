import matplotlib.pyplot as plt

class Visualizer:
    def __init__(self, strategy):
        self.strategy = strategy
        plt.ion()

    def plot(self, data):
        if len(data) < self.strategy.slow_period:
            return

        plt.clf()

        plt.plot(data['timestamp'], data['close'], label='Price', linewidth=1)
        plt.plot(data['timestamp'], data['MA_fast'], label='MA Fast', linestyle='--')
        plt.plot(data['timestamp'], data['MA_slow'], label='MA Slow', linestyle='--')

        buys = data[data['signal'] == 1]
        sells = data[data['signal'] == -1]

        plt.scatter(buys['timestamp'], buys['close'], marker='^', label='Buy')
        plt.scatter(sells['timestamp'], sells['close'], marker='v', label='Sell')

        plt.legend()
        plt.title("ES Moving Average Crossover")
        plt.pause(0.01)
