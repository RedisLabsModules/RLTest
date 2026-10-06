"""Regression coverage for Redis processes that refuse graceful shutdown."""
import signal
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

from RLTest.redis_std import MASTER, SLAVE, StandardEnv


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
    setattr(env, role + 'Process', process)
    log_path = tmp_path / env._getFileName(role, '.log')
    log_path.write_text('Writing initial AOF, can\'t exit.\n')
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
            assert 'shutdown stderr' in output
            assert "Writing initial AOF, can't exit." in output
            assert not env.checkExitCode()
        else:
            assert 'sending SIGKILL' not in output
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


@pytest.mark.parametrize('no_log', [False, True])
def test_missing_or_disabled_log_does_not_prevent_cleanup(tmp_path, capsys, no_log):
    env = make_env(tmp_path, noLog=no_log)
    process = start_process(True)
    env.slaveProcess = process
    try:
        with patch('RLTest.redis_std._TERMINATE_TIMEOUT', 0.2):
            env._stopProcess(SLAVE)
        assert process.returncode == -signal.SIGKILL
        assert env.slaveExitCode == -signal.SIGKILL
        output = capsys.readouterr().out
        assert ('Unable to read Redis log' in output) == (not no_log)
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_explicit_retries_reap_killed_process(tmp_path):
    env = make_env(tmp_path, terminateRetries=2, terminateRetrySecs=0.01, noLog=True)
    process = start_process(True)
    env.masterProcess = process
    try:
        env._stopProcess(MASTER)
        assert process.returncode == -signal.SIGKILL
        assert env.masterExitCode == -signal.SIGKILL
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_sigkill_output_wait_is_also_bounded(tmp_path, capsys):
    env = make_env(tmp_path)
    process = Mock()
    process.poll.return_value = None
    process.communicate.side_effect = subprocess.TimeoutExpired('redis-server', 5)
    env.masterProcess = process
    (tmp_path / env._getFileName(MASTER, '.log')).write_text('shutdown refused\n')
    with patch('RLTest.redis_std.platform.system', return_value='Linux'):
        with pytest.raises(subprocess.TimeoutExpired):
            env._stopProcess(MASTER)
    process.kill.assert_called_once_with()
    assert [call.kwargs for call in process.communicate.call_args_list] == [
        {'timeout': 30}, {'timeout': 5}]
    # Diagnostics survive even if a descendant retains an output pipe.
    assert 'shutdown refused' in capsys.readouterr().out
    assert env.masterProcess is process
