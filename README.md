# RLTest
Redis Labs Test Framework, allow to run redis and modules tests on verity of environment.

Supported Environment: oss, oss-cluster, enterprise, enterprise-cluster

# Install
Clone the repository and run:
```
$ python setup.py install

```

# Usage:
```
usage: RLTest [-h] [--module MODULE] [--module-args MODULE_ARGS]
              [--env {oss,oss-cluster,enterprise,enterprise-cluster}]
              [--oss-redis-path OSS_REDIS_PATH]
              [--enterprise-redis-path ENTERPRISE_REDIS_PATH]
              [--stop-on-failure] [--verbose] [--debug]
              [--tests-dir TESTS_DIR] [--test-name TEST_NAME]
              [--tests-file TESTS_FILE] [--env-only] [--log-dir LOG_DIR]
              [--use-slaves] [--shards-count SHARDS_COUNT]
              [--download-enterprise-binaries]
              [--proxy-binary-path PROXY_BINARY_PATH]
              [--enterprise-lib-path ENTERPRISE_LIB_PATH] [--env-reuse]
              [--use-aof] [--debug-print]	
```

# Test Example
```
from RLTest import Env
import time


class testExample():
    '''
    run all tests on a single env without taking
    env down between tests
    '''
    def __init__(self):
        self.env = Env()

    def testExample(self):
        con = self.env.getConnection()
        con.set('x', 1)
        self.env.assertEqual(con.get('x'), '1')

    def testExample1(self):
        con = self.env.getConnection()
        con.set('x', 1)
        self.env.assertEqual(con.get('x'), '1')
        self.env.assertFalse(True)

    def testExample2(self):
        con = self.env.getConnection()
        con.set('x', 1)
        self.env.assertEqual(con.get('x'), '1')


# run each test on different env
def test_example():
    env = Env()
    con = env.getConnection()
    con.set('x', 1)
    env.assertEqual(con.get('x'), '1')


def test_example_2():
    env = Env()
    env.assertOk(env.cmd('set', 'x', '1'))
    env.expect('get', 'x').equal('1')

    env.expect('lpush', 'list', '1', '2', '3').equal(3)
    env.expect('lrange', 'list', '0', '-1').debugPrint().contains('1')
    env.debugPrint('this is some debug printing')


def test_example_3():
    env = Env(useSlaves=True, env='oss')
    con = env.getConnection()
    con.set('x', 1)
    con2 = env.getSlaveConnection()
    time.sleep(0.1)
    env.assertEqual(con2.get('x'), '1')
```