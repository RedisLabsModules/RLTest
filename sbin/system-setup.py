#!/bin/bash
''''[ ! -z $VIRTUAL_ENV ] && exec python -u -- "$0" ${1+"$@"}; command -v python3 > /dev/null && exec python3 -u -- "$0" ${1+"$@"}; exec python2 -u -- "$0" ${1+"$@"} # '''

import sys
import os
import argparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "deps/readies"))
import paella

#----------------------------------------------------------------------------------------------

class RLTestSetup(paella.Setup):
    def __init__(self, nop=False):
        paella.Setup.__init__(self, nop)

    def common_first(self):
        self.setup_pip()
        self.pip_install("wheel")
        self.pip_install("setuptools --upgrade")

    def debian_compat(self):
        self.install("libssl-dev")
        if sys.version_info < (3, 0):
            self.install("python-psutil")
        else:
            self.install("python3-psutil")

    def redhat_compat(self):
        self.install("openssl-devel")
        if sys.version_info < (3, 0):
            self.install("python-psutil")
        else:
            self.install("python36-psutil")

    def macosx(self):
        if sh('xcode-select -p') == '':
            fatal("Xcode tools are not installed. Please run xcode-select --install.")
        self.install_gnu_utils()

    def freebsd(self):
        self.install_gnu_utils()
        
    def common_last(self):
        self.pip_install("-r %s/requirements.txt" % ROOT)
        self.pip_install("pytest pytest-cov")

#----------------------------------------------------------------------------------------------

parser = argparse.ArgumentParser(description='Set up system for build.')
parser.add_argument('-n', '--nop', action="store_true", help='no operation')
args = parser.parse_args()

RLTestSetup(nop = args.nop).setup()
