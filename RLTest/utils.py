import redis
import time


def wait_for_conn(conn, retries=20, command='PING', shouldBe=True):
    """Wait until a given Redis connection is ready"""
    err = None
    while retries > 0:
        try:
            if conn.execute_command(command) == shouldBe:
                return conn
        except redis.exceptions.BusyLoadingError:
            time.sleep(0.1)  # give extra 100msec in case of RDB loading
        except redis.ConnectionError as e:
            err = e
        time.sleep(0.1)
        retries -= 1
    raise Exception('Cannot establish connection %s: %s' % (conn, err))


class Colors(object):
    @staticmethod
    def Cyan(data):
        return '\033[36m' + data + '\033[0m'

    @staticmethod
    def Yellow(data):
        return '\033[33m' + data + '\033[0m'

    @staticmethod
    def Bold(data):
        return '\033[1m' + data + '\033[0m'

    @staticmethod
    def Bred(data):
        return '\033[31;1m' + data + '\033[0m'

    @staticmethod
    def Gray(data):
        return '\033[30;1m' + data + '\033[0m'

    @staticmethod
    def Lgray(data):
        return '\033[30;47m' + data + '\033[0m'

    @staticmethod
    def Blue(data):
        return '\033[34m' + data + '\033[0m'

    @staticmethod
    def Green(data):
        return '\033[32m' + data + '\033[0m'
