from __future__ import print_function

from RLTest.redis_std import StandardEnv
from RLTest.utils import Colors, wait_for_conn
from .CcsMock import CcsMock
from .Dmc import Dmc
import redis
import os
import json
from zipfile import ZipFile


SHARD_PASSWORD = 'password'


class EnterpriseClusterEnv():
    DMC_PORT = 10000
    MODULE_WORKING_DIR = '/tmp/'

    def __init__(self, **kwargs):

        self.shards = []
        self.envIsUp = False
        self.envIsHealthy = False
        self.modulePath = kwargs.pop('modulePath')
        self.moduleArgs = kwargs['moduleArgs']
        self.shardsCount = kwargs.pop('shardsCount')
        self.dmcBinaryPath = kwargs.pop('dmcBinaryPath')
        useSlaves = kwargs.get('useSlaves', False)

        self.preperModule()
        startPort = 20000
        totalRedises = self.shardsCount * (2 if useSlaves else 1)
        for i in range(0, totalRedises, (2 if useSlaves else 1)):
            shard = StandardEnv(port=startPort, serverId=(i + 1), password=SHARD_PASSWORD, modulePath=self.moduleSoFilePath, **kwargs)
            self.shards.append(shard)
            startPort += 2

        self.ccs = CcsMock(redisBinaryPath=kwargs['redisBinaryPath'], directory=kwargs['dbDirPath'], useSlaves=kwargs['useSlaves'],
                           password=SHARD_PASSWORD, proxyPort=self.DMC_PORT, libPath=kwargs['libPath'])
        self.dmc = Dmc(directory=kwargs['dbDirPath'], dmcBinaryPath=self.dmcBinaryPath, libPath=kwargs['libPath'])
        self.envIsUp = False

    def preperModule(self):
        if self.modulePath is None:
            self.moduleSoFilePath = None
            self.moduleConfig = None
            return
        if not self.modulePath.endswith('zip'):
            raise Exception('module on enterprise cluster must be a zip file')
        with ZipFile(self.modulePath, 'r') as myzip:
            moduleJson = [a.filename for a in myzip.infolist() if a.filename.endswith('.json')]
            if len(moduleJson) != 1:
                self.moduleSoFilePath = None
                self.moduleConfig = None
                return
            moduleJson = moduleJson[0]
            myzip.extractall(self.MODULE_WORKING_DIR)
            with open(os.path.join(self.MODULE_WORKING_DIR, moduleJson), 'rt') as f:
                self.moduleConfig = json.load(f)
            self.moduleSoFilePath = os.path.join(self.MODULE_WORKING_DIR, self.moduleConfig['module_file'])
            if self.moduleArgs is None:
                self.moduleArgs = self.moduleConfig['command_line_args']

    def printEnvData(self, prefix=''):
        print(Colors.Yellow(prefix + 'bdb info:'))
        print(Colors.Yellow(prefix + '\tlistening port:%d' % self.DMC_PORT))
        print(Colors.Yellow(prefix + '\tshards count:%d' % len(self.shards)))
        if self.modulePath:
            print(Colors.Yellow(prefix + '\tzip module path:%s' % self.modulePath))
        if self.moduleSoFilePath:
            print(Colors.Yellow(prefix + '\tso module path:%s' % self.moduleSoFilePath))
        if self.moduleArgs:
            print(Colors.Yellow(prefix + '\tmodule args:%s' % self.moduleArgs))
        for i, shard in enumerate(self.shards):
            print(Colors.Yellow(prefix + 'shard: %d' % (i + 1)))
            shard.printEnvData(prefix + '\t')
        print(Colors.Yellow(prefix + 'ccs:'))
        self.ccs.PrintEnvData(prefix + '\t')
        print(Colors.Yellow(prefix + 'dmc:'))
        self.dmc.PrintEnvData(prefix + '\t')

    def startEnv(self, masters = True, slaves = True):
        if self.envIsUp:
            return  # env is already up
        for shard in self.shards:
            shard.startEnv(masters, slaves)

        ccs_bdb_config = {'shard_key_regex': '012.*\{(?<tag>.*)\}.*00a(?<tag>.*)',
                          'sharding': 'enabled' if self.shardsCount > 0 else 'disabled'}

        extra_keys = {}
        if self.moduleConfig:
            ccs_bdb_config['module_list'] = self.moduleConfig['module_name']
            extra_keys['module:%s' % self.moduleConfig['module_name']] = {'module_name': self.moduleConfig['module_name'],
                                                                          'commands': ','.join([c['command_name'] for c in self.moduleConfig['commands']])}
            for c in self.moduleConfig['commands']:
                key_name = 'module_command:%s' % c['command_name']
                extra_keys[key_name] = {}
                for key, val in c.items():
                    extra_keys[key_name][key] = val

        self.ccs.Start(self.shards, bdb_fields=ccs_bdb_config, legacy_hash_slots=False, extra_keys=extra_keys)
        self.dmc.Start()
        con = self.getConnection()
        wait_for_conn(con, command='sping', shouldBe=['SPONG 0' for i in self.shards])
        self.envIsUp = True
        self.envIsHealthy = True

    def stopEnv(self, masters = True, slaves = True):
        for shard in self.shards:
            shard.stopEnv(masters, slaves)
            self.envIsUp = self.envIsUp or shard.envIsUp
            self.envIsHealthy = self.envIsHealthy and shard.envIsUp
        self.ccs.Stop()
        self.dmc.Stop()

    def getConnection(self, shardId=1):
        return redis.Redis('localhost', self.DMC_PORT)

    def getSlaveConnection(self):
        raise Exception('unsupported')

    def flush(self):
        self.getConnection().flushall()

    def dumpAndReload(self, restart=False, shardId=None, timeout_sec=40):
        if shardId is None:
            for shard in self.shards:
                shard.dumpAndReload(restart=restart)
            self.dmc.Stop()
            self.dmc.Start()
            con = self.getConnection()
            wait_for_conn(con, command='sping', shouldBe=['SPONG 0' for i in self.shards])
        else:
            self.shards[shardId - 1].dumpAndReload(restart=restart, shardId=None)

    def broadcast(self, *cmd):
        for shard in self.shards:
            shard.broadcast(*cmd)

    def checkExitCode(self):
        for shard in self.shards:
            if not shard.checkExitCode():
                return False
        return True

    def exists(self, val):
        return self.getConnection().exists(val)

    def hmset(self, *args):
        return self.getConnection().hmset(*args)

    def keys(self, reg):
        return self.getConnection().keys(reg)

    def isUp(self):
        raise Exception('unsupported operation')
