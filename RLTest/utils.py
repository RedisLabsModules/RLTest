import os
import sys
import time
import re
import copy
import redis
import itertools

def wait_for_conn(conn, proc, retries=20, command='PING', shouldBe=True):
    """Wait until a given Redis connection is ready"""
    err1 = ''
    while retries > 0:
        if proc.poll() is not None:
            raise Exception(f'Redis server is dead (pid={proc.pid})')
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
    def Red(data):
        return '\033[31m' + data + '\033[0m'

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
    # modules is one of the following:
    # None
    # ['path',...]
    if modules:
        if not isinstance(modules, list):
            modules = [modules]
        modules = list(map(lambda p: os.path.abspath(p), modules))
    else:
        modules = defaultModules
    return modules

def split_by_semicolon(s):
    return list(filter(lambda s: s != '', map(lambda s: re.sub(r'\\(.)', r'\1', s.strip()), re.split(r'(?<!\\);', s))))

def args_list_to_dict(args_list):
    def dicty(args):
        return dict((seq.split(' ')[0], seq) for seq in args)
    return list(map(lambda args: dicty(args), args_list))

def join_lists(lists):
    return list(itertools.chain.from_iterable(lists))

def fix_modulesArgs(modules, modulesArgs, defaultArgs=None, haveSeqs=True):
    # modulesArgs is one of the following:
    # None
    # 'args ...': arg string for a single module
    # ['args ...', ...]: arg list for a single module
    # [['arg', ...', ...], ...]: arg strings for multiple modules

    # arg string is a string of words seperated by whitespace
    # arg string can be seperated by semicolons into (logical) arg lists.
    # semicolons can be escaped with a backslash.
    # arg list is a list of arg strings.
    # arg list starts with an arg name that can later be used for argument overriding.
    # arg strings are transformed into arg lists (haveSeqs parameter controls this behavior):
    # thus, 'num 1; names a b' becomes ['num 1', 'names a b']

    if type(modulesArgs) == str:
        # case # 'args ...': arg string for a single module
        # transformed into [['arg', ...]]
        modulesArgs = [split_by_semicolon(modulesArgs)]
    elif type(modulesArgs) == list:
        args = []
        is_list = False
        is_str = False
        for argx in modulesArgs:
            if type(argx) == list:
                # case [['arg', ...], ...]: arg strings for multiple modules
                # already transformed into [['arg', ...], ...]
                if is_str:
                    print(Colors.Bred('Error in args: %s' % str(modulesArgs)))
                    sys.exit(1)
                is_list = True
                if haveSeqs:
                    lists = map(lambda x: split_by_semicolon(x), argx)
                    args += [join_lists(lists)]
                else:
                    args += [argx]
            else:
                # case ['args ...', ...]: arg list for a single module
                # transformed into [['arg', ...], ...]
                if is_list:
                    print(Colors.Bred('Error in args: %s' % str(modulesArgs)))
                    sys.exit(1)
                is_str = True
                args += split_by_semicolon(argx)
        if is_str:
            args = [args]
        modulesArgs = args
    # modulesArgs is now [['arg', ...], ...]

    is_copy = not modulesArgs and defaultArgs
    if is_copy:
        modulesArgs = copy.deepcopy(defaultArgs)

    n = 0
    num_mods = len(modulesArgs) if modulesArgs else 0
    if defaultArgs:
        n = len(defaultArgs) - num_mods
        num_mods += n

    if isinstance(modules, list) and len(modules) > 1:
        n = len(modules) - num_mods

    if n > 0:
        if not modulesArgs:
            modulesArgs = []
        modulesArgs.extend([[]] * n)

    if is_copy or not defaultArgs:
        return modulesArgs

    # if there are fewer defaultArgs than modulesArgs, we should bail out
    # as we cannot pad the defaults with emply arg lists
    if defaultArgs and len(modulesArgs) > len(defaultArgs):
        print(Colors.Bred('Number of module args sets in Env does not match number of modules'))
        print(defaultArgs)
        print(modulesArgs)
        sys.exit(1)

    # for each module, sync defaultArgs to modulesARgs
    modules_args_dict = args_list_to_dict(modulesArgs)
    for imod, args_list in enumerate(defaultArgs):
        for arg in args_list:
            name = arg.split(' ')[0]
            if name not in modules_args_dict[imod]:
                modulesArgs[imod] += [arg]

    return modulesArgs
