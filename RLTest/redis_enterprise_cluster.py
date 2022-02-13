from redis import StrictRedis
from .exists_redis import ExistsRedisEnv


class Shard(StrictRedis):

    def __init__(self, cluster_address, port, password, cluster_credentials, **kwargs):
        self.port, self.node_id = port.split(":")
        self.password = password
        self.cluster_username, self.cluster_password = cluster_credentials.split(":")
        self.host = self._get_node_address(cluster_address)
        self.decodeResponses = kwargs.get('decodeResponses', False)
        StrictRedis.__init__(self, host = self.host, port = self.port, password = self.password,
                             decode_responses=self.decodeResponses, **kwargs)

    def dumpAndReload(self, restart=False, shardId=1, timeout_sec=0):
        self.save()
        try:
            self.execute_command('DEBUG', 'RELOAD')
        except redis.RedisError as err:
            raise err
    ###In the feature we want EnterpriseRedisClusterEnv will learn the cluster dynamicly
    ### So we will be able to run the suits without using operetto.
    def _get_node_address(self, cluster_address):
        base_url = 'https://{}:9443'.format(cluster_address)
        full_url ="{}/{}/{}".format(base_url, "v1/nodes", self.node_id)
        res = self.send_request('get', full_url)
        return res['addr']

    def send_request(self, method, url):
        import requests
        import urllib3
        urllib3.disable_warnings()
        responce = requests.api.request(method=method, url=url,
                             verify = False, auth=(self.cluster_username, self.cluster_password))
        if not responce.ok:
            raise Exception("Fail to send_request: responce code is {}".format(responce.status_code))
        return responce.json()

    def getMasterPort(self):
        return self.port

    def getConnection(self, shardId=1):
        return self

    def broadcast(self, *cmd):
        self.execute_command(*cmd)

class DB(StrictRedis):
    def __init__(self, host, port, password, shards_port, cluster_address, cluster_credentials, **kwargs):
        self.host = host
        self.port = port
        self.decodeResponses = kwargs.get('decodeResponses', False)
        self.shard_list = [Shard(cluster_address=cluster_address, 
                                 port=port, password=password, 
                                 cluster_credentials=cluster_credentials) for port in shards_port]
        StrictRedis.__init__(self, host = self.host, port = self.port,
                             decode_responses=self.decodeResponses, **kwargs)


class EnterpriseRedisClusterEnv(ExistsRedisEnv):

    def __init__(self, addr, cluster_address, cluster_credentials, password=None, shards_port=None, **kwargs):
        '''
        provide the ability to run tests on predefind RC
        usage:
        --existing-env-addr 'DB address {host}:{port}' --shards_ports "NODE_ID:INT,[NODE_ID:INT...]"
        --internal_password  "DB - internal_password" --cluster_address "master node IP"
        '''
        self.host, self.port = addr.split(':')
        self.cluster_address = cluster_address
        self.password = password
        self.database = DB(host=self.host, port=self.port,
                           password=password, shards_port = shards_port,
                           cluster_address = cluster_address,
                           cluster_credentials = cluster_credentials, **kwargs)
        self.shards = self.database.shard_list

    def waitCluster(self, timeout_sec=40):
        import time
        st = time.time()
        while st + timeout_sec > time.time():
            if all([shard.ping() for shard in self.shards]):
                return
            time.sleep(0.1)
        raise RuntimeError("Cluster OK wait loop timed out after %s seconds" % timeout_sec)

    def dumpAndReload(self, restart=False, shardId=None, timeout_sec=40):
        if shardId is None:
            for shard in self.shards:
                shard.dumpAndReload(restart=restart, timeout_sec=timeout_sec)
            self.waitCluster()
        else:
            self.shards[shardId - 1].dumpAndReload(restart=restart, shardId=None, timeout_sec=timeout_sec)

    def getClusterConnection(self):
        return self.getConnection()

    def getConnection(self, shardId=1):
        return self.database

    # List of nodes that initial bootstrapping can be done from
    def getMasterNodesList(self):
        full_master_list = []
        for shard in self.shards:
            node_info = {"host": None, "port": None, "unix_socket_path": None, "password": None}
            node_info["password"] = self.password
            node_info["host"] = 'localhost'
            node_info["port"] = shard.getMasterPort()
            full_master_list.append(node_info)
        return full_master_list

    # List containing a connection for each of the master nodes
    def getOSSMasterNodesConnectionList(self):
        full_master_connection_list = []
        for shard in self.shards:
            full_master_connection_list.append(shard.getConnection())
        return full_master_connection_list

    def isUp(self):
        return self.getConnection().ping()

    def isUnixSocket(self):
        return False

    def isTcp(self):
        return True
