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

```

# Test Example
```
from RLTest import Env
import time


def test_example():
    env = Env()
    con = env.GetConnection()
    con.set('x', 1)
    env.AssertEqual(con.get('x'), '1')

def test_example_3():
    # it is possible to overide defualt values on env creation as this example shows
    env = Env(useSlaves=True, env='oss')
    con = env.GetConnection()
    con.set('x', 1)
    con2 = env.GetSlaveConnection()
    time.sleep(0.1)
    env.AssertEqual(con2.get('x'), '1')
```