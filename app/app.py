#!/usr/local/bin/python
"""Main app module
"""

import time
import sys

import logs
import conf
import structlog

from conf import Configuration
from exchange import ExchangeInterface
from exchange_cryptal import CryptalExchangeInterface
from exchange_ashare import AshareExchangeInterface
from notification import Notifier
from behaviour import Behaviour

def main():
    """Initializes the application
    """
     # Load settings and create the config object
    config = Configuration()
    settings = config.settings

    # Set up logger
    logs.configure_logging(settings['log_level'], settings['log_mode'])
    logger = structlog.get_logger()

    # Configure and run configured behaviour.
    exchange_interface = AshareExchangeInterface(config.exchanges) if 'A股' in config.exchanges else CryptalExchangeInterface(config.exchanges)

    notifier = Notifier(config.notifiers)

    behaviour = Behaviour(
        config,
        exchange_interface,
        notifier
    )

    while True:
        # 不管程序何时启动/醒来，都精确计算到下一个调度锚点（如最近的早 8 点）
        # 还需要睡多久；若当前已经落在容差窗口内，返回 0，立即执行。
        sleep_seconds = behaviour.seconds_until_next_run(settings['update_interval'])
        if sleep_seconds > 0:
            logger.info(
                "Sleeping for %s seconds until next scheduled run (Asia/Shanghai)",
                sleep_seconds
            )
            time.sleep(sleep_seconds)
        behaviour.run(settings['market_pairs'], settings['output_mode'])

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)