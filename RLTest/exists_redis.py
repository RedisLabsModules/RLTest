
from __future__ import print_function
import redis
import subprocess
import sys
import os
import platform
from .utils import Colors, wait_for_conn


MASTER = 1
SLAVE = 2


class ExistsRedisEnv(object):
    def __init__(self, addr='localhost:6379', password = None, **kwargs):
        self.host, self.port = addr.split(':')
        self.port = int(self.port)
        self.password = password
        self.useTLS = kwargs['useTLS']
        self.decodeResponses = kwargs.get('decodeResponses', False)

    @property
    def has_interactive_debugger(self):
        return False

    def _printEnvData(self, prefix='', role=MASTER):
        print(Colors.Yellow(prefix + 'addr: %s:%d' % (self.host, self.port)))

    def printEnvData(self, prefix=''):
        print(Colors.Yellow(prefix + 'master:'))
        self._printEnvData(prefix + '\t', MASTER)

    def startEnv(self, masters = True, slaves = True):
        if not self.isUp():
            raise Exception('env is not up')

    def stopEnv(self, masters = True, slaves = True):
        pass

    def getConnection(self, shardId=1):
        return redis.StrictRedis(self.host, self.port, password=self.password, decode_responses=self.decodeResponses)

    def getSlaveConnection(self):
        raise Exception('asked for slave connection but no slave exists')

    # List of nodes that initial bootstrapping can be done from
    def getMasterNodesList(self):
        node_info = {"host": None, "port": None, "unix_socket_path": None, "password": None}
        node_info["password"] = self.password
        node_info["host"] = self.host
        node_info["port"] = self.port
        return [node_info]

    # List containing a connection for each of the master nodes
    def getOSSMasterNodesConnectionList(self):
        return [self.getConnection()]

    def getConnectionByKey(self, key, command):
        return self.getConnection()

    def _waitForBgsaveToFinish(self):
        # on new Redis version (6.2 and above)
        # flush trigger background rdb save
        # waiting for rdbsave to finish
        while True:
            if not self.getConnection().execute_command('info', 'Persistence')['rdb_bgsave_in_progress']:
                break

    def flush(self):
        self.getConnection().flushall()
        self._waitForBgsaveToFinish()

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

    def dumpAndReload(self, restart=False, shardId=1, timeout_sec=0):
        self._waitForBgsaveToFinish()
        conn = self.getConnection()
        conn.save()
        try:
            conn.execute_command('DEBUG', 'RELOAD')
        except redis.RedisError as err:
            raise err

    def broadcast(self, *cmd):
        try:
            self.getConnection().execute_command(*cmd)
        except Exception as e:
            print(e)

    def checkExitCode(self):
        return True

    def isUp(self):
        return self.getConnection().ping()

    def isTLS(self):
        return self.useTLS

    def exists(self, val):
        return self.getConnection().exists(val)

    def hmset(self, *args):
        return self.getConnection().hmset(*args)

    def keys(self, reg):
        return self.getConnection().keys(reg)

    def isUnixSocket(self):
        return False

    def isTcp(self):
        return True
