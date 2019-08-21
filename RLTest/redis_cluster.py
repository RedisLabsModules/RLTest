from __future__ import print_function
from .redis_std import StandardEnv
import redis
import rediscluster
import time
from RLTest.utils import Colors


class ClusterEnv(object):
    def __init__(self, **kwargs):
        self.shards = []
        self.envIsUp = False
        self.modulePath = kwargs['modulePath']
        self.moduleArgs = kwargs['moduleArgs']
        self.shardsCount = kwargs.pop('shardsCount')
        useSlaves = kwargs.get('useSlaves', False)
        startPort = 20000
        totalRedises = self.shardsCount * (2 if useSlaves else 1)
        randomizePorts = kwargs.pop('randomizePorts', False)
        for i in range(0, totalRedises, (2 if useSlaves else 1)):
            port = 0 if randomizePorts else startPort
            shard = StandardEnv(port=port, serverId=(i + 1),
                                clusterEnabled=True, **kwargs)
            self.shards.append(shard)
            startPort += 2

    def printEnvData(self, prefix=''):
        print(Colors.Yellow(prefix + 'info:'))
        print(Colors.Yellow(prefix + '\tshards count:%d' % len(self.shards)))
        if self.modulePath:
            print(Colors.Yellow(prefix + '\tzip module path:%s' % self.modulePath))
        if self.moduleArgs:
            print(Colors.Yellow(prefix + '\tmodule args:%s' % self.moduleArgs))
        for i, shard in enumerate(self.shards):
            print(Colors.Yellow(prefix + 'shard: %d' % (i + 1)))
            shard.printEnvData(prefix + '\t')

    def waitCluster(self, timeout_sec=40):

        st = time.time()
        ok = 0

        while st + timeout_sec > time.time():
            ok = 0
            for shard in self.shards:
                con = shard.getConnection()
                status = con.execute_command('CLUSTER', 'INFO')
                if 'cluster_state:ok' in status:
                    ok += 1
            if ok == len(self.shards):
                return

            time.sleep(0.1)
        raise RuntimeError("Cluster OK wait loop timed out after %s seconds" % timeout_sec)

    def startEnv(self):
        if self.envIsUp:
            return  # env is already up
        for shard in self.shards:
            shard.startEnv()

        slots_per_node = int(16384 / len(self.shards)) + 1
        for i, shard in enumerate(self.shards):
            con = shard.getConnection()
            for s in self.shards:
                con.execute_command('CLUSTER', 'MEET', '127.0.0.1', s.getMasterPort())

            start_slot = i * slots_per_node
            end_slot = start_slot + slots_per_node
            if end_slot > 16384:
                end_slot = 16384

            try:
                con.execute_command('CLUSTER', 'ADDSLOTS', *(str(x) for x in range(start_slot, end_slot)))
            except Exception:
                pass

        self.waitCluster()
        for shard in self.shards:
            try:
                shard.getConnection().execute_command('FT.CLUSTERREFRESH')
            except Exception:
                pass
        self.envIsUp = True

    def stopEnv(self):
        for shard in self.shards:
            shard.stopEnv()
        self.envIsUp = False

    def getConnection(self, shardId=1):
        return self.shards[shardId - 1].getConnection()

    def getClusterConnection(self):
        return rediscluster.StrictRedisCluster(startup_nodes=[{'host': 'localhost', 'port': self.shards[0].getMasterPort()}],
                                               decode_responses=True)

    def getSlaveConnection(self):
        raise Exception('unsupported')

    def flush(self):
        self.getClusterConnection().flushall()

    def dumpAndReload(self, restart=False, shardId=None):
        if shardId is None:
            for shard in self.shards:
                shard.dumpAndReload(restart=restart)
            self.waitCluster()
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

    def isUp(self):
        self.waitCluster()
        return True

    def exists(self, val):
        return self.getClusterConnection().exists(val)

    def hmset(self, *args):
        return self.getClusterConnection().hmset(*args)

    def keys(self, reg):
        return self.getClusterConnection().keys(reg)
