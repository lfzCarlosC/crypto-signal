""" Runs the default analyzer, which performs two functions...
1. Output the signal information to the prompt.
2. Notify users when a threshold is crossed.
"""

from copy import deepcopy

import redis
import structlog
from ccxt import ExchangeError
import ccxt
from tenacity import RetryError

from analysis import StrategyAnalyzer
from outputs import Output

import numpy as np
from collections import defaultdict
import traceback
import json
import uuid
import os

import sys

import mysql.connector
from datetime import date

class Behaviour():
    """Default analyzer which gives users basic trading information.
    """
    trendColor = {
        "分立跳空顶背离":"red",
        "分立跳空底背离": "green",
        "段内顶背离": "red",
        "段内底背离": "green",
        "接近0轴的macd金叉信号": "green",
        "TD 底部 9位置": "green",
        "TD 底部 13位置": "green",
        "TTD 顶部 9位置": "red",
        "TTD 顶部 13位置": "red",
        "TD 底部 1位置": "green",
        "TD 底部 2位置": "green",
        "MACD 量能上涨异常": "green",
        "macd金叉信号": "green",
        "0轴上macd金叉信号": "green",
        "macd金叉信号 + DMI": "green",
        "DMI+": "green",
        "TD+底部2B信号": "green",
        "底部2B信号": "green",
        "沾到ema30/ema60": "green",
        "kdj金叉信号": "green",
        "cci over 100": "green"
    }

    mydb = mysql.connector.connect(
        host="127.0.0.1",  # 数据库主机地址
        user="root",  # 数据库用户名
        passwd="",  # 数据库密码
        database = "cs"
    )

    def __init__(self, config, exchange_interface, notifier):
        """Initializes DefaultBehaviour class.

        Args:
            indicator_conf (dict): A dictionary of configuration for this analyzer.
            exchange_interface (ExchangeInterface): Instance of the ExchangeInterface class for
                making exchange queries.
            notifier (Notifier): Instance of the notifier class for informing a user when a
                threshold has been crossed.
        """
        self.logger = structlog.get_logger()
        self.indicator_conf = config.indicators
        self.informant_conf = config.informants
        self.crossover_conf = config.crossovers
        self.exchange_interface = exchange_interface
        self.strategy_analyzer = StrategyAnalyzer()
        self.notifier = notifier

        self.indicator_dispatcher = self.strategy_analyzer.indicator_dispatcher()
        self.informant_dispatcher = self.strategy_analyzer.informant_dispatcher()
        output_interface = Output()
        self.output = output_interface.dispatcher


    def run(self, market_pairs, output_mode):
        """The analyzer entrypoint

        Args:
            market_pairs (list): List of symbol pairs to operate on, if empty get all pairs.
            output_mode (str): Which console output mode to use.
        """

        self.logger.info("Starting default analyzer...")

        if market_pairs:
            self.logger.info("Found configured markets: %s", market_pairs)
        else:
            self.logger.info("No configured markets, using all available on exchange.")

        if sys.argv[4:] and (sys.argv[4] == '-a'):
            self.logger.info("Scan all flag set to true. using all available on exchange.")
            market_pairs = None

        market_data = self.exchange_interface.get_exchange_markets(markets = market_pairs)
        
        self.logger.info("Using the following exchange(s): %s", list(market_data.keys()))
        exchange = list(market_data.keys())[0]

        (indicatorTypeCoinMap, new_result) = self._get_indicator_data(market_data, output_mode)
        if sys.argv[5:]:
            if (sys.argv[5] == '_get_indicator_data'):
                return indicatorTypeCoinMap
            elif (sys.argv[5] == '_write_strategic_data'):
                return self._write_strategic_data(market_data, output_mode)
            elif (sys.argv[5] == '_write_strategic_data_redis'):
                self.persistInRedis(indicatorTypeCoinMap, exchange)
        else:
            self._notify_strategies_data(indicatorTypeCoinMap, exchange, new_result)

    def truncateFile(self):
        f = open(sys.argv[2],'r+')
        f.truncate()
        f.close()

    def isCloseTo(self, start, actual, target):
        if((target-actual) / (actual-start) < 0.05):
            return True;

    def _notify_strategies_data(self, indicatorTypeCoinMap, exchange, new_result):
        self.truncateFile()
        f = open(sys.argv[2], 'a')
        #self.persistInRedis(indicatorTypeCoinMap, exchange)
        # self.persistInEmailFormat(f, indicatorTypeCoinMap);
        # self.notifier.notify_all(new_result)

    def persistInRedis(self, indicatorTypeCoinMap, exchange):
        r = redis.Redis();
        candle_period = self.indicator_conf['macd'][0]['candle_period']
        for indicator in indicatorTypeCoinMap:
            for coin in indicatorTypeCoinMap[indicator]:
                candle_periods = r.hget(coin, str.encode(indicator).decode('utf-8'))
                r.hset(coin + "|" + exchange, str.encode(indicator).decode('utf-8'),
                       candle_period if candle_periods is None else candle_periods.decode('utf-8') + "|" + candle_period)
        r.close();

    def _write_strategic_data(self, market_data, output_mode):
        (indicatorTypeCoinMap, new_result) = self._get_indicator_data(market_data, output_mode)

        #UUID for DB storage later
        # fileId = uuid.uuid4().hex

        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/tmp")
        fileId = list(market_data)[0] + "-" + self.indicator_conf['macd'][0]['candle_period'] + "-" + "_write_strategic_data"
        with open(fileId, 'w+') as f:
            f.write(json.dumps(indicatorTypeCoinMap, sort_keys=True, ensure_ascii=False))
            f.close()
        return fileId

    def _get_indicator_data(self, market_data, output_mode):
        (indicatorTypeCoinMap, new_result) = self._apply_strategies(market_data, output_mode)
        return (indicatorTypeCoinMap, new_result)

    def persistInPlainFormat(self, f, indicatorTypeCoinMap) :
        #write everything to the email
        for indicator in indicatorTypeCoinMap:
            f.write("<p style='color: " + Behaviour.trendColor[indicator] +"; font-size:30px;'> <b>" + indicator + "</b></p>\n");
            for coin in indicatorTypeCoinMap[indicator]:
                f.write("<p style='color: " + Behaviour.trendColor[indicator] + ";'>  币种/交易对:" + coin.replace('/','') + " " + indicator + '</p>\n' );
        f.close();

    def persistInEmailFormat(self, f, indicatorTypeCoinMap) :
        #write everything to the email
        for indicator in indicatorTypeCoinMap:
            f.write("<p style='color: " + Behaviour.trendColor[indicator] +"; font-size:30px;'> <b>" + indicator + "</b></p>\n");
            for coin in indicatorTypeCoinMap[indicator]:
                f.write("<p style='color: " + Behaviour.trendColor[indicator] + ";'>  币种/交易对:" + coin.replace('/','') + " " + indicator + '</p>\n' );
        f.close();

    def detectCoinPairs(self, exchange, market_pair, marketPairFlag):
        if exchange == 'A股':
            return True;

        if marketPairFlag == 'usd/btc':
            return  ( market_pair.lower().endswith("usdt") ) \
               and (self.indicator_conf['macd'][0]['candle_period'] in ['1h','6h', '4h', '12h', '1d', '3d', '1w', '15m', '30m', '5m']);
    
    def postProcessPair(self, market_pair):
        if ':' in market_pair:
            return market_pair.split('/')[0] + '/' + market_pair.split(':')[-1]

        return market_pair
                
    def _apply_strategies(self, market_data, output_mode):
        """Test the strategies and perform notifications as required
        
        Args:
            market_data (dict): A dictionary containing the market data of the symbols to analyze.
            output_mode (str): Which console output mode to use.
        """

        if len(sys.argv) > 5:
            marketPairFlag = sys.argv[5]
        else:
            marketPairFlag = 'usd/btc'

        indicatorModes = sys.argv[3]
        indicatorTypeCoinMap = defaultdict(list)
        new_result = dict()

        for exchange in market_data:
            if exchange not in new_result:
                new_result[exchange] = dict()

            for market_pair in market_data[exchange]:
                market_pair = self.postProcessPair(market_pair);

                if not (self.detectCoinPairs(exchange, market_pair, marketPairFlag)):
                    continue;

                if market_pair not in new_result[exchange]:
                    new_result[exchange][market_pair] = dict()
                
                """
                set olhcv data
                a bad implementation: this should be performed concurrently
                """
                new_result[exchange][market_pair]['indicators'] = self._get_indicator_results(
                    exchange,
                    market_pair
                )

                new_result[exchange][market_pair]['informants'] = self._get_informant_results(
                    exchange,
                    market_pair
                )

                ################################# Indicator data retrieving and strategy
                try:
                    arr = new_result[exchange][market_pair]['informants']['ohlcv']
                    if not arr:
                        continue;

                    ohlcv = arr[0]['result']

                    # upperband = new_result[exchange][market_pair]['informants']['bollinger_bands'][0]['result']['upperband'] ;
                    # middleband = new_result[exchange][market_pair]['informants']['bollinger_bands'][0]['result']['middleband'] ;
                    # lowerband = new_result[exchange][market_pair]['informants']['bollinger_bands'][0]['result']['lowerband'] ;
                    # distance_close_open = close - opened;
                    opened = ohlcv['open'];
                    close = ohlcv['close'] ;
                    low = ohlcv['low'];
                    high = ohlcv['high'] ;
                    volume = ohlcv['volume'] ;
                    plus_di = new_result[exchange][market_pair]['indicators']['plus_di'][0]['result']['plus_di'] ;
                    minus_di = new_result[exchange][market_pair]['indicators']['minus_di'][0]['result']['minus_di'] ;
                    plus_dm = new_result[exchange][market_pair]['indicators']['plus_dm'][0]['result']['plus_dm'];
                    minus_dm = new_result[exchange][market_pair]['indicators']['minus_dm'][0]['result']['minus_dm'];
                    delta_di = plus_di - minus_di
                    delta_dm = plus_dm - minus_dm
                    macd = new_result[exchange][market_pair]['indicators']['macd'][0]['result']['macd'];  #white line
                    macd_signal = new_result[exchange][market_pair]['indicators']['macd'][0]['result']['macdsignal']; #yellow line
                    delta_macd = new_result[exchange][market_pair]['indicators']['macd'][0]['result']['macdhist']; #macd volume
                
                    # rsi = new_result[exchange][market_pair]['indicators']['rsi'][0]['result']['rsi'];
                    # stoch_slow_k = new_result[exchange][market_pair]['indicators']['stoch_rsi'][0]['result']['slow_k'];
                    # stoch_slow_d = new_result[exchange][market_pair]['indicators']['stoch_rsi'][0]['result']['slow_d'];
                    kt = new_result[exchange][market_pair]['indicators']['kdj'][0]['result']['k'];
                    dt = new_result[exchange][market_pair]['indicators']['kdj'][0]['result']['d'];
                    jt = new_result[exchange][market_pair]['indicators']['kdj'][0]['result']['j'];

                    #cci
                    cci = new_result[exchange][market_pair]['indicators']['cci'][0]['result']['cci'];
                    ######################################### ema indicator
                    #now contains: ema7IsOverEma65 ema7IsOverEma22 ema7IsOverEma33
                    # try:
                    #     ema7 = new_result[exchange][market_pair]['informants']['ema7'][0]['result']['ema'];
                    #     ema22 = new_result[exchange][market_pair]['informants']['ema22'][0]['result']['ema'];
                    ema30 = new_result[exchange][market_pair]['informants']['ema30'][0]['result']['ema'];
                    ema60 = new_result[exchange][market_pair]['informants']['ema60'][0]['result']['ema'];
                    #
                    #     ema7IsOverEma65 = self.ema7OverEma65(ema7, ema65);
                    #     ema7IsOverEma22 = self.ema7OverEma22(ema7, ema22);
                    #     ema7IsOverEma33 = self.ema7OverEma33(ema7, ema33);
                    #
                    #     # candleOverEma
                    #     if ema33 is not None:
                    #         candleIsOverEma = self.candleOverEma(opened, close, ema33)
                    #
                    # except RuntimeError:
                    #     print('ema data has errors')

                    ###################################### td indicator
                    indicators = new_result[exchange][market_pair]['indicators']
                    td9PositiveFlag = False
                    td13PositiveFlag = False
                    td9NegativeFlag = False
                    td13NegativeFlag = False

                    td9PositiveFlag42B = False
                    td13PositiveFlag42B = False
                    td1PostiveFlag42B = False
                    td2PositiveFlag42B = False
                    td9NegativeFlag42B = False
                    td13NegativeFlag42B = False
                    if('td' in indicators):
                        td = indicators['td'][0]['result']['td'];
                        (td9PositiveFlag, td9NegativeFlag, td13PositiveFlag, td13NegativeFlag) = self.tdDeteminator(td, False)
                        ###################################### 2B indicator
                        # This 2B is based on TD bottom point. It pick ups the 2B point near/at TD 9 point.
                        # argrelextrema is not very useful due to massive but not distinguished valley points.
                        # peakIndex = new_result[exchange][market_pair]['indicators']['peak_loc'][0]['result']['peak_loc']
                        # valleyIndex = new_result[exchange][market_pair]['indicators']['valley_loc'][0]['result']['valley_loc']

                        #- bottom 2B for later use
                        (td9PositiveFlag42B, td9NegativeFlag42B, td13PositiveFlag42B, td13NegativeFlag42B) = self.tdDeteminator(td, True)

                    ########################################## cci
                    isCciOver100 = (cci[len(cci) - 1] > 100) and (cci[len(cci) - 2] < 100)

                    ########################################## goldenMacdFork
                    intersectionValueAndMin = [0, 0]

                    goldenForkMacd = None
                    if not (len(macd) == 0 \
                            or len(macd_signal) == 0 \
                            or len(delta_macd) == 0):

                      goldenForkMacd = (
                        (delta_macd[len(delta_macd)-1] >= 0  and delta_macd[len(delta_macd)-2] <= 0 and self.isTheIntersectionPointCloseToBePositive(macd, macd_signal, 1, intersectionValueAndMin)) or

                        (delta_macd[len(delta_macd)-1] >= 0  and delta_macd[len(delta_macd)-2] >= 0 and delta_macd[len(delta_macd)-3] <= 0 and self.isTheIntersectionPointCloseToBePositive(macd, macd_signal, 2, intersectionValueAndMin))
                      
                      )

                      macdVolumeIncreasesSurprisingly = (delta_macd[len(delta_macd) - 1] >= 0) and (
                                delta_macd[len(delta_macd) - 2] >= 0) and (delta_macd[len(delta_macd) - 1] >= (
                                delta_macd[len(delta_macd) - 2] * 3))

                    ############################################## goldenForkKdj
                    # len_k = len(kt)
                    # len_d = len(dt)
                    # len_j = len(jt)
                    # goldenForkKdj = (
                    #     ((dt[len_d-2] >= kt[len_k-2]) and (kt[len_k-2] >= jt[len_j-2]))
                    #     and
                    #     ((dt[len_d-1] <= kt[len_k-1]) and (kt[len_k-1] <= jt[len_j-1]))
                    # )

                    ############################################# dmi
                    lastNDMIIsPositiveVolume = (self.lastNDataIsPositive(delta_di, 3) > 0) or (self.lastNDataIsPositive(delta_di, 2) > 0) or (self.lastNDataIsPositive(delta_di, 1) > 0)
                    lastNDIIsPositiveFork = self.lastNDMIIsPositive(delta_di, 5)
                    lastNDMIsPositiveFork = self.lastNDMIIsPositive(delta_dm, 5)

                    ############################################# macdBottomDivergence
                    # hasBottomDivergence = self.detectBottomDivergence(delta_macd, low, macd_signal)
                    # hasPeakDivergence = self.detectPeakDivergence(delta_macd, high, macd_signal)
                    # hasMultipleBottomDivergence = self.detectMultipleBottomDivergence(delta_macd, low, macd_signal)
                    # hasMultiplePeakDivergnce = self.detectMultiplePeakDivergence(delta_macd, high, macd_signal)

                    ############################################ macd正值平滑
                    #c(macd+)>5 + D<0.1
                    #counts: 10,
                    # flatPositive = False
                    # positiveFlag = self.lastNDataIsPositive(delta_macd, 10);
                    # if(positiveFlag):
                    #     variance, mean, max = self.getVariance(delta_macd, 10);
                    #     flatPositive = self.lastNDataIsPositive(delta_macd, 10) and (variance <= 0.01) and (mean/max <= 0.2)

                    #narrowedBoll
                    #(narrowedBoll, test_arr) = self.lastNBoolIsNarrowed((upperband/lowerband)**10, 5) # counts of narrowed points
                    #continuousKRise
                    # lastNKPositive = self.lastNKIsPositive(distance_close_open)

                    # isBottom3kFlag = self.isBottom3k(low, high)


#=============================================signal rendering=============================================
                    if(indicatorModes == 'custom'):

                        # if(self.isOverceedingTriangleLine(peakLoc, ohlcv)):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "上升突破三角形",
                        #                      indicatorTypeCoinMap)

                        #if (macdVolumeIncreasesSurprisingly):
                        #    self.printResult(new_result, exchange, market_pair, output_mode, "MACD 量能上涨异常",
                        #                     indicatorTypeCoinMap)

                        # if(isBottom3kFlag):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "底部3k", indicatorTypeCoinMap)
                        #     self.toDb("底部3k", exchange, market_pair)

                        if (td9NegativeFlag):
                            self.printResult(new_result, exchange, market_pair, output_mode, "TD 底部 9位置", indicatorTypeCoinMap)
                            self.toDb("TD 底部 9位置", exchange, market_pair)

                        if (td13NegativeFlag):
                            self.printResult(new_result, exchange, market_pair, output_mode, "TD 底部 13位置", indicatorTypeCoinMap)
                            self.toDb("TD 底部 13位置", exchange, market_pair)

                        if (td9PositiveFlag):
                           self.printResult(new_result, exchange, market_pair, output_mode, "TD 顶部 9位置", indicatorTypeCoinMap)
                           self.toDb("TD 顶部 9位置", exchange, market_pair)

                        if (td13PositiveFlag):
                           self.printResult(new_result, exchange, market_pair, output_mode, "TD 顶部 13位置", indicatorTypeCoinMap)
                           self.toDb("TD 顶部 13位置", exchange, market_pair)

                        if (td13NegativeFlag42B or td9NegativeFlag42B):
                            if (self.isBottom2B(volume, opened, close)):
                                self.printResult(new_result, exchange, market_pair, output_mode, "TD+底部2B信号", indicatorTypeCoinMap)
                                self.toDb("TD+底部2B信号", exchange, market_pair)



                        # if (goldenForkMacd and (intersectionValueAndMin[0] > 0)):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "0轴上macd金叉信号", indicatorTypeCoinMap)
                        #     self.toDb("0轴上macd金叉信号", exchange, market_pair)

                        # if (lastNDIIsPositiveFork or lastNDMIsPositiveFork):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "DMI+", indicatorTypeCoinMap)
                        #     self.toDb("DMI+", exchange, market_pair)



                        # if (self.isBottomPinBar(low, high, close, opened)):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "底部pin bar", indicatorTypeCoinMap)
                        #     self.toDb("底部pin bar", exchange, market_pair)

                        # if (self.isTopPinBar(low, high, close, opened)):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "顶部pin bar", indicatorTypeCoinMap)
                        #     self.toDb("顶部pin bar", exchange, market_pair)

                        # if (flatPositive):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "macd正值平滑", indicatorTypeCoinMap)
#================================================


                        # (start, end) = self.detectMacdSlots(delta_macd, 0, 'positive')
                        # if (goldenForkMacd and (intersectionValueAndMin[0] > 0.2 * 2 * delta_macd[
                        #     self.getIndexOfMacdValley(delta_macd, start, end)])):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "接近0轴的macd金叉信号",
                        #                      indicatorTypeCoinMap)
                        #     self.toDb("接近0轴的macd金叉信号", exchange, market_pair)





                        # if ((lastNDIIsPositiveFork or lastNDMIsPositiveFork) and (goldenForkMacd and (intersectionValueAndMin[0] > 0.2 * 2 * delta_macd[self.getIndexOfMacdValley(delta_macd, start, end)]))):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "macd金叉信号 + DMI",
                        #                      indicatorTypeCoinMap)
                        #     self.toDb("macd金叉信号 + DMI", exchange, market_pair)

                        # if (
                        #         ((close[len(close)-1] > opened[len(opened)-1]) and (high[len(high)-1] > ema60[len(ema60)-1]) and (low[len(low)-1] < ema60[len(ema60)-1])
                        #         )
                        # ):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "沾到ema60",
                        #                      indicatorTypeCoinMap)
                        #     self.toDb("沾到ema60", exchange, market_pair)

                        # if (
                        #         ((low[len(low)-1] >= (1-0.03) * ema30[len(ema30)-1] and low[len(low)-1] <= (1+0.03) * ema30[len(ema30)-1])
                        #         )
                        # ):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "沾到ema30",
                        #                      indicatorTypeCoinMap)
                        #     self.toDb("沾到ema30", exchange, market_pair)
#================================================
                        # if (macdBottomDivergence and lastNDMIIsPositiveFork):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "macd底背离 + DMI", indicatorTypeCoinMap)

                        # if (macdBottomDivergence and stochrsi_goldenfork):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "macd底背离 + stochrsi强弱指标金叉", indicatorTypeCoinMap)

                        # if (goldenForkKdj and goldenForkMacd):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "kdj金叉信号 + macd金叉信号", indicatorTypeCoinMap)

                        # if (goldenForkMacd):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "macd金叉信号", indicatorTypeCoinMap)

                        # if (goldenForkKdj):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "kdj金叉信号", indicatorTypeCoinMap)

                        # if (goldenForkKdj and lastNDMIIsPositiveFork):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "kdj金叉信号 + DMI", indicatorTypeCoinMap)

                        # compound indicator
                        # if (hasBottomDivergence):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "段内底背离", indicatorTypeCoinMap)

                        #if (hasPeakDivergence):
                        #    self.printResult(new_result, exchange, market_pair, output_mode, "段内顶背离", indicatorTypeCoinMap)

                        # if (hasMultipleBottomDivergence):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "分立跳空底背离", indicatorTypeCoinMap)

                        #if (hasMultiplePeakDivergnce):
                        #    self.printResult(new_result, exchange, market_pair, output_mode, "分立跳空顶背离", indicatorTypeCoinMap)

                        # if (stochrsi_goldenfork and goldenForkKdj and lastNDMIIsPositiveVolume and (delta_macd[len(delta_macd)-1] > delta_macd[len(delta_macd)-2])):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "stochrsi强弱指标金叉 + kdj金叉信号 + DMI+ + macd量能减小", indicatorTypeCoinMap)

                        # if (stochrsi_goldenfork and macdIsDecreased):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "stochrsi强弱指标金叉 + macd下跌量能减弱",
                        #                      indicatorTypeCoinMap)

                        if (isCciOver100):
                            self.printResult(new_result, exchange, market_pair, output_mode, "cci over 100", indicatorTypeCoinMap)
                            self.toDb("cci over 100", exchange, market_pair)
                    
                        indices, prices, dirs, ratios = self.pine_zigzag_exact(high, low, length=2, deviation=0, max_size=30)
                        if (self.isCrabPattern(opened, close, low, high, indices, prices, ratios)):
                            self.printResult(new_result, exchange, market_pair, output_mode, "螃蟹形态", indicatorTypeCoinMap)
                            self.toDb("螃蟹形态", exchange, market_pair)
                        
                        if (self.isDeepCrabPattern(opened, close, low, high, indices, prices, ratios)):
                            self.printResult(new_result, exchange, market_pair, output_mode, "deep螃蟹形态", indicatorTypeCoinMap)
                            self.toDb("deep螃蟹形态", exchange, market_pair)
                        
                        if (self.isButterflyPattern(opened, close, low, high, indices, prices, ratios)):
                            self.printResult(new_result, exchange, market_pair, output_mode, "蝴蝶形态", indicatorTypeCoinMap)
                            self.toDb("蝴蝶形态", exchange, market_pair)

                        if (self.isBatPattern(opened, close, low, high, indices, prices, ratios)):
                            self.printResult(new_result, exchange, market_pair, output_mode, "蝙蝠形态", indicatorTypeCoinMap)
                            self.toDb("蝙蝠形态", exchange, market_pair)

                        if (self.isGartleyPattern(opened, close, low, high, indices, prices, ratios)):
                            self.printResult(new_result, exchange, market_pair, output_mode, "加特利形态", indicatorTypeCoinMap)
                            self.toDb("加特利形态", exchange, market_pair)

                        if (self.isSharkPattern(opened, close, low, high, indices, prices, ratios)):
                            self.printResult(new_result, exchange, market_pair, output_mode, "鲨鱼形态", indicatorTypeCoinMap)
                            self.toDb("鲨鱼形态", exchange, market_pair)

                        if (self.isCypherPattern(opened, close, low, high, indices, prices, ratios)):
                            self.printResult(new_result, exchange, market_pair, output_mode, "Cypher形态", indicatorTypeCoinMap)
                            self.toDb("Cypher形态", exchange, market_pair)

                        if (self.isDoublePattern(high, low, indices, prices, dirs)):
                            self.printResult(new_result, exchange, market_pair, output_mode, "DB DT形态", indicatorTypeCoinMap)
                            self.toDb("DB DT形态", exchange, market_pair)

                        # if (self.isThreeDrivesPattern(opened, close, low, high, indices, prices, ratios)):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "ThreeDrives形态", indicatorTypeCoinMap)
                        #     self.toDb("ThreeDrives形态", exchange, market_pair)

                        # if (self.isFiveZeroPattern(opened, close, low, high, indices, prices, ratios)):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "5-0形态", indicatorTypeCoinMap)
                        #     self.toDb("5-0形态", exchange, market_pair)

######################################################
                except Exception as e:
                    print("An exception occurred for " + market_pair + ":" + exchange)
                    print(e)
                    traceback.print_exc()

        return (indicatorTypeCoinMap, new_result);

    def pine_zigzag_exact(self, high, low, length=10, deviation=0, max_size=20):
        n = len(high)
        pivots = [0] * n
        dir_arr = [0] * n
        
        # 1. 计算pivots和dir（只看过去length个bar）
        for i in range(length, n - length):
            ph = high[i] == max(high[i-length:i+1])
            pl = low[i] == min(low[i-length:i+1])
            
            if ph and not pl:
                pivots[i] = 1
                dir_arr[i] = 1
            elif pl and not ph:
                pivots[i] = -1
                dir_arr[i] = -1
            else:
                dir_arr[i] = dir_arr[i-1]  # 继承上一bar
        
        zigzag_indices = []
        zigzag_prices = []
        zigzag_dirs = []

        last_dir = 0
        last_price = None
        last_index = None

        # 2. 迭代添加zigzag点，考虑方向内点跳过逻辑和deviation阈值
        for i in range(n):
            if pivots[i] == 0:
                continue
            cur_dir = pivots[i]
            cur_price = high[i] if cur_dir == 1 else low[i]
            
            if not zigzag_indices:
                zigzag_indices.append(i)
                zigzag_prices.append(cur_price)
                zigzag_dirs.append(cur_dir)
                last_dir = cur_dir
                last_price = cur_price
                last_index = i
                continue
            
            dir_changed = (cur_dir != last_dir)
            
            # 方向未变时，判断是否需要替换当前zigzag点
            if not dir_changed:
                # 方向内点跳过逻辑：只有当前点价格突破之前线段高低时才替换
                if cur_price * cur_dir >= last_price * cur_dir:
                    # 判断偏差阈值
                    if deviation > 0:
                        change_pct = abs(cur_price - last_price) * 100 / last_price if last_price != 0 else 0
                        if change_pct >= deviation:
                            zigzag_indices[-1] = i
                            zigzag_prices[-1] = cur_price
                            zigzag_dirs[-1] = cur_dir
                            last_price = cur_price
                            last_index = i
                    else:
                        zigzag_indices[-1] = i
                        zigzag_prices[-1] = cur_price
                        zigzag_dirs[-1] = cur_dir
                        last_price = cur_price
                        last_index = i
            else:
                # 方向变了，直接加点
                # 方向变化前后线段长度变化判断（类似pine ratio的计算）用来参考
                zigzag_indices.append(i)
                zigzag_prices.append(cur_price)
                zigzag_dirs.append(cur_dir)
                last_dir = cur_dir
                last_price = cur_price
                last_index = i
            
            # 限制最大数组长度
            if len(zigzag_indices) > max_size:
                zigzag_indices.pop(0)
                zigzag_prices.pop(0)
                zigzag_dirs.pop(0)
        
        if not zigzag_indices:
            return [], [], [], []
        
        # 3. 保证点顺序是升序
        zipped = sorted(zip(zigzag_indices, zigzag_prices, zigzag_dirs), key=lambda x: x[0])
        indices, prices, dirs = zip(*zipped)
        
        # 4. 计算线段长度ratio：当前线段长度 / 上一线段长度
        def safe_ratio(a, b):
            return abs(b - a) / abs(a) if a != 0 else 0
        
        ratios = []
        for i in range(1, len(prices)):
            ratio = round(safe_ratio(prices[i-1], prices[i]), 3)
            ratios.append(ratio)

        if indices[-1] < n - 3:
            return list([0]), list([0]), list([0]), []
        
        return list(indices), list(prices), list(dirs), ratios

    def get_harmonic_ratios_from_prices(self, prices):
        if len(prices) < 5:
            return (0, 0, 0, 0)
        
        x, a, b, c, d = prices[-5:] 
        def safe_ratio(numer, denom):
            return abs(numer) / abs(denom) if abs(denom) > 1e-6 else 0

        xab = safe_ratio(b - a, a - x)
        abc = safe_ratio(c - b, b - a)
        bcd = safe_ratio(d - c, c - b)
        xad = safe_ratio(d - a, a - x)

        return xab, abc, bcd, xad

    def isCrabPattern(self, opened, close, low, high, indices, prices, ratios, error_percent=10):
        err_min = (100 - error_percent) / 100
        err_max = (100 + error_percent) / 100
        
        if len(prices) < 5:
            return False
        xab, abc, bcd, xad = self.get_harmonic_ratios_from_prices(prices)
        if (xab >= 0.382 * err_min and xab <= 0.618 * err_max and
            abc >= 0.382 * err_min and abc <= 0.886 * err_max and
            (bcd >= 2.24 * err_min and bcd <= 3.618 * err_max or
            xad >= 1.618 * err_min and xad <= 1.618 * err_max)):
            return True
        return False

    def isGartleyPattern(self, opened, close, low, high, indices, prices, ratios, error_percent=10):
        err_min = (100 - error_percent) / 100
        err_max = (100 + error_percent) / 100
        if len(prices) < 5:
            return False
        xab, abc, bcd, xad = self.get_harmonic_ratios_from_prices(prices)
        if (xab >= 0.618 * err_min and xab <= 0.618 * err_max and
            abc >= 0.382 * err_min and abc <= 0.886 * err_max and
            ((bcd >= 1.272 * err_min and bcd <= 1.618 * err_max) or
            (xad >= 0.786 * err_min and xad <= 0.786 * err_max))):
            return True
        return False

    def isDeepCrabPattern(self, opened, close, low, high, indices, prices, ratios, error_percent=10):
        err_min = (100 - error_percent) / 100
        err_max = (100 + error_percent) / 100
        if len(prices) < 5:
            return False
        xab, abc, bcd, xad = self.get_harmonic_ratios_from_prices(prices)
        if (xab >= 0.886 * err_min and xab <= 0.886 * err_max and
            abc >= 0.382 * err_min and abc <= 0.886 * err_max and
            ((bcd >= 2.00 * err_min and bcd <= 3.618 * err_max) or
            (xad >= 1.618 * err_min and xad <= 1.618 * err_max))):
            return True
        return False

    def isBatPattern(self, opened, close, low, high, indices, prices, ratios, error_percent=10):
        err_min = (100 - error_percent) / 100
        err_max = (100 + error_percent) / 100
        if len(prices) < 5:
            return False
        xab, abc, bcd, xad = self.get_harmonic_ratios_from_prices(prices)
        if (xab >= 0.382 * err_min and xab <= 0.50 * err_max and
            abc >= 0.382 * err_min and abc <= 0.886 * err_max and
            ((bcd >= 1.618 * err_min and bcd <= 2.618 * err_max) or
            (xad >= 0.886 * err_min and xad <= 0.886 * err_max))):
            return True
        return False

    #length tuning
    def isButterflyPattern(self, opened, close, low, high, indices, prices, ratios, error_percent=10):
        err_min = (100 - error_percent) / 100
        err_max = (100 + error_percent) / 100
        if len(prices) < 5:
            return False
        xab, abc, bcd, xad = self.get_harmonic_ratios_from_prices(prices)

        if (xab >= 0.786 * err_min and xab <= 0.786 * err_max and
            abc >= 0.382 * err_min and abc <= 0.886 * err_max and
            ((bcd >= 1.618 * err_min and bcd <= 2.618 * err_max) or
            (xad >= 1.272 * err_min and xad <= 1.618 * err_max))):
            return True
        return False

    def isDoublePattern(self, high, low, indices, prices, dirs, max_risk_per_reward=40):
        # 获取zigzag点和方向
        if len(indices) < 4 or len(dirs) < 4:
            return None  # 不足4个点无法画
        
        # 取倒数第2和第3段的线段
        x1 = indices[-3]
        y1 = prices[-3]
        x2 = indices[-2]
        y2 = prices[-2]

        midline = prices[-2]
        midlineIndex = indices[-2]
        risk = abs(y2 - y1)
        reward = abs(y2 - midline)
        riskPerReward = round(risk * 100 / (risk + reward), 2) if (risk + reward) != 0 else 100

        # 检查是否为double top/bottom
        doubleTop = dirs[-2] == 1 and dirs[-4] == 2 and dirs[-3] == -1 and riskPerReward < max_risk_per_reward
        doubleBottom = dirs[-2] == -1 and dirs[-4] == -2 and dirs[-3] == 1 and riskPerReward < max_risk_per_reward

        if doubleTop or doubleBottom:
            return True
        return False

    def isSharkPattern(self, opened, close, low, high, indices, prices, ratios, error_percent=10):
        err_min = (100 - error_percent) / 100
        err_max = (100 + error_percent) / 100
        if len(prices) < 5:
            return False
        xab, abc, bcd, xad = self.get_harmonic_ratios_from_prices(prices)
        if (abc >= 1.13 * err_min and abc <= 1.618 * err_max and
            bcd >= 1.618 * err_min and bcd <= 2.24 * err_max and
            xad >= 0.886 * err_min and xad <= 1.13 * err_max):
            return True
        return False

    def isCypherPattern(self, opened, close, low, high, indices, prices, ratios, error_percent=10):
        err_min = (100 - error_percent) / 100
        err_max = (100 + error_percent) / 100
        if len(prices) < 5:
            return False
        xab, abc, bcd, xad = self.get_harmonic_ratios_from_prices(prices)
        if (xab >= 0.382 * err_min and xab <= 0.618 * err_max and
            abc >= 1.13 * err_min and abc <= 1.414 * err_max and
            ((bcd >= 1.272 * err_min and bcd <= 2.00 * err_max) or
            (xad >= 0.786 * err_min and xad <= 0.786 * err_max))):
            return True
        return False

    def isThreeDrivesPattern(self, opened, close, low, high, indices, prices, ratios, error_percent=10):
        err_min = (100 - error_percent) / 100
        err_max = (100 + error_percent) / 100
        indices, prices, _, ratios = self.pine_zigzag_exact(high, low, length=2, deviation=0, max_size=30)
        if len(prices) < 6:
            return False
        # 3 drive 需要 yxaRatio
        x, a, b, c, d, y = prices[-7:-1]
        def safe_ratio(numer, denom):
            return abs(numer) / abs(denom) if abs(denom) > 1e-6 else 0
        yxa = safe_ratio(a - x, y - x)
        xab = safe_ratio(b - a, a - x)
        abc = safe_ratio(c - b, b - a)
        bcd = safe_ratio(d - c, c - b)
        if (yxa >= 0.618 * err_min and yxa <= 0.618 * err_max and
            xab >= 1.27 * err_min and xab <= 1.618 * err_max and
            abc >= 0.618 * err_min and abc <= 0.618 * err_max and
            bcd >= 1.27 * err_min and bcd <= 1.618 * err_max):
            return True
        return False

    def isFiveZeroPattern(self, opened, close, low, high, indices, prices, ratios, error_percent=10):
        err_min = (100 - error_percent) / 100
        err_max = (100 + error_percent) / 100
        indices, prices, _, ratios = self.pine_zigzag_exact(high, low, length=2, deviation=0, max_size=30)
        if len(prices) < 5:
            return False
        xab, abc, bcd, xad = self.get_harmonic_ratios_from_prices(prices)
        if (xab >= 1.13 * err_min and xab <= 1.618 * err_max and
            abc >= 1.618 * err_min and abc <= 2.24 * err_max and
            bcd >= 0.5 * err_min and bcd <= 0.5 * err_max):
            return True
        return False

    def isBottomPinBar(self, low, high, close, opened):
        line = np.min([opened[len(opened)-1], close[len(close)-1]]) - low[len(low)-1]
        volume = 2.2 * np.abs(opened[len(opened)-1] - close[len(close)-1])
        centerVolume = (opened[len(opened)-1] + close[len(close)-1])/2
        centerLine = (high[len(high)-1] + low[len(low)-1])/2
        return (line > volume) and (centerVolume > centerLine)

    def isTopPinBar(self, low, high, close, opened):
        line = high[len(high)-1] - np.max([opened[len(opened)-1], close[len(close)-1]])
        volume = 2.2 * np.abs(opened[len(opened)-1] - close[len(close)-1])
        centerVolume = (opened[len(opened)-1] + close[len(close)-1])/2
        centerLine = (high[len(high)-1] + low[len(low)-1])/2
        return (line > volume) and (centerVolume < centerLine)

    #3k线判别
    def isBottom3k(self, low, high):  
        #low[0] > low[-1], low[-2] > low[-1], high[0] > high[-2]
        return (low[len(low)-1] > low[len(low)-2]) and (low[len(low)-3] > low[len(low)-2]) and (low[len(low)-1] > low[len(low)-3])

    def isBottom2B(self, volume, opened, close):
        # -- price
        priceMatches2BPattern = (opened[-3] > close[-3]) and (opened[-2] < close[-2])\
                                and (opened[-2] <= (close[-3] + (opened[-3] - close[-3])*0.05))\
                                and (close[-2] > opened[-3])
        # -- volume
        volumeMatches2BPattern = (volume[-3] < volume[-2])

        # -- price
        priceMatches2BPatternMinusOne = (opened[-4] > close[-4]) and (opened[-3] < close[-3])\
                                and (opened[-3] <= (close[-4] + (opened[-4] - close[-4])*0.05))\
                                and (close[-3] > opened[-4])
        # -- volume
        volumeMatches2BPatternMinusOne = (volume[-4] < volume[-3])

        # --indicator
        return (priceMatches2BPattern and volumeMatches2BPattern) \
               or (priceMatches2BPatternMinusOne and volumeMatches2BPatternMinusOne)

    def tdDeteminator(self, td, needtd8):
        td9PositiveFlag = False
        td9NegativeFlag = False
        td13PositiveFlag = False
        td13NegativeFlag = False

        if ((td[len(td) - 1] in (9,9.0)) or (td[len(td) - 2] in (9,9.0))):
            td9PositiveFlag = True;

        if ((td[len(td) - 1] in (-9,-9.0)) or (td[len(td) - 2] in (-9,-9.0))):
            td9NegativeFlag = True;

        if ((td[len(td) - 1] in (13, 13.0)) or (td[len(td) - 2] in (13, 13.0))):
            td13PositiveFlag = True;

        if ((td[len(td) - 1] in (-13, -13.0)) or (td[len(td) - 2] in (-13, -13.0))):
            td13NegativeFlag = True;

        return td9PositiveFlag, td9NegativeFlag, td13PositiveFlag, td13NegativeFlag;

    def isOverceedingTriangleLine(self, loc_ids, ohlcv):
        indexX1 = loc_ids[0]
        indexX2 = loc_ids[1]
        priceX1 = ohlcv['close'][indexX1] if ohlcv['close'][indexX1] > ohlcv['open'][indexX1] else ohlcv['open'][indexX1];
        priceX2 = ohlcv['close'][indexX2] if ohlcv['close'][indexX2] > ohlcv['open'][indexX1] else ohlcv['open'][indexX2];
        slope = self.getSlope(priceX1, indexX1, priceX2, indexX2);
        slopedPrice = self.calculatePriceAtGivenPlace(slope, indexX1, priceX1);
        return self.isGreaterThanSlopedPrice(slopedPrice, ohlcv);

    def isGreaterThanSlopedPrice(self, slopedPrice, ohlcv):
        # close[0] > open[0] && close[0] > estimatedValue && close[-1] <= estimatedValue
        if (ohlcv[0] > slopedPrice):
            return True;
        else:
            return False;

    def calculatePriceAtGivenPlace(self, slope, indexX2, x2):
        return slope * indexX2 + x2;

    def getSlope(self, x1, indexX1, x2, indexX2):
        return (x2 - x1) / (indexX2 - indexX1);

    def candleOverEma(self, opened, close, ema):
        currentCandleOverEma = (opened[len(opened)-1] < ema[len(ema)-1]) and (ema[len(ema)-1] < close[len(close)-1])
        previousCandleIsNotOverEma = not ((opened[len(opened)-2] < ema[len(ema)-2]) and (ema[len(ema)-2] < close[len(close)-2]))
        if currentCandleOverEma and previousCandleIsNotOverEma:
            return True;

    def getVariance(self, delta_macd, n):
        delta_max = np.max(np.abs(delta_macd));
        # maxMinNormalization = lambda x : (x - delta_min) / (delta_max - delta_min);
        # normalizedDeltaMacd = maxMinNormalization(delta_macd);
        variance = np.std(delta_macd[0 - n:], ddof=1);
        mean = np.mean(delta_macd[0 - n:]);
        return (variance, mean, delta_max)

    #check if ema7 is crossing over ema65
    def ema7OverEma65(self, ema7, ema65):
        N = 5
        #check 5 is below all lines
        arr = []
        for index in range(1, N):
            arr.append((ema7[len(ema7)-index] > ema65[len(ema65)-index]))
            if ((ema7[len(ema7)-index-1] < ema65[len(ema65)-index-1]) and (ema7[len(ema7)-index] > ema65[len(ema65)-index])):
                if(all(flag == True for flag in arr)):
                    return True;
        return False;

    #check if ema7 is crossing over ema22
    def ema7OverEma22(self, ema7, ema22):
        N = 5
        #check 5 is below all lines
        arr = []
        for index in range(1, N):
            arr.append((ema7[len(ema7)-index] > ema22[len(ema22)-index]))
            if ((ema7[len(ema7)-index-1] < ema22[len(ema22)-index-1]) and (ema7[len(ema7)-index] > ema22[len(ema22)-index])):
                if(all(flag == True for flag in arr)):
                    return True;
        return False;

    #check if ema7 is crossing over ema33
    def ema7OverEma33(self, ema7, ema33):
        N = 5
        #check 5 is below all lines
        arr = []
        for index in range(1, N):
            arr.append((ema7[len(ema7)-index] > ema33[len(ema33)-index]))
            if ((ema7[len(ema7)-index-1] < ema33[len(ema33)-index-1]) and (ema7[len(ema7)-index] > ema33[len(ema33)-index])):
                if(all(flag == True for flag in arr)):
                    return True;
        return False;

    def lastNKIsPositive(self, distance_close_open):
        N = 3;
        for i in range(N):
            if (distance_close_open[len(distance_close_open)-i-1] < 0):
                return False;
        return True;

######################## main strategy #######################################
    def detectFirstMacdPositiveSlotPosition(self, macd):
        flag = False;
        for i in range(len(macd)-1, -1, -1):
            if (macd[i] > 0):
                if (flag == True):
                    return i + 1;
                else:
                    flag = True;

                if(i == 0):
                    return 0;
            elif (flag == True) :
                return i;

    def detectMacdVolumeShrinked(self, macd, start):
        maxIndex = self.getIndexOfMacdPeak(macd, start)
        max = macd[(maxIndex-len(macd))]
        loc = maxIndex
        for index, value in enumerate(macd[(maxIndex - len(macd)):]):
            if(value < max):
                return True;
            loc = loc + 1
        return False;

    #deprecated
    def detectBottomDivergenceIsPositiveMacd(self, macd, data, start):
        minIndex = self.getIndexOfMacdValley(macd, start)
        min = data[(minIndex-len(macd))]
        loc = minIndex
        for index, value in enumerate(data[(minIndex-len(macd)):]):
            if(value < min):
                if(macd[ index + (minIndex-len(macd)) ] > 0):
                    return True;
            loc = loc + 1
        return False;

    #段内底背离
    #macd=[1, 3, -3, -4, -1, -3, -1]
    #data=[10, 9, 8, 7, 8, 5, 8]
    def detectBottomDivergence(self, delta_macd, data, macd_signal):
        try:
          delta_len = (len(data) - len(macd_signal))
          zeroMacd = self.detectMacdSlots(delta_macd, 0, "negative")
          if not zeroMacd:
              return False;

          (start, end) = zeroMacd
          min = self.getIndexOfMacdValley(delta_macd, start, end)
          for i in range(min, end, 1):
            if(0 > delta_macd[i] > delta_macd[min]) and (data[i + delta_len] < data[min + delta_len]) \
                    and (macd_signal[i] < 0 and macd_signal[min] < 0):
                return True;
        except  Exception as e:
          print("段内底背离 异常:")
          print(e)
        return False

    #段内顶背离
    def detectPeakDivergence(self, delta_macd, data, macd_signal):
        try:
          delta_len = (len(data) - len(macd_signal))
          zeroMacd = self.detectMacdSlots(delta_macd, 0, "positive")
          if not zeroMacd:
              return False;

          (start, end) = zeroMacd
          maxx = self.getIndexOfMacdPeak(delta_macd, start, end)
          for i in range(maxx, end, 1):
            if(0 < delta_macd[i] < delta_macd[maxx]) and (data[i + delta_len] > data[maxx + delta_len]) \
                    and (macd_signal[i] > 0 and macd_signal[maxx] > 0):
                return True;
        except  Exception as e:
          print("段内顶背离 异常:")
          print(e)
        return False

    #分立跳空底背离
    def detectMultipleBottomDivergence(self, delta_macd, data, macd_signal):
        try:
          delta_len = (len(data) - len(macd_signal))
          zeroMacd = self.detectMacdSlots(delta_macd, 0, "negative")
          firstMacd = self.detectMacdSlots(delta_macd, 1, "negative")
          if not zeroMacd or not firstMacd:
            return False;

          (start1, end1) = zeroMacd
          (start2, end2) = firstMacd
          min1 = self.getIndexOfMacdValley(delta_macd, start1, end1)
          min2 = self.getIndexOfMacdValley(delta_macd, start2, end2)
          if (delta_macd[min2] < delta_macd[min1] < 0) \
                and (data[min2 + delta_len] > data[min1 + delta_len]) \
                and (macd_signal[min2] < 0 and macd_signal[min1] < 0):
            return True;
          else:
            return False;
        except Exception as e:
          print("分立跳空底背离:")
          print(e)
        return False

    #分立跳空顶背离
    def detectMultiplePeakDivergence(self, delta_macd, data, macd_signal):
        try:
          delta_len = (len(data) - len(macd_signal))
          zeroMacd = self.detectMacdSlots(delta_macd, 0, "positive")
          firstMacd = self.detectMacdSlots(delta_macd, 1, "positive")
          if not zeroMacd or not firstMacd:
            return False;

          (start1, end1) = zeroMacd
          (start2, end2) = firstMacd
          max1 = self.getIndexOfMacdPeak(delta_macd, start1, end1)
          max2 = self.getIndexOfMacdPeak(delta_macd, start2, end2)
          if (delta_macd[max2] > delta_macd[max1] > 0) \
                and (data[max2 + delta_len] < data[max1 + delta_len]) \
                and (macd_signal[max1] > 0 and macd_signal[max2] > 0):
            return True;
          else:
            return False;
        except Exception as e:
          print("分立跳空顶背离:")
          print(e)
        return False

    def detectMacdSlots(self, macd, times, direction):
        start = len(macd)-1
        initialPoint = start
        directionIsPositive = (direction == 'positive');
        if (macd[start] > 0) ^ directionIsPositive:
            return (-1, -1)
        start = self.walksOneSlotLength(macd, start);
        if(times == 0):
            return (start+1, initialPoint)
        for i in range(start, -1, -1):
            i = self.walksOneSlotLength(macd, i);
            slotStart = i
            i = self.walksOneSlotLength(macd, i);
            times = times - 1;
            if (times == 0):
                return (i+1, slotStart)

    def walksOneSlotLength(self, slot, start):
        isPositive = (slot[start] > 0);
        for i in range(start, -1, -1):
            if (not (isPositive^(slot[i] <= 0))):
                return i;
        return -1;


    #Test: a=[1,2,3,4,5,6,-1,-2]
    def detectLastMacdNegativeSlots(self, macd):
        flag = False;
        for i in range(len(macd)-1, -1, -1):
            if (macd[i] > 0):
                if(flag == True):
                    return i+1;
            elif (flag == False):
                flag = True;

    def getIndexOfMacdPeak(self, macd, start, end):
        maxx = start
        for i in range(start, end):
            if(macd[i] > macd[maxx]):
                maxx = i;
        return maxx;

    def getIndexOfMacdValley(self, macd, start, end):
        min = start
        for i in range(start, end):
            if(macd[i] < macd[min]):
                min = i;
        return min;
 ################################################################

    def isTheIntersectionPointCloseToBePositive(self, macd, macd_signal, n, intersectionValueAndMin):
        return self.calIntersectionPointRate(self.GetIntersectPointofLines(self.organizeDataPoint(macd, macd_signal, n))[0], macd, intersectionValueAndMin) is not None ;

    def organizeDataPoint(self, macd, macd_signal, n):
        return (macd[len(macd)-1-n], 1, macd[len(macd)-n], 2, macd_signal[len(macd_signal)-1-n], 1, macd_signal[len(macd_signal)-n], 2);

    def calIntersectionPointRate(self, intersectionValue, macd, intersectionValueAndMin): #intersectionRate
        (result, min) = self.lastNMinusMacdVolume(macd)
        intersectionValueAndMin[0] = intersectionValue;
        intersectionValueAndMin[1] = min;
        return intersectionValueAndMin;

    def GeneralEquation(self, first_x,first_y,second_x,second_y):
        A=second_y - first_y
        B=first_x - second_x
        C=second_x*first_y - first_x*second_y
        return A,B,C

    def GetIntersectPointofLines(self, vector):
        x1 = vector[0]
        y1 = vector[1]
        x2 = vector[2]
        y2 = vector[3]
        x3 = vector[4]
        y3 = vector[5]
        x4 = vector[6]
        y4 = vector[7]
        A1,B1,C1 = self.GeneralEquation(x1,y1,x2,y2)
        A2, B2, C2 = self.GeneralEquation(x3,y3,x4,y4)
        m=A1*B2-A2*B1
        if m==0:
            print("no intersection")
        else:
            x=(C2*B1-C1*B2)/m
            y=(C1*A2-C2*A1)/m
        return x,y

    def lastNBoolIsNarrowed(self, delta_boll,n):
        test_arr = delta_boll[0-n:];
        for x in test_arr:
            if(x > 5.0): #narrowed area
                return (False, test_arr);
        return (True, test_arr);

    def lastNDMIIsPositive(self, delta_dmi,n):
        if ((delta_dmi[len(delta_dmi) - 1] > 0 and
            delta_dmi[len(delta_dmi) - 2] < 0)

        or

            (delta_dmi[len(delta_dmi) - 1] > 0 and
            delta_dmi[len(delta_dmi) - 2] > 0 and
            delta_dmi[len(delta_dmi) - 3] < 0)

        or 
            (delta_dmi[len(delta_dmi) - 1] > 0 and
            delta_dmi[len(delta_dmi) - 2] > 0 and
            delta_dmi[len(delta_dmi) - 3] > 0 and
            delta_dmi[len(delta_dmi) - 4] < 0)

        or
            (delta_dmi[len(delta_dmi) - 1] > 0 and
            delta_dmi[len(delta_dmi) - 2] > 0 and
            delta_dmi[len(delta_dmi) - 3] > 0 and
            delta_dmi[len(delta_dmi) - 4] > 0 and
            delta_dmi[len(delta_dmi) - 5] < 0)
        or
            (delta_dmi[len(delta_dmi) - 1] > 0 and
            delta_dmi[len(delta_dmi) - 2] > 0 and
            delta_dmi[len(delta_dmi) - 3] > 0 and
            delta_dmi[len(delta_dmi) - 4] > 0 and
            delta_dmi[len(delta_dmi) - 5] > 0 and
            delta_dmi[len(delta_dmi) - 6] < 0)
        ):

            return True;
        return False;

        # theOneBefore = delta_dmi[len(delta_dmi) - n - 1];
        # flag = self.lastNDataIsPositive(delta_dmi, n);
        # if(flag):
        #     return (theOneBefore < 0);
        # else:
        #     return flag;

    def lastNDataIsPositive(self, delta, n):
        test_arr = delta[0 - n:];
        for x in test_arr:
            if (x < 0):
                return False;
        return True;

    def printResult(self, new_result, exchange, market_pair, output_mode, criteriaType, indicatorTypeCoinMap):
        output_data = deepcopy(new_result[exchange][market_pair])
        print(
                                exchange,
                                criteriaType,
                                self.output[output_mode](output_data, criteriaType, self.exchange_interface.get_name_by_market_pair(market_pair), exchange, indicatorTypeCoinMap),
                                end=''
            )

    def toDb(self, td_name, exchange, market_pair):
        candle_period = self.indicator_conf['macd'][0]['candle_period'];
        sql = "INSERT INTO td(td_name, market_pair, candle_period, exchange, create_date) " \
              "select distinct %s,%s,%s,%s,%s from dual where not exists( select 1 from td " \
              "where td_name = %s and market_pair = %s and candle_period = %s and exchange = %s " \
              "and create_date >= date_sub(%s, interval 10 day) and create_date <= %s)"
        val = (td_name, self.exchange_interface.get_name_by_market_pair(market_pair), candle_period, exchange, date.today(),
               td_name, self.exchange_interface.get_name_by_market_pair(market_pair), candle_period, exchange, date.today(), date.today())
        Behaviour.mydb.cursor().execute(sql, val)
        Behaviour.mydb.commit()  # 数据表内容有更新，必须使用到该语句
        print(Behaviour.mydb.cursor().rowcount, "记录插入成功。")

    def lastNMacdsArePositive(self, delta_macd, macd, n):
        (result, min) = self.lastNMinusMacdVolume(macd)
        test_arr = delta_macd[0-n:];
        theOneBefore = delta_macd[len(delta_macd)-n-1];
        for x in test_arr:
            if(x < 0 or (abs(x/min) >= 0.3)): #the rate of macd value divided by the megative highest macd value is less than 0.3
                return False;
            
        return True;
        
    def lastNMinusDecreased(self, delta_macd, min):
        for i in range(len(delta_macd)):
            if(delta_macd[i] == min and i != 0):
                return True;
            else:
                return False;
    
    def lastNMinusMacdVolume(self, delta_macd):
        result = []
        min = 0
        negativeStarted = False
        for x in reversed(delta_macd):
            if(x <= 0):
                negativeStarted = True
                if(x < min):
                    min = x
                result.append(x)
            elif negativeStarted: #always return from here
                return (result, min)
        return (result, min)
    
    def _hasMinusBefore(self, arr, informant):
        n = len(arr)
        period = informant[0]["candle_period"]
        if period == '1d':
            N = 10
        elif period == '1w':
            N = 3
        else:
            N = 10
        try:
            for index in range(n-1, n-1-N, -1):
                if arr[index] <= 0:
                    return True;
            return False;
        except Exception as e:         
            print("An exception occurred:" + str(e))
    
    def _lis(self, arr):
        n = len(arr)
        m = [0]*n
        for x in range(n-2,-1,-1):
            for y in range(n-1,x,-1):
                if arr[x] < arr[y] and m[x] <= m[y]:
                    m[x] += 1
            max_value = max(m)
            result = []
            for i in range(n):
                if m[i] == max_value:
                    result.append(arr[i])
                    max_value -= 1
        return result
     
 
    def _get_indicator_results(self, exchange, market_pair):
        """Execute the indicator analysis on a particular exchange and pair.

        Args:
            exchange (str): The exchange to get the indicator results for.
            market_pair (str): The pair to get the market pair results for.

        Returns:
            list: A list of dictinaries containing the results of the analysis.
        """

        results = { indicator: list() for indicator in self.indicator_conf.keys() }
        historical_data_cache = dict()

        # for indicator in self.indicator_conf:
        #     if indicator not in self.indicator_dispatcher:
        #         self.logger.warn("No such indicator %s, skipping.", indicator)
        #         continue

        for indicator in self.indicator_dispatcher:
            for indicator_conf in self.indicator_conf[indicator]:
                if indicator_conf['enabled']:
                    candle_period = indicator_conf['candle_period']
                else:
                    self.logger.debug("%s is disabled, skipping.", indicator)
                    continue

                if candle_period not in historical_data_cache:
                    historical_data_cache[candle_period] = self._get_historical_data(
                        market_pair,
                        exchange,
                        candle_period
                    )
                
                if historical_data_cache[candle_period]:
                    analysis_args = {
                        'historical_data': historical_data_cache[candle_period],
                        'signal': indicator_conf['signal'],
                        'hot_thresh': indicator_conf['hot'],
                        'cold_thresh': indicator_conf['cold']
                    }

                    if 'period_count' in indicator_conf:
                        analysis_args['period_count'] = indicator_conf['period_count']

                    results[indicator].append({
                        'result': self._get_analysis_result(
                            self.indicator_dispatcher,
                            indicator,
                            analysis_args,
                            market_pair
                        ),
                        'config': indicator_conf
                    })
        return results


    def _get_informant_results(self, exchange, market_pair):
        """Execute the informant analysis on a particular exchange and pair.

        Args:
            exchange (str): The exchange to get the indicator results for.
            market_pair (str): The pair to get the market pair results for.

        Returns:
            list: A list of dictinaries containing the results of the analysis.
        """

        results = { informant: list() for informant in self.informant_conf.keys() }
        historical_data_cache = dict()

        # for informant in self.informant_conf:
        #     if informant not in self.informant_dispatcher:
        #         self.logger.warn("No such informant %s, skipping.", informant)
        #         continue
        for informant in self.informant_dispatcher:

            for informant_conf in self.informant_conf[informant]:
                if informant_conf['enabled']:
                    candle_period = informant_conf['candle_period']
                else:
                    self.logger.debug("%s is disabled, skipping.", informant)
                    continue

                if candle_period not in historical_data_cache:
                    historical_data_cache[candle_period] = self._get_historical_data(
                        market_pair,
                        exchange,
                        candle_period
                    )

                if historical_data_cache[candle_period]:
                    analysis_args = {
                        'historical_data': historical_data_cache[candle_period]
                    }

                    if 'period_count' in informant_conf:
                        analysis_args['period_count'] = informant_conf['period_count']

                    results[informant].append({
                        'result': self._get_analysis_result(
                            self.informant_dispatcher,
                            informant,
                            analysis_args,
                            market_pair
                        ),
                        'config': informant_conf
                    })

        return results


    def _get_crossover_results(self, new_result):
        """Execute crossover analysis on the results so far.

        Args:
            new_result (dict): A dictionary containing the results of the informant and indicator
                analysis.

        Returns:
            list: A list of dictinaries containing the results of the analysis.
        """

        crossover_dispatcher = self.strategy_analyzer.crossover_dispatcher()
        results = { crossover: list() for crossover in self.crossover_conf.keys() }

        for crossover in self.crossover_conf:
            if crossover not in crossover_dispatcher:
                self.logger.warn("No such crossover %s, skipping.", crossover)
                continue

            for crossover_conf in self.crossover_conf[crossover]:
                if not crossover_conf['enabled']:
                    self.logger.debug("%s is disabled, skipping.", crossover)
                    continue
                
                key_indicator = new_result[crossover_conf['key_indicator_type']][crossover_conf['key_indicator']][crossover_conf['key_indicator_index']]
                crossed_indicator = new_result[crossover_conf['crossed_indicator_type']][crossover_conf['crossed_indicator']][crossover_conf['crossed_indicator_index']]

                dispatcher_args = {
                    'key_indicator': key_indicator['result'],
                    'key_signal': crossover_conf['key_signal'],
                    'key_indicator_index': crossover_conf['key_indicator_index'],
                    'crossed_indicator': crossed_indicator['result'],
                    'crossed_signal': crossover_conf['crossed_signal'],
                    'crossed_indicator_index': crossover_conf['crossed_indicator_index']
                }

                results[crossover].append({
                    'result': crossover_dispatcher[crossover](**dispatcher_args),
                    'config': crossover_conf
                })
        return results


    def _get_historical_data(self, market_pair, exchange, candle_period):
        """Gets a list of OHLCV data for the given pair and exchange.

        Args:
            market_pair (str): The market pair to get the OHLCV data for.
            exchange (str): The exchange to get the OHLCV data for.
            candle_period (str): The timeperiod to collect for the given pair and exchange.

        Returns:
            list: A list of OHLCV data.
        """
        historical_data = list()
        try:
            historical_data = self.exchange_interface.get_historical_data(
                market_pair,
                exchange,
                candle_period
            )
        except RetryError:
            self.logger.error(
                'Too many retries fetching information for pair %s, skipping',
                market_pair
            )
        except ExchangeError:
            self.logger.error(
                'Exchange supplied bad data for pair %s, skipping',
                market_pair
            )
        except ValueError as e:
            self.logger.error(
                'Invalid data encountered while processing pair %s, skipping',
                market_pair
            )
        except AttributeError:
            self.logger.error(
                'Something went wrong fetching data for %s, skipping',
                market_pair
            )
        return historical_data


    def _get_analysis_result(self, dispatcher, indicator, dispatcher_args, market_pair):
        """Get the results of performing technical analysis

        Args:
            dispatcher (dict): A dictionary of functions for performing TA.
            indicator (str): The name of the desired indicator.
            dispatcher_args (dict): A dictionary of arguments to provide the analyser
            market_pair (str): The market pair to analyse

        Returns:
            pandas.DataFrame: Returns a pandas.DataFrame of results or an empty string.
        """

        try:
            results = dispatcher[indicator](**dispatcher_args)
        except TypeError:
            self.logger.info(
                'Invalid type encountered while processing pair %s for indicator %s, skipping',
                market_pair,
                indicator
            )
            self.logger.info(traceback.format_exc())
            results = str()
        return results
