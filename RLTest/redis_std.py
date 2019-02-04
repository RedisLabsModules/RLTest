import redis
import subprocess
import sys
import os
import platform
from utils import Colors, wait_for_conn


MASTER = 1
SLAVE = 2


class StandardEnv(object):
    def __init__(self, redisBinaryPath, port=6379, modulePath=None, moduleArgs=None, outputFilesFormat=None,
                 dbDirPath=None, useSlaves=False, serverId=1, password=None, libPath=None, clusterEnabled=False,
                 useAof=False, debugger=None, noCatch=False):
        self.redisBinaryPath = os.path.expanduser(redisBinaryPath) if redisBinaryPath.startswith('~/') else redisBinaryPath
        self.port = port
        self.modulePath = os.path.abspath(modulePath) if modulePath is not None else None
        self.moduleArgs = moduleArgs
        self.outputFilesFormat = outputFilesFormat
        self.dbDirPath = dbDirPath
        self.useSlaves = useSlaves
        self.masterServerId = serverId
        self.password = password
        self.clusterEnabled = clusterEnabled
        self.useAof = useAof
        self.envIsUp = False
        self.debugger = debugger
        self.noCatch = noCatch
        self.environ = os.environ.copy()

        if self.has_interactive_debugger:
            assert self.noCatch and not self.useSlaves and not self.clusterEnabled

        if libPath:
            self.libPath = os.path.expanduser(libPath) if libPath.startswith('~/') else libPath
        else:
            self.libPath = None
        if self.libPath:
            self.environ['LD_LIBRARY_PATH'] = self.libPath

        self.masterCmdArgs = self.createCmdArgs(MASTER)
        if self.useSlaves:
            self.slaveServerId = serverId + 1
            self.slaveCmdArgs = self.createCmdArgs(SLAVE)

    def _getFileName(self, role, suffix):
        return (self.outputFilesFormat + suffix) % ('master-%d' % self.masterServerId if role == MASTER else 'slave-%d' % self.slaveServerId)

    def _getVlgrindFilePath(self, role):
        return os.path.join(self.dbDirPath, self._getFileName(role, '.valgrind.log'))

    def getSlavePort(self):
        return self.port + 1

    def getMasterPort(self):
        return self.port

    @property
    def has_interactive_debugger(self):
        return self.debugger and self.debugger.is_interactive

    def createCmdArgs(self, role):
        cmdArgs = []
        if self.debugger:
            cmdArgs += self.debugger.generate_command(self._getVlgrindFilePath(role) if not self.noCatch else None)

        cmdArgs += [self.redisBinaryPath]
        if role == MASTER:
            cmdArgs += ['--port', str(self.port)]
        else:
            cmdArgs += ['--port', str(self.getSlavePort())]
        if self.modulePath:
            cmdArgs += ['--loadmodule', self.modulePath]
            if self.moduleArgs:
                cmdArgs += self.moduleArgs.split(' ')
        if self.dbDirPath is not None:
            cmdArgs += ['--dir', self.dbDirPath]
        if self.outputFilesFormat is not None and not self.noCatch:
            cmdArgs += ['--logfile', self._getFileName(role, '.log')]
        if self.outputFilesFormat is not None:
            cmdArgs += ['--dbfilename', self._getFileName(role, '.rdb')]
        if role == SLAVE:
            cmdArgs += ['--slaveof', 'localhost', str(self.port)]
            if self.password:
                cmdArgs += ['--masterauth', self.password]
        if self.password:
            cmdArgs += ['--requirepass', self.password]
        if self.clusterEnabled and role is not SLAVE:
            cmdArgs += ['--cluster-enabled', 'yes', '--cluster-config-file', self._getFileName(role, '.cluster.conf'),
                        '--cluster-node-timeout', '5000']
        if self.useAof:
            cmdArgs += ['--appendonly yes']
            cmdArgs += ['--appendfilename', self._getFileName(role, '.aof')]
            cmdArgs += ['--aof-use-rdb-preamble', 'yes']

        return cmdArgs

    def waitForRedisToStart(self, con):
        wait_for_conn(con, retries=1000 if self.debugger else 200)

    def getPid(self, role):
        return self.masterProcess.pid if role == MASTER else self.slaveProcess.pid

    def getPort(self, role):
        return self.port if role == MASTER else self.getSlavePort()

    def getServerId(self, role):
        return self.masterServerId if role == MASTER else self.slaveServerId

    def _printEnvData(self, prefix='', role=MASTER):
        print Colors.Yellow(prefix + 'pid: %d' % (self.getPid(role)))
        print Colors.Yellow(prefix + 'port: %d' % (self.getPort(role)))
        print Colors.Yellow(prefix + 'binary path: %s' % (self.redisBinaryPath))
        print Colors.Yellow(prefix + 'server id: %d' % (self.getServerId(role)))
        print Colors.Yellow(prefix + 'using debugger: {}'.format(bool(self.debugger)))
        if self.modulePath:
            print Colors.Yellow(prefix + 'module: %s' % (self.modulePath))
            if self.moduleArgs:
                print Colors.Yellow(prefix + 'module args: %s' % (self.moduleArgs))
        if self.outputFilesFormat:
            print Colors.Yellow(prefix + 'log file: %s' % (self._getFileName(role, '.log')))
            print Colors.Yellow(prefix + 'db file name: %s' % self._getFileName(role, '.rdb'))
        if self.dbDirPath:
            print Colors.Yellow(prefix + 'db dir path: %s' % (self.dbDirPath))
        if self.libPath:
            print Colors.Yellow(prefix + 'library path: %s' % (self.libPath))

    def printEnvData(self, prefix=''):
        print Colors.Yellow(prefix + 'master:')
        self._printEnvData(prefix + '\t', MASTER)
        if self.useSlaves:
            print Colors.Yellow(prefix + 'slave:')
            self._printEnvData(prefix + '\t', SLAVE)

    def startEnv(self):
        if self.envIsUp:
            return  # env is already up
        stdoutPipe = subprocess.PIPE
        stderrPipe = subprocess.STDOUT
        stdinPipe = subprocess.PIPE
        if self.noCatch:
            stdoutPipe = sys.stdout
            stderrPipe = sys.stderr

        if self.has_interactive_debugger:
            stdinPipe = sys.stdin

        options = {
            'stderr': stderrPipe,
            'stdin': stdinPipe,
            'stdout': stdoutPipe,
            'env': self.environ
        }

        self.masterProcess = subprocess.Popen(args=self.masterCmdArgs, **options)
        con = self.getConnection()
        self.waitForRedisToStart(con)
        if self.useSlaves:
            self.slaveProcess = subprocess.Popen(args=self.slaveCmdArgs, **options)
            con = self.getSlaveConnection()
            self.waitForRedisToStart(con)
        self.envIsUp = True

    def _isAlive(self, process):
        if process.poll() is None:
            return True
        return False

    def _stopProcess(self, role):
        process = self.masterProcess if role == MASTER else self.slaveProcess
        serverId = self.masterServerId if role == MASTER else self.slaveServerId
        if not self._isAlive(process):
            if not self.has_interactive_debugger:
                # on interactive debugger its expected that then process will not be alive
                print '\t' + Colors.Bred('process is not alive, might have crash durring test execution, check this out. server id : %s' % str(serverId))
            return
        try:
            process.terminate()
            process.wait()
            if role == MASTER:
                self.masterExitCode = process.poll()
            else:
                self.slaveExitCode = process.poll()
        except OSError:
            pass

    def stopEnv(self):
        if self.masterProcess:
            self._stopProcess(MASTER)
            self.masterProcess = None
        if self.useSlaves:
            self._stopProcess(SLAVE)
            self.slaveProcess = None
        self.envIsUp = False

    def getConnection(self):
        return redis.Redis('localhost', self.port, password=self.password)

    def getSlaveConnection(self):
        if self.useSlaves:
            return redis.Redis('localhost', self.getSlavePort(), password=self.password)
        raise Exception('asked for slave connection but no slave exists')

    def flush(self):
        self.getConnection().flushall()

    def _waitForChild(self, conns):
        import time
        # Wait until file is available
        for con in conns:
            while True:
                info = con.info('persistence')
                if info['aof_rewrite_scheduled'] or info['aof_rewrite_in_progress']:
                    time.sleep(0.1)
                else:
                    break

    def dumpAndReload(self, restart=False):
        conns = []
        conns.append(self.getConnection())
        if self.useSlaves:
            conns.append(self.getSlaveConnection())
        if restart:
            [con.bgrewriteaof() for con in conns]
            self._waitForChild(conns)

            self.stopEnv()
            self.startEnv()
        else:
            [con.save() for con in conns]
            try:
                [con.execute_command('DEBUG', 'RELOAD') for con in conns]
            except redis.RedisError as err:
                raise err

    def broadcast(self, *cmd):
        try:
            self.getConnection().execute_command(*cmd)
        except Exception as e:
            print e

    def checkExitCode(self):
        ret = True
        if self.masterExitCode != 0:
            print '\t' + Colors.Bred('bad exit code for serverId %s' % str(self.masterServerId))
            ret = False
        if self.useSlaves and self.slaveExitCode != 0:
            print '\t' + Colors.Bred('bad exit code for serverId %s' % str(self.slaveServerId))
            ret = False
        return ret

    def isUp(self):
        if self.useSlaves:
            raise Exception('unsupported operation')
        return self._isAlive(self.masterProcess)

    def exists(self, val):
        return self.getConnection().exists(val)

    def hmset(self, *args):
        return self.getConnection().hmset(*args)

    def keys(self, reg):
        return self.getConnection().keys(reg)
