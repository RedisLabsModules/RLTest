import os

import redis
import time


def wait_for_conn(conn, retries=20, command='PING', shouldBe=True):
    """Wait until a given Redis connection is ready"""
    err1 = ''
    while retries > 0:
        try:
            if conn.execute_command(command) == shouldBe:
                return conn
        except redis.exceptions.BusyLoadingError:
            time.sleep(0.1)  # give extra 100msec in case of RDB loading
        except redis.ConnectionError as err:
            err1 = str(err)
        except redis.ResponseError as err:
            err1 = str(err)
            if not err1.startswith('DENIED'):
                raise
        time.sleep(0.1)
        retries -= 1
    raise Exception('Cannot establish connection %s: %s' % (conn, err1))

def expandBinary(binaryPath):
    if binaryPath is None:
        return binaryPath
    return os.path.expanduser(binaryPath) if binaryPath.startswith(
        '~/') else binaryPath

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

def fix_modules(modules, defaultModules=None):
    # modules is either None or ['path',...]
    if modules:
        if not isinstance(modules, list):
            modules = [modules]
        modules = list(map(lambda p: os.path.abspath(p), modules))
    else:
        modules = defaultModules
    return modules

def fix_modulesArgs(modules, modulesArgs, defaultArgs=None):
    # modulesArgs is either None or 'arg1 arg2 ...' or ['arg1 arg2 ...', ...] or [['arg', ...], ...]
    if type(modulesArgs) == str:
        modulesArgs = [modulesArgs.split(' ')]
    elif type(modulesArgs) == list:
        args = []
        for argx in modulesArgs:
            if type(argx) == list:
                args += [argx]
            else:
                args += [str(argx).split(' ')]
        modulesArgs = args
    # modulesArgs is now [['arg1', 'arg2', ...], ...]

    # modulesArgs are added to default args
    if not defaultArgs:
        return modulesArgs
        
    fixed_modulesArgs = copy.deepcopy(defaultArgs)
    if not modulesArgs:
        return fixed_modulesArgs

    if isinstance(modules, list) and len(modules) > 1:
        n = len(modules) - len(modulesArgs)
        if n > 0:
            modulesArgs.extend([['']] * n)
    n = len(defaultArgs) - len(modulesArgs)
    if n > 0:
        modulesArgs.extend([['']] * n)

    if defaultArgs and len(modulesArgs) != len(defaultArgs):
        print(Colors.Bred('Number of module args sets in Env does not match number of modules'))
        print(defaultArgs)
        print(modulesArgs)
        sys.exit(1)
    # for each module
    for imod, args in enumerate(modulesArgs):
        fixed_modulesArgs[imod] += args

    return fixed_modulesArgs
