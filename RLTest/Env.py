import os
import inspect
from OssEnv import OssEnv
from utils import Colors
from Enterprise.EnterpriseClusterEnv import EnterpriseClusterEnv


class Env:

    defaultModule = None
    defaultEnv = 'oss'
    defaultWait = False
    defaultOssRedisBinary = None
    defaultVerbose = False
    defaultLogDir = None
    defaultDebug = False
    defaultUseSlaves = False
    defaultShardsCount = 1
    defaultModuleArgs = None
    defaultProxyBinaryPath = None

    RTestInstance = None

    def __init__(self, testName=None, module=None, moduleArgs=None, env=None, wait=None, ossRedisBinary=None, verbose=False,
                 logDir=None, debug=None, useSlaves=None, shardsCount=None):

        self.testName = testName if testName else inspect.currentframe().f_back.f_code.co_name
        print Colors.Cyan(self.testName + ':')

        self.module = module if module else Env.defaultModule
        self.moduleArgs = moduleArgs if moduleArgs else Env.defaultModuleArgs
        self.env = env if env else Env.defaultEnv
        self.ossRedisBinary = ossRedisBinary if ossRedisBinary else Env.defaultOssRedisBinary
        self.wait = env if env else Env.defaultWait
        self.verbose = verbose if verbose else Env.defaultVerbose
        self.logDir = logDir if logDir else Env.defaultLogDir
        self.debug = debug if debug else Env.defaultDebug
        self.useSlaves = useSlaves if useSlaves else Env.defaultUseSlaves
        self.shardsCount = shardsCount if shardsCount else Env.defaultShardsCount

        self.envRunner = self.GetEnvByName()
        self.assertionFailed = 0

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
            return OssEnv(redisBinaryPath=self.ossRedisBinary, modulePath=self.module, moduleArgs=self.moduleArgs,
                          logFileFormat='%s-' + '%s-oss-redis.log' % self.testName,
                          dbFileNameFormat='%s-' + '%s-oss-redis.rdb' % self.testName,
                          dbDirPath=self.logDir, useSlaves=self.useSlaves)
        if self.env == 'enterprise-cluster':
            return EnterpriseClusterEnv(shardsCount=self.shardsCount, redisBinaryPath=self.ossRedisBinary,
                                        modulePath=self.module, moduleArgs=self.moduleArgs,
                                        logFileFormat='%s-' + '%s-oss-redis.log' % self.testName,
                                        dbFileNameFormat='%s-' + '%s-oss-redis.rdb' % self.testName,
                                        dbDirPath=self.logDir, useSlaves=self.useSlaves, dmcBinaryPath=Env.defaultProxyBinaryPath)

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
            print '\t' + Colors.Bred('assertion faild:\t') + Colors.Yellow(checkStr) + '\t' + Colors.Gray(self._get_caller_position(3))
            self.assertionFailed += 1

    def AssertEqual(self, first, second):
        self._Assertion('expected %s == %s' % (first, second), first == second)

    def AssertNotEqual(self, first, second):
        self._Assertion('expected %s != %s' % (first, second), first != second)
