"""Regression coverage for Redis processes that refuse graceful shutdown."""
import argparse
import os
import time
import signal
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

from RLTest.redis_std import MASTER, SLAVE, StandardEnv
from RLTest.redis_cluster import ClusterEnv
from RLTest.env import Env
from RLTest.__main__ import RLTest


def make_env(tmp_path, **kwargs):
    with patch.object(StandardEnv, '_getRedisVersion', return_value=80000):
        return StandardEnv(redisBinaryPath='redis-server', dbDirPath=str(tmp_path),
                           outputFilesFormat='%s-shutdown', useSlaves=True, **kwargs)


def start_process(ignore_sigterm):
    handler = 'signal.SIG_IGN' if ignore_sigterm else 'lambda *_: sys.exit(0)'
    code = ('import signal, sys, time\n'
            'signal.signal(signal.SIGTERM, {0})\n'
            'print("ready", flush=True)\n'
            'print("shutdown stderr", file=sys.stderr, flush=True)\n'
            'while True: time.sleep(0.1)\n').format(handler)
    process = subprocess.Popen([sys.executable, '-c', code],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout.readline() == b'ready\n'
    return process


@pytest.mark.parametrize('role', [MASTER, SLAVE])
@pytest.mark.parametrize('ignore_sigterm', [False, True])
def test_stop_reaps_process_and_reports_forced_shutdown(tmp_path, capsys, role, ignore_sigterm):
    env = make_env(tmp_path)
    process = start_process(ignore_sigterm)
    (tmp_path / env._getFileName(role, '.log')).write_text('Writing initial AOF, can\'t exit.\n')
    setattr(env, role + 'Process', process)
    try:
        with patch('RLTest.redis_std._TERMINATE_TIMEOUT', 0.2):
            env.stopEnv(masters=role == MASTER, slaves=role == SLAVE)
        expected_code = -signal.SIGKILL if ignore_sigterm else 0
        assert process.returncode == expected_code
        assert getattr(env, role + 'ExitCode') == expected_code
        assert getattr(env, role + 'Process') is None
        output = capsys.readouterr().out
        if ignore_sigterm:
            assert 'sending SIGKILL' in output
            assert role in output
            assert 'Writing initial AOF' in output
            assert env.hasShutdownFailure()
            assert not env.checkExitCode()
        else:
            assert 'sending SIGKILL' not in output
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_sigkill_wait_timeout_does_not_abort_remaining_shards(tmp_path):
    env = make_env(tmp_path)
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = subprocess.TimeoutExpired('redis-server', 5)
    env.masterProcess = process
    cluster = ClusterEnv.__new__(ClusterEnv)
    other = Mock()
    cluster.shards = [env, other]
    with patch('RLTest.redis_std._TERMINATE_TIMEOUT', 0):
        cluster.stopEnv()
    process.kill.assert_called_once_with()
    process.wait.assert_called_once_with(timeout=5)
    assert env.masterProcess is None
    assert env.masterExitCode is None
    assert env.hasShutdownFailure()
    other.stopEnv.assert_called_once()


@pytest.mark.parametrize('ignore_sigterm', [False, True])
def test_inherited_pipes_do_not_block_parent_shutdown(tmp_path, ignore_sigterm):
    env = make_env(tmp_path)
    handler = 'signal.SIG_IGN' if ignore_sigterm else 'lambda *_: sys.exit(0)'
    code = ("import os, signal, sys, time\n"
            "signal.signal(signal.SIGTERM, {0})\n"
            "child = os.fork()\n"
            "if child == 0:\n"
            "    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "    time.sleep(60)\n"
            "    os._exit(0)\n"
            "print(child, flush=True)\n"
            "while True: time.sleep(.1)\n").format(handler)
    process = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    child = int(process.stdout.readline())
    env.slaveProcess = process
    try:
        start = time.monotonic()
        with patch('RLTest.redis_std._TERMINATE_TIMEOUT', .2):
            env.stopEnv(masters=False)
        assert time.monotonic() - start < 2
        assert env.slaveExitCode == (-signal.SIGKILL if ignore_sigterm else 0)
        assert env.slaveProcess is None
        assert env.hasShutdownFailure() == ignore_sigterm
        os.kill(child, 0)  # The inherited pipes are still held open.
    finally:
        os.kill(child, signal.SIGKILL)
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_retries_sigterm_after_initial_refusal(tmp_path):
    env = make_env(tmp_path)
    code = ("import signal, sys, time\n"
            "def refused(*_):\n"
            "    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n"
            "signal.signal(signal.SIGTERM, refused)\n"
            "print('ready', flush=True)\n"
            "while True: time.sleep(.1)\n")
    process = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE)
    assert process.stdout.readline() == b'ready\n'
    env.masterProcess = process
    try:
        with patch('RLTest.redis_std._TERMINATE_TIMEOUT', 3):
            env.stopEnv()
        assert env.masterExitCode == 0
        assert not env.hasShutdownFailure()
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


@pytest.mark.parametrize('clustered', [False, True])
def test_forced_shutdown_fails_runner_without_check_exitcode(tmp_path, clustered):
    std = make_env(tmp_path)
    process = start_process(True)
    std.masterProcess = process
    runner = std
    if clustered:
        runner = ClusterEnv.__new__(ClusterEnv)
        runner.shards = [std]
    env = Env.__new__(Env)
    env.envRunner = runner
    env.testName = 'shutdown-regression'
    rl = RLTest.__new__(RLTest)
    rl.args = argparse.Namespace(env_reuse=False, check_exitcode=False)
    rl.require_clean_exit = False
    rl.testsFailed = {}
    rl.currEnv = env
    try:
        with patch.object(env, 'isUp', return_value=False):
            with patch('RLTest.redis_std._TERMINATE_TIMEOUT', .1):
                rl.takeEnvDown()
        assert rl.testsFailed == {'shutdown-regression': ['redis process failure']}
        assert rl.currEnv is None
        assert std.masterProcess is None
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_darwin_debugger_child_wait_is_bounded(tmp_path):
    env = make_env(tmp_path)
    process = Mock()
    process.poll.return_value = 0
    env.masterProcess = process
    child = Mock()
    with patch.object(env, '_isAlive', return_value=True), \
         patch.object(StandardEnv, 'has_interactive_debugger', True), \
         patch('RLTest.redis_std.platform.system', return_value='Darwin'), \
         patch('RLTest.redis_std.psutil.Process') as parent, \
         patch('RLTest.redis_std.psutil.wait_procs', side_effect=[([], [child]), ([], [child])]) as wait:
        parent.return_value.children.return_value = [child]
        env.stopEnv()
    assert [call[1]['timeout'] for call in wait.call_args_list] == [30, 5]
    child.kill.assert_called_once_with()
    assert env.masterProcess is None
    assert env.hasShutdownFailure()
