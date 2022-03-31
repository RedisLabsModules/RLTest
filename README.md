[![license](https://img.shields.io/github/license/RedisLabsModules/RLTest.svg)](https://github.com/RedisLabsModules/RLTest/blob/master/LICENSE)
[![PyPI version](https://badge.fury.io/py/rltest.svg)](https://badge.fury.io/py/rltest)
[![CI](https://github.com/RedisLabsModules/RLTest/workflows/CI/badge.svg)](https://github.com/RedisLabsModules/RLTest/actions)
[![Version](https://img.shields.io/github/release/RedisLabsModules/RLTest.svg)](https://github.com/RedisLabsModules/RLTest/releases/latest)
[![Codecov](https://codecov.io/gh/RedisLabsModules/RLTest/branch/master/graph/badge.svg)](https://codecov.io/gh/RedisLabsModules/RLTest)
[![Known Vulnerabilities](https://snyk.io/test/github/RedisLabsModules/RLTest/badge.svg?targetFile=pyproject.toml)](https://snyk.io/test/github/RedisLabsModules/RLTest?targetFile=pyproject.toml)



# RLTest

Redis Labs Test Framework, allow running tests on redis and modules on a variety of environments.

Supported Environment: oss, oss-cluster, enterprise, enterprise-cluster

The framework allow you to write a test without environment specification and then run the test on all supported environment.


# Install
```
$ pip install git+https://github.com/RedisLabsModules/RLTest.git@master

```

# Usage:
```
$ RLTest --help
usage: RLTest [-h] [--version] [--module MODULE] [--module-args MODULE_ARGS]
              [--env {oss,oss-cluster,enterprise,enterprise-cluster,existing-env,cluster_existing-env}]
              [--existing-env-addr EXISTING_ENV_ADDR]
              [--shards_ports SHARDS_PORTS]
              [--cluster_address CLUSTER_ADDRESS]
              [--oss_password OSS_PASSWORD]
              [--cluster_credentials CLUSTER_CREDENTIALS]
              [--cluster_node_timeout CLUSTER_NODE_TIMEOUT]
              [--internal_password INTERNAL_PASSWORD]
              [--oss-redis-path OSS_REDIS_PATH]
              [--enterprise-redis-path ENTERPRISE_REDIS_PATH]
              [--stop-on-failure] [-x] [--verbose] [--debug] [-t TEST]
              [--env-only] [--clear-logs] [--log-dir LOG_DIR] [--use-slaves]
              [--shards-count SHARDS_COUNT] [--download-enterprise-binaries]
              [--proxy-binary-path PROXY_BINARY_PATH]
              [--enterprise-lib-path ENTERPRISE_LIB_PATH] [-r]
              [--use-aof] [--use-rdb-preamble]
              [--debug-print] [-V] [--vg-suppressions VG_SUPPRESSIONS]
              [--vg-options VG_OPTIONS] [--vg-no-leakcheck] [--vg-verbose]
              [--vg-no-fail-on-errors] [-i] [--debugger DEBUGGER] [-s]
              [--check-exitcode] [--unix] [--randomize-ports] [--collect-only]
              [--tls] [--tls-cert-file TLS_CERT_FILE]
              [--tls-key-file TLS_KEY_FILE]
              [--tls-ca-cert-file TLS_CA_CERT_FILE]

Test Framework for redis and redis module

optional arguments:
  -h, --help            show this help message and exit
  --version             Print RLTest version and exit (default: False)
  --module MODULE       path to the module file. You can use `--module` more
                        than once but it imples that you explicitly specify
                        `--module-args` as well. Notice that on enterprise the
                        file should be a zip file packed with
                        [RAMP](https://github.com/RedisLabs/RAMP). (default:
                        None)
  --module-args MODULE_ARGS
                        arguments to give to the module on loading (default:
                        None)
  --env {oss,oss-cluster,enterprise,enterprise-cluster,existing-env,cluster_existing-env}, -e {oss,oss-cluster,enterprise,enterprise-cluster,existing-env,cluster_existing-env}
                        env on which to run the test (default: oss)
  --existing-env-addr EXISTING_ENV_ADDR
                        Address of existing env, relevent only when running
                        with existing-env, cluster_existing-env (default:
                        localhost:6379)
  --shards_ports SHARDS_PORTS
                        list of ports, the shards are listening to, relevent
                        only when running with cluster_existing-env (default:
                        None)
  --cluster_address CLUSTER_ADDRESS
                        enterprise cluster ip, relevent only when running with
                        cluster_existing-env (default: None)
  --oss_password OSS_PASSWORD
                        set redis password, relevant for oss and oss-cluster
                        environment (default: None)
  --cluster_credentials CLUSTER_CREDENTIALS
                        enterprise cluster cluster_credentials
                        "username:password", relevent only when running with
                        cluster_existing-env (default: None)
  --cluster_node_timeout CLUSTER_NODE_TIMEOUT
                        cluster node timeout in milliseconds
  --internal_password INTERNAL_PASSWORD
                        Give an ability to execute commands on shards
                        directly, relevent only when running with
                        cluster_existing-env (default: )
  --oss-redis-path OSS_REDIS_PATH
                        path to the oss redis binary (default: redis-server)
  --enterprise-redis-path ENTERPRISE_REDIS_PATH
                        path to the entrprise redis binary (default:
                        ~/.RLTest/opt/redislabs/bin/redis-server)
  --stop-on-failure     stop running on failure (default: False)
  -x, --exit-on-failure
                        Stop test execution and exit on first assertion
                        failure (default: False)
  --verbose, -v         print more information about the test (default: 0)
  --debug               stop before each test allow gdb attachment (default:
                        False)
  -t TEST, --test TEST  Specify test to run, in the form of "file:test"
                        (default: None)
  --env-only            start the env but do not run any tests (default:
                        False)
  --clear-logs          deleting the log direcotry before the execution
                        (default: False)
  --log-dir LOG_DIR     directory to write logs to (default: ./logs)
  --use-slaves          run env with slaves enabled (default: False)
  --shards-count SHARDS_COUNT
                        Number shards in bdb (default: 1)
  --download-enterprise-binaries
                        run env with slaves enabled (default: False)
  --proxy-binary-path PROXY_BINARY_PATH
                        dmc proxy binary path (default:
                        ~/.RLTest/opt/redislabs/bin/dmcproxy)
  --enterprise-lib-path ENTERPRISE_LIB_PATH
                        path of needed libraries to run enterprise binaries
                        (default: ~/.RLTest/opt/redislabs/lib/)
  -r, --env-reuse       reuse exists env, this feature is based on best
                        efforts, if the env can not be reused then it will be
                        taken down. (default: False)
  --use-aof             use aof instead of rdb (default: False)
  --use-rdb-preamble    use rdb preamble when rewriting aof file (default: True)
  --debug-print         print debug messages (default: False)
  -V, --vg, --use-valgrind
                        running redis under valgrind (assuming valgrind is
                        install on the machine) (default: False)
  --vg-suppressions VG_SUPPRESSIONS
                        path valgrind suppressions file (default: None)
  --vg-options VG_OPTIONS
                        valgrind [options] (default: None)
  --vg-no-leakcheck     Don't perform a leak check (default: False)
  --vg-verbose          Don't log valgrind output. Output to screen directly
                        (default: False)
  --vg-no-fail-on-errors
                        Dont Fail test when valgrind reported any errors in
                        the run.By default on RLTest the return value from
                        Valgrind will be used to fail the tests.Use this
                        option when you wish to dry-run valgrind but not fail
                        the test on valgrind reported errors. (default: False)
  -i, --interactive-debugger
                        runs the redis on a debuger (gdb/lldb)
                        interactivly.debugger interactive mode is only
                        possible on a single process and so unsupported on
                        cluste or with slaves.it is also not possible to use
                        valgrind on interactive mode.interactive mode direcly
                        applies: --no-output-catch and --stop-on-failure.it is
                        also implies that only one test will be run (if --env-
                        only was not specify), an error will be raise
                        otherwise. (default: False)
  --debugger DEBUGGER   Run specified command line as the debugger (default:
                        None)
  -s, --no-output-catch
                        all output will be written to the stdout, no log
                        files. (default: False)
  --check-exitcode      Check redis process exit code (default: False)
  --unix                Use Unix domain sockets instead of TCP (default:
                        False)
  --randomize-ports     Randomize Redis listening port assignment rather
                        thanusing default port (default: False)
  --collect-only        Collect the tests and exit (default: False)
  --tls                 Enable TLS Support and disable the non-TLS port
                        completely. TLS connections will be available at the
                        default non-TLS ports. (default: False)
  --tls-cert-file TLS_CERT_FILE
                        /path/to/redis.crt (default: None)
  --tls-key-file TLS_KEY_FILE
                        /path/to/redis.key (default: None)
  --tls-ca-cert-file TLS_CA_CERT_FILE
                        /path/to/ca.crt (default: None)

```

## Sample usages

### Multiple modules

```
RLTest --module modules/module1.so --module-args '' --module modules/module2.so --module-args ''
```

# Configuration File
By default, the framework search for configuration file on the current directory. The configuration file name is: config.txt.
It is possible to specify different configuration file on command line using the '@' prefix, for example:
```
RLTest @myConfig.txt # search for myConfig.txt configuration file
```
The configuration file format is the same as the command line argument, i.e : '--< param_name > < param_val >'.

It is also possible to comment a specific lines in the configuration file using '#'.

Example:

```
-vv
--clear-logs
#--debug
```


# Test Example

```python
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
