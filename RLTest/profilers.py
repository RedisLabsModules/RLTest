import os.path
import re
import subprocess

from RLTest.utils import Colors


class Perf:
    def __init__(self):
        """
        RLTest profiling on top of perf
        """
        self.minor = 0
        self.perf = os.getenv("PERF")
        if not self.perf:
            self.perf = "perf"

        self.stack_collapser = os.getenv("STACKCOLLAPSE")
        if not self.stack_collapser:
            self.stack_collapser ="stackcollapse-perf.pl"

        self.output = None
        self.profiler_process = None
        self.profiler_process_stdout = None
        self.profiler_process_stderr = None
        self.profiler_process_exit_code = None
        self.trace_file = None
        self.collapsed_stack_file = None
        self.collapsed_stacks = []
        self.pid = None
        self.started_profile = False
        self.environ = os.environ.copy()

        self.version = ""
        self.version_major = ""
        self.version_minor = ""
        self.retrieve_perf_version()

    def retrieve_perf_version(self):
        try:
            self.version = subprocess.Popen([self.perf, "--version"], stdout=subprocess.PIPE).communicate()[0]
        except OSError:
            print('\t' + Colors.Bred('Unable to run perf %s'.format(self.perf)))
        m = re.match(r"perf version (\d+)\.(\d+)\.", self.version.decode('utf-8'))
        if m:
            self.version_major = m.group(1)
            self.version_minor = m.group(2)

    def generate_record_command(self, pid, output, frequency=None):
        self.output = output
        self.pid = pid
        cmd = [self.perf, 'record', '-g', '--pid', '{}'.format(pid), '--output', output]
        if frequency:
            cmd += ['--freq', '{}'.format(frequency)]
        return cmd

    def startProfile(self, pid, output, frequency):
        """

        @param pid: profile events on specified process id
        @param output: output file name
        @param frequency: profile at this frequency
        @return: returns True if profiler started, False if unsuccessful
        """
        result = False
        # profiler is already running
        if not self.started_profile:
            stderrPipe = subprocess.PIPE
            stdoutPipe = subprocess.PIPE
            stdinPipe = subprocess.PIPE

            options = {
                'stderr': stderrPipe,
                'stdin': stdinPipe,
                'stdout': stdoutPipe,
                'env': self.environ
            }

            args = self.generate_record_command(pid, output, frequency)
            self.profiler_process = subprocess.Popen(args=args, **options)
            self.started_profile = True
            result = True
        return result

    def _isAlive(self, process):
        """

        @param process:
        @return: returns True if specified process is running, False if not running
        """
        if not process:
            return False
        # Check if child process has terminated. Set and return returncode
        # attribute
        if process.poll() is None:
            return True
        return False

    def stopProfile(self):
        """

        @return: returns True if profiler stop, False if unsuccessful
        """
        result = False
        if not self._isAlive(self.profiler_process):
            print('\t' + Colors.Bred('Profiler process is not alive, might have crash during test execution, '))
            return result
        try:
            self.profiler_process.terminate()
            self.profiler_process.wait()
            self.profiler_process_stdout, self.profiler_process_stderr = self.profiler_process.communicate()
            self.profiler_process_exit_code = self.profiler_process.poll()
            result = True

        except OSError as e:
            print('\t' + Colors.Bred(
                'OSError caught while waiting for profiler process to end: {0}'.format(e.__str__())))
            result = False
            pass
        return result

    def getProfilerOutputFile(self):
        """

        @return:  output file name
        """
        return self.output

    def getProfilerStdOut(self):
        """

        @return: returns the stdout output ( bytes ) of the profiler process if we have ran a profiler. If not returns None
        """
        return self.profiler_process_stdout

    def getProfilerStdErr(self):
        """

        @return: returns the stderr output ( bytes ) of the profiler process if we have ran a profiler. If not returns None
        """
        return self.profiler_process_stderr

    def getTraceFile(self):
        return self.trace_file

    def generateTraceFileFromProfile(self, filename="out.perf"):
        result = False
        if self.output is not None:
            if os.path.isfile(self.output):
                with open(filename, "w") as outfile:
                    args = [self.perf, "script", "-i", self.output]
                    try:
                        subprocess.Popen(args=args, stdout=outfile).wait()
                    except OSError as e:
                        print('\t' + Colors.Bred('Unable to run %s script %s'.format(self.perf, e.__str__())))
                result = True
                self.trace_file = filename

        return result

    def stackCollapse(self, filename="out.stacks-folded"):
        result = False
        if self.trace_file is not None:
            if os.path.isfile(self.trace_file):
                with open(filename, "w") as outfile:
                    args = [self.stack_collapser, os.path.abspath(self.trace_file) ]
                    try:
                        subprocess.Popen(args=args, stdout=outfile).wait()
                    except OSError as e:
                        print('\t' + Colors.Bred(
                            'Unable to stack collapse using: {0} {1}. Error {2}'.format(self.stack_collapser,
                                                                                        self.trace_file, e.__str__())))
                result = True
            else:
                print('\t' + Colors.Bred('Unable to open {0}'.format(self.trace_file)))
        return result

    def getCollapsedStacks(self):
        return self.collapsed_stacks
