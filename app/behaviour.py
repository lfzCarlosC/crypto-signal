""" Runs the default analyzer, which performs two functions...
1. Output the signal information to the prompt.
2. Notify users when a threshold is crossed.
"""

from copy import deepcopy

import structlog
from ccxt import ExchangeError
from tenacity import RetryError

from analysis import StrategyAnalyzer
from outputs import Output

import numpy as np
from collections import defaultdict
import traceback

import sys

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
        "MACD 量能上涨异常": "green",
        "macd金叉信号": "green",
        "0轴上macd金叉信号": "green",
        "macd金叉信号 + DMI": "green",
        "DMI+": "green",
        "TD+底部2B信号": "green"
    }

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

        market_data = self.exchange_interface.get_exchange_markets(markets=market_pairs)

        self.logger.info("Using the following exchange(s): %s", list(market_data.keys()))

        self.truncateFile()
        new_result = self._test_strategies(market_data, output_mode)

        self.notifier.notify_all(new_result)

    def truncateFile(self):
        f = open(sys.argv[2],'r+')
        f.truncate()

    def isCloseTo(self, start, actual, target):
        if((target-actual)/(actual-start) < 0.05):
            return True;

    def _test_strategies(self, market_data, output_mode):
        """Test the strategies and perform notifications as required

        Args:
            market_data (dict): A dictionary containing the market data of the symbols to analyze.
            output_mode (str): Which console output mode to use.
        """
        f = open(sys.argv[2],'a')
        indicatorModes = sys.argv[3]
        indicatorTypeCoinMap = defaultdict(list)
        new_result = dict()
        for exchange in market_data:
            if exchange not in new_result:
                new_result[exchange] = dict()

            for market_pair in market_data[exchange]:

                if not (market_pair.lower().endswith("usdt") or market_pair.lower().endswith("usd")):
                    continue;

                if market_pair not in new_result[exchange]:
                    new_result[exchange][market_pair] = dict()

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

                    ohlcv = new_result[exchange][market_pair]['informants']['ohlcv'][0]['result']

                    upperband = new_result[exchange][market_pair]['informants']['bollinger_bands'][0]['result']['upperband'] ;
                    middleband = new_result[exchange][market_pair]['informants']['bollinger_bands'][0]['result']['middleband'] ;
                    lowerband = new_result[exchange][market_pair]['informants']['bollinger_bands'][0]['result']['lowerband'] ;
                    opened = ohlcv['open'];
                    close = ohlcv['close'] ;
                    distance_close_open = close - opened;
                    low = ohlcv['low'];
                    high = ohlcv['high'] ;
                    volume = ohlcv['volume'] ;
                    plus_di = new_result[exchange][market_pair]['indicators']['plus_di'][0]['result']['plus_di'] ;
                    minus_di = new_result[exchange][market_pair]['indicators']['minus_di'][0]['result']['minus_di'] ;
                    delta_di = plus_di - minus_di
                    macd = new_result[exchange][market_pair]['indicators']['macd'][0]['result']['macd'];  #white line
                    macd_signal = new_result[exchange][market_pair]['indicators']['macd'][0]['result']['macdsignal']; #yellow line
                    delta_macd = new_result[exchange][market_pair]['indicators']['macd'][0]['result']['macdhist']; #macd volume

                    # rsi = new_result[exchange][market_pair]['indicators']['rsi'][0]['result']['rsi'];
                    # stoch_slow_k = new_result[exchange][market_pair]['indicators']['stoch_rsi'][0]['result']['slow_k'];
                    # stoch_slow_d = new_result[exchange][market_pair]['indicators']['stoch_rsi'][0]['result']['slow_d'];
                    # kt = new_result[exchange][market_pair]['indicators']['kdj'][0]['result']['k'];
                    # dt = new_result[exchange][market_pair]['indicators']['kdj'][0]['result']['d'];
                    # jt = new_result[exchange][market_pair]['indicators']['kdj'][0]['result']['j'];

                    ######################################### ema indicator
                    #now contains: ema7IsOverEma65 ema7IsOverEma22 ema7IsOverEma33
                    # try:
                    #     ema7 = new_result[exchange][market_pair]['informants']['ema7'][0]['result']['ema'];
                    #     ema22 = new_result[exchange][market_pair]['informants']['ema22'][0]['result']['ema'];
                    #     ema33 = new_result[exchange][market_pair]['informants']['ema33'][0]['result']['ema'];
                    #     ema65 = new_result[exchange][market_pair]['informants']['ema65'][0]['result']['ema'];
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
                    td9NegativeFlag42B = False
                    td13NegativeFlag42B = False
                    if('td' in indicators):
                        td = indicators['td'][0]['result']['td'];
                        (td9PositiveFlag, td9NegativeFlag, td13PositiveFlag, td13NegativeFlag) = self.tdDeteminator(2, td)

                        ###################################### 2B indicator
                        # This 2B is based on TD bottom point. It pick ups the 2B point near/at TD 9 point.
                        # argrelextrema is not very useful due to massive but not distinguished valley points.
                        # peakIndex = new_result[exchange][market_pair]['indicators']['peak_loc'][0]['result']['peak_loc']
                        # valleyIndex = new_result[exchange][market_pair]['indicators']['valley_loc'][0]['result']['valley_loc']

                        #- bottom 2B for later use
                        (td9PositiveFlag42B, td9NegativeFlag42B, td13PositiveFlag42B, td13NegativeFlag42B) = self.tdDeteminator(3, td)

                    ########################################## goldenMacdFork
                    intersectionValueAndMin = [0, 0]
                    if not (len(macd) == 0 \
                            or len(macd_signal) == 0 \
                            or len(delta_macd) == 0):

                      goldenForkMacd = (

                        (delta_macd[len(delta_macd)-1] >= 0  and delta_macd[len(delta_macd)-2] <= 0
                         and self.isTheIntersectionPointCloseToBePositive(macd, macd_signal, 1, intersectionValueAndMin)) or

                        (delta_macd[len(delta_macd)-1] >= 0  and delta_macd[len(delta_macd)-2] >= 0 and delta_macd[len(delta_macd)-3] <= 0
                         and self.isTheIntersectionPointCloseToBePositive(macd, macd_signal, 2, intersectionValueAndMin)) or

                        (delta_macd[len(delta_macd)-1] >= 0  and delta_macd[len(delta_macd)-2] >= 0 and delta_macd[len(delta_macd)-3] >= 0
                         and delta_macd[len(delta_macd)-4] <= 0
                         and self.isTheIntersectionPointCloseToBePositive(macd, macd_signal, 3, intersectionValueAndMin))
                      )

                      macdVolumeIncreasesSurprisingly = (delta_macd[len(delta_macd) - 1] >= 0) and (
                                delta_macd[len(delta_macd) - 2] >= 0) and (delta_macd[len(delta_macd) - 1] >= (
                                delta_macd[len(delta_macd) - 2] * 3))

                    ############################################## deadForkMacd
                    # deadForkMacd = (
                    #     delta_macd[len(delta_macd) - 1] <= 0 and delta_macd[len(delta_macd) - 2] >= 0
                    # )
                    #
                    # macdVolumeMinusIsDecreased = False
                    # (macdVolumeMinus,min) = self.lastNMinusMacdVolume(delta_macd[0:len(delta_macd)-1])
                    # if( len(macdVolumeMinus) != 0 and self.lastNMinusDecreased(macdVolumeMinus,min) ):
                    #     macdVolumeMinusIsDecreased = True

                    ############################################## goldenForkKdj
                    # len_k = len(kt)
                    # len_d = len(dt)
                    # len_j = len(jt)
                    # goldenForkKdj = (
                    #     ((dt[len_d-2] >= kt[len_k-2]) and (kt[len_k-2] >= jt[len_j-2]))
                    #     and
                    #     ((dt[len_d-1] <= kt[len_k-1]) and (kt[len_k-1] <= jt[len_j-1]))
                    # )

                    ############################################# deadForkKdj
                    # deadForkKdj = (
                    #     ((dt[len_d - 2] <= kt[len_k - 2]) and (kt[len_k - 2] <= jt[len_j - 2]))
                    #     and
                    #     ((dt[len_d - 1] >= kt[len_k - 1]) and (kt[len_k - 1] >= jt[len_j - 1]))
                    # )

                    ############################################# dmi
                    lastNDMIIsPositiveVolume = (self.lastNDataIsPositive(delta_di, 3) > 0) or (self.lastNDataIsPositive(delta_di, 2) > 0) or (self.lastNDataIsPositive(delta_di, 1) > 0)
                    lastNDMIIsPositiveFork = self.lastNDMIIsPositive(delta_di, 3)

                    ############################################# macdBottomDivergence
                    hasBottomDivergence = self.detectBottomDivergence(delta_macd, low, macd_signal)
                    hasPeakDivergence = self.detectPeakDivergence(delta_macd, high, macd_signal)
                    hasMultipleBottomDivergence = self.detectMultipleBottomDivergence(delta_macd, low, macd_signal)
                    hasMultiplePeakDivergnce = self.detectMultiplePeakDivergence(delta_macd, high, macd_signal)

                    ############################################# bollCross
                    # bollCross = False
                    # if (len(middleband) != 0):
                    #     delta_close_middleband = close - middleband;
                    #     delta_low_middleband = low - middleband;
                    #     if ((delta_close_middleband.iloc[-1] > 0 and delta_low_middleband.iloc[-1] < 0) or
                    #         (delta_close_middleband.iloc[-2] > 0 and delta_low_middleband.iloc[-2] < 0)
                    #         ):
                    #         bollCross = True

                    ########################################### rsi < 30
                    # rsiIsLessThan30 = (rsi[len(rsi)-1] <= 30)

                    ########################################### detectMacdVolumeIsShrinked
                    # detectMacdVolumeIsShrinked = self.detectMacdVolumeShrinked(delta_macd, self.detectFirstMacdPositiveSlotPosition(delta_macd))

                    ########################################### stochrsi
                    # len_sd = len(stoch_slow_d)
                    # len_sk = len(stoch_slow_k)
                    # stochrsi_goldenfork = (
                    #     (stoch_slow_d[len_sd-2] >= stoch_slow_k[len_sk-2])
                    #     and
                    #     (stoch_slow_d[len_sd-1] <= stoch_slow_k[len_sk-1])
                    # )
                    #
                    # stochrsi_deadfork = (
                    #     (stoch_slow_d[len_sd - 2] <= stoch_slow_k[len_sk - 2])
                    #     and
                    #     (stoch_slow_d[len_sd - 1] >= stoch_slow_k[len_sk - 1])
                    # )

                    ########################################## volume is 3 times greater than before
                    # len_volume = len(volume)
                    # volumeIsGreater = volume[len_volume-1] >= 3 * volume[len_volume-2]

                    ############################################ macd正值平滑
                    #c(macd+)>5 + D<0.1
                    #counts: 10,
                    flatPositive = False
                    positiveFlag = self.lastNDataIsPositive(delta_macd, 10);
                    if(positiveFlag):
                        variance, mean, max = self.getVariance(delta_macd, 10);
                        # print(market_pair + "===" + str(variance) + "===" + str(mean) + "===" + str(max))
                        flatPositive = self.lastNDataIsPositive(delta_macd, 10) and (variance <= 0.01) and (mean/max <= 0.2)

                    #narrowedBoll
                    #(narrowedBoll, test_arr) = self.lastNBoolIsNarrowed((upperband/lowerband)**10, 5) # counts of narrowed points
                    #continuousKRise
                    lastNKPositive = self.lastNKIsPositive(distance_close_open)

                    ######################################## report coins that match indicators
                    if(indicatorModes == 'easy'):

                        if (goldenForkMacd and intersectionValueAndMin[0]>0):
                           self.printResult(new_result, exchange, market_pair, output_mode, "0轴上macd金叉信号", indicatorTypeCoinMap)

                        if (rsiIsLessThan30 and goldenForkMacd):
                            self.printResult(new_result, exchange, market_pair, output_mode, "macd金叉信号 + rsi小于30", indicatorTypeCoinMap)

                        # if (lastNKPositive):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "连续3根k阳线", indicatorTypeCoinMap)

                        if (stochrsi_goldenfork and goldenForkMacd):
                            self.printResult(new_result, exchange, market_pair, output_mode,"stochrsi强弱指标金叉 + macd金叉信号", indicatorTypeCoinMap)

                        if (macdBottomDivergence and lastNDMIIsPositive):
                            self.printResult(new_result, exchange, market_pair, output_mode, "macd底背离 + DMI", indicatorTypeCoinMap)

                        if (macdBottomDivergence and stochrsi_goldenfork):
                            self.printResult(new_result, exchange, market_pair, output_mode, "macd底背离 + stochrsi强弱指标金叉", indicatorTypeCoinMap)

                        if (volumeIsGreater):
                            self.printResult(new_result, exchange, market_pair, output_mode, "volume放量涨幅超过3倍",
                                             indicatorTypeCoinMap)

                        #contract market
                        if (market_pair[-1:].isdigit()):

                            if (goldenForkKdj):
                                self.printResult(new_result, exchange, market_pair, output_mode, "kdj金叉信号", indicatorTypeCoinMap)

                            if (deadForkKdj):
                                self.printResult(new_result, exchange, market_pair, output_mode, "kdj死叉信号", indicatorTypeCoinMap)

                            # if (detectMacdVolumeIsShrinked and stochrsi_deadfork):
                            #         self.printResult(new_result, exchange, market_pair, output_mode, "macd量能萎缩 + stochrsi强弱指标死叉", indicatorTypeCoinMap)

                            #stochrsi_deadfork and deadForkMacd

                    if(indicatorModes == 'custom'):

                        # if(self.isOverceedingTriangleLine(peakLoc, ohlcv)):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "上升突破三角形",
                        #                      indicatorTypeCoinMap)

                        if (macdVolumeIncreasesSurprisingly):
                            self.printResult(new_result, exchange, market_pair, output_mode, "MACD 量能上涨异常",
                                             indicatorTypeCoinMap)

                        if (td9NegativeFlag):
                            self.printResult(new_result, exchange, market_pair, output_mode, "TD 底部 9位置", indicatorTypeCoinMap)

                        if (td13NegativeFlag):
                            self.printResult(new_result, exchange, market_pair, output_mode, "TD 底部 13位置", indicatorTypeCoinMap)

                        if (td9PositiveFlag):
                            self.printResult(new_result, exchange, market_pair, output_mode, "TTD 顶部 9位置", indicatorTypeCoinMap)

                        if (td13PositiveFlag):
                            self.printResult(new_result, exchange, market_pair, output_mode, "TTD 顶部 13位置", indicatorTypeCoinMap)

                        if (td13NegativeFlag42B or td9NegativeFlag42B):
                            if (self.isBottom2B(volume, opened, close)):
                                self.printResult(new_result, exchange, market_pair, output_mode, "TD+底部2B信号", indicatorTypeCoinMap)

                        if (goldenForkMacd):
                            self.printResult(new_result, exchange, market_pair, output_mode, ("0轴上" if intersectionValueAndMin[0] > 0 else "") + "macd金叉信号", indicatorTypeCoinMap)

                        if (lastNDMIIsPositiveFork):
                            self.printResult(new_result, exchange, market_pair, output_mode, "DMI+", indicatorTypeCoinMap)
                        #
                        # if (ema7IsOverEma65):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "7日线上穿65日ema线", indicatorTypeCoinMap)
                        #
                        # if (ema7IsOverEma22):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "7日线上穿22日ema线", indicatorTypeCoinMap)
                        #
                        # if (ema7IsOverEma33):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "7日线上穿33日ema线", indicatorTypeCoinMap)
                        #
                        # if (candleIsOverEma):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "k线上穿33日ema线", indicatorTypeCoinMap)

                        # if (flatPositive):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "macd正值平滑", indicatorTypeCoinMap)

                        (start, end) = self.detectMacdSlots(delta_macd, 0, 'positive')
                        if (goldenForkMacd and (intersectionValueAndMin[0] > 0.2 * 2 * delta_macd[
                            self.getIndexOfMacdValley(delta_macd, start, end)])):
                            self.printResult(new_result, exchange, market_pair, output_mode, "接近0轴的macd金叉信号",
                                             indicatorTypeCoinMap)

                        if (lastNDMIIsPositiveFork and goldenForkMacd):
                            self.printResult(new_result, exchange, market_pair, output_mode, "macd金叉信号 + DMI",
                                             indicatorTypeCoinMap)

                        # if (goldenForkMacd and stochrsi_goldenfork):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "stochrsi强弱指标金叉 + macd金叉信号", indicatorTypeCoinMap)


                        # if (macdBottomDivergence and lastNDMIIsPositiveFork):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "macd底背离 + DMI", indicatorTypeCoinMap)

                        # if (macdBottomDivergence and stochrsi_goldenfork):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "macd底背离 + stochrsi强弱指标金叉", indicatorTypeCoinMap)

                        # if (goldenForkKdj and goldenForkMacd):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "kdj金叉信号 + macd金叉信号", indicatorTypeCoinMap)

                        # if (goldenForkKdj and lastNDMIIsPositiveFork):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "kdj金叉信号 + DMI", indicatorTypeCoinMap)

                        # if (stochrsi_goldenfork and lastNDMIIsPositiveFork):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "stochrsi强弱指标金叉 + DMI", indicatorTypeCoinMap)

                        # compound indicator
                        if (hasBottomDivergence):
                            self.printResult(new_result, exchange, market_pair, output_mode, "段内底背离", indicatorTypeCoinMap)

                        if (hasPeakDivergence):
                            self.printResult(new_result, exchange, market_pair, output_mode, "段内顶背离", indicatorTypeCoinMap)

                        if (hasMultipleBottomDivergence):
                            self.printResult(new_result, exchange, market_pair, output_mode, "分立跳空底背离", indicatorTypeCoinMap)

                        if (hasMultiplePeakDivergnce):
                            self.printResult(new_result, exchange, market_pair, output_mode, "分立跳空顶背离", indicatorTypeCoinMap)

                        # if (stochrsi_goldenfork and goldenForkKdj and lastNDMIIsPositiveVolume and (delta_macd[len(delta_macd)-1] > delta_macd[len(delta_macd)-2])):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "stochrsi强弱指标金叉 + kdj金叉信号 + DMI+ + macd量能减小", indicatorTypeCoinMap)

                        # if (stochrsi_goldenfork and macdIsDecreased):
                        #     self.printResult(new_result, exchange, market_pair, output_mode, "stochrsi强弱指标金叉 + macd下跌量能减弱",
                        #                      indicatorTypeCoinMap)

######################################################
                except Exception as e:
                    print("An exception occurred for " + market_pair + ":" + exchange)
                    print(e)
                    traceback.print_exc()

        #write everything to the email
        for indicator in indicatorTypeCoinMap:
            f.write("<p style='color: " + Behaviour.trendColor[indicator] +"; font-size:30px;'> <b>" + indicator + "</b></p>\n");
            for coin in indicatorTypeCoinMap[indicator]:
                f.write("<p style='color: " + Behaviour.trendColor[indicator] + ";'>  币种/交易对:" +  coin.replace('/','') + " " + indicator + '</p>\n' );
        f.close();
        
        # Print an empty line when complete
        return new_result

    def isBottom2B(self, volume, opened, close):
        # -- price
        priceMatches2BPattern = (opened[-2] < close[-2]) and (opened[-2] <= opened[-3]) and (close[-2] > close[-3])
        # -- volume
        volumeMatches2BPattern = (volume[-3] < volume[-2])
        # --indicator
        return (priceMatches2BPattern and volumeMatches2BPattern)

    def tdDeteminator(self, gap, td):
        td9PositiveFlag = False
        td9NegativeFlag = False
        td13PositiveFlag = False
        td13NegativeFlag = False
        if (td[len(td) - gap] == 9):
            td9PositiveFlag = True;

        if (td[len(td) - gap] == -9):
            td9NegativeFlag = True;

        if (td[len(td) - gap] == 13):
            td13PositiveFlag = True;

        if (td[len(td) - gap] == -13):
            td13NegativeFlag = True;

        return td9PositiveFlag, td9NegativeFlag, td13PositiveFlag, td13NegativeFlag;

    def isOverceedingTriangleLine(self, loc_ids, ohlcv):
        indexX1 = loc_ids[0]
        indexX2 = loc_ids[1]
        priceX1 = ohlcv['close'][indexX1] if ohlcv['close'][indexX1] > ohlcv['open'][indexX1] else ohlcv['open'][indexX1];
        priceX2 = ohlcv['close'][indexX2] if ohlcv['close'][indexX2] > ohlcv['open'][indexX1] else ohlcv['open'][indexX2];
        slope = self.getSlope(priceX1, indexX1, priceX2, indexX2);
        slopedPrice = self.calculatePriceAtGivenPlace(slope, indexX1, priceX1);
        return self.isGreaterThanSlopedPrice(slopedPrice);

    def isGreaterThanSlopedPrice(self, slopedPrice):
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
        theOneBefore = delta_dmi[len(delta_dmi) - n - 1];
        flag = self.lastNDataIsPositive(delta_dmi, n);
        if(flag):
            return (theOneBefore < 0);
        else:
            return flag;

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
                                self.output[output_mode](output_data, criteriaType, market_pair, exchange, indicatorTypeCoinMap),
                                end=''
            )
    
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
            self.logger.error(e)
            self.logger.error(
                'Invalid data encountered while processing pair %s, skipping',
                market_pair
            )
            self.logger.debug(traceback.format_exc())
        except AttributeError:
            self.logger.error(
                'Something went wrong fetching data for %s, skipping',
                market_pair
            )
            self.logger.debug(traceback.format_exc())
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
