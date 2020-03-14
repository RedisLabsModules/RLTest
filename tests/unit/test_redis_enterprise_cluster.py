import shutil
import tempfile
from unittest import TestCase

from RLTest.env import Defaults
from RLTest.redis_enterprise_cluster import EnterpriseRedisClusterEnv


class TestEnterpriseRedisClusterEnv(TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        pass
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_wait_cluster(self):
        pass

    def test_dump_and_reload(self):
        pass

    def test_get_cluster_connection(self):
        pass

    def test_get_connection(self):
        pass

    def test_get_master_nodes_list(self):
        pass

    def test_get_ossmaster_nodes_connection_list(self):
        pass

    def test_is_up(self):
        pass

    def test_is_unix_socket(self):
        pass

    def test_is_tcp(self):
        pass

