import json

import structlog


class ObjectMapperUtil():

    def __init__(self):
        self.logger = structlog.get_logger()

    def toJson(self, object):
        return json.dumps(object).encode('utf-8')


