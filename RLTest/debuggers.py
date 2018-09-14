import platform


class Valgrind(object):
    is_interactive = False

    def __init__(self, verbose=False, suppressions=None, leakcheck=True):
        self.verbose = verbose
        self.suppressions = suppressions
        self.leakcheck = leakcheck

    def generate_command(self, logfile=None):
        cmd = ['valgrind', '--error-exitcode=1']
        if self.leakcheck:
            cmd += ['--leak-check=full', '--errors-for-leak-kinds=definite']
        if self.suppressions:
            cmd += ['--suppressions=' + self.suppressions]
        if logfile:
            cmd += ['--log-file' + logfile]
        return cmd

    def is_interactive(self):
        return False


class GenericInteractiveDebugger(object):
    is_interactive = True

    def __init__(self, cmdline):
        self.args = cmdline.split()

    def generate_command(self, **kw):
        return [self.args]


class GDB(object):
    is_interactive = True

    def generate_command(self, **kw):
        return ['gdb', '-ex', 'run', '--args']


class LLDB(object):
    is_interactive = True

    def generate_command(self, **kw):
        return ['lldb', '--']


if platform.system() == 'Darwin':
    DefaultInteractiveDebugger = LLDB
else:
    DefaultInteractiveDebugger = GDB
