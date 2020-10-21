import traceback

from outputs import Output


class diff_cycles_resonance():

    trendColor = {
        "TD9共振多头":"green"
    }

    def __init__(self):
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

    def _test_strategies(self, market_data, output_mode):
        new_result = dict()
        for exchange in market_data:

            for market_pair in market_data[exchange]:

                new_result[exchange][market_pair]['indicators'] = self._get_indicator_results(
                    exchange,
                    market_pair
                )

                new_result[exchange][market_pair]['informants'] = self._get_informant_results(
                    exchange,
                    market_pair
                )

                try:
                    indicators = new_result[exchange][market_pair]['indicators']
                    td9NegativeFlag = False
                    td13NegativeFlag = False

                    if ('td' in indicators):
                        td4h = indicators['td']['4h']['result']['td'];
                        td1d = indicators['td']['1d']['result']['td'];
                        td7d = indicators['td']['7d']['result']['td'];
                        td12h = indicators['td']['12h']['result']['td'];
                        td6h = indicators['td']['6h']['result']['td'];
                        td1h = indicators['td']['1h']['result']['td'];

                except Exception as e:
                    print(e)
                    traceback.print_exc()


    def tdDeteminator(self, gap, td):
        td9PositiveFlag = False
        td9NegativeFlag = False
        td13PositiveFlag = False
        td13NegativeFlag = False
        td1PositiveFlag = False
        td2PositiveFlag = False

        if (td[len(td) - gap] == 9):
            td9PositiveFlag = True;

        if (td[len(td) - gap] == -9):
            td9NegativeFlag = True;

        if (td[len(td) - gap] == 13):
            td13PositiveFlag = True;

        if (td[len(td) - gap] == -13):
            td13NegativeFlag = True;

        if (td[len(td) - gap] == 1):
            td1PositiveFlag = True;

        if (td[len(td) - gap] == 2):
            td2PositiveFlag = True;

        return td9PositiveFlag, td9NegativeFlag, td13PositiveFlag, td13NegativeFlag, td1PositiveFlag, td2PositiveFlag;
