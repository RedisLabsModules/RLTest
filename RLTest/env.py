# coding=utf-8
from __future__ import print_function

import contextlib
import inspect
import os
import sys
import unittest
import warnings

from .exists_redis import ExistsRedisEnv
from .redis_cluster import ClusterEnv
from .redis_enterprise_cluster import EnterpriseRedisClusterEnv
from .redis_std import StandardEnv
from .utils import Colors, expandBinary, fix_modules, fix_modulesArgs
from packaging import version


class TestAssertionFailure(Exception):
    pass


def genDeprecated(name, target):
    def method(*argc, **nargs):
        warnings.warn('%s is deprecated, use %s instead' % (str(name), str(target)), DeprecationWarning)
        return target(*argc, **nargs)
    return method


class Query:
    def __init__(self, env, *query, **options):
        self.query = query
        self.options = options
        self.env = env
        self.errorRaised = False
        self._evaluate()

    def _evaluate(self):
        try:
            self.res = self.env.cmd(*self.query, **self.options)
        except Exception as e:
            self.res = str(e)
            self.errorRaised = True

    def _prettyPrint(self, result, prefix='\t'):
        if type(result) is list:
            print(prefix + '[')
            for r in result:
                self._prettyPrint(r, prefix + '\t')
            print(prefix + ']')
            return
        print(prefix + str(result))

    def prettyPrint(self):
        self._prettyPrint(self.res)
        return self

    def debugPrint(self):
        self.env.debugPrint('query: %s, result: %s' % (self.query, self.res), force=True)
        return self

    def apply(self, fn):
        self.res = fn(self.res)
        return self

    def map(self, fn):
        self.res = list(map(fn, self.res))
        return self

    def equal(self, expected):
        self.env.assertEqual(self.res, expected, 1)
        return self

    def noEqual(self, expected):
        self.env.assertNotEqual(self.res, expected, 1)
        return self

    def true(self):
        self.env.assertTrue(self.res, 1)
        return self

    def false(self):
        self.env.assertFalse(self.res, 1)
        return self

    def ok(self):
        self.env.assertEqual(self.res, 'OK', 1)
        return self

    def contains(self, val):
        self.env.assertContains(val, self.res, 1)
        return self

    def notContains(self, val):
        self.env.assertNotContains(val, self.res, 1)
        return self

    def error(self):
        self.env.assertTrue(self.errorRaised, 1)
        return self

    def noError(self):
        self.env.assertFalse(self.errorRaised, 1)
        return self

    raiseError = genDeprecated('raiseError', error)
    notRaiseError = genDeprecated('notRaiseError', noError)


class Defaults:
    module = None
    module_args = None

    env = 'oss'
    binary = 'redis-server'
    proxy_binary = None
    re_binary = None
    re_libdir = None
    decode_responses = False
    use_aof = False
    use_rdb_preamble = True
    use_TLS = False
    tls_cert_file = None
    tls_key_file = None
    tls_ca_cert_file = None
    tls_passphrase = None
    debugger = None
    sanitizer = None
    debug_print = False
    debug_pause = False
    no_capture_output = False
    no_log = False
    exit_on_failure = False
    verbose = 0
    logdir = None
    use_slaves = False
    num_shards = 1
    external_addr = 'localhost:6379'
    use_unix = False
    randomize_ports = False
    oss_password = None
    cluster_node_timeout = None
    curr_test_name = None
    port=6379
    enable_debug_command=False

    def getKwargs(self):
        kwargs = {
            'modulePath': self.module,
            'moduleArgs': self.module_args,
            'port': self.port,
            'useSlaves': self.use_slaves,
            'useAof': self.use_aof,
            'useRdbPreamble': self.use_rdb_preamble,
            'dbDirPath': self.logdir,
            'debugger': self.debugger,
            'sanitizer': self.sanitizer,
            'noCatch': self.no_capture_output,
            'noLog': self.no_log,
            'verbose': self.verbose,
            'useTLS': self.use_TLS,
            'tlsCertFile': self.tls_cert_file,
            'tlsKeyFile': self.tls_key_file,
            'tlsCaCertFile': self.tls_ca_cert_file,
            'tlsPassphrase': self.tls_passphrase,
            'password': self.oss_password
        }
        return kwargs


class Env:
    RTestInstance = None
    EnvCompareParams = ['module', 'moduleArgs', 'env', 'useSlaves', 'shardsCount', 'useAof',
                        'useRdbPreamble', 'forceTcp', 'enableDebugCommand']

    def compareEnvs(self, env):
        if env is None:
            return False
        for param in Env.EnvCompareParams:
            if self.__dict__[param] != env.__dict__[param]:
                return False
        return True

    def __init__(self, testName=None, testDescription=None, module=None,
                 moduleArgs=None, env=None, useSlaves=None, shardsCount=None, decodeResponses=None,
                 useAof=None, useRdbPreamble=None, forceTcp=False, useTLS=False, tlsCertFile=None, tlsKeyFile=None,
                 tlsCaCertFile=None, tlsPassphrase=None, logDir=None, redisBinaryPath=None, dmcBinaryPath=None,
                 redisEnterpriseBinaryPath=None, noDefaultModuleArgs=False, clusterNodeTimeout = None,
                 freshEnv=False, enableDebugCommand=None):

        self.testName = testName if testName else Defaults.curr_test_name
        if self.testName is None:
            self.testName = '%s.%s' % (inspect.getmodule(inspect.currentframe().f_back).__name__, inspect.currentframe().f_back.f_code.co_name)
        self.testName = self.testName.replace(' ', '_')

        if testDescription:
            print(Colors.Gray('\tdescription: ' + testDescription))

        self.module = fix_modules(module, Defaults.module)
        if noDefaultModuleArgs:
            self.moduleArgs = fix_modulesArgs(self.module, moduleArgs)
        else:
            self.moduleArgs = fix_modulesArgs(self.module, moduleArgs, Defaults.module_args)
        self.env = env if env else Defaults.env
        self.useSlaves = useSlaves if useSlaves else Defaults.use_slaves
        self.shardsCount = shardsCount if shardsCount else Defaults.num_shards
        self.decodeResponses = decodeResponses if decodeResponses else Defaults.decode_responses
        self.useAof = useAof if useAof else Defaults.use_aof
        self.useRdbPreamble = useRdbPreamble if useRdbPreamble is not None else Defaults.use_rdb_preamble
        self.verbose = Defaults.verbose
        self.logDir = logDir if logDir else Defaults.logdir
        self.forceTcp = forceTcp
        self.debugger = Defaults.debugger
        self.sanitizer = Defaults.sanitizer
        self.useTLS = useTLS if useTLS else Defaults.use_TLS
        self.tlsCertFile = tlsCertFile if tlsCertFile else Defaults.tls_cert_file
        self.tlsKeyFile = tlsKeyFile if tlsKeyFile else Defaults.tls_key_file
        self.tlsCaCertFile = tlsCaCertFile if tlsCaCertFile else Defaults.tls_ca_cert_file
        self.tlsPassphrase = tlsPassphrase if tlsPassphrase else Defaults.tls_passphrase

        self.redisBinaryPath = expandBinary(redisBinaryPath) if redisBinaryPath else Defaults.binary
        self.dmcBinaryPath = expandBinary(dmcBinaryPath) if dmcBinaryPath else Defaults.proxy_binary
        self.redisEnterpriseBinaryPath = expandBinary(redisEnterpriseBinaryPath) if redisEnterpriseBinaryPath else Defaults.re_binary
        self.clusterNodeTimeout = clusterNodeTimeout if clusterNodeTimeout else Defaults.cluster_node_timeout
        self.port = Defaults.port
        self.enableDebugCommand = enableDebugCommand if enableDebugCommand else Defaults.enable_debug_command

        self.assertionFailedSummary = []

        if (not freshEnv) and Env.RTestInstance and Env.RTestInstance.currEnv and self.compareEnvs(Env.RTestInstance.currEnv):
            self.envRunner = Env.RTestInstance.currEnv.envRunner
        else:
            if Env.RTestInstance and Env.RTestInstance.currEnv:
                Env.RTestInstance.currEnv.stop()
            self.envRunner = self.getEnvByName()

        try:
            os.makedirs(self.logDir)
        except Exception:
            pass

        self.start()
        if self.verbose >= 2:
            print(Colors.Blue('\tenv data:'))
            self.envRunner.printEnvData('\t\t')

        if Env.RTestInstance:
            Env.RTestInstance.currEnv = self

        if Defaults.debug_pause:
            input('\tenv is up, attach to any process with gdb and press any button to continue.')

    def getEnvByName(self):
        verbose = False
        kwargs = self.getEnvKwargs()
        single_args = self.getSingleArgs()

        test_fname = self.testName.replace(':', '_')

        if self.env == 'oss':
            kwargs.update(single_args)
            kwargs['password'] = Defaults.oss_password
            return StandardEnv(redisBinaryPath=self.redisBinaryPath,
                               outputFilesFormat='%s-' + '%s-oss' % test_fname,
                               **kwargs)
        if self.env == 'enterprise':
            kwargs.update(single_args)
            kwargs['libPath'] = Defaults.re_libdir
            return StandardEnv(redisBinaryPath=self.redisEnterpriseBinaryPath,
                               outputFilesFormat='%s-' + '%s-oss' % test_fname,
                               **kwargs)
        if self.env == 'enterprise-cluster':
            kwargs['libPath'] = Defaults.re_libdir
            return EnterpriseClusterEnv(shardsCount=self.shardsCount,
                                        redisBinaryPath=self.redisEnterpriseBinaryPath,
                                        outputFilesFormat='%s-' + '%s-re-cluster' % test_fname,
                                        dmcBinaryPath=Defaults.proxy_binary,
                                        **kwargs)
        if self.env == 'oss-cluster':
            kwargs['password'] = Defaults.oss_password
            return ClusterEnv(shardsCount=self.shardsCount, redisBinaryPath=self.redisBinaryPath,
                              outputFilesFormat='%s-' + '%s-oss-cluster' % test_fname,
                              randomizePorts=Defaults.randomize_ports,
                              **kwargs)

        if self.env == 'existing-env':
            return ExistsRedisEnv(addr=Defaults.external_addr, **kwargs)

        if self.env == 'cluster_existing-env':
            return EnterpriseRedisClusterEnv(addr = Defaults.external_addr, password = Defaults.internal_password,
                                             shards_port=Defaults.shards_ports,
                                             cluster_address = Defaults.cluster_address,
                                             cluster_credentials= Defaults.cluster_credentials, **kwargs)

    def getSingleArgs(self):
        single_args = {}
        if Defaults.randomize_ports:
            single_args['port'] = 0
        if Defaults.use_unix:
            single_args['unix'] = True
        if self.forceTcp and self.env != 'existing-env':
            single_args['port'] = 0
            single_args.pop('unix', None)
        return single_args

    def getEnvKwargs(self):
        kwargs = {
            'modulePath': self.module,
            'moduleArgs': self.moduleArgs,
            'useSlaves': self.useSlaves,
            'decodeResponses': self.decodeResponses,
            'useAof': self.useAof,
            'useRdbPreamble': self.useRdbPreamble,
            'dbDirPath': self.logDir,
            'debugger': Defaults.debugger,
            'sanitizer': Defaults.sanitizer,
            'noCatch': Defaults.no_capture_output,
            'noLog': Defaults.no_log,
            'verbose': Defaults.verbose,
            'useTLS': self.useTLS,
            'tlsCertFile': self.tlsCertFile,
            'tlsKeyFile': self.tlsKeyFile,
            'tlsCaCertFile': self.tlsCaCertFile,
            'clusterNodeTimeout': self.clusterNodeTimeout,
            'tlsPassphrase': self.tlsPassphrase,
            'port': self.port,
            'enableDebugCommand': self.enableDebugCommand
        }
        return kwargs

    def start(self, masters = True, slaves = True ):
        self.envRunner.startEnv(masters, slaves)
        self.con = self.getConnection()

    def stop(self, masters = True, slaves = True):
        self.envRunner.stopEnv(masters, slaves)

    def getEnvStr(self):
        return self.env

    def getConnection(self, shardId=1):
        return self.envRunner.getConnection(shardId)

    def getClusterConnectionIfNeeded(self):
        if isinstance(self.envRunner, ClusterEnv):
            return self.envRunner.getClusterConnection()
        elif isinstance(self.envRunner, EnterpriseRedisClusterEnv):
            return self.envRunner.getClusterConnection()
        else:
            return self.getConnection()

    def getSlaveConnection(self):
        return self.envRunner.getSlaveConnection()

    # List of nodes that initial bootstrapping can be done from
    def getMasterNodesList(self):
        return self.envRunner.getMasterNodesList()

    # List containing a connection for each of the master nodes
    def getOSSMasterNodesConnectionList(self):
        return self.envRunner.getOSSMasterNodesConnectionList()

    def getConnectionByKey(self, key, command):
        return self.envRunner.getConnectionByKey(key, command)

    def flush(self):
        self.envRunner.flush()

    def isCluster(self):
        return 'cluster' in self.env or os.getenv("RLEC_CLUSTER") == "1"

    def isEnterpiseCluster(self):
        return isinstance(self.envRunner, EnterpriseRedisClusterEnv)

    def isDebugger(self):
        return self.debugger is not None

    def _getCallerPosition(self, back_frames):
        frame = inspect.currentframe()
        while frame and back_frames > 0:
            back_frames -= 1
            frame = frame.f_back
        if frame:
            return '%s:%s' % (
                os.path.basename(frame.f_code.co_filename),
                frame.f_lineno)

    def _assertion(self, checkStr, trueValue, depth=0, message=None):
        basemsg = Colors.Yellow(checkStr) + '\t' + Colors.Gray(self._getCallerPosition(3 + depth))
        if message:
            basemsg += ' [{}]'.format(message)

        if trueValue and self.verbose:
            print('\t' + Colors.Green('✅  (OK):\t') + basemsg)
        elif not trueValue:
            failureSummary = Colors.Bred('❌  (FAIL):\t') + basemsg
            print('\t' + failureSummary)
            if Defaults.exit_on_failure:
                raise TestAssertionFailure('Assertion Failed!')

            self.assertionFailedSummary.append(failureSummary)

    def getNumberOfFailedAssertion(self):
        return len(self.assertionFailedSummary)

    def assertEqual(self, first, second, depth=0, message=None):
        self._assertion('%s == %s' % (repr(first), repr(second)), first == second, depth, message=message)

    def assertNotEqual(self, first, second, depth=0, message=None):
        self._assertion('%s != %s' % (repr(first), repr(second)), first != second, depth, message=message)

    def assertOk(self, val, depth=0, message=None):
        self.assertEqual(val, 'OK', depth + 1, message=message)

    def assertTrue(self, val, depth=0, message=None):
        self.assertEqual(bool(val), True, depth + 1, message=message)

    def assertFalse(self, val, depth=0, message=None):
        self.assertEqual(bool(val), False, depth + 1, message=message)

    def assertContains(self, value, holder, depth=0):
        self._assertion('%s should contain %s' % (repr(holder), repr(value)), value in holder, depth)

    def assertNotContains(self, value, holder, depth=0):
        self._assertion('%s should not contain %s' % (repr(holder), repr(value)), value not in holder, depth)

    def assertGreaterEqual(self, value1, value2, depth=0):
        self._assertion('%s >= %s' % (repr(value1), repr(value2)), value1 >= value2, depth)

    def assertGreater(self, value1, value2, depth=0):
        self._assertion('%s > %s' % (repr(value1), repr(value2)), value1 > value2, depth)

    def assertLessEqual(self, value1, value2, depth=0):
        self._assertion('%s <= %s' % (repr(value1), repr(value2)), value1 <= value2, depth)

    def assertLess(self, value1, value2, depth=0):
        self._assertion('%s < %s' % (repr(value1), repr(value2)), value1 < value2, depth)

    def assertIsNotNone(self, value, depth=0):
        self._assertion('%s is not None' % (repr(value)), value is not None, depth)

    def assertIsNone(self, value, depth=0):
        self._assertion('%s is None' % (repr(value)), value is None, depth)

    def assertIsInstance(self, value, instance, depth=0):
        self._assertion('%s instance of %s' % (repr(value), repr(instance)), isinstance(value, instance), depth)

    def assertAlmostEqual(self, value1, value2, delta, depth=0, message=None):
        self._assertion('%s almost equels %s (delta %s)' % (repr(value1), repr(value2), repr(delta)), abs(value1 - value2) <= delta, depth, message)

    def expect(self, *query, **options):
        return Query(self, *query, **options)

    def cmd(self, *query, **options):
        res = self.con.execute_command(*query, **options)
        self.debugPrint('query: %s, result: %s' % (repr(query), repr(res)))
        return res

    def assertCmdOk(self, cmd, *args, **kwargs):
        self.assertOk(self.cmd(cmd, *args, **kwargs))

    def exists(self, val):
        warnings.warn("Exists is deprecated, use cmd instead", DeprecationWarning)
        return self.envRunner.exists(val)

    def assertExists(self, val, depth=0):
        warnings.warn("AssertExists is deprecated, use cmd instead", DeprecationWarning)
        self._assertion('%s exists in db' % repr(val), self.con.exists(val), depth=0)

    def executeCommand(self, *query, **options):
        warnings.warn("execute_command is deprecated, use cmd instead", DeprecationWarning)
        return self.cmd(*query, **options)

    def reloadingIterator(self):
        yield 1
        self.dumpAndReload()
        yield 2

    def dumpAndReload(self, restart=False, shardId=None, timeout_sec=40):
        self.envRunner.dumpAndReload(restart=restart, shardId=shardId, timeout_sec=timeout_sec)

    def hmset(self, *args):
        warnings.warn("hmset is deprecated, use Cmd instead", DeprecationWarning)
        return self.envRunner.hmset(*args)

    def keys(self, reg):
        warnings.warn("keys is deprecated, use Cmd instead", DeprecationWarning)
        return self.envRunner.keys(reg)

    def assertRaises(self, var1, var2, *query):
        warnings.warn("assertRaises is deprecated, use Expect + RaiseError instead", DeprecationWarning)
        self.expect(*query).raiseError()

    @contextlib.contextmanager
    def assertResponseError(self, msg=None, contained=None):
        """
        Assert that a context block with a redis command triggers a redis error response.

        For Example:

            with self.assertResponseError():
                r.execute_command('non_existing_command')
        """

        warnings.warn("assertResponseError is deprecated, use Expect + RaiseError instead", DeprecationWarning)

        try:
            yield 1
        except Exception as e:
            if contained:
                self.assertContains(contained, str(e), depth=2)
            self._assertion('Expected Response Error', True, depth=1)
        else:
            self._assertion('Expected Response Error', False, depth=1)

    def restartAndReload(self, shardId=None, timeout_sec=40):
        self.dumpAndReload(restart=True, shardId=shardId, timeout_sec=timeout_sec)

    def broadcast(self, *cmd):
        self.envRunner.broadcast(*cmd)

    def debugPrint(self, msg, force=False):
        if Defaults.debug_print or force:
            print('\t' + Colors.Bold('debug:\t') + Colors.Gray(msg))

    def checkExitCode(self):
        return self.envRunner.checkExitCode()

    def isUp(self):
        return self.envRunner.isUp()

    def isHealthy(self):
        return self.envRunner.isHealthy()

    def skip(self):
        raise unittest.SkipTest()

    def skipOnDebugger(self):
        if self.isDebugger():
            self.skip()

    def skipOnCluster(self):
        if self.isCluster():
            self.skip()

    def skipOnAOF(self):
        if self.useAof:
            self.skip()

    def skipOnSlave(self):
        if self.useSlaves:
            self.skip()

    def skipOnVersionSmaller(self, _version):
        res = self.con.execute_command('INFO')
        if(version.parse(res['redis_version']) < version.parse(_version)):
            self.skip() # copy exists only from version 6

    def isUnixSocket(self):
        return self.envRunner.isUnixSocket()

    def isTcp(self):
        return self.envRunner.isTcp()

    def skipOnTcp(self):
        if self.isTcp():
            self.skip()

    def skipOnUnixSocket(self):
        if self.isUnixSocket():
            self.skip()

    def skipOnEnterpriseCluster(self):
        if self.isEnterpiseCluster():
            self.skip()

    _mm = {
        'assertEquals': assertEqual,
        'assertListEqual': assertEqual,
        'retry_with_reload': reloadingIterator,
        'retry_with_rdb_reload': reloadingIterator,
        'reloading_iterator': reloadingIterator,
        'dump_and_reload': dumpAndReload,
        'restart_and_reload': restartAndReload,
        'execute_command': cmd,
        'assertIn': assertContains,
        'assertNotIn': assertNotContains,
        'is_cluster': isCluster,
        'is_enterprise_redis_clusterEnv':isEnterpiseCluster
    }
    for k, v in _mm.items():
        locals().update({k:genDeprecated(k, v)})
