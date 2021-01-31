""" minus_dm Indicator
"""
import math

import pandas
from talib import abstract

from analyzers.utils import IndicatorUtils

class MINUS_DM(IndicatorUtils):
    def analyze(self, historical_data, period_count=14,
                signal=['minus_dm'], hot_thresh=None, cold_thresh=None):
        
        dataframe = self.convert_to_dataframe(historical_data)
        dmi_values = abstract.MINUS_DM(dataframe).to_frame()
        dmi_values.dropna(how='all', inplace=True)
        dmi_values.rename(columns={0: 'minus_dm'}, inplace=True)
        
        if dmi_values[signal[0]].shape[0]:
            dmi_values['is_hot'] = dmi_values[signal[0]] < hot_thresh
            dmi_values['is_cold'] = dmi_values[signal[0]] > cold_thresh
       
        return dmi_values