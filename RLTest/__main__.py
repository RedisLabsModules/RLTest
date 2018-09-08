import argparse
import os
import imp
import traceback
import sys
import subprocess
import platform
import shutil
import inspect
import unittest
import time
import shlex
from Env import Env
from utils import Colors
from RLTest.loader import TestLoader

RLTest_WORKING_DIR = os.path.expanduser('~/.RLTest/')
RLTest_ENTERPRISE_VERSION = '5.2.0'
RLTest_ENTERPRISE_SUB_VERSION = '14'
OS_NAME = platform.dist()[2]
RLTest_ENTERPRISE_TAR_FILE_NAME = 'redislabs-%s-%s-%s-amd64.tar' % (RLTest_ENTERPRISE_VERSION, RLTest_ENTERPRISE_SUB_VERSION, OS_NAME)
RLTest_ENTERPRISE_URL = 'https://s3.amazonaws.com/rlec-downloads/%s/%s' % (RLTest_ENTERPRISE_VERSION, RLTest_ENTERPRISE_TAR_FILE_NAME)
RLTest_CONFIG_FILE_PREFIX = '@'
RLTest_CONFIG_FILE_NAME = 'config.txt'


class CustomArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwrags):
        super(CustomArgumentParser, self).__init__(*args, **kwrags)

    def convert_arg_line_to_args(self, line):
        for arg in shlex.split(line):
            if not arg.strip():
                continue
            if arg[0] == '#':
                break
            yield arg


parser = CustomArgumentParser(fromfile_prefix_chars=RLTest_CONFIG_FILE_PREFIX,
                              formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                              description='Test Framework for redis and redis module')


parser.add_argument(
    '--module', default=None,
    help='path to the module file')

parser.add_argument(
    '--module-args', default=None,
    help='arguments to give to the module on loading')

parser.add_argument(
    '--env', '-e', default='oss', choices=['oss', 'oss-cluster', 'enterprise', 'enterprise-cluster'],
    help='env on which to run the test')

parser.add_argument(
    '--oss-redis-path', default='redis-server',
    help='path to the oss redis binary')

parser.add_argument(
    '--enterprise-redis-path', default=os.path.join(RLTest_WORKING_DIR, 'opt/redislabs/bin/redis-server'),
    help='path to the entrprise redis binary')

parser.add_argument(
    '--stop-on-failure', action='store_const', const=True, default=False,
    help='stop running on failure')

parser.add_argument(
    '--verbose', '-v', action='count', default=0,
    help='print more information about the test')

parser.add_argument(
    '--debug', action='store_const', const=True, default=False,
    help='stop before each test allow gdb attachment')

parser.add_argument(
    '-t', '--test', help='Specify test to run, in the form of "file:test"')

parser.add_argument(
    '--tests-dir', default='.',
    help='directory on which to run the tests')

parser.add_argument(
    '--test-name', default=None,
    help='test name to run')

parser.add_argument(
    '--tests-file', default=None,
    help='tests file to run (with out the .py extention)')

parser.add_argument(
    '--env-only', action='store_const', const=True, default=False,
    help='start the env but do not run any tests')

parser.add_argument(
    '--clear-logs', action='store_const', const=True, default=False,
    help='deleting the log direcotry before the execution')

parser.add_argument(
    '--log-dir', default='./logs',
    help='directory to write logs to')

parser.add_argument(
    '--use-slaves', action='store_const', const=True, default=False,
    help='run env with slaves enabled')

parser.add_argument(
    '--shards-count', default=1, type=int,
    help='Number shards in bdb')

parser.add_argument(
    '--download-enterprise-binaries', action='store_const', const=True, default=False,
    help='run env with slaves enabled')

parser.add_argument(
    '--proxy-binary-path', default=os.path.join(RLTest_WORKING_DIR, 'opt/redislabs/bin/dmcproxy'),
    help='dmc proxy binary path')

parser.add_argument(
    '--enterprise-lib-path', default=os.path.join(RLTest_WORKING_DIR, 'opt/redislabs/lib/'),
    help='path of needed libraries to run enterprise binaries')

parser.add_argument(
    '-r', '--env-reuse', action='store_const', const=True, default=False,
    help='reuse exists env, this feature is based on best efforts, if the env can not be reused then it will be taken down.')

parser.add_argument(
    '--use-aof', action='store_const', const=True, default=False,
    help='use aof instead of rdb')

parser.add_argument(
    '--debug-print', action='store_const', const=True, default=False,
    help='print debug messages')

parser.add_argument(
    '-V', '--use-valgrind', action='store_const', const=True, default=False,
    help='running redis under valgrind (assuming valgrind is install on the machine)')

parser.add_argument(
    '--valgrind-suppressions-file', default=None,
    help='path valgrind suppressions file')

parser.add_argument(
    '--config-file', default=None,
    help='path to configuration file, parameters value will be taken from configuration file,'
         'values which was not specified on configuration file will get their value from the command line args,'
         'values which was not specifies either on configuration file nor on command line args will be getting their default value')

parser.add_argument(
    '-i', '--interactive-debugger', action='store_const', const=True, default=False,
    help='runs the redis on a debuger (gdb/lldb) interactivly.'
         'debugger interactive mode is only possible on a single process and so unsupported on cluste or with slaves.'
         'it is also not possible to use valgrind on interactive mode.'
         'interactive mode direcly applies: --no-output-catch and --stop-on-failure.'
         'it is also implies that only one test will be run (if --inv-only was not specify), an error will be raise otherwise.')

parser.add_argument(
    '--debugger-args', default=None,
    help='arguments to the interactive debugger')

parser.add_argument(
    '-s', '--no-output-catch', action='store_const', const=True, default=False,
    help='all output will be written to the stdout, no log files.')

parser.add_argument(
    '--collect-only', action='store_true',
    help='Collect the tests and exit')


class EnvScopeGuard:
    def __init__(self, runner):
        self.runner = runner

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        self.runner.takeEnvDown()


class RLTest:

    def __init__(self):
        configFilePath = './%s' % RLTest_CONFIG_FILE_NAME
        if os.path.exists(configFilePath):
            args = ['%s%s' % (RLTest_CONFIG_FILE_PREFIX, RLTest_CONFIG_FILE_NAME)] + sys.argv[1:]
        else:
            args = sys.argv[1:]
        self.args = parser.parse_args(args=args)

        if self.args.interactive_debugger:
            if self.args.env != 'oss' and self.args.env != 'enterprise':
                print Colors.Bred('interactive debugger can only be used on non cluster env')
                sys.exit(1)
            if self.args.use_valgrind:
                print Colors.Bred('can not use valgrind with interactive debugger')
                sys.exit(1)
            if self.args.use_slaves:
                print Colors.Bred('can not use slaves with interactive debugger')
                sys.exit(1)

            self.args.no_output_catch = True
            self.args.stop_on_failure = True

        if self.args.download_enterprise_binaries:
            self._downloadEnterpriseBinaries()

        if self.args.clear_logs:
            try:
                shutil.rmtree(self.args.log_dir)
            except Exception:
                pass

        Env.defaultModule = self.args.module
        Env.defaultModuleArgs = self.args.module_args
        Env.defaultEnv = self.args.env
        Env.defaultOssRedisBinary = self.args.oss_redis_path
        Env.defaultVerbose = self.args.verbose
        Env.defaultLogDir = self.args.log_dir
        Env.defaultUseSlaves = self.args.use_slaves
        Env.defaultShardsCount = self.args.shards_count
        Env.defaultProxyBinaryPath = self.args.proxy_binary_path
        Env.defaultEnterpriseRedisBinaryPath = self.args.enterprise_redis_path
        Env.defaultEnterpriseLibsPath = self.args.enterprise_lib_path
        Env.defaultUseAof = self.args.use_aof
        Env.defaultDebugPrints = self.args.debug_print
        Env.defaultUseValgrind = self.args.use_valgrind
        Env.defaultValgrindSuppressionsFile = self.args.valgrind_suppressions_file
        Env.defaultInteractiveDebugger = self.args.interactive_debugger
        Env.defaultInteractiveDebuggerArgs = self.args.debugger_args
        Env.defaultNoCatch = self.args.no_output_catch

        sys.path.append(self.args.tests_dir)

        self.tests = []
        self.currEnv = None
        self.loader = TestLoader(filter=self.args.test_name)
        if self.args.test:
            self.loader.load_spec(self.args.test)
        else:
            self.loader.scan_dir(self.args.tests_dir)

        if self.args.collect_only:
            self.loader.print_tests()
            sys.exit(0)

    def _convertArgsType(self):
        pass

    def _downloadEnterpriseBinaries(self):
        binariesName = 'binaries.tar'
        print Colors.Yellow('installing enterprise binaries')
        print Colors.Yellow('creating RLTest working dir: %s' % RLTest_WORKING_DIR)
        try:
            shutil.rmtree(RLTest_WORKING_DIR)
            os.makedirs(RLTest_WORKING_DIR)
        except Exception:
            pass

        print Colors.Yellow('download binaries')
        args = ['wget', RLTest_ENTERPRISE_URL, '-O', os.path.join(RLTest_WORKING_DIR, binariesName)]
        self.process = subprocess.Popen(args=args, stdout=sys.stdout, stderr=sys.stdout)
        self.process.wait()
        if self.process.poll() != 0:
            raise Exception('failed to download enterprise binaries from s3')

        print Colors.Yellow('extracting binaries')
        debFileName = 'redislabs_%s-%s~%s_amd64.deb' % (RLTest_ENTERPRISE_VERSION, RLTest_ENTERPRISE_SUB_VERSION, OS_NAME)
        args = ['tar', '-xvf', os.path.join(RLTest_WORKING_DIR, binariesName), '--directory', RLTest_WORKING_DIR, debFileName]
        self.process = subprocess.Popen(args=args, stdout=sys.stdout, stderr=sys.stdout)
        self.process.wait()
        if self.process.poll() != 0:
            raise Exception('failed to extract binaries to %s' % self.RLTest_WORKING_DIR)

        # TODO: Support centos that does not have dpkg command
        args = ['dpkg', '-x', os.path.join(RLTest_WORKING_DIR, debFileName), RLTest_WORKING_DIR]
        self.process = subprocess.Popen(args=args, stdout=sys.stdout, stderr=sys.stdout)
        self.process.wait()
        if self.process.poll() != 0:
            raise Exception('failed to extract binaries to %s' % self.RLTest_WORKING_DIR)

        print Colors.Yellow('finished installing enterprise binaries')

    def takeEnvDown(self, fullShutDown=False):
        if self.currEnv:
            if self.args.env_reuse and not fullShutDown:
                self.currEnv.flush()
            else:
                self.currEnv.stop()
                if self.args.use_valgrind and self.currEnv and not self.currEnv.checkExitCode():
                    print Colors.Bred('\tvalgrind check failure')
                    self.testsFailed.add(self.currEnv)
                self.currEnv = None

    def _runTest(self, test, printTestName=False, numberOfAssertionFailed=0):
        if len(inspect.getargspec(test.target).args) > 0 and not test.is_method:
            env = Env(testName=test.name)
            fn = lambda: test.target(env)
        else:
            fn = test.target

        exceptionRaised = False
        msgPrefix = test.name if not printTestName else ''

        if printTestName:
            print '\t' + Colors.Cyan(test.name)
        try:
            if self.args.debug:
                raw_input('\tenv is up, attach to any process with gdb and press any button to continue.')

            fn()
        except unittest.SkipTest:
            self.printSkip(prefix=msgPrefix)
        except Exception as err:
            msg = 'Unhandled exception: {}'.format(err)
            print '\t' + Colors.Bred(msg)
            traceback.print_exc(file=sys.stdout)
            exceptionRaised = True

        isFailed = self.currEnv is None or self.currEnv.getNumberOfFailedAssertion() > numberOfAssertionFailed or exceptionRaised

        if isFailed:
            if exceptionRaised:
                self.printError(prefix=msgPrefix)
            else:
                self.printFail(prefix=msgPrefix)

            self.testsFailed.add(self.currEnv)
        else:
            self.printPass()

        if self.args.stop_on_failure and isFailed:
            if self.args.interactive_debugger:
                while self.currEnv.isUp():
                    time.sleep(1)
            raw_input('press any button to move to the next test')

        return self.currEnv.getNumberOfFailedAssertion()

    def _fmtPrefix(self, prefix):
        return prefix + ': ' if prefix else ''

    def printSkip(self, prefix=''):
        print '\t' + Colors.Green(self._fmtPrefix(prefix) + '[SKIP]')

    def printFail(self, prefix=''):
        print '\t' + Colors.Bred(self._fmtPrefix(prefix) + '[FAIL]')

    def printError(self, prefix=''):
        print '\t' + Colors.Yellow(self._fmtPrefix(prefix) + '[ERROR]')

    def printPass(self, prefix=''):
        print '\t' + Colors.Green(self._fmtPrefix(prefix) + '[PASS]')

    def envScopeGuard(self):
        return EnvScopeGuard(self)

    def execute(self):
        self.testsFailed = set()
        Env.RTestInstance = self
        if self.args.env_only:
            Env.defaultVerbose = 2
            env = Env(testName='manual test env')
            if self.args.interactive_debugger:
                while env.isUp():
                    time.sleep(1)
            raw_input('press any button to stop')
            env.stop()
            return
        done = 0
        startTime = time.time()
        if self.args.interactive_debugger and len(self.tests) != 1:
            print Colors.Bred('only one test can be run on interactive-debugger use --test-name')
            sys.exit(1)

        for test in self.loader:
            with self.envScopeGuard():
                if test.is_class:
                    try:
                        obj = test.create_instance()
                    except unittest.SkipTest:
                        self.printSkip(test.name)
                        continue

                    for subtest in test.get_functions(obj):
                        self._runTest(subtest, printTestName=True)
                        done += 1

                else:
                    self._runTest(test)
                    done += 1

        self.takeEnvDown(fullShutDown=True)
        endTime = time.time()

        print Colors.Bold('Test Took: %d sec' % (endTime - startTime))
        print Colors.Bold('Total Tests Run: %d, Total Tests Failed: %d, Total Tests Passed: %d' % (done, len(self.testsFailed), done - len(self.testsFailed)))
        if len(self.testsFailed) > 0:
            print Colors.Bold('Faild Tests Summery:')
            for testFaild in self.testsFailed:
                print '\t' + Colors.Bold(testFaild.testNamePrintable)
                testFaild.printFailuresSummery('\t\t')
            sys.exit(1)


def main():
    RLTest().execute()


if __name__ == '__main__':
    main()
