from OssEnv import OssEnv
import redis
import rediscluster
import time


class OssClusterEnv():
    def __init__(self, redisBinaryPath, modulePath=None, moduleArgs=None, outputFilesFormat=None,
                 dbDirPath=None, useSlaves=False, shardsCount=1):
        self.redisBinaryPath = redisBinaryPath
        self.modulePath = modulePath
        self.moduleArgs = moduleArgs
        self.outputFilesFormat = outputFilesFormat
        self.dbDirPath = dbDirPath
        self.useSlaves = useSlaves
        self.shardsCount = shardsCount
        self.shards = []
        self.envIsUp = False

        startPort = 20000
        totalRedises = self.shardsCount * (2 if useSlaves else 1)
        for i in range(0, totalRedises, (2 if useSlaves else 1)):
            shard = OssEnv(redisBinaryPath=redisBinaryPath, port=startPort, modulePath=self.modulePath, moduleArgs=self.moduleArgs,
                           outputFilesFormat=self.outputFilesFormat, dbDirPath=dbDirPath, useSlaves=useSlaves,
                           serverId=(i + 1), clusterEnabled=True)
            self.shards.append(shard)
            startPort += 2

    def PrintEnvData(self, prefix=''):
        pass

    def waitCluster(self, timeout_sec=5):

        st = time.time()
        ok = 0

        while st + timeout_sec > time.time():
            ok = 0
            for shard in self.shards:
                con = shard.GetConnection()
                status = con.cluster('INFO')
                if status.get('cluster_state') == 'ok':
                    ok += 1
            if ok == len(self.shards):
                return

            time.sleep(0.0001)
        raise RuntimeError("Cluster OK wait loop timed out after %s seconds" % timeout_sec)

    def StartEnv(self):
        if self.envIsUp:
            return  # env is already up
        for shard in self.shards:
            shard.StartEnv()

        slots_per_node = int(16384 / len(self.shards)) + 1
        for i, shard in enumerate(self.shards):
            con = shard.GetConnection()
            for s in self.shards:
                con.cluster('MEET', '127.0.0.1', s.GetMasterPort())

            start_slot = i * slots_per_node
            end_slot = start_slot + slots_per_node
            if end_slot > 16384:
                end_slot = 16384

            try:
                con.cluster('ADDSLOTS', *(str(x) for x in range(start_slot, end_slot)))
            except Exception:
                pass

        self.waitCluster()
        self.envIsUp = True

    def StopEnv(self):
        for shard in self.shards:
            shard.StopEnv()
        self.envIsUp = False

    def GetConnection(self):
        return rediscluster.StrictRedisCluster(startup_nodes=[{'host': 'localhost', 'port': self.shards[0].GetMasterPort()}],
                                               decode_responses=True)

    def GetSlaveConnection(self):
        raise Exception('unsupported')

    def Flush(self):
        self.GetConnection().flushall()
