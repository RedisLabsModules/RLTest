import os
import sys
import time
import re
import copy
import redis
import itertools


def is_github_actions():
    """Check if running in GitHub Actions environment"""
    return os.getenv('GITHUB_ACTIONS', '') != ''


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
        return '\033[90;1m' + data + '\033[0m'

    @staticmethod
    def Blue(data):
        return '\033[34m' + data + '\033[0m'

    @staticmethod
    def Green(data):
        return '\033[32m' + data + '\033[0m'

def fix_modules(modules, defaultModules=None):
    # modules is one of the following:
    # None - take the default modules
    # ['path',...] - load module(s) from given path(s)
    # Empty list - return None, meaning don't load any module.
    if modules is not None:
        if len(modules) == 0:
            return None
        elif not isinstance(modules, list):
            modules = [modules]
        modules = list(map(lambda p: os.path.abspath(p), modules))
    else:
        modules = defaultModules
    return modules

def split_by_semicolon(s):
    return list(filter(lambda s: s != '', map(lambda s: re.sub(r'\\(.)', r'\1', s.strip()), re.split(r'(?<!\\);', s))))

def args_list_to_dict(args_list):
    """Convert a list of arg lists into a list of dicts for key-based merging.

    Each arg string (e.g., 'DEFAULT_DIALECT 2 WORKERS 5') may contain multiple
    space-separated key-value pairs. We register the string under ALL keys
    (words at even positions: 0, 2, 4, ...) so that default-arg merging can
    detect ALL keys present in per-test args.

    Example:
        Input:  [['DEFAULT_DIALECT 2 WORKERS 5']]
        Output: [{'DEFAULT_DIALECT': 'DEFAULT_DIALECT 2 WORKERS 5',
                  'WORKERS': 'DEFAULT_DIALECT 2 WORKERS 5'}]

    This ensures that when MODARGS defaults contain 'WORKERS 0', the merge
    logic sees that 'WORKERS' already exists in per-test args and skips it.
    """
    def extract_keys_and_register(args):
        d = {}
        for seq in args:
            words = seq.split(' ')
            # Each arg string may contain multiple key-value pairs:
            #   'KEY1 VAL1 KEY2 VAL2 ...'
            # Words at even positions (0, 2, 4, ...) are keys.
            # Register the full string under each key for deduplication.
            for i in range(0, len(words), 2):
                d[words[i].upper()] = seq
        return d
    return list(map(extract_keys_and_register, args_list))

def join_lists(lists):
    return list(itertools.chain.from_iterable(lists))

def fix_modulesArgs(modules, modulesArgs, defaultArgs=None, haveSeqs=True):
    # modulesArgs is one of the following:
    # None
    # 'args ...': arg string for a single module
    # ['args ...', ...]: arg list for a single module
    # [['arg', ...', ...], ...]: arg strings for multiple modules

    # arg string is a string of words separated by whitespace.
    # arg string can be separated by semicolons into (logical) arg lists.
    # semicolons can be escaped with a backslash.
    # if no semicolons are present, the entire string is kept as a single arg.
    # thus, 'K1 V1 K2 V2' becomes ['K1 V1 K2 V2']
    # for args with multiple values, semicolons are required:
    # thus, 'K1 V1; K2 V2 V3' becomes ['K1 V1', 'K2 V2 V3']
    # arg list is a list of arg strings.
    # arg list starts with an arg name that can later be used for argument overriding.

    if type(modulesArgs) == str:
        # case # 'args ...': arg string for a single module
        # transformed into [['arg', ...]]
        parts = split_by_semicolon(modulesArgs)
        modulesArgs = [parts]
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
            name = arg.split(' ')[0].upper()
            if name not in modules_args_dict[imod]:
                modulesArgs[imod] += [arg]

    return modulesArgs
