"""Interface for performing queries against exchange API's
"""

import re
import sys
import time
from datetime import datetime, timedelta, timezone, date

import efinance as ef
from exchange import ExchangeInterface
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt

class AshareExchangeInterface(ExchangeInterface):
    """Interface for performing queries against exchange API's
    """

    def __init__(self, exchange_config):
        super().__init__(exchange_config)

    def get_historical_data(self, market_pair, exchange, time_unit, start_date=None, max_periods=100):
        """Get historical OHLCV for a symbol pair

        Decorators:
            retry

        Args:
            market_pair (str): Contains the symbol pair to operate on i.e. BURST/BTC
            exchange (str): Contains the exchange to fetch the historical data from.
            time_unit (str): A string specifying the time unit i.e. 5m or 1d.
            start_date (int, optional): Timestamp in milliseconds.
            max_periods (int, optional): Defaults to 100. Maximum number of time periods
              back to fetch data for.

        Returns:
            list: Contains a list of lists which contain timestamp, open, high, low, close, volume.
        """
        if not start_date:
            timeframe_regex = re.compile('([0-9]+)([a-zA-Z])')
            timeframe_matches = timeframe_regex.match(time_unit)
            time_quantity = timeframe_matches.group(1)
            time_period = timeframe_matches.group(2)

            timedelta_values = {
                'm': 'minutes',
                'h': 'hours',
                'd': 'days',
                'w': 'weeks',
                'M': 'months',
                'y': 'years'
            }
            
            timedelta_args = { timedelta_values[time_period]: int(time_quantity) }
            start_date_delta = timedelta(**timedelta_args)
            max_days_date = datetime.now() - (max_periods * start_date_delta)
            end_date = date.today().strftime("%Y%m%d")

        default_start_date = '20230401'

        #股票名称    股票代码          日期       开盘       收盘       最高       最低     成交量           成交额    振幅   涨跌幅    涨跌额    换手率
        historical_data = ef.stock.get_quote_history(
            market_pair,
            default_start_date,
            end_date,
            self.convertToTimeUnit(time_unit) # 1d 1w 1m
        )

        #from dataframe to list
        historical_data = historical_data.values.tolist()

        #normalize data
        historical_data = list(map(self.normalizeToOlhcv, historical_data))

        # Sort by timestamp in ascending order
        historical_data.sort(key=lambda d: d[0], reverse = True)

        return historical_data
    
    def normalizeToOlhcv(self, t):
        # to ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        return [int(datetime.strptime(t[2], '%Y-%m-%d').timestamp()) * 1000, t[3], t[5], t[6], t[4], t[7]]

    def convertToTimeUnit(self, term):
        if term == '1d':
            return 101
        elif term == '1w':
            return 102
        elif term == '1m':
            return 103
        else:
            return None;  

    def get_exchange_markets(self, exchanges=[], markets=[]):
        """Get market data for all symbol pairs listed on all configured exchanges.

        Args:
            markets (list, optional): A list of markets to get from the exchanges. Default is all
                markets.
            exchanges (list, optional): A list of exchanges to collect market data from. Default is
                all enabled exchanges.

        Decorators:
            retry

        Returns:
            dict: A dictionary containing market data for all symbol pairs.
        """

        exchange_markets = dict()
        exchange_markets['A股'] = ef.stock.get_all_company_performance()['股票代码'].values

        if markets:
            curr_markets = exchange_markets[exchange]

            # Only retrieve markets the users specified
            exchange_markets[exchange] = { key: curr_markets[key] for key in curr_markets if key in markets }

        return exchange_markets
    
    def get_name_by_market_pair(self, market_pair):
        return ef.stock.get_base_info(market_pair)['股票名称']
