import redis
import subprocess
import sys
import os
from utils import Colors, wait_for_conn


MASTER = 1
SLAVE = 2


class OssEnv:
    def __init__(self, redisBinaryPath, port=6379, modulePath=None, moduleArgs=None, outputFilesFormat=None,
                 dbDirPath=None, useSlaves=False, serverId=1, password=None, libPath=None, clusterEnabled=False):
        self.redisBinaryPath = os.path.expanduser(redisBinaryPath) if redisBinaryPath.startswith('~/') else redisBinaryPath
        self.port = port
        self.modulePath = modulePath
        self.moduleArgs = moduleArgs
        self.outputFilesFormat = outputFilesFormat
        self.dbDirPath = dbDirPath
        self.useSlaves = useSlaves
        self.masterServerId = serverId
        self.password = password
        self.clusterEnabled = clusterEnabled
        self.envIsUp = False
        if libPath:
            self.libPath = os.path.expanduser(libPath) if libPath.startswith('~/') else libPath
        else:
            self.libPath = None
        if self.libPath:
            self.env = {'LD_LIBRARY_PATH': self.libPath}
        else:
            self.env = None

        self.masterCmdArgs = self.createCmdArgs(MASTER)
        if self.useSlaves:
            self.slaveServerId = serverId + 1
            self.slaveCmdArgs = self.createCmdArgs(SLAVE)

    def getFileName(self, role, strName, suffix):
        return (strName + suffix) % ('master-%d' % self.masterServerId if role == MASTER else 'slave-%d' % self.slaveServerId)

    def GetSlavePort(self):
        return self.port + 1

    def GetMasterPort(self):
        return self.port

    def createCmdArgs(self, role):
        cmdArgs = self.redisBinaryPath.split()
        if role == MASTER:
            cmdArgs += ['--port', str(self.port)]
        else:
            cmdArgs += ['--port', str(self.GetSlavePort())]
        if self.modulePath:
            cmdArgs += ['--loadmodule', self.modulePath]
            if self.moduleArgs:
                cmdArgs += self.moduleArgs.split(' ')
        if self.dbDirPath is not None:
            cmdArgs += ['--dir', self.dbDirPath]
        if self.outputFilesFormat is not None:
            cmdArgs += ['--logfile', self.getFileName(role, self.outputFilesFormat, '.log')]
        if self.outputFilesFormat is not None:
            cmdArgs += ['--dbfilename', self.getFileName(role, self.outputFilesFormat, '.rdb')]
        if role == SLAVE:
            cmdArgs += ['--slaveof', 'localhost', str(self.port)]
            if self.password:
                cmdArgs += ['--masterauth', self.password]
        if self.password:
            cmdArgs += ['--requirepass', self.password]
        if self.clusterEnabled and role is not SLAVE:
            cmdArgs += ['--cluster-enabled', 'yes', '--cluster-config-file', self.getFileName(role, self.outputFilesFormat, '.cluster.conf'),
                        '--cluster-node-timeout', '5000']

        return cmdArgs

    def waitForRedisToStart(self, con):
        wait_for_conn(con)

    def getPid(self, role):
        return self.masterProcess.pid if role == MASTER else self.slaveProcess.pid

    def getPort(self, role):
        return self.port if role == MASTER else self.GetSlavePort()

    def getServerId(self, role):
        return self.masterServerId if role == MASTER else self.slaveServerId

    def printEnvData(self, prefix='', role=MASTER):
        print Colors.Yellow(prefix + 'pid: %d' % (self.getPid(role)))
        print Colors.Yellow(prefix + 'port: %d' % (self.getPort(role)))
        print Colors.Yellow(prefix + 'binary path: %s' % (self.redisBinaryPath))
        print Colors.Yellow(prefix + 'server id: %d' % (self.getServerId(role)))
        if self.modulePath:
            print Colors.Yellow(prefix + 'module: %s' % (self.modulePath))
            if self.moduleArgs:
                print Colors.Yellow(prefix + 'module args: %s' % (self.moduleArgs))
        if self.outputFilesFormat:
            print Colors.Yellow(prefix + 'log file: %s' % (self.getFileName(role, self.outputFilesFormat, '.log')))
            print Colors.Yellow(prefix + 'db file name: %s' % self.getFileName(role, self.outputFilesFormat, '.rdb'))
        if self.dbDirPath:
            print Colors.Yellow(prefix + 'db dir path: %s' % (self.dbDirPath))
        if self.libPath:
            print Colors.Yellow(prefix + 'library path: %s' % (self.libPath))

    def PrintEnvData(self, prefix=''):
        print Colors.Yellow(prefix + 'master:')
        self.printEnvData(prefix + '\t', MASTER)
        if self.useSlaves:
            print Colors.Yellow(prefix + 'slave:')
            self.printEnvData(prefix + '\t', SLAVE)

    def StartEnv(self):
        if self.envIsUp:
            return  # env is already up
        self.masterProcess = subprocess.Popen(args=self.masterCmdArgs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env)
        con = self.GetConnection()
        self.waitForRedisToStart(con)
        if self.useSlaves:
            self.slaveProcess = subprocess.Popen(args=self.slaveCmdArgs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.env)
            con = self.GetSlaveConnection()
            self.waitForRedisToStart(con)
        self.envIsUp = True

    def StopEnv(self):
        if self.masterProcess:
            try:
                self.masterProcess.terminate()
                self.masterProcess.wait()
            except OSError:
                pass
            self.masterProcess = None
        if self.useSlaves:
            try:
                self.slaveProcess.terminate()
                self.slaveProcess.wait()
            except OSError:
                pass
            self.slaveProcess = None

    def GetConnection(self):
        return redis.Redis('localhost', self.port, password=self.password)

    def GetSlaveConnection(self):
        if self.useSlaves:
            return redis.Redis('localhost', self.GetSlavePort(), password=self.password)
        raise Exception('asked for slave connection but no slave exists')

    def Flush(self):
        self.GetConnection().flushall()
