import platform
import os.path


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
            cmd += ['--log-file=' + logfile]
        return cmd


class GenericInteractiveDebugger(object):
    is_interactive = True

    def __init__(self, cmdline):
        self.args = cmdline.split()

    def generate_command(self, *argc, **kw):
        return [self.args]


class GDB(GenericInteractiveDebugger):
    def __init__(self, cmdline="gdb"):
        super(GDB, self).__init__(cmdline)

    def generate_command(self, *argc, **kw):
        return ['gdb', '-ex', 'run', '--args']


class CGDB(GenericInteractiveDebugger):
    def __init__(self, cmdline="cgdb"):
        super(CGDB, self).__init__(cmdline)

    def generate_command(self, *argc, **kw):
        return ['cgdb', '-ex', 'run', '--args']


class LLDB(GenericInteractiveDebugger):
    def __init__(self, cmdline="lldb"):
        super(LLDB, self).__init__(cmdline)

    def generate_command(self, *argc, **kw):
        return ['lldb', '--']


if platform.system() == 'Darwin':
    DefaultInteractiveDebugger = LLDB
else:
    DefaultInteractiveDebugger = GDB

default_interactive_debugger = DefaultInteractiveDebugger()

def set_interactive_debugger(debugger):
    global default_interactive_debugger
    cmd = os.path.basename(debugger.split()[0])
    if cmd == 'gdb':
        default_interactive_debugger = GDB(debugger)
    elif cmd == 'cgdb':
        default_interactive_debugger = CGDB(debugger)
    elif cmd == 'lldb':
        default_interactive_debugger = LLDB(debugger)
