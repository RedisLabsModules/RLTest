from __future__ import print_function

from .redis_std import StandardEnv, MASTER, SLAVE
from redis.cluster import ClusterNode
import redis
import time
from RLTest.utils import Colors

# Interval in seconds between status updates during cluster wait
CLUSTER_STATUS_INTERVAL_SEC = 5

# Brief pause to let master-to-master gossip settle before/after slave MEET.
GOSSIP_SETTLE_SEC = 0.5
# Max attempts when issuing CLUSTER REPLICATE on a freshly-MEET'd slave; the
# slave may not yet have learned the master's node id via gossip.
REPLICATE_RETRY_MAX = 20
# Sleep between CLUSTER REPLICATE retries.
REPLICATE_RETRY_INTERVAL_SEC = 0.25


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
        # replicasPerShard is the number of replicas attached to each shard's
        # master. Default 1 preserves prior single-replica behavior. Only
        # honored when useSlaves is True; otherwise treated as 0.
        self.replicasPerShard = kwargs.get('replicasPerShard', 1) if useSlaves else 0
        self.useTLS = kwargs['useTLS']
        self.decodeResponses = kwargs.get('decodeResponses', False)
        self.tlsPassphrase = kwargs.get('tlsPassphrase', None)
        self.protocol = kwargs.get('protocol', 2)
        self.terminateRetries = kwargs.get('terminateRetries', None)
        self.terminateRetrySecs = kwargs.get('terminateRetrySecs', None)
        self.verbose = kwargs.get('verbose', False)
        self.clusterStartTimeout = kwargs.pop('clusterStartTimeout', 40)
        startPort = kwargs.pop('port', 10000)
        # Each shard owns one master plus N replicas, so allocate
        # shardsCount * (1 + replicasPerShard) total redises when useSlaves is
        # set. With replicasPerShard == 1 this equals the previous 2x layout.
        instancesPerShard = (1 + self.replicasPerShard) if useSlaves else 1
        totalRedises = self.shardsCount * instancesPerShard
        randomizePorts = kwargs.pop('randomizePorts', False)
        # Per-shard port stride: must leave room for the master plus all of
        # its replicas. The historical stride was 2 (matching 1 master + 1
        # slave); with N replicas it grows to 1 + N. When useSlaves is off the
        # stride stays at 2 to match the pre-feature default.
        portStride = (1 + self.replicasPerShard) if useSlaves else 2
        for i in range(0, totalRedises, instancesPerShard):
            port = 0 if randomizePorts else startPort
            shard = StandardEnv(port=port, serverId=(i + 1),
                                clusterEnabled=True, **kwargs)
            self.shards.append(shard)
            startPort += portStride

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

    @staticmethod
    def _normalizeSlotsView(slots_view):
        """Returns a hashable representation of CLUSTER SLOTS that is invariant
        to per-shard replica ordering.

        Each CLUSTER SLOTS row is
            [start, end, master_entry, replica_entry, replica_entry, ...]
        Different masters can report the replica entries in different orders
        when there is more than one replica per shard; that is not a real
        disagreement on the topology. We sort replicas within each row before
        comparing so multi-replica clusters can converge.
        """
        if slots_view is None:
            return None
        normalized = []
        for row in slots_view:
            if len(row) < 3:
                normalized.append(tuple(row))
                continue
            start, end, master_entry = row[0], row[1], row[2]
            replicas = sorted((tuple(r) for r in row[3:]),
                              key=lambda r: tuple(repr(x) for x in r))
            normalized.append((start, end, tuple(master_entry)) + tuple(replicas))
        normalized.sort()
        return tuple(normalized)

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
            normalized = self._normalizeSlotsView(slots_view)
            if first_view is None:
                first_view = normalized
            if normalized == first_view:
                ok += 1
        return ok

    def _expectedReplicasInSlots(self):
        """Return total live slaves across all shards.

        Counts from shard.slaveProcesses (process-side), not from CLUSTER SLOTS.
        This is robust to non-contiguous slot distributions during partial
        migration -- the process count is authoritative regardless of how
        CLUSTER SLOTS rows are partitioned.

        Each shard reports one slot-range row, and that row contains one
        replica entry per running slave attached to that shard's master.
        Returns 0 when no slaves are configured.
        """
        total = 0
        for shard in self.shards:
            if not getattr(shard, 'useSlaves', False):
                continue
            for proc in getattr(shard, 'slaveProcesses', []):
                if proc is not None:
                    total += 1
        return total

    def _countReplicasInSlots(self):
        """Returns the number of replica entries reported across all shards.

        Queries CLUSTER SLOTS from a master and counts the replica entries
        (positions after the first master entry in each slot row). Only the
        first master is queried because all masters should agree post-gossip.
        """
        if not self.shards:
            return 0
        con = self.shards[0].getConnection()
        try:
            slots_view = con.execute_command('CLUSTER', 'SLOTS')
        except Exception as e:
            print('got error on cluster slots, will try again, %s' % str(e))
            return 0
        count = 0
        for row in slots_view:
            # row = [start, end, master_entry, replica_entry, replica_entry, ...]
            if len(row) > 3:
                count += len(row) - 3
        return count

    def waitCluster(self, timeout_sec=40, verbose=True):
        st = time.time()
        last_status_time = st
        total_shards = len(self.shards)
        expected_replicas = self._expectedReplicasInSlots()

        if verbose:
            print(Colors.Yellow('Waiting for cluster to be ready (timeout: %d seconds, %d shards, %d replicas)...' %
                                (timeout_sec, total_shards, expected_replicas)))

        while st + timeout_sec > time.time():
            ok_count = self._countOk()
            slots_count = self._countAgreeSlots()
            replicas_count = self._countReplicasInSlots() if expected_replicas else 0

            if (ok_count == total_shards and slots_count == total_shards
                    and replicas_count >= expected_replicas):
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
            if verbose and (now - last_status_time) >= CLUSTER_STATUS_INTERVAL_SEC:
                elapsed = now - st
                if expected_replicas:
                    print(Colors.Yellow(
                        '  Cluster wait: %.1fs elapsed - %d/%d shards OK, %d/%d agree on slots, %d/%d replicas visible...'
                        % (elapsed, ok_count, total_shards, slots_count, total_shards,
                           replicas_count, expected_replicas)))
                else:
                    print(Colors.Yellow('  Cluster wait: %.1fs elapsed - %d/%d shards OK, %d/%d agree on slots...' %
                                        (elapsed, ok_count, total_shards, slots_count, total_shards)))
                last_status_time = now

            time.sleep(0.1)
        raise RuntimeError(
            "Cluster OK wait loop timed out after %s seconds" % timeout_sec)

    def _attachSlavesToCluster(self):
        """Attach slaves to their masters via CLUSTER MEET + CLUSTER REPLICATE.

        Each StandardEnv shard owns one master and (when useSlaves is True)
        one or more slaves (controlled by --replicas-per-shard). Slaves were
        booted with --cluster-enabled but no master link (see redis_std.py).
        Now that masters have MEET'd each other and slots are assigned, MEET
        every slave from its master so the slave joins gossip, then issue
        CLUSTER REPLICATE on each slave's connection to attach it to the
        master.
        """
        total_shards = len(self.shards)
        # Total live slaves across all shards.
        total_slaves = sum(
            sum(1 for p in getattr(s, 'slaveProcesses', []) if p is not None)
            for s in self.shards
            if getattr(s, 'useSlaves', False)
        )
        if total_slaves == 0:
            return

        if self.verbose:
            print(Colors.Yellow('Attaching %d slave(s) to cluster...' % total_slaves))

        # Briefly wait for masters to finish gossiping with each other.
        time.sleep(GOSSIP_SETTLE_SEC)

        # Phase 1: MEET each slave from its master so the slave joins gossip.
        master_node_ids = {}
        for i, shard in enumerate(self.shards):
            if not getattr(shard, 'useSlaves', False):
                continue
            live_slave_indices = [j for j, p in enumerate(shard.slaveProcesses) if p is not None]
            if not live_slave_indices:
                continue
            master_conn = shard.getConnection()
            master_node_id = master_conn.execute_command('CLUSTER', 'MYID')
            if isinstance(master_node_id, bytes):
                master_node_id = master_node_id.decode()
            master_node_ids[i] = (master_node_id, live_slave_indices)
            for j in live_slave_indices:
                slave_port = shard.getSlavePort(j)
                master_conn.execute_command('CLUSTER', 'MEET', '127.0.0.1', slave_port)

        # Allow gossip to propagate so each slave sees the master it will replicate.
        time.sleep(GOSSIP_SETTLE_SEC)

        # Phase 2: CLUSTER REPLICATE on each slave connection.
        for i, shard in enumerate(self.shards):
            if i not in master_node_ids:
                continue
            master_node_id, live_slave_indices = master_node_ids[i]
            for j in live_slave_indices:
                slave_conn = shard.getSlaveConnection(j)
                # Retry briefly to handle the race where the slave has not yet
                # learned the master node id via gossip.
                attached = False
                last_err = None
                for _ in range(REPLICATE_RETRY_MAX):
                    try:
                        slave_conn.execute_command('CLUSTER', 'REPLICATE', master_node_id)
                        attached = True
                        break
                    except Exception as e:
                        last_err = e
                        time.sleep(REPLICATE_RETRY_INTERVAL_SEC)
                if not attached:
                    raise RuntimeError(
                        'CLUSTER REPLICATE failed for shard %d/%d slave[%d]: %s'
                        % (i + 1, total_shards, j, last_err))
                if self.verbose:
                    label = ('slave' if len(live_slave_indices) == 1
                             else 'slave[%d]' % j)
                    print(Colors.Yellow('  Attached %s for shard %d/%d (replicate %s)' %
                                        (label, i + 1, total_shards, master_node_id[:8])))

    def startEnv(self, masters=True, slaves=True):
        if self.envIsUp == True:
            return  # env is already up

        total_shards = len(self.shards)
        if self.verbose:
            print(Colors.Yellow('Starting cluster with %d shards...' % total_shards))

        try:
            for i, shard in enumerate(self.shards):
                shard.startEnv(masters, slaves)
                if self.verbose:
                    print(Colors.Yellow('  Started shard %d/%d' % (i + 1, total_shards)))
        except Exception as e:
            print(Colors.Bred('Error starting shard %d: %s' % (i + 1, str(e))))
            print(Colors.Bred('Stopping all shards...'))
            for shard in self.shards:
                shard.stopEnv()
            raise

        if self.verbose:
            print(Colors.Yellow('Configuring cluster topology...'))
        slots_per_node = int(16384 / len(self.shards)) + 1
        try:
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
                except Exception as e:
                    print(Colors.Bred('  Error assigning slots %d-%d to shard %d: %s' %
                                      (start_slot, end_slot - 1, i + 1, str(e))))

                if self.verbose:
                    print(Colors.Yellow('  Configured shard %d/%d (slots %d-%d)' %
                                        (i + 1, total_shards, start_slot, min(end_slot - 1, 16383))))

            # Attach slaves (if any) before waiting for cluster_state:ok so the
            # final waitCluster call also covers replica readiness.
            self._attachSlavesToCluster()

            self.waitCluster(timeout_sec=self.clusterStartTimeout, verbose=self.verbose)
        except Exception:
            # Topology phase failures (waitCluster timeout, REPLICATE retry
            # exhaustion, etc.) would otherwise leak every redis-server we
            # already booted in the shard loop above. Tear them down.
            self.stopEnv()
            raise
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
        # Skip past the previous shard's master and all of its replicas so we
        # land on a free port. With replicasPerShard==1 the stride is 2,
        # matching the prior +2 hop.
        port_stride = 1 + self.replicasPerShard if self.replicasPerShard else 2
        port = self.shards[-1].port + port_stride  # use a fresh port
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
