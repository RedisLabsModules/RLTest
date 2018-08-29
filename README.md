# RLTest
Redis Labs Test Framework, allow to run tests on redis and modules on verity of environment.

Supported Environment: oss, oss-cluster, enterprise, enterprise-cluster

The framework allow you to write a test without environment specification and then run the test on all supported environment.

# Install
```
$ pip install git+https://github.com/RedisLabsModules/RLTest.git@master

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
              [--use-aof] [--debug-print] [--use-valgrind]
              [--valgrind-suppressions-file VALGRIND_SUPPRESSIONS_FILE]
```

### module
load a spacific module to the environment, notice that on enterprise the file should be a zip file packed with [RAMP](https://github.com/RedisLabs/RAMP). might overide by the test.

### module-args
pass arguments to the loaded module. might overide by the test.

### env
the environment on which to run the tests (oss,oss-cluster,enterprise,enterprise-cluster), might overide by the test.

### oss-redis-path
path to the oss redis binary (default - redis-server)

### enterprise-redis-path
path to the enterprise redis binarty (default - ~/.RLTest/opt/redislabs/bin/redis-server).

### stop-on-failure
stop the tests run on failure, allows you to check what went wrong.

### verbose
increase verbosity, it is possible to write this options twice (-vv) to increase verbosity even more.

### debug
stop before each test execution and allow you to attach to any process with debuger.

### tests-dir
directory to search for tests (default - current directory).

### test-name
name of spacific test function to run.

### tests-file
file inside the test_dir to search for tests (if not specified the framework searches in all files)

### env-only
not running any tests, just setup the environment and keep it up for manual tests.

### log-dir
directory on which logs will be written to (default - ./logs).

### use-slaves
setup the environment with slaves. might overide by the test.

### shards-count
on cluster, setting the amount on required shards. might overide by the test.

### download-enterprise-binaries
downloading the enterprise binaries before running the tests and save it under ~/.RLTest/.

### proxy-binary-path
enterprise proxy binary path (default - ~/.RLTest/opt/redislabs/bin/dmcproxy)

### enterprise-lib-path
enterprise libraries requires for run (default - ~/.RLTest/opt/redislabs/lib/)

### use-aof
using aof instead of rdb, might overide by the test.

### use-valgrind
run redis under valgrind (assuming valgrind is installed on the machine).

### valgrind-suppressions-file
path to valgrind suppressions (not mandatory).


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
        self.env.assertFalse(True)  # check failure

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