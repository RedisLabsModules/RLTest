from __future__ import print_function
import subprocess
import redis
import os
from RLTest.utils import wait_for_conn, Colors


class CcsMock():
    CCS_UNIX_SOCKET_DEFAULT_PATH = '/tmp/ccs.sock'
    CCS_DB_RDB_FILE_NAME = 'syncer-pixie-ccs.rdb'
    CCS_LOG_FILE_NAME = 'ccs.log'

    def __init__(self, redisBinaryPath, proxyPort, directory=None, useSlaves=False, password=None, libPath=None):
        self.redisBinaryPath = os.path.expanduser(redisBinaryPath) if redisBinaryPath.startswith('~/') else redisBinaryPath
        self.useSlaves = useSlaves
        self.directory = directory
        self.generateArgs()
        self.libPath = os.path.expanduser(libPath) if libPath.startswith('~/') else libPath
        self.env = {}
        if self.libPath:
            self.env['LD_LIBRARY_PATH'] = self.libPath
        self.password = password
        self.proxyPort = proxyPort

    def generateArgs(self):
        self.args = self.redisBinaryPath.split()
        if self.directory:
            self.args += ['--dir', self.directory]
        self.args += ['--port', '0',
                      '--unixsocket', self.CCS_UNIX_SOCKET_DEFAULT_PATH,
                      '--dbfilename', self.CCS_DB_RDB_FILE_NAME,
                      '--logfile', self.CCS_LOG_FILE_NAME]

    def Start(self, shards, bdb_fields=None, endpoint_ccs_params=None, legacy_hash_slots=True, extra_keys=None):
        self.setup(shards, bdb_fields, endpoint_ccs_params, legacy_hash_slots, extra_keys)

    def Stop(self):
        if self.process:
            try:
                self.process.terminate()
                self.process.wait()
            except OSError:
                pass
            self.process = None

    def PrintEnvData(self, prefix=''):
        print(Colors.Yellow(prefix + 'pid: %d' % self.process.pid))
        print(Colors.Yellow(prefix + 'unix socket: %s' % self.CCS_UNIX_SOCKET_DEFAULT_PATH))
        print(Colors.Yellow(prefix + 'binary path: %s' % self.redisBinaryPath))
        if self.directory:
            print(Colors.Yellow(prefix + 'db dir path: %s' % (self.directory)))
        print(Colors.Yellow(prefix + 'rdb file name: %s' % (self.CCS_DB_RDB_FILE_NAME)))
        print(Colors.Yellow(prefix + 'log file name: %s' % (self.CCS_LOG_FILE_NAME)))
        if self.libPath:
            print(Colors.Yellow(prefix + 'lib path: %s' % (self.libPath)))

    def setup(self, shards, bdb_fields=None, endpoint_ccs_params=None, legacy_hash_slots=True, extra_keys=None):

        self.process = subprocess.Popen(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, args=self.args, env=self.env)

        # Create fake cluster, node and dmc objects
        self.conn = redis.Redis(unix_socket_path=self.CCS_UNIX_SOCKET_DEFAULT_PATH)
        wait_for_conn(self.conn)

        self.conn.hmset('cluster', {'name': 'fakecluster'})
        self.conn.hmset('node:1', {'addr': '127.0.0.1',
                                   'dmc_uid': '1'})
        self.conn.sadd('node:all', '1')
        self.conn.hmset('dmc:1', {'threads': '1',
                                  'max_threads': '1',
                                  'log_level': 'info'})
        self.conn.sadd('dmc:all', '1')
        # self.conn.hmset('cluster_cert', {"syncer_cert": "syncer_cert", "syncer_key": "syncer_key"}) todo: check if needed
        self.disperse_shards = False
        self.next_node_uid = 1

        self.create_bdb(shards, bdb_fields, endpoint_ccs_params, legacy_hash_slots, extra_keys)

    def set_server_ccs_values(self, serverId, port, assigned_slots, bdb_uid, role):
        """
        Set all the neccesary values of a server in the ccs
        """
        redis_uid = serverId
        self.conn.hmset('redis:%s' % str(redis_uid),
                        {'port': port,
                         'node_uid': str(self.next_node_uid),
                         'bdb_uid': bdb_uid,
                         'role': role,
                         'assigned_slots': assigned_slots})
        self.conn.sadd('redis:all', redis_uid)
        # we promote the node uid just in case of master shard because we want disperion of master shards
        if role == 'master' and self.disperse_shards:
            n_nodes = len(self.conn.smembers('node:all'))
            self.next_node_uid = self.next_node_uid % n_nodes + 1

    def update_bdb_redis_list(self, bdb_uid, shards):
        """
        Update the redis list in the ccs of the given bdb
        """
        bdb_uid = str(bdb_uid)
        redis_uids = []
        for shard in shards:
            redis_uids.append(str(shard.masterServerId))
            if self.useSlaves:
                redis_uids.append(str(shard.slaveServerId))
        self.conn.hset('bdb:%s' % bdb_uid, 'redis_list', ','.join(redis_uids))

    def create_bdb(self, shards, bdb_fields=None, endpoint_ccs_params=None, legacy_hash_slots=True, extra_keys=None):
        bdb_uid = 1
        port = self.proxyPort

        if legacy_hash_slots:
            number_of_slots_in_bdb = 4096
            translation_offset = 1
        else:
            number_of_slots_in_bdb = 16384
            translation_offset = 0
        slots_per_shard = float(number_of_slots_in_bdb) / len(shards)
        first_slot = translation_offset
        last_slot = number_of_slots_in_bdb - 1 + translation_offset

        start_slots = [int(round(first_slot + i * slots_per_shard)) for i in range(len(shards))]
        end_slots = [next_start_slot - 1 for next_start_slot in start_slots[1:]] + [last_slot]
        slots = ["%s-%s" % (pair[0], pair[1]) for pair in zip(start_slots, end_slots)]

        for index, shard in enumerate(shards):
            self.set_server_ccs_values(shard.masterServerId, shard.port, str(slots[index]), bdb_uid, 'master')

            if self.useSlaves:
                self.set_server_ccs_values(shard.slaveServerId, shard.GetSlavePort(), str(slots[index]), bdb_uid, 'slave')

        self.conn.hmset('bdb:%s' % bdb_uid,
                        {'shards_count': len(shards),
                         'type': 'redis',
                         'endpoint_list': '%s:1' % bdb_uid,
                         'replication': ('enabled' if self.useSlaves else 'disabled'),
                         'authentication_admin_pass': 'secret',
                         'internal_pass': self.password,
                         'redis_version': '4.0',
                         'implicit_shard_key': 'enabled'})

        if legacy_hash_slots:
            self.conn.hmset('bdb:%s' % bdb_uid,
                            {'hash_slots_policy': 'legacy',
                             'shard_function': 'crc12'})
        else:
            self.conn.hmset('bdb:%s' % bdb_uid,
                            {'hash_slots_policy': '16k'})

        if bdb_fields:
            self.conn.hmset('bdb:%s' % bdb_uid, bdb_fields)
            # if 'ssl' in bdb_fields and bdb_fields['ssl'] in ["enabled", "replica_ssl"]:
            #     with open(CLIENT_CERT_FILE, 'r') as cert_file:
            #         cert = cert_file.readlines()
            #     self.conn.hmset('bdb:%s' % bdb_uid,
            #                     {'authentication_ssl_client_certs': "".join(cert)})

        if extra_keys:
            for key, val in extra_keys.items():
                self.conn.hmset(key, val)

        # Set up endpoint
        proxy_policy = self.conn.hget('bdb:%s' % bdb_uid, 'proxy_policy')
        if not proxy_policy:
            proxy_policy = 'all-nodes'

        self.conn.hmset('endpoint:%s:1' % bdb_uid,
                        {'bdb_uid': bdb_uid,
                         'port': port,
                         'proxy_policy': proxy_policy})
        self.conn.hmset('endpoint:%s:1' % bdb_uid,
                        {'bdb_uid': bdb_uid,
                         'port': port,
                         'proxy_policy': proxy_policy,
                         'proxy_uids': '1'})

        if endpoint_ccs_params:
            self.conn.hmset('endpoint:%s:1' % bdb_uid, endpoint_ccs_params)

        self.conn.sadd('endpoint:all', '%s:1' % bdb_uid)

        self.conn.sadd('bdb:all', bdb_uid)
        self.update_bdb_redis_list(bdb_uid, shards)
