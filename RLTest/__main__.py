from __future__ import print_function

import argparse
import os
import cmd
import traceback
import sys
import shutil
import inspect
import unittest
import time
import shlex
from multiprocessing import Process, Queue

from RLTest.env import Env, TestAssertionFailure, Defaults
from RLTest.utils import Colors, fix_modules, fix_modulesArgs
from RLTest.loader import TestLoader
from RLTest.Enterprise import binaryrepo
from RLTest import debuggers
from RLTest._version import __version__

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

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


class MyCmd(cmd.Cmd):

    def __init__(self, env):
        cmd.Cmd.__init__(self)
        self.env = env
        self.prompt = '> '
        try:
            commands_reply = env.cmd('command')
        except Exception:
            return
        commands = [c[0] for c in commands_reply]
        for c in commands:
            if type(c)==bytes:
                c=c.decode('utf-8')
            setattr(MyCmd, 'do_' + c, self._create_functio(c))

    def _exec(self, command):
        self.env.expect(*command).prettyPrint()

    def _create_functio(self, command):
        c = command
        return lambda self, x: self._exec([c] + shlex.split(x))

    def do_exec(self, line):
        self.env.expect(*shlex.split(line)).prettyPrint()

    def do_print(self, line):
        '''
        print
        '''
        print('print')

    def do_stop(self, line):
        '''
        print
        '''
        print('BYE BYE')
        return True

    def do_cluster_conn(self, line):
        '''
        move to oss-cluster connection
        '''
        if self.env.env == 'oss-cluster':
            self.env.con = self.env.envRunner.getClusterConnection()
            print('moved to cluster connection')
        else:
            print('cluster connection only available on oss-cluster env')

    def do_normal_conn(self, line):
        '''
        move to normal connection (will connect to the first shard on oss-cluster)
        '''
        self.env.con = self.env.envRunner.getConnection()
        print('moved to normal connection (first shard on oss-cluster)')

    do_exit = do_stop


parser = CustomArgumentParser(fromfile_prefix_chars=RLTest_CONFIG_FILE_PREFIX,
                              formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                              description='Test Framework for redis and redis module')
parser.add_argument(
    '--version', action='store_const', const=True, default=False,
    help='Print RLTest version and exit')

parser.add_argument(
    '--module', default=None, action='append',
    help='path to the module file. '
         'You can use `--module` more than once but it imples that you explicitly specify `--module-args` as well. '
         'Notice that on enterprise the file should be a zip file packed with [RAMP](https://github.com/RedisLabs/RAMP).')

parser.add_argument(
    '--module-args', default=None, action='append', nargs='*',
    help='arguments to give to the module on loading')

parser.add_argument(
    '--env', '-e', default='oss', choices=['oss', 'oss-cluster', 'enterprise', 'enterprise-cluster', 'existing-env', 'cluster_existing-env'],
    help='env on which to run the test')

parser.add_argument(
    '-p', '--redis-port', type=int, default=6379,
    help='Redis server port')

parser.add_argument(
    '--existing-env-addr', default='localhost:6379',
    help='Address of existing env, relevent only when running with existing-env, cluster_existing-env')

parser.add_argument(
    '--shards_ports',
    help=' list of ports, the shards are listening to, relevent only when running with cluster_existing-env')

parser.add_argument(
    '--cluster_address',
    help='enterprise cluster ip, relevent only when running with cluster_existing-env')

parser.add_argument(
    '--oss_password', default=None,
    help='set redis password, relevant for oss and oss-cluster environment')

parser.add_argument(
    '--cluster_node_timeout', default=5000,
    help='sets the node timeout on cluster in milliseconds')

parser.add_argument(
    '--cluster_credentials',
    help='enterprise cluster cluster_credentials "username:password", relevent only when running with cluster_existing-env')

parser.add_argument(
    '--internal_password', default='',
    help='Give an ability to execute commands on shards directly, relevent only when running with cluster_existing-env')

parser.add_argument(
    '--oss-redis-path', default='redis-server',
    help='path to the oss redis binary')

parser.add_argument(
    '--enterprise-redis-path', default=os.path.join(binaryrepo.REPO_ROOT, 'opt/redislabs/bin/redis-server'),
    help='path to the entrprise redis binary')

parser.add_argument(
    '--stop-on-failure', action='store_const', const=True, default=False,
    help='stop running on failure')

parser.add_argument(
    '-x', '--exit-on-failure', action='store_true',
    help='Stop test execution and exit on first assertion failure')

parser.add_argument(
    '--verbose', '-v', action='count', default=0,
    help='print more information about the test')

parser.add_argument(
    '--debug', action='store_const', const=True, default=False,
    help='stop before each test allow gdb attachment')

parser.add_argument(
    '-t', '--test', metavar='TEST', action='append', help='test to run, in the form of "file:test"')

parser.add_argument(
    '-f', '--tests-file', metavar='FILE', action='append', help='file containing test to run, in the form of "file:test"')

parser.add_argument(
    '-F', '--failed-tests-file', metavar='FILE', help='destination file for failed tests')

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
    '--proxy-binary-path', default=os.path.join(binaryrepo.REPO_ROOT, 'opt/redislabs/bin/dmcproxy'),
    help='dmc proxy binary path')

parser.add_argument(
    '--enterprise-lib-path', default=os.path.join(binaryrepo.REPO_ROOT, 'opt/redislabs/lib/'),
    help='path of needed libraries to run enterprise binaries')

parser.add_argument(
    '-r', '--env-reuse', action='store_const', const=True, default=False,
    help='reuse exists env, this feature is based on best efforts, if the env can not be reused then it will be taken down.')

parser.add_argument(
    '--use-aof', action='store_const', const=True, default=False,
    help='use aof instead of rdb')

parser.add_argument(
    '--use-rdb-preamble', action='store_const', const=True, default=True,
    help='use rdb preamble when rewriting aof file')

parser.add_argument(
    '--debug-print', action='store_const', const=True, default=False,
    help='print debug messages')

parser.add_argument(
    '-V', '--vg', '--use-valgrind', action='store_const', const=True, default=False,
    dest='use_valgrind',
    help='running redis under valgrind (assuming valgrind is install on the machine)')

parser.add_argument(
    '--vg-suppressions', default=None, help='path valgrind suppressions file')
parser.add_argument(
    '--vg-options', default=None, dest='vg_options', help='valgrind [options]')
parser.add_argument(
    '--vg-no-leakcheck', action='store_true', help="Don't perform a leak check")
parser.add_argument(
    '--vg-verbose', action='store_true', help="Don't log valgrind output. "
                                              "Output to screen directly")
parser.add_argument(
    '--vg-no-fail-on-errors', action='store_true', dest='vg_no_fail_on_errors', help="Dont Fail test when valgrind reported any errors in the run."
                                                  "By default on RLTest the return value from Valgrind will be used to fail the tests."
                                                  "Use this option when you wish to dry-run valgrind but not fail the test on valgrind reported errors."
)

parser.add_argument(
    '--sanitizer', default=None, help='type of CLang sanitizer (addr|mem)')

parser.add_argument(
    '-i', '--interactive-debugger', action='store_const', const=True, default=False,
    help='runs the redis on a debuger (gdb/lldb) interactivly.'
         'debugger interactive mode is only possible on a single process and so unsupported on cluste or with slaves.'
         'it is also not possible to use valgrind on interactive mode.'
         'interactive mode direcly applies: --no-output-catch and --stop-on-failure.'
         'it is also implies that only one test will be run (if --env-only was not specify), an error will be raise otherwise.')

parser.add_argument('--debugger', help='Run specified command line as the debugger')

parser.add_argument(
    '-s', '--no-output-catch', action='store_const', const=True, default=False,
    help='all output will be written to the stdout, no log files.')

parser.add_argument(
    '--enable-debug-command', action='store_const', const=True, default=False,
    help='On Redis 7, debug command need to be enabled in order to be used.')

parser.add_argument('--check-exitcode', help='Check redis process exit code',
                    default=False, action='store_true')

parser.add_argument('--unix', help='Use Unix domain sockets instead of TCP',
                    default=False, action='store_true')

parser.add_argument('--randomize-ports',
                    help='Randomize Redis listening port assignment rather than'
                    'using default port',
                    default=False, action='store_true')

parser.add_argument('--parallelism', help='Run tests in parallel', default=1, type=int)

parser.add_argument(
    '--collect-only', action='store_true',
    help='Collect the tests and exit')

parser.add_argument('--tls', help='Enable TLS Support and disable the non-TLS port completely. TLS connections will be available at the default non-TLS ports.',
                    default=False, action='store_true')

parser.add_argument(
    '--tls-cert-file', default=None, help='/path/to/redis.crt')

parser.add_argument(
    '--tls-key-file', default=None, help='/path/to/redis.key')

parser.add_argument(
    '--tls-ca-cert-file', default=None, help='/path/to/ca.crt')

parser.add_argument(
    '--tls-passphrase', default=None, help='passphrase to use on decript key file')

class EnvScopeGuard:
    def __init__(self, runner):
        self.runner = runner

    def __enter__(self):
        pass

    def __exit__(self, type, value, traceback):
        self.runner.takeEnvDown()


class RLTest:
    def __init__(self):
        # adding the current path to sys.path for test import puspused
        sys.path.append(os.getcwd())

        configFilePath = './%s' % RLTest_CONFIG_FILE_NAME
        if os.path.exists(configFilePath):
            args = ['%s%s' % (RLTest_CONFIG_FILE_PREFIX, RLTest_CONFIG_FILE_NAME)] + sys.argv[1:]
        else:
            args = sys.argv[1:]
        self.args = parser.parse_args(args=args)

        if self.args.version:
            print(Colors.Green('RLTest version {}'.format(__version__)))
            sys.exit(0)

        if self.args.redis_port not in range(1, pow(2, 16)):
            print(Colors.Bred(f'requested port {self.args.redis_port} is not valid'))
            sys.exit(1)

        if self.args.interactive_debugger:
            if self.args.env != 'oss' and not (self.args.env == 'oss-cluster' and Defaults.num_shards == 1) and self.args.env != 'enterprise':
                print(Colors.Bred('interactive debugger can only be used on non cluster env'))
                sys.exit(1)
            if self.args.use_valgrind:
                print(Colors.Bred('can not use valgrind with interactive debugger'))
                sys.exit(1)
            if self.args.use_slaves:
                print(Colors.Bred('can not use slaves with interactive debugger'))
                sys.exit(1)

            self.args.no_output_catch = True
            self.args.stop_on_failure = True

        if self.args.download_enterprise_binaries:
            br = binaryrepo.BinaryRepository()
            br.download_binaries()

        if self.args.clear_logs:
            if os.path.exists(self.args.log_dir):
                try:
                    shutil.rmtree(self.args.log_dir)
                except Exception as e:
                    print(e, file=sys.stderr)

        debugger = None
        if self.args.debugger:
            if self.args.env.endswith('existing-env'):
                print(Colors.Bred('can not use debug with existing-env'))
                sys.exit(1)
            debuggers.set_interactive_debugger(self.args.debugger)
            self.args.interactive_debugger = True
        if self.args.use_valgrind:
            if self.args.env.endswith('existing-env'):
                print(Colors.Bred('can not use valgrind with existing-env'))
                sys.exit(1)
            if self.args.vg_options is None:
                self.args.vg_options = os.getenv('VG_OPTIONS', '--leak-check=full --errors-for-leak-kinds=definite')
            vg_debugger = debuggers.Valgrind(options=self.args.vg_options,
                                             suppressions=self.args.vg_suppressions,
                                             fail_on_errors=not(self.args.vg_no_fail_on_errors),
                                             leakcheck=not(self.args.vg_no_leakcheck)
            )
            if self.args.vg_no_leakcheck:
                vg_debugger.leakcheck = False
            if self.args.no_output_catch or self.args.vg_verbose:
                vg_debugger.verbose = True
            debugger = vg_debugger
        elif self.args.interactive_debugger:
            debugger = debuggers.default_interactive_debugger

        sanitizer = None
        if self.args.sanitizer:
            sanitizer = self.args.sanitizer

        if self.args.env.endswith('existing-env'):
            # when running on existing env we always reuse it
            self.args.env_reuse = True

        # unless None, they must match in length
        if self.args.module_args:
            len_module_args = len(self.args.module_args)
            modules = self.args.module
            if type(modules) == list:
                if (len(modules) != len_module_args):
                    print(Colors.Bred('Using `--module` multiple time implies that you specify the `--module-args` in the the same number'))
                    sys.exit(1)

        Defaults.module = fix_modules(self.args.module)
        Defaults.module_args = fix_modulesArgs(Defaults.module, self.args.module_args)
        Defaults.env = self.args.env
        Defaults.binary = self.args.oss_redis_path
        Defaults.verbose = self.args.verbose
        Defaults.logdir = self.args.log_dir
        Defaults.use_slaves = self.args.use_slaves
        Defaults.num_shards = self.args.shards_count
        Defaults.shards_ports = self.args.shards_ports.split(',') if self.args.shards_ports is not None else None
        Defaults.cluster_address = self.args.cluster_address
        Defaults.cluster_credentials = self.args.cluster_credentials
        Defaults.internal_password = self.args.internal_password
        Defaults.proxy_binary = self.args.proxy_binary_path
        Defaults.re_binary = self.args.enterprise_redis_path
        Defaults.re_libdir = self.args.enterprise_lib_path
        Defaults.use_aof = self.args.use_aof
        Defaults.debug_pause = self.args.debug
        Defaults.debug_print = self.args.debug_print
        Defaults.no_capture_output = self.args.no_output_catch
        Defaults.debugger = debugger
        Defaults.sanitizer = sanitizer
        Defaults.exit_on_failure = self.args.exit_on_failure
        Defaults.port = self.args.redis_port
        Defaults.external_addr = self.args.existing_env_addr
        Defaults.use_unix = self.args.unix
        Defaults.randomize_ports = self.args.randomize_ports
        Defaults.use_TLS = self.args.tls
        Defaults.tls_cert_file = self.args.tls_cert_file
        Defaults.tls_key_file = self.args.tls_key_file
        Defaults.tls_ca_cert_file = self.args.tls_ca_cert_file
        Defaults.tls_passphrase = self.args.tls_passphrase
        Defaults.oss_password = self.args.oss_password
        Defaults.cluster_node_timeout = self.args.cluster_node_timeout
        Defaults.enable_debug_command = self.args.enable_debug_command
        if Defaults.use_unix and Defaults.use_slaves:
            raise Exception('Cannot use unix sockets with slaves')

        self.tests = []
        self.testsFailed = []
        self.currEnv = None
        self.loader = TestLoader()
        if self.args.test is not None:
            self.loader.load_spec(self.args.test)
        if self.args.tests_file is not None:
            for fname in self.args.tests_file:
                try:
                    with open(fname, 'r') as file:
                        for line in file.readlines():
                            line = line.strip()
                            if line.startswith('#') or line == "":
                                continue
                            try:
                                self.loader.load_spec(line)
                            except:
                                print(Colors.Red('Invalid test {TEST} in file {FILE}'.format(TEST=line, FILE=fname)))
                except:
                    print(Colors.Red('Test file {} not found'.format(fname)))
        if self.args.test is None and self.args.tests_file is None:
            self.loader.scan_dir(os.getcwd())

        if self.args.collect_only:
            self.loader.print_tests()
            sys.exit(0)
        if self.args.use_valgrind or self.args.check_exitcode:
            self.require_clean_exit = True
        else:
            self.require_clean_exit = False

        self.parallelism = self.args.parallelism

    def _convertArgsType(self):
        pass

    def takeEnvDown(self, fullShutDown=False):
        if not self.currEnv:
            return

        needShutdown = True
        if self.args.env_reuse and not fullShutDown:
            try:
                self.currEnv.flush()
                needShutdown = False
            except Exception as e:
                self.currEnv.stop()
                self.handleFailure(exception=e, testname='[env dtor]',
                                   env=self.currEnv)

        if needShutdown:
            if self.currEnv.isUp():
                try:
                    self.currEnv.flush()
                    flush_ok = True
                except:
                    flush_ok = False
            self.currEnv.stop()
            if self.require_clean_exit and self.currEnv and (not self.currEnv.checkExitCode() or not flush_ok):
                print(Colors.Bred('\tRedis did not exit cleanly'))
                self.addFailure(self.currEnv.testName, ['redis process failure'])
                if self.args.check_exitcode:
                    raise Exception('Process exited dirty')
            self.currEnv = None

    def printException(self, err):
        msg = 'Unhandled exception: {}'.format(err)
        print('\t' + Colors.Bred(msg))
        traceback.print_exc(file=sys.stdout)

    def addFailuresFromEnv(self, name, env):
        """
        Extract the list of failures from the given test Env
        :param name: The name of the test that failed
        :param env: The Environment which contains the failures
        """
        if not env:
            self.addFailure(name, ['<unknown (environment destroyed)>'])
        else:
            self.addFailure(name, failures=env.assertionFailedSummary)

    def addFailure(self, name, failures=None):
        """
        Adds a list of failures to the report
        :param name: The name of the test that has failures
        :param failures: A string or of strings describing the individual failures
        """
        if failures and not isinstance(failures, (list, tuple)):
            failures = [failures]
        if not failures:
            failures = []
        self.testsFailed.append([name, failures])

    def getTotalFailureCount(self):
        ret = 0
        for _, failures in self.testsFailed:
            ret += len(failures)
        return ret

    def handleFailure(self, testFullName=None, exception=None, prefix='', testname=None, env=None):
        """
        Failure omni-function.

        This function handles failures given a set of input parameters.
        At least one of these must not be empty
        :param exception: The exception to report, of any
        :param prefix: The prefix to use for logging.
            This is usually the test name
        :param testname: The test name, use for recording the failures
        :param env: The environment, used for extracting failed assertions
        """
        if not testname and env:
            testname = env.testName
        elif not testname:
            if prefix:
                testname = prefix
            else:
                testname = '<unknown>'

        if exception:
            self.printError(testFullName if testFullName is not None else '')
            self.printException(exception)
        else:
            self.printFail(testFullName if testFullName is not None else '')

        if env:
            self.addFailuresFromEnv(testname, env)
        elif exception:
            self.addFailure(testname, str(exception))
        else:
            self.addFailure(testname, '<No exception or environment>')

    def _runTest(self, test, numberOfAssertionFailed=0, prefix='', before=None, after=None):
        test.initialize()

        msgPrefix = test.name

        testFullName = prefix + test.name

        if not test.is_method:
            Defaults.curr_test_name = testFullName

        try:
            # Python < 3.11
            test_args = inspect.getargspec(test.target).args
        except:
            test_args = inspect.getfullargspec(test.target).args
        
        if len(test_args) > 0 and not test.is_method:
            try:
                env = Env(testName=test.name)
            except Exception as e:
                self.handleFailure(testFullName=testFullName, exception=e, prefix=msgPrefix, testname=test.name)
                return 0

            fn = lambda: test.target(env)
            before_func = (lambda: before(env)) if before is not None else None
            after_func = (lambda: after(env)) if after is not None else None
        else:
            fn = test.target
            before_func = before
            after_func = after

        hasException = False
        try:
            if before_func:
                before_func()
            fn()
            passed = True
        except unittest.SkipTest:
            self.printSkip(testFullName)
            return 0
        except TestAssertionFailure:
            if self.args.exit_on_failure:
                self.takeEnvDown(fullShutDown=True)

            # Don't fall-through
            raise
        except Exception as err:
            if self.args.exit_on_failure:
                self.takeEnvDown(fullShutDown=True)
                after = None
                raise

            self.handleFailure(testFullName=testFullName, exception=err, prefix=msgPrefix,
                               testname=test.name, env=self.currEnv)
            hasException = True
            passed = False
        finally:
            if after_func:
                after_func()

        numFailed = 0
        if self.currEnv:
            numFailed = self.currEnv.getNumberOfFailedAssertion()
            if numFailed > numberOfAssertionFailed:
                self.handleFailure(testFullName=testFullName, prefix=msgPrefix,
                                   testname=test.name, env=self.currEnv)
                passed = False
        elif not hasException:
            self.addFailure(test.name, '<Environment destroyed>')
            passed = False

        # Handle debugger, if needed
        if self.args.stop_on_failure and not passed:
            if self.args.interactive_debugger:
                while self.currEnv.isUp():
                    time.sleep(1)
            input('press any button to move to the next test')

        if passed:
            self.printPass(testFullName)

        return numFailed

    def printSkip(self, name):
        print('%s:\r\n\t%s' % (Colors.Cyan(name), Colors.Green('[SKIP]')))

    def printFail(self, name):
        print('%s:\r\n\t%s' % (Colors.Cyan(name), Colors.Bred('[FAIL]')))

    def printError(self, name):
        print('%s:\r\n\t%s' % (Colors.Cyan(name), Colors.Bred('[ERROR]')))

    def printPass(self, name):
        print('%s:\r\n\t%s' % (Colors.Cyan(name), Colors.Green('[PASS]')))

    def envScopeGuard(self):
        return EnvScopeGuard(self)

    def execute(self):
        Env.RTestInstance = self
        if self.args.env_only:
            Defaults.verbose = 2
            env = Env(testName='manual test env')
            if self.args.interactive_debugger:
                while env.isUp():
                    time.sleep(1)
            else:
                cmd = MyCmd(env)
                cmd.cmdloop()
            env.stop()
            return
        done = 0
        startTime = time.time()
        if self.args.interactive_debugger and len(self.loader.tests) != 1:
            print(self.tests)
            print(Colors.Bred('only one test can be run on interactive-debugger use -t'))
            sys.exit(1)

        jobs = Queue()
        for test in self.loader:
            jobs.put(test, block=False)

        def run_jobs(jobs, results, port):
            Defaults.port = port
            done = 0
            while True:
                try:
                    test = jobs.get(timeout=0.1)
                except Exception as e:
                    break

                with self.envScopeGuard():
                    if test.is_class:
                        test.initialize()

                        Defaults.curr_test_name = test.name
                        try:
                            obj = test.create_instance()

                        except unittest.SkipTest:
                            self.printSkip(test.name)
                            continue

                        except Exception as e:
                            self.printException(e)
                            self.addFailure(test.name + " [__init__]")
                            continue

                        failures = 0
                        before = getattr(obj, 'setUp', None)
                        after = getattr(obj, 'tearDown', None)
                        for subtest in test.get_functions(obj):
                            failures += self._runTest(subtest, prefix='\t',
                                                    numberOfAssertionFailed=failures,
                                                    before=before, after=after)
                            done += 1

                    else:
                        self._runTest(test)
                        done += 1
            self.takeEnvDown(fullShutDown=True)

            # serialized the results back
            results.put({'done': done, 'failures': self.testsFailed}, block=False)

        results = Queue()
        if self.parallelism == 1:
            run_jobs(jobs, results, Defaults.port)
        else :
            processes = []
            currPort = Defaults.port
            for i in range(self.parallelism):
                p = Process(target=run_jobs, args=(jobs,results,currPort))
                currPort += 30 # safe distance for cluster and replicas
                processes.append(p)
                p.start()

            for p in processes:
                p.join()

        # join results
        while True:
            try:
                res = results.get(timeout=0.1)
            except Exception as e:
                break
            done += res['done']
            self.testsFailed.extend(res['failures'])

        endTime = time.time()

        print(Colors.Bold('Test Took: %d sec' % (endTime - startTime)))
        print(Colors.Bold('Total Tests Run: %d, Total Tests Failed: %d, Total Tests Passed: %d' % (done, self.getTotalFailureCount(), done - self.getTotalFailureCount())))
        if self.testsFailed:
            if self.args.failed_tests_file:
                with open(self.args.failed_tests_file, 'w') as file:
                    for test, _ in self.testsFailed:
                        file.write(test.split(' ')[0] + "\n")

            print(Colors.Bold('Failed Tests Summary:'))
            for group, failures in self.testsFailed:
                print('\t' + Colors.Bold(group))
                if not failures:
                    print('\t\t' + Colors.Bred('Exception raised during test execution. See logs'))
                for failure in failures:
                    print('\t\t' + failure)
            sys.exit(1)
        else:
            if self.args.failed_tests_file:
                with open(self.args.failed_tests_file, 'w') as file:
                    pass


def main():
    RLTest().execute()


if __name__ == '__main__':
    main()
