
"""Parent Interface for performing queries against exchange API's
"""
import structlog

class ExchangeInterface():

    def __init__(self, exchange_config):
        """Initializes ExchangeInterface class

        Args:
            exchange_config (dict): A dictionary containing configuration for the exchanges.
        """

        self.logger = structlog.get_logger()
        self.exchanges = dict()
    

    def get_historical_data(self, market_pair, exchange, time_unit, start_date=None, max_periods=100):
        pass
    
    def get_exchange_markets(self, exchanges=[], markets=[]):
        pass
    
    def get_name_by_market_pair(self, market_pair):
        return market_pair