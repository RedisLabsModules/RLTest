# RLTest
![CI](https://github.com/RedisLabsModules/RLTest/workflows/CI/badge.svg)

Redis Labs Test Framework, allow to run tests on redis and modules on verity of environments.

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
              [--tests-file TESTS_FILE] [--env-only] [--clear-logs]
              [--log-dir LOG_DIR] [--use-slaves] [--shards-count SHARDS_COUNT]
              [--download-enterprise-binaries]
              [--proxy-binary-path PROXY_BINARY_PATH]
              [--enterprise-lib-path ENTERPRISE_LIB_PATH] [--env-reuse]
              [--use-aof] [--debug-print] 
              [--use-valgrind] [--vg-verbose] [--vg-no-leakcheck]
              [--vg-options VALGRIND_OPTIONS]
              [--vg-suppressions VALGRIND_SUPPRESSIONS_FILE]
              [--interactive-debugger]
              [--debugger-args DEBUGGER_ARGS] [--no-output-catch]
```

### module
Load a spacific module to the environment, notice that on enterprise the file should be a zip file packed with [RAMP](https://github.com/RedisLabs/RAMP). might override by the test.

### module-args
Pass arguments to the loaded module. might override by the test.

### env
The environment on which to run the tests (oss,oss-cluster,enterprise,enterprise-cluster), might override by the test.

### oss-redis-path
Path to the oss redis binary (default - redis-server)

### enterprise-redis-path
Path to the enterprise redis binarty (default - ~/.RLTest/opt/redislabs/bin/redis-server).

### stop-on-failure
Stop the tests run on failure, allows you to check what went wrong.

### verbose
Increase verbosity, it is possible to write this options twice (-vv) to increase verbosity even more.

### debug
Stop before each test execution and allow you to attach to any process with debuger.

### tests-dir
Directory to search for tests (default - current directory).

### test-name
Name of spacific test function to run.

### tests-file
File inside the test_dir to search for tests (if not specified the framework searches in all files)

### env-only
Not running any tests, just setup the environment and keep it up for manual tests.

### log-dir
Directory on which logs will be written to (default - ./logs).

### use-slaves
Setup the environment with slaves. might override by the test.

### shards-count
On cluster, setting the amount on required shards. might override by the test.

### download-enterprise-binaries
Downloading the enterprise binaries before running the tests and save it under ~/.RLTest/.

### proxy-binary-path
Enterprise proxy binary path (default - ~/.RLTest/opt/redislabs/bin/dmcproxy)

### enterprise-lib-path
Enterprise libraries requires for run (default - ~/.RLTest/opt/redislabs/lib/)

### env-reuse
Reuse the existing env between tests. Notice that if some test requires a different env setting then the current env will be taken down (and a new one will be setup) regardless this parameter value.

### use-aof
Using aof instead of rdb, might override by the test.

### use-valgrind
Run redis under valgrind (assuming valgrind is installed on the machine).

### valgrind-suppressions-file
Path to valgrind suppressions (not mandatory).

### interactive-debugger
runs the redis on a debugger (gdb/lldb) interactivly.
debugger interactive mode is only possible on a single process and so unsupported on cluste or with slaves.
it is also not possible to use valgrind on interactive debugger.
interactive debugger direcly applies: --no-output-catch and --stop-on-failure.
it is also implies that only one test will be run (if --inv-only was not specify), an error will be raise otherwise.

### debugger-args
arguments to pass to the debugger.

### no-output-catch
all output will be written to the stdout, no log files.

# Configuration File
By default the framework search for configuration file on the current directory. The configuration file name is: config.txt.
It is possible to specify different configuration file on command line using the '@' prefix, for example:
```
RLTest @myConfig.txt # search for myConfig.txt configuration file
```
The configuration file format is the same as the command line argument, i.e : '--< param_name > < param_val >'.

It is also possible to comment a spacific lines in the configuration file using '#'.

Example:
```
-vv
--clear-logs
#--debug
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
