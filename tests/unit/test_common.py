import os

REDIS_BINARY = os.environ.get("REDIS_BINARY", "redis-server")
REDIS_ENTERPRISE_BINARY = os.environ.get("REDIS_ENTERPRISE_BINARY", None)
DMC_PROXY_BINARY = os.environ.get("DMC_PROXY_BINARY", None)

TLS_CERT = os.environ.get("TLS_CERT", "./tls/redis.crt")
TLS_KEY = os.environ.get("TLS_KEY", "./tls/redis.key")
TLS_CACERT = os.environ.get("TLS_CACERT", "./tls/ca.crt")


def whereis(program):
    for path in os.environ.get('PATH', '').split(':'):
        if os.path.exists(os.path.join(path, program)) and \
                not os.path.isdir(os.path.join(path, program)):
            return os.path.join(path, program)
    return None
