import os
from unittest import TestCase

REDIS_BINARY = os.environ.get("REDIS_BINARY", "redis-server")

TLS_CERT = os.environ.get("TLS_CERT", "./tls/redis.crt")
TLS_KEY = os.environ.get("TLS_KEY", "./tls/redis.key")
TLS_CACERT = os.environ.get("TLS_CACERT", "./tls/ca.crt")


def whereis(program):
    for path in os.environ.get('PATH', '').split(':'):
        if os.path.exists(os.path.join(path, program)) and \
                not os.path.isdir(os.path.join(path, program)):
            return os.path.join(path, program)
    return None

class TestCommon(TestCase):

    def testVersionRuntime(self):
        import RLTest as rltest_pkg
        self.assertNotEqual("",rltest_pkg.__version__)
