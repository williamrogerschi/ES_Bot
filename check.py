from models import get_pullback_config
from strategy import GridStrategy
import broker as broker_mod
strat = GridStrategy(broker=broker_mod.IBKRBroker(), config=get_pullback_config())
print('ALL CHECKS PASSED')
