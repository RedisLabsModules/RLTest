import redis
import subprocess
import sys
from utils import Colors, wait_for_conn


MASTER = 1
SLAVE = 2


class OssEnv:
    def __init__(self, redisBinaryPath=None, port=6379, modulePath=None, moduleArgs=None, logFileFormat=None, dbFileNameFormat=None, dbDirPath=None,
                 useSlaves=False, serverId=1, password=None):
        self.redisBinaryPath = redisBinaryPath if redisBinaryPath else 'redis-server'
        self.port = port
        self.modulePath = modulePath
        self.moduleArgs = moduleArgs
        self.logFileFormat = logFileFormat
        self.dbFileNameFormat = dbFileNameFormat
        self.dbDirPath = dbDirPath
        self.useSlaves = useSlaves
        self.masterServerId = serverId
        self.password = password

        self.masterCmdArgs = self.createCmdArgs(MASTER)
        if self.useSlaves:
            self.slaveServerId = serverId + 1
            self.slaveCmdArgs = self.createCmdArgs(SLAVE)

    def getFileWithPrefix(self, role, strName):
        return strName % ('master-%d' % self.masterServerId if role == MASTER else 'slave-%d' % self.slaveServerId)

    def GetSlavePort(self):
        return self.port + 1

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
        if self.logFileFormat is not None:
            cmdArgs += ['--logfile', self.getFileWithPrefix(role, self.logFileFormat)]
        if self.dbFileNameFormat is not None:
            cmdArgs += ['--dbfilename', self.getFileWithPrefix(role, self.dbFileNameFormat)]
        if role == SLAVE:
            cmdArgs += ['--slaveof', 'localhost', str(self.port)]
            if self.password:
                cmdArgs += ['--masterauth', self.password]
        if self.password:
            cmdArgs += ['--requirepass', self.password]

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
        print Colors.Yellow(prefix + 'server id: %d' % (self.getServerId(role)))
        if self.modulePath:
            print Colors.Yellow(prefix + 'module: %s' % (self.modulePath))
            if self.moduleArgs:
                print Colors.Yellow(prefix + 'module args: %s' % (self.moduleArgs))
        if self.logFileFormat:
            print Colors.Yellow(prefix + 'log file: %s' % (self.getFileWithPrefix(role, self.logFileFormat)))
        if self.dbFileNameFormat:
            print Colors.Yellow(prefix + 'db file name: %s' % self.getFileWithPrefix(role, self.dbFileNameFormat))
        if self.dbDirPath:
            print Colors.Yellow(prefix + 'db dir path: %s' % (self.dbDirPath))

    def PrintEnvData(self, prefix=''):
        print Colors.Yellow(prefix + 'master:')
        self.printEnvData(prefix + '\t', MASTER)
        if self.useSlaves:
            print Colors.Yellow(prefix + 'slave:')
            self.printEnvData(prefix + '\t', SLAVE)

    def StartEnv(self):
        self.masterProcess = subprocess.Popen(args=self.masterCmdArgs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        con = self.GetConnection()
        self.waitForRedisToStart(con)
        if self.useSlaves:
            self.slaveProcess = subprocess.Popen(args=self.slaveCmdArgs, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            con = self.GetSlaveConnection()
            self.waitForRedisToStart(con)

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
