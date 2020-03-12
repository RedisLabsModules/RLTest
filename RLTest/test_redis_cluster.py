import shutil
import tempfile
from unittest import TestCase

from RLTest.env import Defaults
from RLTest.redis_cluster import ClusterEnv
from RLTest.test_common import REDIS_BINARY


class TestClusterEnv(TestCase):

    def setUp(self):
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
        pass

    def test_is_unix_socket(self):
        pass

    def test_is_tcp(self):
        pass

    def test_is_tls(self):
        pass

    def test_exists(self):
        pass

    def test_hmset(self):
        pass

    def test_keys(self):
        pass
