from __future__ import print_function

import os
import subprocess
import sys
import time
import uuid
import platform
import psutil

import redis

from .random_port import get_random_port
from .utils import Colors, wait_for_conn, fix_modules, fix_modulesArgs

MASTER = 'master'
SLAVE = 'slave'


class StandardEnv(object):
    def __init__(self, redisBinaryPath, port=6379, modulePath=None, moduleArgs=None, outputFilesFormat=None,
                 dbDirPath=None, useSlaves=False, serverId=1, password=None, libPath=None, clusterEnabled=False, decodeResponses=False,
                 useAof=False, useRdbPreamble=True, debugger=None, sanitizer=None, noCatch=False, noLog=False, unix=False, verbose=False, useTLS=False,
                 tlsCertFile=None, tlsKeyFile=None, tlsCaCertFile=None, clusterNodeTimeout=None, tlsPassphrase=None, enableDebugCommand=False):
        self.uuid = uuid.uuid4().hex
        self.redisBinaryPath = os.path.expanduser(redisBinaryPath) if redisBinaryPath.startswith(
            '~/') else redisBinaryPath

        self.modulePath = fix_modules(modulePath)
        self.moduleArgs = fix_modulesArgs(self.modulePath, moduleArgs, haveSeqs=False)
        self.outputFilesFormat = self.uuid + '.' + outputFilesFormat
        self.useSlaves = useSlaves
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
        self.environ = os.environ.copy()
        self.useUnix = unix
        self.dbDirPath = dbDirPath
        self.masterProcess = None
        self.masterExitCode = None
        self.slaveProcess = None
        self.slaveExitCode = None
        self.verbose = verbose
        self.role = MASTER
        self.useTLS = useTLS
        self.tlsCertFile = tlsCertFile
        self.tlsKeyFile = tlsKeyFile
        self.tlsCaCertFile = tlsCaCertFile
        self.clusterNodeTimeout = clusterNodeTimeout
        self.tlsPassphrase = tlsPassphrase
        self.enableDebugCommand = enableDebugCommand
        self.terminateRetries = None
        self.terminateRetrySecs = None

        if port > 0:
            self.port = port
            self.slavePort = port + 1 if self.useSlaves else 0
        elif port == 0:
            self.port = get_random_port()
            self.slavePort = get_random_port() if self.useSlaves else 0
        else:
            self.port = -1
            self.slavePort = -1

        if self.useUnix:
            if self.clusterEnabled:
                raise ValueError('Unix sockets cannot be used with cluster mode')
            self.port = -1

        if self.has_interactive_debugger and serverId > 1:
            assert self.noCatch and not self.useSlaves and not self.clusterEnabled

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
        if self.useSlaves:
            self.slaveServerId = serverId + 1
            self.slaveCmdArgs = self.createCmdArgs(SLAVE)
            self.slaveOSEnv = self.createCmdOSEnv(SLAVE)

        self.envIsHealthy = True

    def _getFileName(self, role, suffix):
        return (self.outputFilesFormat + suffix) % (
            'master-%d' % self.masterServerId if role == MASTER else 'slave-%d' % self.slaveServerId)

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

        if self.port > -1:
            if self.useTLS:
                cmdArgs += ['--port', str(0), '--tls-port', str(self.getPort(role))]
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

        if self.dbDirPath is not None:
            cmdArgs += ['--dir', self.dbDirPath]
        if self.noLog:
            cmdArgs += ['--logfile', '/dev/null']
        elif self.outputFilesFormat is not None and not self.noCatch:
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

        if self.enableDebugCommand:
            if self._getRedisVersion() > 70000:
                cmdArgs += ['--enable-debug-command', 'yes']

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

    def getPid(self, role):
        return self.masterProcess.pid if role == MASTER else self.slaveProcess.pid

    def getPort(self, role):
        return self.port if role == MASTER else self.slavePort

    def getServerId(self, role):
        return self.masterServerId if role == MASTER else self.slaveServerId

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
            print(Colors.Yellow(prefix + 'slave:'))
            self._printEnvData(prefix + '\t', SLAVE)

    def startEnv(self, masters = True, slaves = True):
        if self.envIsUp and self.envIsHealthy:
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
        }

        if self.verbose:
            print(Colors.Green("Redis master command: " + ' '.join(self.masterCmdArgs)))
        if masters and self.masterProcess is None:
            self.masterProcess = subprocess.Popen(args=self.masterCmdArgs, env=self.masterOSEnv, **options)
            time.sleep(0.1)
            if self._isAlive(self.masterProcess):
                con = self.getConnection()
                self.waitForRedisToStart(con, self.masterProcess)
            else:
                self.masterProcess = None
        if self.useSlaves and slaves and self.slaveProcess is None:
            if self.verbose:
                print(Colors.Green("Redis slave command: " + ' '.join(self.slaveCmdArgs)))
            self.slaveProcess = subprocess.Popen(args=self.slaveCmdArgs, env=self.slaveOSEnv, **options)
            time.sleep(0.1)
            if self._isAlive(self.slaveProcess):
                con = self.getSlaveConnection()
                self.waitForRedisToStart(con, self.slaveProcess)
            else:
                self.slaveProcess = None

        self.envIsUp = self.masterProcess is not None or self.slaveProcess is not None
        self.envIsHealthy = self.masterProcess is not None and (self.slaveProcess is not None if self.useSlaves else True)

    def _isAlive(self, process):
        if not process:
            return False
        # check if child process has terminated
        if process.poll() is None:
            return True
        return False

    def _stopProcess(self, role):
        process = self.masterProcess if role == MASTER else self.slaveProcess
        serverId = self.masterServerId if role == MASTER else self.slaveServerId
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
                while True:
                    if process.poll() is None:  # None returns if the processes is not finished yet, retry until redis exits
                        time.sleep(0.1)
                    else:
                        break
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
                self.slaveExitCode = process.poll()
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
        if self.useSlaves and self.slaveProcess is not None and slaves is True:
            self._stopProcess(SLAVE)
            self.slaveProcess = None
        self.envIsUp = self.masterProcess is not None or self.slaveProcess is not None
        self.envIsHealthy = self.masterProcess is not None and (self.slaveProcess is not None if self.useSlaves else True)


    def _getConnection(self, role):
        if self.useUnix:
            return redis.StrictRedis(unix_socket_path=self.getUnixPath(role),
                                     password=self.password, decode_responses=self.decodeResponses)
        elif self.useTLS:
            return redis.StrictRedis('localhost', self.getPort(role),
                                     password=self.password,
                                     ssl=True,
                                     ssl_password=self.tlsPassphrase,
                                     ssl_keyfile=self.getTLSKeyFile(),
                                     ssl_certfile=self.getTLSCertFile(),
                                     ssl_cert_reqs=None,
                                     ssl_ca_certs=self.getTLSCACertFile(),
                                     decode_responses=self.decodeResponses
                                     )
        else:
            return redis.StrictRedis('localhost', self.getPort(role),
                                     password=self.password, decode_responses=self.decodeResponses)

    def getConnection(self, shardId=1):
        return self._getConnection(MASTER)

    # List containing a connection for each of the master nodes
    def getOSSMasterNodesConnectionList(self):
        return [self.getConnection()]

    def getSlaveConnection(self):
        if self.useSlaves:
            return self._getConnection(SLAVE)
        raise Exception('asked for slave connection but no slave exists')

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
            conns.append(self.getSlaveConnection())
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
        if self.useSlaves and (self.slaveExitCode is None or self.slaveExitCode != 0):
            print('\t' + Colors.Bred('bad exit code for serverId %s' % str(self.slaveServerId)))
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
