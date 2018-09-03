import os
import sys
import redis
import unittest
import inspect
import contextlib
import warnings
from OssEnv import OssEnv
from OssClusterEnv import OssClusterEnv
from utils import Colors
from Enterprise.EnterpriseClusterEnv import EnterpriseClusterEnv


class Query:
    def __init__(self, env, *query):
        self.query = query
        self.env = env
        self.errorRaised = False
        self._evaluate()

    def _evaluate(self):
        try:
            self.res = self.env.con.execute_command(*self.query)
        except Exception as e:
            self.res = str(e)
            self.errorRaised = True
        self.debugPrint(force=False)

    def debugPrint(self, force=True):
        self.env.debugPrint('query: %s, result: %s' % (self.query, self.res), force=force)
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

    def raiseError(self):
        self.env.assertTrue(self.errorRaised, 1)
        return self

    def notRaiseError(self):
        self.env.assertFalse(self.errorRaised, 1)
        return self


class Env:

    defaultModule = None
    defaultEnv = 'oss'
    defaultOssRedisBinary = None
    defaultVerbose = False
    defaultLogDir = None
    defaultUseSlaves = False
    defaultShardsCount = 1
    defaultModuleArgs = None
    defaultProxyBinaryPath = None
    defaultEnterpriseRedisBinaryPath = None
    defaultEnterpriseLibsPath = None
    defaultUseAof = None

    RTestInstance = None

    defaultDebugPrints = False

    defaultUseValgrind = False
    defaultValgrindSuppressionsFile = None

    defaultInteractiveDebugger = False
    defaultInteractiveDebuggerArgs = None

    defaultNoCatch = False

    EnvCompareParams = ['module', 'moduleArgs', 'env', 'useSlaves', 'shardsCount', 'useAof']

    def compareEnvs(self, env):
        if env is None:
            return False
        for param in Env.EnvCompareParams:
            if self.__dict__[param] != env.__dict__[param]:
                return False
        return True

    def __init__(self, testName=None, module=None, moduleArgs=None, env=None, useSlaves=None, shardsCount=None, useAof=None, ):
        self.testName = testName if testName else '%s.%s' % (inspect.getmodule(inspect.currentframe().f_back).__name__, inspect.currentframe().f_back.f_code.co_name)
        self.testNamePrintable = self.testName
        self.testName = self.testName.replace(' ', '_')

        print Colors.Cyan(self.testNamePrintable + ':')

        self.module = module if module else Env.defaultModule
        self.moduleArgs = moduleArgs if moduleArgs else Env.defaultModuleArgs
        self.env = env if env else Env.defaultEnv
        self.useSlaves = useSlaves if useSlaves else Env.defaultUseSlaves
        self.shardsCount = shardsCount if shardsCount else Env.defaultShardsCount
        self.useAof = useAof if useAof else Env.defaultUseAof
        self.verbose = Env.defaultVerbose
        self.logDir = Env.defaultLogDir

        self.assertionFailedSummery = []

        if Env.RTestInstance.currEnv and self.compareEnvs(Env.RTestInstance.currEnv):
            self.envRunner = Env.RTestInstance.currEnv.envRunner
        else:
            if Env.RTestInstance.currEnv:
                Env.RTestInstance.currEnv.stop()
            self.envRunner = self.getEnvByName()

        try:
            os.makedirs(self.logDir)
        except Exception:
            pass

        self.start()
        if self.verbose >= 2:
            print Colors.Blue('\tenv data:')
            self.envRunner.printEnvData('\t\t')

        Env.RTestInstance.currEnv = self

    def getEnvByName(self):
        if self.env == 'oss':
            return OssEnv(redisBinaryPath=Env.defaultOssRedisBinary, modulePath=self.module, moduleArgs=self.moduleArgs,
                          outputFilesFormat='%s-' + '%s-oss-redis' % self.testName,
                          dbDirPath=self.logDir, useSlaves=self.useSlaves, useAof=self.useAof, useValgrind=Env.defaultUseValgrind,
                          valgrindSuppressionsFile=Env.defaultValgrindSuppressionsFile,
                          interactiveDebugger=Env.defaultInteractiveDebugger, interactiveDebuggerArgs=Env.defaultInteractiveDebuggerArgs,
                          noCatch=Env.defaultNoCatch)
        if self.env == 'enterprise':
            return OssEnv(redisBinaryPath=Env.defaultEnterpriseRedisBinaryPath, modulePath=self.module, moduleArgs=self.moduleArgs,
                          outputFilesFormat='%s-' + '%s-oss-redis' % self.testName,
                          dbDirPath=self.logDir, useSlaves=self.useSlaves, libPath=Env.defaultEnterpriseLibsPath,
                          useAof=self.useAof, useValgrind=Env.defaultUseValgrind, valgrindSuppressionsFile=Env.defaultValgrindSuppressionsFile,
                          interactiveDebugger=Env.defaultInteractiveDebugger, interactiveDebuggerArgs=Env.defaultInteractiveDebuggerArgs,
                          noCatch=Env.defaultNoCatch)
        if self.env == 'enterprise-cluster':
            return EnterpriseClusterEnv(shardsCount=self.shardsCount, redisBinaryPath=Env.defaultEnterpriseRedisBinaryPath,
                                        modulePath=self.module, moduleArgs=self.moduleArgs,
                                        outputFilesFormat='%s-' + '%s-enterprise-cluster-redis' % self.testName,
                                        dbDirPath=self.logDir, useSlaves=self.useSlaves, dmcBinaryPath=Env.defaultProxyBinaryPath,
                                        libPath=Env.defaultEnterpriseLibsPath, useAof=self.useAof, useValgrind=Env.defaultUseValgrind,
                                        valgrindSuppressionsFile=Env.defaultValgrindSuppressionsFile, noCatch=Env.defaultNoCatch)
        if self.env == 'oss-cluster':
            return OssClusterEnv(shardsCount=self.shardsCount, redisBinaryPath=Env.defaultOssRedisBinary,
                                 modulePath=self.module, moduleArgs=self.moduleArgs,
                                 outputFilesFormat='%s-' + '%s-oss-cluster-redis' % self.testName,
                                 dbDirPath=self.logDir, useSlaves=self.useSlaves, useAof=self.useAof, useValgrind=Env.defaultUseValgrind,
                                 valgrindSuppressionsFile=Env.defaultValgrindSuppressionsFile, noCatch=Env.defaultNoCatch)

    def start(self):
        self.envRunner.startEnv()
        self.con = self.getConnection()

    def stop(self):
        self.envRunner.stopEnv()

    def getEnvStr(self):
        return self.env

    def getConnection(self):
        return self.envRunner.getConnection()

    def getSlaveConnection(self):
        return self.envRunner.getSlaveConnection()

    def flush(self):
        self.envRunner.flush()

    def isCluster(self):
        return 'cluster' in self.env

    def _getCallerPosition(self, back_frames):
        frame = inspect.currentframe()
        while frame and back_frames > 0:
            back_frames -= 1
            frame = frame.f_back
        if frame:
            return '%s:%s' % (
                os.path.basename(frame.f_code.co_filename),
                frame.f_lineno)

    def _assertion(self, checkStr, trueValue, depth=0):
        if trueValue and self.verbose:
            print '\t' + Colors.Green('assertion success:\t') + Colors.Yellow(checkStr) + '\t' + Colors.Gray(self._getCallerPosition(3 + depth))
        elif not trueValue:
            FailureSummery = Colors.Bred('assertion faild:\t') + Colors.Yellow(checkStr) + '\t' + Colors.Gray(self._getCallerPosition(3 + depth))
            print '\t' + FailureSummery
            self.assertionFailedSummery.append(FailureSummery)

    def getNumberOfFailedAssertion(self):
        return len(self.assertionFailedSummery)

    def printFailuresSummery(self, prefix=''):
        for failure in self.assertionFailedSummery:
            print prefix + failure

    def assertEqual(self, first, second, depth=0):
        self._assertion('%s == %s' % (first, second), first == second, depth)

    def assertNotEqual(self, first, second, depth=0):
        self._assertion('%s != %s' % (first, second), first != second, depth)

    def assertOk(self, val, depth=0):
        self.assertEqual(val, 'OK', depth + 1)

    def assertTrue(self, val, depth=0):
        self.assertEqual(val, True, depth + 1)

    def assertFalse(self, val, depth=0):
        self.assertEqual(val, False, depth + 1)

    def assertContains(self, value, holder, depth=0):
        self._assertion('%s should contains %s' % (str(holder), str(value)), value in holder, depth)

    def assertNotContains(self, value, holder, depth=0):
        self._assertion('%s should not contains %s' % (str(holder), str(value)), value not in holder, depth)

    def assertGreaterEqual(self, value1, value2, depth=0):
        self._assertion('%s >= %s' % (str(value1), str(value2)), value1 >= value2, depth)

    def assertGreater(self, value1, value2, depth=0):
        self._assertion('%s > %s' % (str(value1), str(value2)), value1 > value2, depth)

    def assertLessEqual(self, value1, value2, depth=0):
        self._assertion('%s <= %s' % (str(value1), str(value2)), value1 <= value2, depth)

    def assertLess(self, value1, value2, depth=0):
        self._assertion('%s < %s' % (str(value1), str(value2)), value1 < value2, depth)

    def assertIsNotNone(self, value, depth=0):
        self._assertion('%s is not None' % (str(value)), value is not None, depth)

    def assertIsNone(self, value, depth=0):
        self._assertion('%s is None' % (str(value)), value is None, depth)

    def assertIsInstance(self, value, instance, depth=0):
        self._assertion('%s instance of %s' % (str(value), str(instance)), isinstance(value, instance), depth)

    def assertAlmostEqual(self, value1, value2, delta, depth=0):
        self._assertion('%s almost equels %s (delta %s)' % (str(value1), str(value2), str(delta)), abs(value1 - value2) <= delta, depth)

    def expect(self, *query):
        return Query(self, *query)

    def cmd(self, *query):
        return self.con.execute_command(*query)

    def assertCmdOk(self, cmd, *args, **kwargs):
        self.assertOk(self.cmd(cmd, *args, **kwargs))

    def exists(self, val):
        warnings.warn("Exists is deprecated, use cmd instead", DeprecationWarning)
        return self.envRunner.exists(val)

    def assertExists(self, val, depth=0):
        warnings.warn("AssertExists is deprecated, use cmd instead", DeprecationWarning)
        self._assertion('%s exists in db' % str(val), self.con.exists(val), depth=0)

    def executeCommand(self, *query):
        warnings.warn("execute_command is deprecated, use cmd instead", DeprecationWarning)
        return self.cmd(*query)

    def reloadingIterator(self):
        yield 1
        self.dumpAndReload()
        yield 2

    def dumpAndReload(self, restart=False):
        self.envRunner.dumpAndReload(restart=restart)

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

    def restartAndReload(self):
        self.dumpAndReload(restart=True)

    def broadcast(self, *cmd):
        self.envRunner.broadcast(*cmd)

    def debugPrint(self, msg, force=False):
        if Env.defaultDebugPrints or force:
            print '\t' + Colors.Bold('debug:\t') + Colors.Gray(msg)

    def checkExitCode(self):
        return self.envRunner.checkExitCode()

    def isUp(self):
        return self.envRunner.isUp()

    def skip(self):
        raise unittest.SkipTest()

    def skipOnCluster(self):
        if self.isCluster():
            self.skip()


def addDepricatedMethod(cls, name, invoke):
    def method(*argc, **nargs):
        warnings.warn('%s is deprecated, use %s instead' % (str(name), str(invoke)), DeprecationWarning)
        return invoke(*argc, **nargs)
    cls.__dict__[name] = method


addDepricatedMethod(Env, 'assertEquals', Env.assertEqual)
addDepricatedMethod(Env, 'assertListEqual', Env.assertEqual)
addDepricatedMethod(Env, 'retry_with_reload', Env.reloadingIterator)
addDepricatedMethod(Env, 'retry_with_rdb_reload', Env.reloadingIterator)
addDepricatedMethod(Env, 'reloading_iterator', Env.reloadingIterator)
addDepricatedMethod(Env, 'dump_and_reload', Env.dumpAndReload)
addDepricatedMethod(Env, 'is_cluster', Env.isCluster)
addDepricatedMethod(Env, 'restart_and_reload', Env.restartAndReload)
addDepricatedMethod(Env, 'execute_command', Env.cmd)
addDepricatedMethod(Env, 'assertIn', Env.assertContains)
addDepricatedMethod(Env, 'assertNotIn', Env.assertNotContains)
