from __future__ import print_function

import os
import psutil
import subprocess
from RLTest.utils import Colors


class Dmc():
    DMC_LOG_FILE_NAME = 'dmc.log'

    def __init__(self, dmcBinaryPath, libPath, directory=None):
        self.dmcBinaryPath = os.path.expanduser(dmcBinaryPath) if dmcBinaryPath.startswith('~/') else dmcBinaryPath
        self.env = {'MEMTIER_NODE_ID': '1'}
        self.libPath = libPath
        if 'LD_LIBRARY_PATH' in os.environ:
            self.env['LD_LIBRARY_PATH'] = os.environ['LD_LIBRARY_PATH']
        else:
            self.env['LD_LIBRARY_PATH'] = os.path.expanduser(self.libPath) if dmcBinaryPath.startswith('~/') else self.libPath
        self.directory = directory

        logFile = self.DMC_LOG_FILE_NAME if self.directory is None else os.path.join(self.directory, self.DMC_LOG_FILE_NAME)
        self.proxyArgs = [
            self.dmcBinaryPath,
            '-c', '500',
            '-O', logFile
        ]

    def Start(self):
        self.process = psutil.Popen(executable=self.dmcBinaryPath,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    env=self.env,
                                    args=self.proxyArgs)

    def Stop(self):
        if self.process:
            self.process.kill()
            self.process.wait()
        self.process = None

    def PrintEnvData(self, prefix=''):
        print(Colors.Yellow(prefix + 'dmc binary path: %s' % self.dmcBinaryPath))
        print(Colors.Yellow(prefix + 'dmc env: %s' % str(self.env)))
        print(Colors.Yellow(prefix + 'dir path: %s' % str(self.directory)))
        print(Colors.Yellow(prefix + 'log file name: %s' % str(self.DMC_LOG_FILE_NAME)))
        if self.libPath:
            print(Colors.Yellow(prefix + 'lib path: %s' % str(self.libPath)))
