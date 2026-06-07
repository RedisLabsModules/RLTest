from __future__ import print_function

import os
import subprocess
import sys
import time
import uuid
import platform
import psutil
import signal
import redis

from .random_port import get_random_port
from .utils import Colors, wait_for_conn, fix_modules, fix_modulesArgs

MASTER = 'master'
SLAVE = 'slave'


class StandardEnv(object):
    def __init__(self, redisBinaryPath, port=6379, modulePath=None, moduleArgs=None, outputFilesFormat=None,
                 dbDirPath=None, useSlaves=False, serverId=1, password=None, libPath=None, clusterEnabled=False, decodeResponses=False,
                 useAof=False, useRdbPreamble=True, debugger=None, sanitizer=None, noCatch=False, noLog=False, unix=False, verbose=False, useTLS=False,
                 tlsCertFile=None, tlsKeyFile=None, tlsCaCertFile=None, clusterNodeTimeout=None, tlsPassphrase=None, enableDebugCommand=False, protocol=2,
                 terminateRetries=None, terminateRetrySecs=None, enableProtectedConfigs=False, enableModuleCommand=False, loglevel=None,
                 redisConfigFile=None, dualTLS=False, startupGraceSecs=0.1, replicasPerShard=1
                 ):
        self.uuid = uuid.uuid4().hex
        self.redisBinaryPath = os.path.expanduser(redisBinaryPath) if redisBinaryPath.startswith(
            '~/') else redisBinaryPath

        self.modulePath = fix_modules(modulePath)
        self.moduleArgs = fix_modulesArgs(self.modulePath, moduleArgs, haveSeqs=False)
        self.outputFilesFormat = self.uuid + '.' + outputFilesFormat
        self.useSlaves = useSlaves
        # Number of replicas attached to this shard's master. Default 1
        # preserves the historical single-replica behavior. Multi-replica
        # support (>1) is only meaningful for cluster mode; in standalone we
        # cap at 1 to keep behavior unchanged.
        if useSlaves:
            if not clusterEnabled and replicasPerShard != 1:
                # Standalone replication keeps a single replica; per design
                # there is no clear use case for multiple chained replicas at
                # this level.
                replicasPerShard = 1
            self.replicasPerShard = replicasPerShard
        else:
            self.replicasPerShard = 0
        self.masterServerId = serverId
        self.password = password
        self.clusterEnabled = clusterEnabled
        self.decodeResponses = decodeResponses
        self.useAof = useAof
        self.useRdbPreamble = useRdbPreamble
        self.envIsUp = False
        self.debugger = debugger
        self.sanitizer = sanitizer
        self.noCatch = noCatch
        self.noLog = noLog
        self.loglevel = loglevel
        self.environ = os.environ.copy()
        self.useUnix = unix
        self.dbDirPath = dbDirPath
        self.masterProcess = None
        self.masterStdout = None
        self.masterStderr = None
        self.masterExitCode = None
        # Slave state is stored as per-replica lists so a single shard can own
        # more than one replica (controlled by replicasPerShard). The legacy
        # scalar attributes (slaveProcess, slavePort, slaveStdout, slaveStderr,
        # slaveExitCode, slaveServerId) remain accessible via @property
        # accessors below for backward compatibility; they map to index 0.
        n_slaves = self.replicasPerShard if self.useSlaves else 0
        self.slaveProcesses = [None] * n_slaves
        self.slaveStdouts = [None] * n_slaves
        self.slaveStderrs = [None] * n_slaves
        self.slaveExitCodes = [None] * n_slaves
        self.verbose = verbose
        self.role = MASTER
        self.useTLS = useTLS
        self.tlsCertFile = tlsCertFile
        self.tlsKeyFile = tlsKeyFile
        self.tlsCaCertFile = tlsCaCertFile
        self.clusterNodeTimeout = clusterNodeTimeout
        self.tlsPassphrase = tlsPassphrase
        self.enableDebugCommand = enableDebugCommand
        self.enableModuleCommand = enableModuleCommand
        self.enableProtectedConfigs = enableProtectedConfigs
        self.protocol = protocol
        self.terminateRetries = terminateRetries
        self.terminateRetrySecs = terminateRetrySecs
        self.redisConfigFile = redisConfigFile
        self.dualTLS = dualTLS
        self.startupGraceSecs = startupGraceSecs

        if port > 0:
            self.port = port
            # Allocate sequential ports right after the master port, one per
            # replica. With replicasPerShard==1 this matches historical
            # behavior (slavePort == port + 1).
            self.slavePorts = [port + 1 + i for i in range(n_slaves)] if self.useSlaves else []
        elif port == 0:
            self.port = get_random_port()
            self.slavePorts = [get_random_port() for _ in range(n_slaves)] if self.useSlaves else []
        else:
            self.port = -1
            self.slavePorts = [-1] * n_slaves if self.useSlaves else []

        if self.has_interactive_debugger and serverId > 1:
            assert self.noCatch and not self.useSlaves and not self.clusterEnabled

        if self.useUnix:
            if self.clusterEnabled:
                raise ValueError('Unix sockets cannot be used with cluster mode')
            self.port = -1

        if self.useTLS:
            if self.useUnix:
                raise ValueError('Unix sockets cannot be used with TLS enabled mode')
            if self.tlsCertFile is None:
                raise ValueError('When useTLS option is True tlsCertFile must be defined')
            if os.path.isfile(self.tlsCertFile) is False:
                raise ValueError(
                    'When useTLS option is True tlsCertFile must exist. specified path {}'.format(self.tlsCertFile))
            if self.tlsKeyFile is None:
                raise ValueError('When useTLS option is True tlsKeyFile must be defined')
            if os.path.isfile(self.tlsKeyFile) is False:
                raise ValueError(
                    'When useTLS option is True tlsKeyFile must exist. specified path {}'.format(self.tlsKeyFile))
            if self.tlsCaCertFile is None:
                raise ValueError('When useTLS option is True tlsCaCertFile must be defined')
            if not os.path.isfile(self.tlsCaCertFile):
                raise ValueError(
                    'When useTLS option is True tlsCaCertFile must exist. specified path {}'.format(self.tlsCaCertFile))

        if libPath:
            self.libPath = os.path.expanduser(libPath) if libPath.startswith('~/') else libPath
        else:
            self.libPath = None
        if self.libPath:
            if 'LD_LIBRARY_PATH' in self.environ.keys():
                self.environ['LD_LIBRARY_PATH'] = self.libPath + ":" + self.environ['LD_LIBRARY_PATH']
            else:
                self.environ['LD_LIBRARY_PATH'] = self.libPath

        self.masterCmdArgs = self.createCmdArgs(MASTER)
        self.masterOSEnv = self.createCmdOSEnv(MASTER)
        # Per-replica command args / env / server ids. The current slave index
        # used by createCmdArgs/createCmdOSEnv/_getFileName is tracked via the
        # transient self._slaveIdx attribute set during the loop below; this
        # avoids changing the createCmdArgs/_getFileName signatures and
        # therefore preserves backward compatibility.
        self.slaveServerIds = []
        self.slaveCmdArgsList = []
        self.slaveOSEnvList = []
        if self.useSlaves:
            for i in range(self.replicasPerShard):
                self._slaveIdx = i
                self.slaveServerIds.append(serverId + 1 + i)
                self.slaveCmdArgsList.append(self.createCmdArgs(SLAVE))
                self.slaveOSEnvList.append(self.createCmdOSEnv(SLAVE))
            self._slaveIdx = 0

        self.envIsHealthy = True

    # ---- Backward-compatibility scalar accessors ----
    # External callers (and the existing test suite) read/write scalar
    # attributes such as self.slaveProcess, self.slavePort, self.slaveServerId,
    # self.slaveStdout, self.slaveStderr, self.slaveExitCode, self.slaveCmdArgs
    # and self.slaveOSEnv. These properties expose index 0 of the underlying
    # per-replica lists so that pre-existing code continues to work unchanged
    # whenever replicasPerShard == 1 (the default).
    @property
    def slaveProcess(self):
        return self.slaveProcesses[0] if self.slaveProcesses else None

    @slaveProcess.setter
    def slaveProcess(self, value):
        if self.slaveProcesses:
            self.slaveProcesses[0] = value
        else:
            self.slaveProcesses = [value]

    @property
    def slavePort(self):
        return self.slavePorts[0] if self.slavePorts else 0

    @slavePort.setter
    def slavePort(self, value):
        if self.slavePorts:
            self.slavePorts[0] = value
        else:
            self.slavePorts = [value]

    @property
    def slaveServerId(self):
        return self.slaveServerIds[0] if self.slaveServerIds else None

    @slaveServerId.setter
    def slaveServerId(self, value):
        if self.slaveServerIds:
            self.slaveServerIds[0] = value
        else:
            self.slaveServerIds = [value]

    @property
    def slaveStdout(self):
        return self.slaveStdouts[0] if self.slaveStdouts else None

    @slaveStdout.setter
    def slaveStdout(self, value):
        if self.slaveStdouts:
            self.slaveStdouts[0] = value
        else:
            self.slaveStdouts = [value]

    @property
    def slaveStderr(self):
        return self.slaveStderrs[0] if self.slaveStderrs else None

    @slaveStderr.setter
    def slaveStderr(self, value):
        if self.slaveStderrs:
            self.slaveStderrs[0] = value
        else:
            self.slaveStderrs = [value]

    @property
    def slaveExitCode(self):
        return self.slaveExitCodes[0] if self.slaveExitCodes else None

    @slaveExitCode.setter
    def slaveExitCode(self, value):
        if self.slaveExitCodes:
            self.slaveExitCodes[0] = value
        else:
            self.slaveExitCodes = [value]

    @property
    def slaveCmdArgs(self):
        return self.slaveCmdArgsList[0] if self.slaveCmdArgsList else None

    @property
    def slaveOSEnv(self):
        return self.slaveOSEnvList[0] if self.slaveOSEnvList else None

    def getNumSlaves(self):
        """Returns the number of slaves configured for this shard."""
        return len(self.slaveProcesses)

    def _getFileName(self, role, suffix):
        if role == MASTER:
            tag = 'master-%d' % self.masterServerId
        else:
            # When createCmdArgs is called once per replica during __init__,
            # self._slaveIdx points to the replica currently being built. After
            # construction, callers that pass role=SLAVE expect the legacy
            # single-slave tag (index 0).
            idx = getattr(self, '_slaveIdx', 0)
            server_id = (self.slaveServerIds[idx]
                         if self.slaveServerIds and idx < len(self.slaveServerIds)
                         else self.masterServerId + 1)
            tag = 'slave-%d' % server_id
        return (self.outputFilesFormat + suffix) % tag

    def _getValgrindFilePath(self, role):
        return os.path.join(self.dbDirPath, self._getFileName(role, '.valgrind.log'))

    def getMasterPort(self):
        return self.port

    def getPassword(self):
        return self.password

    def getUnixPath(self, role):
        basename = '{}-{}.sock'.format(self.uuid, role)
        return os.path.abspath(os.path.join(self.dbDirPath, basename))

    def getTLSCertFile(self):
        return os.path.abspath(self.tlsCertFile)

    def getTLSKeyFile(self):
        return os.path.abspath(self.tlsKeyFile)

    def getTLSCACertFile(self):
        return os.path.abspath(self.tlsCaCertFile)

    @property
    def has_interactive_debugger(self):
        return self.debugger and self.debugger.is_interactive

    def _getRedisVersion(self):
        options = {
            'stderr': subprocess.PIPE,
            'stdin': subprocess.PIPE,
            'stdout': subprocess.PIPE,
        }
        p = subprocess.Popen(args=[self.redisBinaryPath, '--version'], **options)
        while p.poll() is None:
            time.sleep(0.1)
        exit_code = p.poll()
        if exit_code != 0:
            raise Exception('Could not extract Redis version')
        out, err = p.communicate()
        out = out.decode('utf-8')
        v = out[out.find("v=") + 2:out.find("sha=") - 1].split('.')
        return int(v[0]) * 10000 + int(v[1]) * 100 + int(v[2])

    def createCmdArgs(self, role):
        cmdArgs = []
        if self.debugger:
            cmdArgs += self.debugger.generate_command(self._getValgrindFilePath(role) if not self.noCatch else None)

        cmdArgs += [self.redisBinaryPath]

        if self.redisConfigFile:
            cmdArgs += [self.redisConfigFile]

        if self.port > -1:
            if self.useTLS:
                cmdArgs += ['--port', str(self.getPort(role) + 1500) if self.dualTLS else str(0), '--tls-port', str(self.getPort(role))]
            else:
                cmdArgs += ['--port', str(self.getPort(role))]
        else:
            cmdArgs += ['--port', str(0), '--unixsocket', self.getUnixPath(role)]

        if self.modulePath:
            if self.moduleArgs and len(self.modulePath) != len(self.moduleArgs):
                print(Colors.Bred('Number of module args sets in Env does not match number of modules'))
                print(self.modulePath)
                print(self.moduleArgs)
                sys.exit(1)
            for pos, module in enumerate(self.modulePath):
                cmdArgs += ['--loadmodule', module]
                if self.moduleArgs:
                    module_args = self.moduleArgs[pos]
                    if module_args:
                        # make sure there are no spaces within args
                        args = []
                        for arg in module_args:
                            if arg.strip() != '':
                                args += arg.split(' ')
                        cmdArgs += args

        if self.noLog:
            cmdArgs += ['--logfile', '/dev/null']
        elif self.outputFilesFormat is not None and not self.noCatch:
            cmdArgs += ['--logfile', self._getFileName(role, '.log')]
        if self.loglevel is not None:
            cmdArgs += ['--loglevel', self.loglevel]
        if self.outputFilesFormat is not None:
            cmdArgs += ['--dbfilename', self._getFileName(role, '.rdb')]
        if role == SLAVE and not self.clusterEnabled:
            # Standalone replication: tie the slave to its master at boot.
            cmdArgs += ['--slaveof', 'localhost', str(self.port)]
            if self.password:
                cmdArgs += ['--masterauth', self.password]
        elif role == SLAVE and self.clusterEnabled:
            # Cluster mode: do NOT use --slaveof. The slave will be attached
            # to its master via CLUSTER REPLICATE after the cluster is formed
            # (see redis_cluster.py::startEnv). Boot it as an empty
            # cluster-enabled node so it can join gossip.
            if self.password:
                cmdArgs += ['--masterauth', self.password]
        if self.password:
            cmdArgs += ['--requirepass', self.password]
        if self.clusterEnabled:
            # creating .cluster.conf in /tmp as lock fails on NFS
            cmdArgs += ['--cluster-enabled', 'yes', '--cluster-config-file', '/tmp/' + self._getFileName(role, '.cluster.conf'),
                        '--cluster-node-timeout', '5000' if self.clusterNodeTimeout is None else str(self.clusterNodeTimeout)]
            if self.useTLS:
                cmdArgs += ['--tls-cluster', 'yes']
        if self.useAof:
            cmdArgs += ['--appendonly', 'yes']
            cmdArgs += ['--appendfilename', self._getFileName(role, '.aof')]
            if not self.useRdbPreamble:
                cmdArgs += ['--aof-use-rdb-preamble', 'no']
        if self.useTLS:
            cmdArgs += ['--tls-cert-file', self.getTLSCertFile()]
            cmdArgs += ['--tls-key-file', self.getTLSKeyFile()]
            cmdArgs += ['--tls-ca-cert-file', self.getTLSCACertFile()]
            if self.tlsPassphrase:
                cmdArgs += ['--tls-key-file-pass', self.tlsPassphrase]

            cmdArgs += ['--tls-replication', 'yes']

        if self._getRedisVersion() > 70000:
            if self.enableDebugCommand:
                cmdArgs += ['--enable-debug-command', 'yes']
            if self.enableProtectedConfigs:
                cmdArgs += ['--enable-protected-configs', 'yes']
            if self.enableModuleCommand:
                cmdArgs += ['--enable-module-command', 'yes']
        return cmdArgs

    def createCmdOSEnv(self, role):
        if self.sanitizer != 'addr' and self.sanitizer != 'address':
            return self.environ
        osenv = self.environ.copy()
        san_log = self._getFileName(role, '.asan.log')
        asan_options = osenv.get("ASAN_OPTIONS")
        osenv["ASAN_OPTIONS"] = "{OPT}:log_path={DIR}".format(OPT=asan_options, DIR=san_log)
        return osenv

    def waitForRedisToStart(self, con, proc):
        wait_for_conn(con, proc, retries=1000 if self.debugger else 200)
        self._waitForAOFChild(con)

    def getPid(self, role, slaveIdx=0):
        if role == MASTER:
            return self.masterProcess.pid
        idx = getattr(self, '_slaveIdx', slaveIdx)
        return self.slaveProcesses[idx].pid

    def getPort(self, role, slaveIdx=0):
        if role == MASTER:
            return self.port
        # During __init__, createCmdArgs(SLAVE) is invoked once per replica
        # while self._slaveIdx walks through the index range; honor it so each
        # replica gets its own port wired into its command line.
        idx = getattr(self, '_slaveIdx', slaveIdx)
        return self.slavePorts[idx] if self.slavePorts else 0

    def getServerId(self, role, slaveIdx=0):
        if role == MASTER:
            return self.masterServerId
        idx = getattr(self, '_slaveIdx', slaveIdx)
        return self.slaveServerIds[idx] if self.slaveServerIds else None

    def _printEnvData(self, prefix='', role=MASTER):
        print(Colors.Yellow(prefix + 'pid: %d' % (self.getPid(role))))
        if self.useUnix:
            print(Colors.Yellow(prefix + 'unix_socket_path: %s' % (self.getUnixPath(role))))
        else:
            print(Colors.Yellow(prefix + 'port: %d' % (self.getPort(role))))
        print(Colors.Yellow(prefix + 'binary path: %s' % (self.redisBinaryPath)))
        print(Colors.Yellow(prefix + 'server id: %d' % (self.getServerId(role))))
        print(Colors.Yellow(prefix + 'using debugger: {}'.format(bool(self.debugger))))
        if self.modulePath:
            print(Colors.Yellow(prefix + 'module: %s' % (self.modulePath)))
            if self.moduleArgs:
                print(Colors.Yellow(prefix + 'module args: %s' % (self.moduleArgs)))
        if self.outputFilesFormat:
            print(Colors.Yellow(prefix + 'log file: %s' % (self._getFileName(role, '.log'))))
            print(Colors.Yellow(prefix + 'db file name: %s' % self._getFileName(role, '.rdb')))
        if self.dbDirPath:
            print(Colors.Yellow(prefix + 'db dir path: %s' % (self.dbDirPath)))
        if self.libPath:
            print(Colors.Yellow(prefix + 'library path: %s' % (self.libPath)))
        if self.useTLS:
            print(Colors.Yellow(prefix + 'TLS Cert File: %s' % (self.getTLSCertFile())))
            print(Colors.Yellow(prefix + 'TLS Key File: %s' % (self.getTLSKeyFile())))
            print(Colors.Yellow(prefix + 'TLS CA Cert File: %s' % (self.getTLSCACertFile())))

    def printEnvData(self, prefix=''):
        print(Colors.Yellow(prefix + 'master:'))
        self._printEnvData(prefix + '\t', MASTER)
        if self.useSlaves:
            for i in range(self.getNumSlaves()):
                label = 'slave:' if self.getNumSlaves() == 1 else 'slave[%d]:' % i
                print(Colors.Yellow(prefix + label))
                # _printEnvData reads role-keyed scalars; switch self._slaveIdx
                # so the helpers (getPid/getPort/getServerId/_getFileName)
                # return the i-th replica's values for this print iteration.
                old_idx = getattr(self, '_slaveIdx', 0)
                self._slaveIdx = i
                try:
                    self._printEnvData(prefix + '\t', SLAVE)
                finally:
                    self._slaveIdx = old_idx

    def getInformationBeforeDispose(self):
        res = {}
        instances = [(MASTER, self.getConnection(), self.masterProcess)]
        if self.useSlaves:
            for i in range(self.getNumSlaves()):
                instances.append((SLAVE if i == 0 and self.getNumSlaves() == 1
                                  else '%s-%d' % (SLAVE, i),
                                  self.getSlaveConnection(i),
                                  self.slaveProcesses[i]))
        for role, conn, proc in instances:
            info = None
            try:
                info = conn.execute_command('info', 'everything')
            except redis.exceptions.RedisError:
                pass
            res[role] = {
                'info': info
            }
        return res

    def getInformationAfterDispose(self):
        res = {}
        instances = [(MASTER, self.masterStdout, self.masterStderr)]
        if self.useSlaves:
            for i in range(self.getNumSlaves()):
                instances.append((SLAVE if i == 0 and self.getNumSlaves() == 1
                                  else '%s-%d' % (SLAVE, i),
                                  self.slaveStdouts[i],
                                  self.slaveStderrs[i]))
        for role, stdout, stderr in instances:
            stdoutStr = None
            stderrStr = None
            logs = None
            try:
                stdoutStr = stdout.read().decode('utf8')
            except (NameError, AttributeError):
                pass

            try:
                stderrStr = stderr.read().decode('utf8')
            except (NameError, AttributeError):
                pass

            try:
                with open(os.path.join(self.dbDirPath, self._getFileName(role, '.log'))) as f:
                    logs = f.read()
            except FileNotFoundError:
                pass

            res[role] = {
                'stdout': stdoutStr,
                'stderr': stderrStr,
                'logs': logs,
            }
        return res

    def startEnv(self, masters = True, slaves = True):
        if self.envIsUp and self.envIsHealthy:
            return  # env is already up
        stdoutPipe = subprocess.PIPE
        stderrPipe = subprocess.PIPE
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
        }

        if self.verbose:
            print(Colors.Green("Redis master command: " + ' '.join(self.masterCmdArgs)))
        if masters and self.masterProcess is None:
            self.masterProcess = subprocess.Popen(args=self.masterCmdArgs, env=self.masterOSEnv, cwd=self.dbDirPath,
                                                  **options)
            time.sleep(self.startupGraceSecs)
            if self._isAlive(self.masterProcess):
                con = self.getConnection()
                self.waitForRedisToStart(con, self.masterProcess)
            else:
                self.masterProcess = None
        if self.useSlaves and slaves:
            for i in range(self.getNumSlaves()):
                if self.slaveProcesses[i] is not None:
                    continue
                if self.verbose:
                    label = "Redis slave command" if self.getNumSlaves() == 1 \
                        else "Redis slave[%d] command" % i
                    print(Colors.Green("%s: %s" % (label, ' '.join(self.slaveCmdArgsList[i]))))
                self.slaveProcesses[i] = subprocess.Popen(
                    args=self.slaveCmdArgsList[i], env=self.slaveOSEnvList[i],
                    cwd=self.dbDirPath, **options)
                time.sleep(self.startupGraceSecs)
                if self._isAlive(self.slaveProcesses[i]):
                    con = self.getSlaveConnection(i)
                    self.waitForRedisToStart(con, self.slaveProcesses[i])
                else:
                    self.slaveProcesses[i] = None

        any_slave_alive = any(p is not None for p in self.slaveProcesses)
        all_slaves_alive = all(p is not None for p in self.slaveProcesses) if self.slaveProcesses else True
        self.envIsUp = self.masterProcess is not None or any_slave_alive
        self.envIsHealthy = self.masterProcess is not None and (all_slaves_alive if self.useSlaves else True)

        # self.masterStdout = self.masterProcess.stdout if self.masterProcess else None
        # self.masterStderr = self.masterProcess.stderr if self.masterProcess else None

        # if self.slaveProcess is not None:
        #     self.slaveStdout = self.slaveProcess.stdout if self.slaveProcess else None
        #     self.slaveStderr = self.slaveProcess.stderr if self.slaveProcess else None

    def _isAlive(self, process):
        if not process:
            return False
        # check if child process has terminated
        if process.poll() is None:
            return True
        return False

    def _segfault(self, role, retries=3, slaveIdx=0):
        if role == MASTER:
            process = self.masterProcess
        else:
            process = self.slaveProcesses[slaveIdx]
        if not self._isAlive(process):
            return
        for _ in range(retries):
            if process.poll() is None:  # None returns if the processes is not finished yet, retry until redis exits
                time.sleep(1)
                process.send_signal(signal.SIGSEGV)
            else:
                return
        print(Colors.Bred('Failed killing processes with sigsegv, forcely kill the processes.'))
        for _ in range(retries):
            if process.poll() is None:  # None returns if the processes is not finished yet, retry until redis exits
                time.sleep(1)
                process.kill()
            else:
                return
        print(Colors.Bred('Failed killing processes with sigkill.'))

    def stopEnvWithSegFault(self, masters = True, slaves = True):
        if self.masterProcess is not None and masters is True:
            self._segfault(MASTER)
        if self.useSlaves and slaves is True:
            for i in range(self.getNumSlaves()):
                if self.slaveProcesses[i] is not None:
                    self._segfault(SLAVE, slaveIdx=i)

    def _stopProcess(self, role, slaveIdx=0):
        if role == MASTER:
            process = self.masterProcess
            serverId = self.masterServerId
        else:
            process = self.slaveProcesses[slaveIdx]
            serverId = self.slaveServerIds[slaveIdx]
        # _getFileName(SLAVE, ...) reads self._slaveIdx to pick the correct
        # log file when verbose_analyse_server_log is invoked below.
        old_idx = getattr(self, '_slaveIdx', 0)
        self._slaveIdx = slaveIdx
        try:
            return self.__stopProcessImpl(process, role, serverId, slaveIdx)
        finally:
            self._slaveIdx = old_idx

    def __stopProcessImpl(self, process, role, serverId, slaveIdx):
        if not self._isAlive(process):
            if not self.has_interactive_debugger:
                # on interactive debugger its expected that then process will not be alive
                print('\t' + Colors.Bred('process is not alive, might have crash durring test execution, '
                                         'check this out. server id : %s' % str(serverId)))
                if self.outputFilesFormat is not None and not self.noCatch:
                    self.verbose_analyse_server_log(role)
            return
        try:
            if platform.system() == 'Darwin':
                # On macOS, with lldb, killing lldb process does not terminate inferior processes
                p0 = psutil.Process(pid=process.pid)
                pchi = p0.children(recursive=True)
                for p in pchi:
                    try:
                        p.terminate()
                        p.wait()
                    except:
                        pass

            if self.terminateRetries is None:
                # ask once, then wait for process to exit
                process.terminate()
                termination_start_time = time.time()
                while process.poll() is None:  # None returns if the processes is not finished yet, retry until redis exits
                    time.sleep(0.1)
                    if time.time() - termination_start_time > 30:
                        # if process is still running after 30 seconds, try reading its output
                        process_out, process_err = process.communicate()
                        print(Colors.Bred(f'\t[TERMINATING] out ({process_out}), error ({process_err})'))
            else:
                # keep asking every few seconds until process has exited, otherwise kill
                if self.terminateRetrySecs is None:
                    self.terminateRetrySecs = 1
                done = False
                for i in range(0, self.terminateRetries):
                    process.terminate()
                    if process.poll() is None:  # None returns if the processes is not finished yet, retry until redis exits
                        time.sleep(self.terminateRetrySecs)
                    else:
                        done = True
                        break
                if not done:
                    process.kill()

            if role == MASTER:
                self.masterExitCode = process.poll()
            else:
                self.slaveExitCodes[slaveIdx] = process.poll()
        except OSError as e:
            print('\t' + Colors.Bred(
                'OSError caught while waiting for {0} process to end: {1}'.format(role, e.__str__())))
            pass

    def verbose_analyse_server_log(self, role):
        path = "{0}".format(self._getFileName(role, '.log'))
        if self.dbDirPath is not None:
            path = "{0}/{1}".format(self.dbDirPath, self._getFileName(role, '.log'))
        print('\t' + Colors.Bred('check the redis log at: {0}'.format(path)))
        print('\t' + Colors.Yellow('Printing only REDIS BUG REPORT START and STACK TRACE'))
        with open(path) as file:
            bug_report_found = False
            for line in file:
                if "REDIS BUG REPORT START" in line:
                    bug_report_found = True
                if "------ INFO OUTPUT ------" in line:
                    break
                if bug_report_found is True:
                    print('\t\t' + Colors.Yellow(line.rstrip()))

    def stopEnv(self, masters = True, slaves = True):
        if self.masterProcess is not None and masters is True:
            self._stopProcess(MASTER)
            self.masterProcess = None
        if self.useSlaves and slaves is True:
            for i in range(self.getNumSlaves()):
                if self.slaveProcesses[i] is not None:
                    self._stopProcess(SLAVE, slaveIdx=i)
                    self.slaveProcesses[i] = None
        any_slave_alive = any(p is not None for p in self.slaveProcesses)
        all_slaves_alive = all(p is not None for p in self.slaveProcesses) if self.slaveProcesses else True
        self.envIsUp = self.masterProcess is not None or any_slave_alive
        self.envIsHealthy = self.masterProcess is not None and (all_slaves_alive if self.useSlaves else True)

    def _getConnection(self, role, slaveIdx=0):
        # When fetching a slave connection, temporarily steer the role-aware
        # helpers (getPort/getUnixPath) at the requested replica index.
        old_idx = getattr(self, '_slaveIdx', 0)
        self._slaveIdx = slaveIdx
        try:
            if self.useUnix:
                return redis.StrictRedis(unix_socket_path=self.getUnixPath(role),
                                         password=self.password, decode_responses=self.decodeResponses, protocol=self.protocol)
            elif self.useTLS:
                return redis.StrictRedis('localhost', self.getPort(role),
                                         password=self.password,
                                         ssl=True,
                                         ssl_password=self.tlsPassphrase,
                                         ssl_keyfile=self.getTLSKeyFile(),
                                         ssl_certfile=self.getTLSCertFile(),
                                         ssl_cert_reqs=None,
                                         ssl_ca_certs=self.getTLSCACertFile(),
                                         decode_responses=self.decodeResponses,
                                         protocol=self.protocol
                                         )
            else:
                return redis.StrictRedis('localhost', self.getPort(role),
                                         password=self.password, decode_responses=self.decodeResponses, protocol=self.protocol)
        finally:
            self._slaveIdx = old_idx

    def getConnection(self, shardId=1):
        return self._getConnection(MASTER)

    # List containing a connection for each of the master nodes
    def getOSSMasterNodesConnectionList(self):
        return [self.getConnection()]

    def getSlaveConnection(self, slaveIdx=0):
        if self.useSlaves:
            return self._getConnection(SLAVE, slaveIdx=slaveIdx)
        raise Exception('asked for slave connection but no slave exists')

    def getSlavePort(self, slaveIdx=0):
        """Returns the port for the slave at the given index (default 0)."""
        if not self.useSlaves or not self.slavePorts:
            raise Exception('asked for slave port but no slave exists')
        return self.slavePorts[slaveIdx]

    # List of nodes that initial bootstrapping can be done from
    def getMasterNodesList(self):
        node_info = {"host": None, "port": None, "unix_socket_path": None, "password": None}
        node_info["password"] = self.password
        if self.useUnix:
            node_info["unix_socket_path"] = self.getUnixPath(MASTER)

        else:
            node_info["host"] = 'localhost'
            node_info["port"] = self.getPort(MASTER)
        return [node_info]

    def getConnectionByKey(self, key, command):
        return self.getConnection()

    def flush(self):
        self.getConnection().flushall()

    def _waitForAOFChild(self, con):
        import time
        # Wait until file is available
        while True:
            info = con.info('persistence')
            if info['aof_rewrite_scheduled'] or info['aof_rewrite_in_progress']:
                time.sleep(0.1)
            else:
                break

    def dumpAndReload(self, restart=False, shardId=None, timeout_sec=0):
        conns = []
        conns.append(self.getConnection())
        if self.useSlaves:
            for i in range(self.getNumSlaves()):
                conns.append(self.getSlaveConnection(i))
        if restart:
            for con in conns:
                self._waitForAOFChild(con)
                con.bgrewriteaof()
                self._waitForAOFChild(con)

            self.stopEnv()
            self.startEnv()
        else:
            [con.save() for con in conns]
            try:
                # Given we've already saved on the prior step, there is no need to SAVE again on the DEBUG RELOAD
                [con.execute_command('DEBUG', 'RELOAD', 'NOSAVE') for con in conns]
            except redis.RedisError as err:
                raise err

    def broadcast(self, *cmd):
        try:
            self.getConnection().execute_command(*cmd)
        except Exception as e:
            print(e)

    def checkExitCode(self):
        ret = True

        if self.masterExitCode != 0:
            print('\t' + Colors.Bred('bad exit code for serverId %s' % str(self.masterServerId)))
            ret = False
        if self.useSlaves:
            for i in range(self.getNumSlaves()):
                exit_code = self.slaveExitCodes[i]
                if exit_code is None or exit_code != 0:
                    print('\t' + Colors.Bred('bad exit code for serverId %s' %
                                             str(self.slaveServerIds[i])))
                    ret = False
        return ret

    def isUp(self):
        return self.envIsUp

    def isHealthy(self):
        return self.envIsHealthy

    def isUnixSocket(self):
        return self.useUnix

    def isTcp(self):
        return not (self.useUnix)

    def isTLS(self):
        return self.useTLS

    def exists(self, val):
        return self.getConnection().exists(val)

    def hmset(self, *args):
        return self.getConnection().hmset(*args)

    def keys(self, reg):
        return self.getConnection().keys(reg)

    def setTerminateRetries(self, retries=3, seconds=1):
        self.terminateRetries = retries
        self.terminateRetrySecs = seconds
