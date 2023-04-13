import redis

from RLTest import Env


# run each test on different env
def test_getConnection(env):
    con = env.getConnection()

def test_getTLSConnection(env):
    """
    Check if it's an enviroment with TLS enabled. If so, force a non-TLS and expect an error
    @param env:
    """
    if env.useTLS:
        # since we're using TLS for sure this is a TCP connection. So host, port and password should be filled
        master_nodes = env.getMasterNodesList()
        node_0 = master_nodes[0]
        host = node_0['host']
        port = node_0['port']
        password = node_0['password']
        try:
            insecure_redis = redis.StrictRedis(host, port, password=password)
            insecure_redis.execute_command("info")
        except redis.exceptions.ConnectionError as exc:
            # we where expecting this exception
            pass

        secure_redis = env.getConnection()
        secure_redis.execute_command("info")

def test_getSlaveConnection(env):
    env.skipOnCluster()
    con = env.getConnection()
    if env.useSlaves:
        con2 = env.getSlaveConnection()

def test_skipOnSlave(env):
    env.skipOnSlave()

def test_skipOnCluster(env):
    env.skipOnCluster()

def test_skipOnAOF(env):
    env.skipOnAOF()

def test_skipOnDebugger(env):
    env.skipOnDebugger()

def test_skipOnEnterpriseCluster(env):
    env.skipOnEnterpriseCluster()

def test_skipOnTcp(env):
    env.skipOnTcp()

def test_skipOnUnixSocket(env):
    env.skipOnUnixSocket()

def test_resp3(env):
    env = Env(protocol=3)
