from __future__ import print_function
import os.path
import shutil
import distro
import subprocess
import sys

from RLTest.utils import Colors


OS_NAME = distro.linux_distribution()[2]
REPO_ROOT = os.path.expanduser('~/.RLTest')
ENTERPRISE_VERSION = '5.2.0'
ENTERPRISE_SUB_VERSION = '14'
ENTERPRISE_TAR_FILE_NAME = 'redislabs-%s-%s-%s-amd64.tar' % (
    ENTERPRISE_VERSION, ENTERPRISE_SUB_VERSION, OS_NAME)
ENTERPRISE_URL = 'https://s3.amazonaws.com/rlec-downloads/%s/%s' % (
    ENTERPRISE_VERSION, ENTERPRISE_TAR_FILE_NAME)
DEBIAN_PKG_NAME = 'redislabs_%s-%s~%s_amd64.deb' % (
        ENTERPRISE_VERSION, ENTERPRISE_SUB_VERSION, OS_NAME)


class BinaryRepository(object):
    """
    Installation manager for Redis Enterprise.
    The long-term idea behind this is to allow for managing different versions, etc.
    but for now it's just here to cut some code out of the main executable
    """
    def __init__(self, root=REPO_ROOT, url=ENTERPRISE_URL, debname=DEBIAN_PKG_NAME):
        self.root = root
        self.url = url
        self.debname = debname

    def download_binaries(self, binariesName='binaries.tar'):
        print(Colors.Yellow('installing enterprise binaries'))
        print(Colors.Yellow('creating RLTest working dir: %s' % self.root))
        try:
            shutil.rmtree(self.root)
            os.makedirs(self.root)
        except Exception:
            pass

        print(Colors.Yellow('download binaries'))
        args = ['wget', self.url, '-O', os.path.join(self.root, binariesName)]
        process = subprocess.Popen(args=args, stdout=sys.stdout,
                                        stderr=sys.stdout)
        process.wait()
        if process.poll() != 0:
            raise Exception('failed to download enterprise binaries from s3')

        print(Colors.Yellow('extracting binaries'))

        args = ['tar', '-xvf', os.path.join(self.root, binariesName),
                '--directory', self.root, self.debname]
        process = subprocess.Popen(args=args, stdout=sys.stdout, stderr=sys.stdout)
        process.wait()
        if process.poll() != 0:
            raise Exception(
                'failed to extract binaries to %s' % self.self.root)

        # TODO: Support centos that does not have dpkg command
        args = ['dpkg', '-x', os.path.join(self.root, self.debname),
                self.root]
        process = subprocess.Popen(args=args, stdout=sys.stdout,
                                        stderr=sys.stdout)
        process.wait()
        if process.poll() != 0:
            raise Exception(
                'failed to extract binaries to %s' % self.self.root)

        print(Colors.Yellow('finished installing enterprise binaries'))