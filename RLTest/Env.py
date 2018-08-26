import os
import inspect
from OssEnv import OssEnv
from OssClusterEnv import OssClusterEnv
from utils import Colors
from Enterprise.EnterpriseClusterEnv import EnterpriseClusterEnv


class Env:

    defaultModule = None
    defaultEnv = 'oss'
    defaultOssRedisBinary = None
    defaultVerbose = False
    defaultLogDir = None
    defaultDebug = False
    defaultUseSlaves = False
    defaultShardsCount = 1
    defaultModuleArgs = None
    defaultProxyBinaryPath = None
    defaultEnterpriseRedisBinaryPath = None
    defaultEnterpriseLibsPath = None

    RTestInstance = None

    EnvCompareParams = ['module', 'moduleArgs', 'env', 'useSlaves', 'shardsCount']

    def compareEnvs(self, env):
        if env is None:
            return False
        for param in Env.EnvCompareParams:
            if self.__dict__[param] != env.__dict__[param]:
                return False
        return True

    def __init__(self, testName=None, module=None, moduleArgs=None, env=None, useSlaves=None, shardsCount=None):
        self.testName = testName if testName else inspect.currentframe().f_back.f_code.co_name
        self.testNamePrintable = self.testName
        self.testName = self.testName.replace(' ', '_')

        print Colors.Cyan(self.testNamePrintable + ':')

        self.module = module if module else Env.defaultModule
        self.moduleArgs = moduleArgs if moduleArgs else Env.defaultModuleArgs
        self.env = env if env else Env.defaultEnv
        self.useSlaves = useSlaves if useSlaves else Env.defaultUseSlaves
        self.shardsCount = shardsCount if shardsCount else Env.defaultShardsCount
        self.verbose = Env.defaultVerbose
        self.logDir = Env.defaultLogDir
        self.debug = Env.defaultDebug

        self.assertionFailedSummery = []

        if Env.RTestInstance.currEnv and self.compareEnvs(Env.RTestInstance.currEnv):
            self.envRunner = Env.RTestInstance.currEnv.envRunner
        else:
            if Env.RTestInstance.currEnv:
                Env.RTestInstance.currEnv.Stop()
            self.envRunner = self.GetEnvByName()

        try:
            os.makedirs(self.logDir)
        except Exception:
            pass

        self.Start()
        if self.verbose >= 2:
            print Colors.Blue('\tenv data:')
            self.envRunner.PrintEnvData('\t\t')

        Env.RTestInstance.currEnv = self

        if self.debug:
            raw_input('\tenv is up, attach to any process with gdb and press any button to continue.')

    def GetEnvByName(self):
        if self.env == 'oss':
            return OssEnv(redisBinaryPath=Env.defaultOssRedisBinary, modulePath=self.module, moduleArgs=self.moduleArgs,
                          outputFilesFormat='%s-' + '%s-oss-redis.log' % self.testName,
                          dbDirPath=self.logDir, useSlaves=self.useSlaves)
        if self.env == 'enterprise':
            return OssEnv(redisBinaryPath=Env.defaultEnterpriseRedisBinaryPath, modulePath=self.module, moduleArgs=self.moduleArgs,
                          outputFilesFormat='%s-' + '%s-oss-redis.log' % self.testName,
                          dbDirPath=self.logDir, useSlaves=self.useSlaves, libPath=Env.defaultEnterpriseLibsPath)
        if self.env == 'enterprise-cluster':
            return EnterpriseClusterEnv(shardsCount=self.shardsCount, redisBinaryPath=Env.defaultEnterpriseRedisBinaryPath,
                                        modulePath=self.module, moduleArgs=self.moduleArgs,
                                        outputFilesFormat='%s-' + '%s-enterprise-cluster-redis' % self.testName,
                                        dbDirPath=self.logDir, useSlaves=self.useSlaves, dmcBinaryPath=Env.defaultProxyBinaryPath,
                                        libPath=Env.defaultEnterpriseLibsPath)
        if self.env == 'oss-cluster':
            return OssClusterEnv(shardsCount=self.shardsCount, redisBinaryPath=Env.defaultOssRedisBinary,
                                 modulePath=self.module, moduleArgs=self.moduleArgs,
                                 outputFilesFormat='%s-' + '%s-oss-cluster-redis' % self.testName,
                                 dbDirPath=self.logDir, useSlaves=self.useSlaves)

    def Start(self):
        self.envRunner.StartEnv()

    def Stop(self):
        self.envRunner.StopEnv()

    def GetEnvStr(self):
        return self.env

    def GetConnection(self):
        return self.envRunner.GetConnection()

    def GetSlaveConnection(self):
        return self.envRunner.GetSlaveConnection()

    def Flush(self):
        self.envRunner.Flush()

    def _get_caller_position(self, back_frames):
        frame = inspect.currentframe()
        while frame and back_frames > 0:
            back_frames -= 1
            frame = frame.f_back
        if frame:
            return '%s:%s' % (
                os.path.basename(frame.f_code.co_filename),
                frame.f_lineno)

    def _Assertion(self, checkStr, trueValue):
        if trueValue and self.verbose:
            print '\t' + Colors.Green('assertion success:\t') + Colors.Yellow(checkStr) + '\t' + Colors.Gray(self._get_caller_position(3))
        elif not trueValue:
            FailureSummery = Colors.Bred('assertion faild:\t') + Colors.Yellow(checkStr) + '\t' + Colors.Gray(self._get_caller_position(3))
            print '\t' + FailureSummery
            self.assertionFailedSummery.append(FailureSummery)

    def GetNumberOfFailedAssertion(self):
        return len(self.assertionFailedSummery)

    def PrintFailuresSummery(self, prefix=''):
        for failure in self.assertionFailedSummery:
            print prefix + failure

    def AssertEqual(self, first, second):
        self._Assertion('expected %s == %s' % (first, second), first == second)

    def AssertNotEqual(self, first, second):
        self._Assertion('expected %s != %s' % (first, second), first != second)
