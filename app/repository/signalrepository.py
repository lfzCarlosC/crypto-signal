import structlog
import redis

from repository.utils import ObjectMapperUtil


class SignalRepository():

    def __init__(self):
        self.logger = structlog.get_logger()
        self.object_mapper_util = ObjectMapperUtil()

    def storeIndicator(self, key, coins):
        conn = redis.Redis(host = 'localhost', port = 6379, decode_responses=True)
        indicatorMapStr = self.object_mapper_util.toJson(coins)
        conn.set(key, indicatorMapStr)
        conn.close()
