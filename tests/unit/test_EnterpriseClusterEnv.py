import shutil
import tempfile
from unittest import TestCase

from RLTest.Enterprise import EnterpriseClusterEnv
from RLTest.env import Defaults
from tests.unit.test_common import DMC_PROXY_BINARY, REDIS_BINARY


class TestEnterpriseClusterEnv(TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        pass
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test_preper_module(self):
        pass

    def test_print_env_data(self):
        pass

    def test_start_env(self):
        pass

    def test_stop_env(self):
        default_args = Defaults().getKwargs()
        default_args['dbDirPath'] = self.test_dir
        default_args['libPath'] = self.test_dir
        default_args['shardsCount'] = 1
        default_args['dmcBinaryPath'] = DMC_PROXY_BINARY
        default_args['redisBinaryPath'] = REDIS_BINARY
        # TODO: install RE and enable this ( we need the DMC_PROXY_BINARY )
        # default_enterprise_cluster = EnterpriseClusterEnv(outputFilesFormat='%s-test',**default_args)

    def test_get_connection(self):
        pass

    def test_get_slave_connection(self):
        pass

    def test_flush(self):
        pass

    def test_dump_and_reload(self):
        pass

    def test_broadcast(self):
        pass

    def test_check_exit_code(self):
        pass

    def test_exists(self):
        pass

    def test_hmset(self):
        pass

    def test_keys(self):
        pass

    def test_is_up(self):
        pass
