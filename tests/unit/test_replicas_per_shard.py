"""Tests for the --replicas-per-shard / replicasPerShard feature.

The feature lets a cluster carry more than one replica per shard. It is
cluster-mode only; standalone mode is intentionally capped at a single
replica regardless of the requested value.
"""

import os
import shutil
import tempfile
from unittest import TestCase

from RLTest.env import Defaults
from RLTest.redis_cluster import ClusterEnv
from RLTest.redis_std import StandardEnv
from tests.unit.test_common import REDIS_BINARY


class TestReplicasPerShardStandardEnv(TestCase):
    """StandardEnv-level checks for the per-replica list bookkeeping."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_default_replicas_per_shard_is_one(self):
        env = StandardEnv(redisBinaryPath=REDIS_BINARY,
                          outputFilesFormat='%s-test',
                          dbDirPath=self.test_dir,
                          useSlaves=True)
        assert env.replicasPerShard == 1
        assert env.getNumSlaves() == 1
        assert len(env.slaveProcesses) == 1
        assert len(env.slavePorts) == 1
        # Legacy scalar accessor still works.
        assert env.slavePort == env.slavePorts[0]

    def test_standalone_caps_replicas_at_one(self):
        # Standalone (non-cluster) must stay single-slave; the request for 3
        # replicas is clamped back to 1.
        env = StandardEnv(redisBinaryPath=REDIS_BINARY,
                          outputFilesFormat='%s-test',
                          dbDirPath=self.test_dir,
                          useSlaves=True,
                          replicasPerShard=3)
        assert env.replicasPerShard == 1
        assert env.getNumSlaves() == 1

    def test_no_slaves_zeroes_replicas(self):
        env = StandardEnv(redisBinaryPath=REDIS_BINARY,
                          outputFilesFormat='%s-test',
                          dbDirPath=self.test_dir,
                          useSlaves=False,
                          replicasPerShard=4)
        assert env.replicasPerShard == 0
        assert env.getNumSlaves() == 0
        assert env.slavePorts == []

    def test_cluster_shard_multi_replicas_allocates_ports(self):
        # In cluster mode multi-replica is allowed; expect sequential ports
        # immediately after the master port.
        env = StandardEnv(redisBinaryPath=REDIS_BINARY,
                          outputFilesFormat='%s-test',
                          dbDirPath=self.test_dir,
                          useSlaves=True,
                          clusterEnabled=True,
                          replicasPerShard=3,
                          port=20000)
        assert env.replicasPerShard == 3
        assert env.getNumSlaves() == 3
        assert env.slavePorts == [20001, 20002, 20003]
        # Each replica gets its own server id, command line, and process slot.
        assert len(set(env.slaveServerIds)) == 3
        assert len(env.slaveCmdArgsList) == 3
        assert len(env.slaveProcesses) == 3
        # getSlavePort returns the right port per index.
        assert env.getSlavePort(0) == 20001
        assert env.getSlavePort(2) == 20003


class TestReplicasPerShardClusterEnv(TestCase):
    """End-to-end ClusterEnv tests that actually launch redis-server."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _build_default_args(self):
        default_args = Defaults().getKwargs()
        default_args['dbDirPath'] = self.test_dir
        return default_args

    def test_total_redises_three_shards_two_replicas(self):
        # Construction-time check: 3 shards * (1 master + 2 replicas) = 9 redises.
        default_args = self._build_default_args()
        default_args['useSlaves'] = True
        default_args['replicasPerShard'] = 2
        cluster_env = ClusterEnv(shardsCount=3, redisBinaryPath=REDIS_BINARY,
                                 outputFilesFormat='%s-test',
                                 randomizePorts=True, **default_args)
        try:
            assert len(cluster_env.shards) == 3
            assert cluster_env.replicasPerShard == 2
            total_redises = sum(1 + s.getNumSlaves() for s in cluster_env.shards)
            assert total_redises == 9
            for shard in cluster_env.shards:
                assert shard.getNumSlaves() == 2
                assert shard.replicasPerShard == 2
        finally:
            cluster_env.stopEnv()

    def test_start_three_shards_two_replicas_and_cluster_slots(self):
        # Run an actual cluster and verify CLUSTER SLOTS exposes 2 replica
        # entries per slot-range row.
        default_args = self._build_default_args()
        default_args['useSlaves'] = True
        default_args['replicasPerShard'] = 2
        cluster_env = ClusterEnv(shardsCount=3, redisBinaryPath=REDIS_BINARY,
                                 outputFilesFormat='%s-test',
                                 randomizePorts=True, **default_args)
        try:
            cluster_env.startEnv()
            # All 9 processes alive.
            for shard in cluster_env.shards:
                assert shard.masterProcess is not None
                assert shard.masterProcess.poll() is None
                assert shard.getNumSlaves() == 2
                for proc in shard.slaveProcesses:
                    assert proc is not None
                    assert proc.poll() is None
            # CLUSTER SLOTS should report 2 replicas per slot range.
            master_conn = cluster_env.shards[0].getConnection()
            slots_view = master_conn.execute_command('CLUSTER', 'SLOTS')
            assert len(slots_view) == 3
            for row in slots_view:
                # row = [start, end, master_entry, replica_entry, replica_entry]
                assert len(row) == 5, (
                    'expected 2 replica entries per slot row, got row=%r' % (row,))
            # Each replica should be cluster-enabled.
            for shard in cluster_env.shards:
                for i in range(shard.getNumSlaves()):
                    replica_conn = shard.getSlaveConnection(i)
                    info = replica_conn.execute_command('INFO', 'cluster')
                    if isinstance(info, dict):
                        # decoded response client
                        assert info.get('cluster_enabled') in (1, '1', True)
                    else:
                        assert b'cluster_enabled:1' in info or 'cluster_enabled:1' in str(info)
        finally:
            cluster_env.stopEnv()
