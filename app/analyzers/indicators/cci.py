""" MACD Indicator
"""

import math

import pandas
from talib import abstract

from analyzers.utils import IndicatorUtils


class CCI(IndicatorUtils):
    def analyze(self, historical_data, signal=['cci'], hot_thresh=None, cold_thresh=None):
        """Performs a macd analysis on the historical data

        Args:
            historical_data (list): A matrix of historical OHCLV data.
            signal (list, optional): Defaults to macd. The indicator line to check hot/cold
                against.
            hot_thresh (float, optional): Defaults to None. The threshold at which this might be
                good to purchase.
            cold_thresh (float, optional): Defaults to None. The threshold at which this might be
                good to sell.

        Returns:
            pandas.DataFrame: A dataframe containing the indicators and hot/cold values.
        """

        dataframe = self.convert_to_dataframe(historical_data)
        cci_values = abstract.CCI(dataframe, timeperiod=55).to_frame()
        cci_values.dropna(how='all', inplace=True)
        cci_values.rename(columns={0: 'cci'}, inplace=True)

        if cci_values[signal[0]].shape[0]:
            cci_values['is_hot'] = cci_values[signal[0]] > hot_thresh
            cci_values['is_cold'] = cci_values[signal[0]] < cold_thresh

        return cci_values
