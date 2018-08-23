from RLTest.OssEnv import OssEnv
from RLTest.utils import Colors, wait_for_conn
from CcsMock import CcsMock
from Dmc import Dmc
import redis
import os
import json
from zipfile import ZipFile


SHARD_PASSWORD = 'password'


class EnterpriseClusterEnv():
    DMC_PORT = 10000
    MODULE_WORKING_DIR = '/tmp/'

    def __init__(self, redisBinaryPath, dmcBinaryPath, libPath, shardsCount=1, modulePath=None, moduleArgs=None, logFileFormat=None,
                 dbFileNameFormat=None, dbDirPath=None, useSlaves=False):
        self.shardsCount = shardsCount
        self.shards = []
        self.modulePath = modulePath
        self.moduleArgs = moduleArgs
        self.preperModule()
        startPort = 20000
        totalRedises = self.shardsCount * (2 if useSlaves else 1)
        for i in range(0, totalRedises, (2 if useSlaves else 1)):
            shard = OssEnv(redisBinaryPath=redisBinaryPath, port=startPort, modulePath=self.moduleSoFilePath, moduleArgs=self.moduleArgs,
                           logFileFormat=logFileFormat, dbFileNameFormat=dbFileNameFormat, dbDirPath=dbDirPath, useSlaves=useSlaves,
                           serverId=(i + 1), password=SHARD_PASSWORD, libPath=libPath)
            self.shards.append(shard)
            startPort += 2

        self.ccs = CcsMock(redisBinaryPath=redisBinaryPath, directory=dbDirPath, useSlaves=useSlaves,
                           password=SHARD_PASSWORD, proxyPort=self.DMC_PORT, libPath=libPath)
        self.dmc = Dmc(directory=dbDirPath, dmcBinaryPath=dmcBinaryPath, libPath=libPath)

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

    def PrintEnvData(self, prefix=''):
        print Colors.Yellow(prefix + 'bdb info:')
        print Colors.Yellow(prefix + '\tlistening port:%d' % self.DMC_PORT)
        print Colors.Yellow(prefix + '\tshards count:%d' % len(self.shards))
        if self.modulePath:
            print Colors.Yellow(prefix + '\tzip module path:%s' % self.modulePath)
        if self.moduleSoFilePath:
            print Colors.Yellow(prefix + '\tso module path:%s' % self.moduleSoFilePath)
        if self.moduleArgs:
            print Colors.Yellow(prefix + '\tmodule args:%s' % self.moduleArgs)
        for i, shard in enumerate(self.shards):
            print Colors.Yellow(prefix + 'shard: %d' % (i + 1))
            shard.PrintEnvData(prefix + '\t')
        print Colors.Yellow(prefix + 'ccs:')
        self.ccs.PrintEnvData(prefix + '\t')
        print Colors.Yellow(prefix + 'dmc:')
        self.dmc.PrintEnvData(prefix + '\t')

    def StartEnv(self):
        for shard in self.shards:
            shard.StartEnv()

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

        self.ccs.Start(self.shards, bdb_fields=ccs_bdb_config, legacy_hash_slots=True, extra_keys=extra_keys)
        self.dmc.Start()
        con = self.GetConnection()
        wait_for_conn(con)

    def StopEnv(self):
        for shard in self.shards:
            shard.StopEnv()
        self.ccs.Stop()
        self.dmc.Stop()

    def GetConnection(self):
        return redis.Redis('localhost', self.DMC_PORT)

    def GetSlaveConnection(self):
        raise Exception('unsupported')
