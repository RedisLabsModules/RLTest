#!/bin/bash

set -e

show_if_error() {
	[[ $SHOW == 1 ]] && echo "${@:1}"
	if [[ $VERBOSE == 1 ]]; then
		{ "${@:1}"; }
	else
		{ "${@:1}"; } > /tmp/rltest.log 2>&1
		[ $? != 0 ] && cat /tmp/rltest.log
		rm -f /tmp/rltest.log
	fi
}

install_prerequisites() {
	[[ -f .installed2 ]] && return
	show_if_error apt-get -qq update
	show_if_error apt-get -q install -y python2 python-psutil
	show_if_error apt-get -q install -y curl ca-certificates
	show_if_error curl -s https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
	show_if_error python2 /tmp/get-pip.py
	show_if_error pip install virtualenv
	touch .installed2
}

is_installed() {
	[[ $({ dpkg -l "$*" >/dev/null 2>&1 ; echo $? ;}) == 0 ]] && echo yes
}

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

install_prerequisites
if [[ -d venv2 ]]; then
	. $HERE/venv2/bin/activate
else
	show_if_error python2 -m virtualenv --system-site-packages venv2
	. $HERE/venv2/bin/activate
	show_if_error pip install -r $HERE/requirements.txt
fi
PYTHONPATH=$HERE/RLTest python2 -m RLTest "$@"
