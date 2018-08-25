import argparse
import os
import imp
import traceback
import sys
import subprocess
import platform
import shutil
from Env import Env
from utils import Colors


RLTest_WORKING_DIR = os.path.expanduser('~/.RLTest/')
RLTest_ENTERPRISE_VERSION = '5.2.0'
RLTest_ENTERPRISE_SUB_VERSION = '14'
OS_NAME = platform.dist()[2]
RLTest_ENTERPRISE_TAR_FILE_NAME = 'redislabs-%s-%s-%s-amd64.tar' % (RLTest_ENTERPRISE_VERSION, RLTest_ENTERPRISE_SUB_VERSION, OS_NAME)
RLTest_ENTERPRISE_URL = 'https://s3.amazonaws.com/rlec-downloads/%s/%s' % (RLTest_ENTERPRISE_VERSION, RLTest_ENTERPRISE_TAR_FILE_NAME)


class RLTest:

    def __init__(self):
        parser = argparse.ArgumentParser(
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description='RedisConTest Test Suite Runner')

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

        self.args = parser.parse_args()

        if self.args.download_enterprise_binaries:
            self.downloadEnterpriseBinaries()

        Env.defaultModule = self.args.module
        Env.defaultModuleArgs = self.args.module_args
        Env.defaultEnv = self.args.env
        Env.defaultOssRedisBinary = self.args.oss_redis_path
        Env.defaultVerbose = self.args.verbose
        Env.defaultLogDir = self.args.log_dir
        Env.defaultDebug = self.args.debug
        Env.defaultUseSlaves = self.args.use_slaves
        Env.defaultShardsCount = self.args.shards_count
        Env.defaultProxyBinaryPath = self.args.proxy_binary_path
        Env.defaultEnterpriseRedisBinaryPath = self.args.enterprise_redis_path
        Env.defaultEnterpriseLibsPath = self.args.enterprise_lib_path

        self.tests = []

        self.currEnv = None

    def downloadEnterpriseBinaries(self):
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

    def load_file_tests(self, module_name):
        filename = '%s/%s.py' % (self.args.tests_dir, module_name)
        module_file = open(filename, 'r')
        module = imp.load_module(module_name, module_file, filename,
                                 ('.py', 'r', imp.PY_SOURCE))
        for func in dir(module):
            if self.args.test_name:
                if func == self.args.test_name:
                    self.tests.append(getattr(module, func))
                    return
            elif func.startswith('test_'):
                self.tests.append(getattr(module, func))

    def load_tests(self):
        for filename in os.listdir(self.args.tests_dir):
            if filename.startswith('test_') and filename.endswith('.py'):
                module_name, ext = os.path.splitext(filename)
                self.load_file_tests(module_name)

    def execute(self):
        testsFailed = []
        Env.RTestInstance = self
        if self.args.env_only:
            Env.defaultVerbose = 2
            env = Env(testName='manual test env')
            raw_input('press any button to stop')
            env.Stop()
            return
        if self.args.tests_file:
            self.load_file_tests(self.args.tests_file)
        else:
            self.load_tests()
        done = 0
        while self.tests:
            done += 1
            test = self.tests.pop(0)
            exceptionRaised = False
            try:
                test()
            except Exception as err:
                msg = 'Unhandled exception: %s' % err
                print '\t' + Colors.Bred(msg)
                traceback.print_exc(file=sys.stdout)
                exceptionRaised = True

            isTestFaild = self.currEnv.GetNumberOfFailedAssertion() or exceptionRaised

            if isTestFaild:
                print '\t' + Colors.Bred('Test Failed')
                testsFailed.append(self.currEnv)
            else:
                print '\t' + Colors.Green('Test Passed')

            if self.args.stop_on_failure and isTestFaild:
                raw_input('press any button to move to the next test')

            self.currEnv.Stop()
            self.currEnv = None

        if len(testsFailed) > 0:
            print Colors.Bold('Faild Tests Summery:')
            for testFaild in testsFailed:
                print '\t' + Colors.Bold(testFaild.testNamePrintable)
                testFaild.PrintFailuresSummery('\t\t')
            sys.exit(1)


def main():
    RLTest().execute()


if __name__ == '__main__':
    main()
