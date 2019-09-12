import rediscluster
from redis import StrictRedis
from exists_redis import ExistsRedisEnv


class Shard(StrictRedis):

    def __init__(self, host, port, password, **kwargs):
        self.host = host
        self.port = port
        self.password = password
        StrictRedis.__init__(self, host = host, port = self.port, password = self.password, decode_responses=False, **kwargs)

    def dumpAndReload(self, restart=False, shardId=1):
        self.save()
        try:
            self.execute_command('DEBUG', 'RELOAD')
        except redis.RedisError as err:
            raise err

    def getMasterPort(self):
        return self.port

    def getConnection(self, shardId=1):
        return self

    def broadcast(self, *cmd):
        self.execute_command(*cmd)

class DB(StrictRedis):
    def __init__(self, host, port, password, shards_port, **kwargs):
        self.host = host
        self.port = port
        self.shard_list = [Shard( host=host, port=port, password=password) for port in shards_port]
        StrictRedis.__init__(self, host = self.host, port = self.port, decode_responses=False, **kwargs)


class EnterpriseRedisClusterEnv(ExistsRedisEnv):

    def __init__(self, addr, password=None, shards_port=None, **kwargs):
        '''
        provide the ability to run tests on predefind RC
        usage:
        --existing-env-addr 'DB address {host}:{port}' --shards_ports "INT,[INT...]"  --internal_password  "DB - internal_password"
        '''
        self.host, self.port = addr.split(':')
        self.password = password
        self.data_base = DB(host=self.host, port=self.port, password=password, shards_port = shards_port)
        self.shards = self.data_base.shard_list

     ###In the feature we want EnterpriseRedisClusterEnv will learn the cluster dynamicly
     ### So we will be able to run the suits without using operetto.
#    def send_request(self, method, url):
#        self.base_url = 'https://{}:9443'.format(cluster_address)
#        full_url = "{}/{}".format(self.base_url, url)
#        responce = requests.api.request(method=method, url=full_url,
#                             verify = False, auth=(self.username, self.password))
#        if not responce.ok:
#            raise Exception("Fail to send_request: responce code is {}".format(responce.status_code))
#        return responce.json()

    def waitCluster(self, timeout_sec=40):
        import time
        st = time.time()
        while st + timeout_sec > time.time():
            if all([shard.ping() for shard in self.shards]):
                return
            time.sleep(0.1)
        raise RuntimeError("Cluster OK wait loop timed out after %s seconds" % timeout_sec)

    def dumpAndReload(self, restart=False, shardId=None):
        if shardId is None:
            for shard in self.shards:
                shard.dumpAndReload(restart=restart)
            self.waitCluster()
        else:
            self.shards[shardId - 1].dumpAndReload(restart=restart, shardId=None)

    def getClusterConnection(self):
        return self.getConnection()

    def getConnection(self, shardId=1):
        return self.data_base

    def isUp(self):
        return self.getConnection().ping()
