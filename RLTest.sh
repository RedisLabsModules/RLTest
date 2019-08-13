#!/bin/bash

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

if [[ -d venv ]]; then
	. $HERE/venv/bin/activate
else
	[[ ! `command -v virtualenv` ]] && pip install virtualenv
	python -m virtualenv --system-site-packages venv
	. $HERE/venv/bin/activate
	pip install -r $HERE/requirements.txt
fi
PYTHONPATH=$HERE/RLTest python -m RLTest "$@"
