import os

REDIS_BINARY = os.environ.get("REDIS_BINARY", "redis-server")
REDIS_ENTERPRISE_BINARY = os.environ.get("REDIS_ENTERPRISE_BINARY", None)
DMC_PROXY_BINARY = os.environ.get("DMC_PROXY_BINARY", None)


def whereis(program):
    for path in os.environ.get('PATH', '').split(':'):
        if os.path.exists(os.path.join(path, program)) and \
                not os.path.isdir(os.path.join(path, program)):
            return os.path.join(path, program)
    return None
