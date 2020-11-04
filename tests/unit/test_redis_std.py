import os
import shutil
import tempfile
from unittest import TestCase

from RLTest.redis_std import StandardEnv
from tests.unit.test_common import REDIS_BINARY, TLS_CERT, TLS_KEY, TLS_CACERT

tlsCertFile = 'fake_redis.crt'
tlsKeyFile = 'fake_redis.key'
tlsCaCertFile = 'fake_ca.crt'


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

    def test__get_valgrind_file_path(self):
        pass

    def test_get_master_port(self):
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir)
        assert std_env.getMasterPort() == 6379
        env2 = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir,
                           port=10000)
        assert env2.getMasterPort() == 10000
        pass

    def test_get_password(self):
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir)
        assert std_env.getPassword() == None
        std_env_pass = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir,
                                   password="passwd")
        assert std_env_pass.getPassword() == "passwd"

    def test_get_unix_path(self):
        pass

    def test_get_tlscert_file(self):
        if not os.path.isfile(TLS_CERT) or not os.path.isfile(TLS_KEY) or not os.path.isfile(TLS_CACERT):
            self.skipTest("missing required tls files")
        tls_std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', useTLS=True,
                                  tlsCertFile=os.path.join(self.test_dir, tlsCertFile),
                                  tlsKeyFile=os.path.join(self.test_dir, tlsKeyFile),
                                  tlsCaCertFile=os.path.join(self.test_dir, tlsCaCertFile), port=8000)
        assert os.path.join(self.test_dir, tlsCertFile) == tls_std_env.getTLSCertFile()

    def test_get_tlskey_file(self):
        if not os.path.isfile(TLS_CERT) or not os.path.isfile(TLS_KEY) or not os.path.isfile(TLS_CACERT):
            self.skipTest("missing required tls files")
        tls_std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', useTLS=True,
                                  tlsCertFile=os.path.join(self.test_dir, tlsCertFile),
                                  tlsKeyFile=os.path.join(self.test_dir, tlsKeyFile),
                                  tlsCaCertFile=os.path.join(self.test_dir, tlsCaCertFile), port=8000)
        assert os.path.join(self.test_dir, tlsKeyFile) == tls_std_env.getTLSKeyFile()

    def test_get_tlscacert_file(self):
        if not os.path.isfile(TLS_CERT) or not os.path.isfile(TLS_KEY) or not os.path.isfile(TLS_CACERT):
            self.skipTest("missing required tls files")
        tls_std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', useTLS=True,
                                  tlsCertFile=os.path.join(self.test_dir, tlsCertFile),
                                  tlsKeyFile=os.path.join(self.test_dir, tlsKeyFile),
                                  tlsCaCertFile=os.path.join(self.test_dir, tlsCaCertFile), port=8000)
        assert os.path.join(self.test_dir, tlsCaCertFile) == tls_std_env.getTLSCACertFile()

    def test_has_interactive_debugger(self):
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test')
        assert std_env.has_interactive_debugger == None

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
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir)
        assert std_env.getPort('master') == 6379
        std_env_slave = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir,
                                    useSlaves=True)
        assert std_env_slave.getPort('slave') == 6380
        env2 = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir,
                           port=10000)
        assert env2.getPort('master') == 10000

        env2_slave = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir,
                                 useSlaves=True, port=10000)
        assert env2_slave.getPort('slave') == 10001

    def test_get_server_id(self):
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir)
        assert std_env.getServerId('master') == 1
        std_env_id2 = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir,
                                  serverId=2)
        assert std_env_id2.getServerId('master') == 2

    def test__print_env_data(self):
        pass

    def test_print_env_data(self):
        pass

    def test__is_alive(self):
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir)
        assert std_env.isUp() == False
        std_env.startEnv()
        assert std_env._isAlive(std_env.masterProcess) == True
        std_env.stopEnv()
        assert std_env._isAlive(std_env.masterProcess) == False

    def test__stop_process(self):
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir, useSlaves=True)
        assert std_env.isUp() == False
        std_env.startEnv()
        assert std_env._isAlive(std_env.masterProcess) == True
        assert std_env._isAlive(std_env.slaveProcess) == True
        std_env.stopEnv()
        assert std_env._isAlive(std_env.masterProcess) == False
        assert std_env._isAlive(std_env.slaveProcess) == False

        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir, useSlaves=True)
        assert std_env.isUp() == False
        std_env.startEnv()
        assert std_env._isAlive(std_env.masterProcess) == True
        assert std_env._isAlive(std_env.slaveProcess) == True
        assert std_env.isUp() == True
        assert  std_env.isHealthy() == True
        std_env.stopEnv(masters=True, slaves=False)
        assert std_env._isAlive(std_env.masterProcess) == False
        assert std_env._isAlive(std_env.slaveProcess) == True
        assert std_env.isUp() == True
        assert std_env.isHealthy() == False
        std_env.stopEnv(slaves=True)
        assert std_env._isAlive(std_env.masterProcess) == False
        assert std_env._isAlive(std_env.slaveProcess) == False
        assert std_env.isUp() == False
        assert std_env.isHealthy() == False


    def test_verbose_analyse_server_log(self):
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
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir)
        assert std_env.isUp() == False
        std_env.startEnv()
        assert std_env.isUp() == True
        std_env.stopEnv()
        assert std_env.isUp() == False

    def test_is_unix_socket(self):
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir)
        assert std_env.isUnixSocket() == False

    def test_is_tcp(self):
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir)
        assert std_env.isTcp() == True

    def test_is_tls(self):
        std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir)
        std_env.startEnv()
        assert std_env.isTLS() == False
        std_env.stopEnv()
        if not os.path.isfile(TLS_CERT) or not os.path.isfile(TLS_KEY) or not os.path.isfile(TLS_CACERT):
            self.skipTest("missing required tls files")

        tls_std_env = StandardEnv(redisBinaryPath=REDIS_BINARY, outputFilesFormat='%s-test', dbDirPath=self.test_dir,
                                  useTLS=True,
                                  tlsCertFile=TLS_CERT,
                                  tlsKeyFile=TLS_KEY,
                                  tlsCaCertFile=TLS_CACERT)
        tls_std_env.startEnv()
        assert tls_std_env.isTLS() == True
        tls_std_env.stopEnv()

    def test_exists(self):
        pass

    def test_hmset(self):
        pass

    def test_keys(self):
        pass
