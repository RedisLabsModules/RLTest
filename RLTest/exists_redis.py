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
    def __init__(self, addr='localhost:6379', password = None, **kargs):
        self.host, self.port = addr.split(':')
        self.port = int(self.port)
        self.password = password

    @property
    def has_interactive_debugger(self):
        return False

    def _printEnvData(self, prefix='', role=MASTER):
        print(Colors.Yellow(prefix + 'addr: %s:%d' % (self.host, self.port)))

    def printEnvData(self, prefix=''):
        print(Colors.Yellow(prefix + 'master:'))
        self._printEnvData(prefix + '\t', MASTER)

    def startEnv(self):
        if not self.isUp():
            raise Exception('env is not up')

    def stopEnv(self):
        pass

    def getConnection(self, shardId=1):
        return redis.StrictRedis(self.host, self.port, password=self.password)

    def getSlaveConnection(self):
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

    def dumpAndReload(self, restart=False, shardId=1):
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

    def exists(self, val):
        return self.getConnection().exists(val)

    def hmset(self, *args):
        return self.getConnection().hmset(*args)

    def keys(self, reg):
        return self.getConnection().keys(reg)
