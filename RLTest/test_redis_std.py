import os
import shutil
import tempfile
from unittest import TestCase

from RLTest.redis_std import StandardEnv

tlsCertFile = 'redis.crt'
tlsKeyFile = 'redis.key'
tlsCaCertFile = 'ca.crt'

REDIS_BINARY = os.environ.get("REDIS_BINARY", "redis-server")


class TestStandardEnv(TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        # Create a file in the temporary directory
        with open(os.path.join(self.test_dir, tlsCertFile), 'w') as f:
            f.write('tlsCertFile')
        with open(os.path.join(self.test_dir, tlsKeyFile), 'w') as f:
            f.write('tlsKeyFile')
        with open(os.path.join(self.test_dir, tlsCaCertFile), 'w') as f:
            f.write('tlsCaCertFile')

    def tearDown(self):
        # Remove the directory after the test
        shutil.rmtree(self.test_dir)

    def test__get_file_name(self):
        pass

    def test__get_vlgrind_file_path(self):
        pass

    def test_get_master_port(self):
        pass

    def test_get_password(self):
        pass

    def test_get_unix_path(self):
        pass

    def test_get_tlscert_file(self):
        pass

    def test_get_tlskey_file(self):
        pass

    def test_get_tlscacert_file(self):
        pass

    def test_has_interactive_debugger(self):
        pass

    def test_create_cmd_args_default(self):
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test')
        role = 'master'
        cmd_args = std_env.createCmdArgs(role)
        assert [REDIS_BINARY, '--port', '6379', '--logfile', std_env._getFileName(role, '.log'), '--dbfilename',
                std_env._getFileName(role, '.rdb')] == cmd_args

    def test_create_cmd_args_tls(self):
        port = 8000
        tls_std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', useTLS=True,
                                  tlsCertFile=os.path.join(self.test_dir, tlsCertFile),
                                  tlsKeyFile=os.path.join(self.test_dir, tlsKeyFile),
                                  tlsCaCertFile=os.path.join(self.test_dir, tlsCaCertFile), port=8000)
        role = 'master'
        cmd_args = tls_std_env.createCmdArgs(role)
        assert [REDIS_BINARY, '--port', '0', '--tls-port', '{}'.format(port), '--logfile',
                tls_std_env._getFileName(role, '.log'), '--dbfilename',
                tls_std_env._getFileName(role, '.rdb'), '--tls-cert-file', os.path.join(self.test_dir, tlsCertFile),
                '--tls-key-file', os.path.join(self.test_dir, tlsKeyFile), '--tls-ca-cert-file',
                os.path.join(self.test_dir, tlsCaCertFile)] == cmd_args

    def test_wait_for_redis_to_start(self):
        pass

    def test_get_pid(self):
        pass

    def test_get_port(self):
        pass

    def test_get_server_id(self):
        pass

    def test__print_env_data(self):
        pass

    def test_print_env_data(self):
        pass

    def test_start_env(self):
        pass

    def test__is_alive(self):
        pass

    def test__stop_process(self):
        pass

    def test_verbose_analyse_server_log(self):
        pass

    def test_stop_env(self):
        pass

    def test__get_connection(self):
        pass

    def test_get_connection(self):
        pass

    def test_get_ossmaster_nodes_connection_list(self):
        pass

    def test_get_slave_connection(self):
        pass

    def test_get_master_nodes_list(self):
        pass

    def test_flush(self):
        pass

    def test__wait_for_child(self):
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
