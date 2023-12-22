import os
import shutil
import tempfile
from unittest import TestCase

from RLTest.env import Defaults
from RLTest.redis_cluster import ClusterEnv
from tests.unit.test_common import REDIS_BINARY
from tests.unit.test_common import TLS_CERT, TLS_KEY, TLS_CACERT


class TestClusterEnv(TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        pass
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_print_env_data(self):
        pass

    def test_wait_cluster(self):
        pass

    def test_start_env(self):
        pass

    def test_stop_env(self):
        pass

    def test_start_stop_env(self):
        default_args = Defaults().getKwargs()
        default_args['dbDirPath'] = self.test_dir
        cluster_env = ClusterEnv(shardsCount=1, redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test',
                                 randomizePorts=Defaults.randomize_ports, **default_args)
        cluster_env.startEnv()
        # check that calling twice does not affect
        cluster_env.startEnv()
        cluster_env.stopEnv()

    def test_get_connection(self):
        pass

    def test_get_cluster_connection(self):
        pass

    def test_get_slave_connection(self):
        pass

    def test_get_master_nodes_list(self):
        pass

    def test_get_ossmaster_nodes_connection_list(self):
        pass

    def test_flush(self):
        pass

    def test_dump_and_reload(self):
        pass

    def test_broadcast(self):
        pass

    def test_check_exit_code(self):
        pass

    def test_is_up(self):
        default_args = Defaults().getKwargs()
        default_args['dbDirPath'] = self.test_dir
        cluster_env = ClusterEnv(shardsCount=1, redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test',
                                 randomizePorts=Defaults.randomize_ports, **default_args)
        cluster_env.startEnv()
        cluster_env.stopEnv()

    def test_is_unix_socket(self):
        default_args = Defaults().getKwargs()
        default_args['dbDirPath'] = self.test_dir
        cluster_env = ClusterEnv(shardsCount=1, redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test',
                                 randomizePorts=Defaults.randomize_ports, **default_args)
        cluster_env.startEnv()
        assert cluster_env.isUnixSocket() == False
        cluster_env.stopEnv()

    def test_is_tcp(self):
        default_args = Defaults().getKwargs()
        default_args['dbDirPath'] = self.test_dir
        cluster_env = ClusterEnv(shardsCount=1, redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test',
                                 randomizePorts=Defaults.randomize_ports, **default_args)
        cluster_env.startEnv()
        assert cluster_env.isTcp() == True
        cluster_env.stopEnv()

    def test_is_tls(self):
        default_args = Defaults().getKwargs()
        default_args['dbDirPath'] = self.test_dir
        cluster_env = ClusterEnv(shardsCount=1, redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test',
                                 randomizePorts=Defaults.randomize_ports, **default_args)
        # cluster_env.startEnv()
        assert cluster_env.isTLS() == False
        cluster_env.stopEnv()
        if not os.path.isfile(TLS_CERT) or not os.path.isfile(TLS_KEY) or not os.path.isfile(TLS_CACERT):
            self.skipTest("missing required tls files")
        default_args['useTLS'] = True
        default_args['tlsCertFile'] = TLS_CERT
        default_args['tlsKeyFile'] = TLS_KEY
        default_args['tlsCaCertFile'] = TLS_CACERT
        tls_cluster_env = ClusterEnv(shardsCount=1, redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test',
                                     randomizePorts=Defaults.randomize_ports, **default_args)
        tls_cluster_env.startEnv()
        assert tls_cluster_env.isTLS() == True
        tls_cluster_env.stopEnv()

    def test_exists(self):
        pass

    def test_hmset(self):
        pass

    def test_keys(self):
        pass

    def test_connection_by_key(self):
        shardsCount = 3
        default_args = Defaults().getKwargs()
        default_args['dbDirPath'] = self.test_dir
        cluster_env = ClusterEnv(shardsCount=shardsCount, redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test',
                                 randomizePorts=Defaults.randomize_ports, **default_args)
        cluster_env.startEnv()
        for i in range(shardsCount):
            key = 'x{%i}' % i
            con = cluster_env.getConnectionByKey(key, "set")
            assert(con.set(key, "1"))
        cluster_env.stopEnv()

    def test_add_shard_to_cluster(self):
        shardsCount = 3
        default_args = Defaults().getKwargs()
        default_args['dbDirPath'] = self.test_dir
        cluster_env = ClusterEnv(shardsCount=shardsCount, redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test',
                                 randomizePorts=Defaults.randomize_ports, **default_args)
        cluster_env.startEnv()
        cluster_env.addShardToCluster(REDIS_BINARY, '%s-test', **default_args)
        assert cluster_env.shardsCount == shardsCount+1
        new_shard_conn = cluster_env.getConnection(shardId=4)
        assert new_shard_conn.ping()
        assert new_shard_conn.cluster('info')['cluster_state'] == 'ok'
        cluster_env.stopEnv()
