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
        self.protocol = kwargs.get('protocol', 2)
        self.terminateRetries = kwargs.get('terminateRetries', None)
        self.terminateRetrySecs = kwargs.get('terminateRetrySecs', None)
        self.clusterStartTimeout = kwargs.pop('clusterStartTimeout', 40)
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

    def getInformationBeforeDispose(self):
        return [shard.getInformationBeforeDispose() for shard in self.shards]

    def getInformationAfterDispose(self):
        return [shard.getInformationAfterDispose() for shard in self.shards]

    def _countOk(self):
        """Returns count of shards reporting cluster_state:ok"""
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
        return ok

    def _agreeOk(self):
        return self._countOk() == len(self.shards)

    def _countAgreeSlots(self):
        """Returns count of shards that agree on slots view"""
        ok = 0
        first_view = None
        for shard in self.shards:
            con = shard.getConnection()
            try:
                slots_view = con.execute_command('CLUSTER', 'SLOTS')
            except Exception as e:
                print('got error on cluster slots, will try again, %s' % str(e))
                continue
            if first_view is None:
                first_view = slots_view
            if slots_view == first_view:
                ok += 1
        return ok

    def _agreeSlots(self):
        return self._countAgreeSlots() == len(self.shards)

    def waitCluster(self, timeout_sec=40, verbose=True):
        st = time.time()
        last_status_time = st
        status_interval = 5  # Print status every 5 seconds
        total_shards = len(self.shards)

        if verbose:
            print(Colors.Yellow('Waiting for cluster to be ready (timeout: %d seconds, %d shards)...' %
                                (timeout_sec, total_shards)))

        while st + timeout_sec > time.time():
            ok_count = self._countOk()
            slots_count = self._countAgreeSlots()

            if ok_count == total_shards and slots_count == total_shards:
                elapsed = time.time() - st
                if verbose:
                    print(Colors.Green('Cluster is ready after %.1f seconds' % elapsed))
                for shard in self.shards:
                    try:
                        shard.getConnection().execute_command('SEARCH.CLUSTERREFRESH')
                    except Exception:
                        pass
                return

            # Print periodic status update
            now = time.time()
            if verbose and (now - last_status_time) >= status_interval:
                elapsed = now - st
                print(Colors.Yellow('  Cluster wait: %.1fs elapsed - %d/%d shards OK, %d/%d agree on slots...' %
                                    (elapsed, ok_count, total_shards, slots_count, total_shards)))
                last_status_time = now

            time.sleep(0.1)
        raise RuntimeError(
            "Cluster OK wait loop timed out after %s seconds" % timeout_sec)

    def startEnv(self, masters=True, slaves=True):
        if self.envIsUp == True:
            return  # env is already up

        total_shards = len(self.shards)
        print(Colors.Yellow('Starting cluster with %d shards...' % total_shards))

        try:
            for i, shard in enumerate(self.shards):
                shard.startEnv(masters, slaves)
                if (i + 1) % 10 == 0 or (i + 1) == total_shards:
                    print(Colors.Yellow('  Started %d/%d shards...' % (i + 1, total_shards)))
        except Exception as e:
            print(Colors.Bred('Error starting shard %d: %s' % (i + 1, str(e))))
            print(Colors.Bred('Stopping all shards...'))
            for shard in self.shards:
                shard.stopEnv()
            raise

        print(Colors.Yellow('Configuring cluster topology...'))
        slots_per_node = int(16384 / len(self.shards)) + 1
        for i, shard in enumerate(self.shards):
            con = shard.getConnection()
            for s in self.shards:
                con.execute_command('CLUSTER', 'MEET',
                                    '127.0.0.1', s.getMasterPort())

            start_slot = i * slots_per_node
            end_slot = start_slot + slots_per_node - 1  # ADDSLOTSRANGE uses inclusive end
            if end_slot >= 16384:
                end_slot = 16383

            try:
                con.execute_command('CLUSTER', 'ADDSLOTSRANGE', start_slot, end_slot)
            except Exception as e:
                print(Colors.Bred('  Error assigning slots %d-%d to shard %d: %s' %
                                  (start_slot, end_slot, i + 1, str(e))))

            if (i + 1) % 10 == 0 or (i + 1) == total_shards:
                print(Colors.Yellow('  Configured %d/%d shards (slots %d-%d assigned)...' %
                                    (i + 1, total_shards, 0, end_slot)))

        self.waitCluster(timeout_sec=self.clusterStartTimeout)
        self.envIsUp = True
        self.envIsHealthy = True

    def stopEnvWithSegFault(self, masters=True, slaves=True):
        for shard in self.shards:
            shard.stopEnvWithSegFault(masters, slaves)

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
                decode_responses=self.decodeResponses,
                protocol=self.protocol,
                terminateRetries=self.terminateRetries, terminateRetrySecs=self.terminateRetrySecs
            )
        else:
            return redis.RedisCluster(
                startup_nodes=statupNode,
                decode_responses=self.decodeResponses, password=self.password,
                protocol=self.protocol,
                terminateRetries=self.terminateRetries, terminateRetrySecs=self.terminateRetrySecs)

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

    def addShardToCluster(self, redisBinaryPath, output_files_format, **kwargs):
        kwargs.pop('port')
        port = self.shards[-1].port + 2  # use a fresh port
        self.shardsCount += 1
        new_shard = StandardEnv(redisBinaryPath, port, outputFilesFormat=output_files_format,
                                serverId=self.shardsCount, clusterEnabled=True, **kwargs)
        try:
            new_shard.startEnv()
        except Exception:
            new_shard.stopEnv()
            raise
        self.shards.append(new_shard)
        # Notify other shards that the new shard is available and wait for the topology change to be acknowledged.
        conn = new_shard.getConnection()
        for s in self.shards:
            conn.execute_command('CLUSTER', 'MEET', '127.0.0.1', s.getMasterPort())
        self.waitCluster()

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
