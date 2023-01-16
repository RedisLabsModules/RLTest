from __future__ import print_function

from .redis_std import StandardEnv
from redis.cluster import ClusterNode
import redis
import time
from RLTest.utils import Colors


class ClusterEnv(object):
    def __init__(self, **kwargs):
        self.shards = []
        self.envIsUp = False
        self.envIsHealthy = False
        self.modulePath = kwargs['modulePath']
        self.moduleArgs = kwargs['moduleArgs']
        self.password = kwargs['password']
        self.shardsCount = kwargs.pop('shardsCount')
        useSlaves = kwargs.get('useSlaves', False)
        self.useTLS = kwargs['useTLS']
        self.decodeResponses = kwargs.get('decodeResponses', False)
        self.tlsPassphrase = kwargs.get('tlsPassphrase', None)
        startPort = kwargs.pop('port', 10000)
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
                try:
                    status = con.execute_command('CLUSTER', 'INFO')
                except Exception as e:
                    print('got error on cluster info, will try again, %s' % str(e))
                    continue
                if 'cluster_state:ok' in str(status):
                    ok += 1
            if ok == len(self.shards):
                for shard in self.shards:
                    try:
                        shard.getConnection().execute_command('FT.CLUSTERREFRESH')
                    except Exception:
                        pass
                    try:
                        shard.getConnection().execute_command('SEARCH.CLUSTERREFRESH')
                    except Exception:
                        pass
                return

            time.sleep(0.1)
        raise RuntimeError(
            "Cluster OK wait loop timed out after %s seconds" % timeout_sec)

    def startEnv(self, masters=True, slaves=True):
        if self.envIsUp == True:
            return  # env is already up
        try:
            for shard in self.shards:
                shard.startEnv(masters, slaves)
        except Exception:
            for shard in self.shards:
                shard.stopEnv()
            raise

        slots_per_node = int(16384 / len(self.shards)) + 1
        for i, shard in enumerate(self.shards):
            con = shard.getConnection()
            for s in self.shards:
                con.execute_command('CLUSTER', 'MEET',
                                    '127.0.0.1', s.getMasterPort())

            start_slot = i * slots_per_node
            end_slot = start_slot + slots_per_node
            if end_slot > 16384:
                end_slot = 16384

            try:
                con.execute_command('CLUSTER', 'ADDSLOTS', *(str(x)
                                    for x in range(start_slot, end_slot)))
            except Exception:
                pass

        self.waitCluster()
        self.envIsUp = True
        self.envIsHealthy = True

    def stopEnv(self, masters=True, slaves=True):
        self.envIsUp = False
        self.envIsHealthy = False
        for shard in self.shards:
            shard.stopEnv(masters, slaves)
            self.envIsUp = self.envIsUp or shard.envIsUp
            self.envIsHealthy = self.envIsHealthy and shard.envIsUp

    def getConnection(self, shardId=1):
        return self.shards[shardId - 1].getConnection()

    def getClusterConnection(self):
        statupNode = [ClusterNode(a['host'], a['port']) for a in self.getMasterNodesList()]
        if self.useTLS:
            return redis.RedisCluster(
                ssl=True,
                ssl_keyfile=self.shards[0].getTLSKeyFile(),
                ssl_certfile=self.shards[0].getTLSCertFile(),
                ssl_cert_reqs=None,
                ssl_ca_certs=self.shards[0].getTLSCACertFile(),
                ssl_password=self.tlsPassphrase,
                password=self.password,
                startup_nodes=statupNode,
                decode_responses=self.decodeResponses
            )
        else:
            return redis.RedisCluster(
                startup_nodes=statupNode,
                decode_responses=self.decodeResponses, password=self.password)

    def getSlaveConnection(self):
        raise Exception('unsupported')

    # List of nodes that initial bootstrapping can be done from
    def getMasterNodesList(self):
        full_master_list = []
        for shard in self.shards:
            node_info_list = shard.getMasterNodesList()
            full_master_list.append(node_info_list[0])
        return full_master_list

    # List containing a connection for each of the master nodes
    def getOSSMasterNodesConnectionList(self):
        full_master_connection_list = []
        for shard in self.shards:
            full_master_connection_list.append(shard.getConnection())
        return full_master_connection_list

    # Gets a cluster connection by key. On std redis the default connection is returned.
    def getConnectionByKey(self, key, command):
        clusterConn = self.getClusterConnection()
        target_node = clusterConn._determine_nodes(command, key) # we will always which will give us the node responsible for the key
        return clusterConn.get_redis_connection(target_node[0])

    def flush(self):
        self.getClusterConnection().flushall()

    def dumpAndReload(self, restart=False, shardId=None, timeout_sec=40):
        if shardId is None:
            for shard in self.shards:
                shard.dumpAndReload(restart=restart)
            self.waitCluster(timeout_sec=timeout_sec)
        else:
            self.shards[shardId -
                        1].dumpAndReload(restart=restart, shardId=None, timeout_sec=timeout_sec)

    def broadcast(self, *cmd):
        for shard in self.shards:
            shard.broadcast(*cmd)

    def checkExitCode(self):
        for shard in self.shards:
            if not shard.checkExitCode():
                return False
        return True

    def isUp(self):
        return self.envIsUp or self.envIsHealthy and self.waitCluster()

    def isHealthy(self):
        return self.envIsHealthy

    def isUnixSocket(self):
        return False

    def isTcp(self):
        return True

    def isTLS(self):
        return self.useTLS

    def exists(self, val):
        return self.getClusterConnection().exists(val)

    def hmset(self, *args):
        return self.getClusterConnection().hmset(*args)

    def keys(self, reg):
        return self.getClusterConnection().keys(reg)
