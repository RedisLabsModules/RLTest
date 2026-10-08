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


@pytest.mark.parametrize('instrumentation', ['valgrind', 'sanitizer'])
def test_instrumented_shutdown_can_finish_after_thirty_seconds(tmp_path, instrumentation):
    from RLTest.debuggers import Valgrind
    kwargs = {'debugger': Valgrind('')} if instrumentation == 'valgrind' else {'sanitizer': 'address'}
    env = make_env(tmp_path, **kwargs)
    process = Mock()
    process.poll.side_effect = [None, None, 0, 0, 0]
    process.wait.side_effect = [subprocess.TimeoutExpired('redis-server', 1), 0]
    env.masterProcess = process
    with patch.object(env, '_isAlive', return_value=True), \
         patch('RLTest.redis_std.time.monotonic', side_effect=[0, 0, 31]):
        env.stopEnv()
    process.kill.assert_not_called()
    assert process.wait.call_count == 2
    assert env.masterExitCode == 0
    assert not env.hasShutdownFailure()


def test_diagnostic_path_error_cannot_prevent_teardown(tmp_path, capsys):
    env = make_env(tmp_path)
    process = start_process(True)
    env.masterProcess = process
    try:
        with patch.object(env, '_getFileName', side_effect=TypeError('invalid log format')), \
             patch('RLTest.redis_std._TERMINATE_TIMEOUT', .1):
            env.stopEnv()
        assert process.returncode == -signal.SIGKILL
        assert env.masterProcess is None
        assert env.masterExitCode == -signal.SIGKILL
        assert env.hasShutdownFailure()
        assert 'could not read server log' in capsys.readouterr().out
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


def test_reused_environment_reports_failure_on_original_test(tmp_path):
    from RLTest.loader import TestMethod
    first, second = make_env(tmp_path), make_env(tmp_path)
    cluster = ClusterEnv.__new__(ClusterEnv)
    cluster.shards = [first, second]
    env = Env.__new__(Env)
    env.envRunner = cluster
    env.assertionFailedSummary = []
    env.testName = 'original'
    rl = RLTest.__new__(RLTest)
    rl.currEnv = env
    rl.testsFailed = {}
    rl.args = argparse.Namespace(env_reuse=True, check_exitcode=False,
                                 exit_on_failure=False, stop_on_failure=False)
    rl.require_clean_exit = False
    def original():
        # A mid-test stop/restart must retain the failure until the test ends.
        first.shutdownFailed = second.shutdownFailed = True
    def following():
        pass
    with patch.object(rl, 'printFail'), patch.object(rl, 'printPass'):
        assert rl._runTest(TestMethod(original, name='original')) == 1
        assert not cluster.hasShutdownFailure()
        env.testName = 'following'
        assert rl._runTest(TestMethod(following, name='following')) == 0
        with patch.object(env, 'isUp', return_value=False):
            rl.takeEnvDown(fullShutDown=True)
    assert rl.testsFailed == {'original': ['redis process failure']}


def test_class_shutdown_failure_does_not_hide_later_assertions(tmp_path):
    from contextlib import nullcontext
    from RLTest.env import Defaults
    from RLTest.loader import TestMethod
    std = make_env(tmp_path)
    env = Env.__new__(Env)
    env.envRunner = std
    env.assertionFailedSummary = []
    rl = RLTest.__new__(RLTest)
    rl.currEnv = env
    rl.testsFailed = {}
    rl.args = argparse.Namespace(test_timeout=0, exit_on_failure=False, stop_on_failure=False)

    def forced_shutdown():
        std.shutdownFailed = True

    def assertion_failure():
        env.assertionFailedSummary.append('later assertion failed')

    test = Mock(is_class=True, env_spec=None)
    test.name = 'regression'
    test.get_functions.return_value = [TestMethod(forced_shutdown, 'first'),
                                      TestMethod(assertion_failure, 'second'),
                                      TestMethod(assertion_failure, 'third')]
    with patch.object(Defaults, 'curr_test_name', None), \
         patch.object(rl, 'envScopeGuard', return_value=nullcontext()), \
         patch.object(rl, 'printFail'), patch.object(rl, 'printPass') as passed, \
         patch.object(Defaults, 'print_verbose_information_on_failure', False):
        assert rl.run_single_test(test, lambda: None) == 3
    assert set(rl.testsFailed) == {'first', 'second', 'third'}
    passed.assert_not_called()


@pytest.mark.parametrize('replacements', [1, 2])
def test_environment_replacement_retains_shutdown_failure(tmp_path, replacements):
    from RLTest.env import Defaults
    from RLTest.loader import TestMethod
    old = Env.__new__(Env)
    old.envRunner = make_env(tmp_path)
    old.assertionFailedSummary = []
    rl = RLTest.__new__(RLTest)
    rl.currEnv = old
    rl.testsFailed = {}
    rl.args = argparse.Namespace(exit_on_failure=False, stop_on_failure=False)

    def replacement():
        for _ in range(replacements):
            Env(testName='swap', freshEnv=True, logDir=str(tmp_path))

    def stop(env):
        if env is old:
            env.envRunner.shutdownFailed = True

    with patch.object(Env, 'RTestInstance', rl), \
         patch.object(Env, 'getEnvByName', side_effect=lambda: make_env(tmp_path)), \
         patch.object(Env, 'start'), patch.object(Env, 'stop', stop), \
         patch.object(Defaults, 'debug_pause', False), \
         patch.object(rl, 'printFail'), patch.object(rl, 'printPass') as passed:
        assert rl._runTest(TestMethod(replacement, 'swap')) == 1
        assert not rl.currEnv.hasShutdownFailure()
    assert rl.testsFailed == {'swap': ['redis process failure']}
    passed.assert_not_called()


@pytest.mark.parametrize('forced', [False, True])
@pytest.mark.parametrize('phase', ['body', 'teardown'])
def test_skipped_test_consumes_its_shutdown_failure(tmp_path, forced, phase):
    import unittest
    from RLTest.loader import TestMethod
    std = make_env(tmp_path)
    env = Env.__new__(Env)
    env.envRunner = std
    env.assertionFailedSummary = []
    rl = RLTest.__new__(RLTest)
    rl.currEnv = env
    rl.testsFailed = {}
    rl.args = argparse.Namespace(exit_on_failure=False, stop_on_failure=False)

    def skipped():
        if phase == 'body':
            std.shutdownFailed = forced
        raise unittest.SkipTest()

    def teardown():
        if phase == 'teardown':
            std.shutdownFailed = forced

    with patch.object(rl, 'printSkip') as skip, patch.object(rl, 'printFail'), \
         patch.object(rl, 'printPass') as passed:
        assert rl._runTest(TestMethod(skipped, 'skipped'), after=teardown) == int(forced)
        assert not std.hasShutdownFailure()
        assert skip.call_count == (0 if forced else 1)
        passed.assert_not_called()
        assert rl._runTest(TestMethod(lambda: None, 'following')) == 0
        passed.assert_called_once_with('following')
    assert rl.testsFailed == ({'skipped': ['redis process failure']} if forced else {})


@pytest.mark.parametrize('forced', [False, True])
def test_class_constructor_skip_consumes_shutdown_failure(tmp_path, forced):
    import unittest
    from RLTest.env import Defaults
    from RLTest.loader import TestMethod
    env = Env.__new__(Env)
    env.envRunner = make_env(tmp_path)
    env.assertionFailedSummary = []
    rl = RLTest.__new__(RLTest)
    rl.currEnv = env
    rl.testsFailed = {}
    rl.args = argparse.Namespace(test_timeout=0, env_reuse=True,
                                 exit_on_failure=False, stop_on_failure=False)
    test = Mock(is_class=True, env_spec=None)
    test.name = 'constructor'

    def skipped():
        env.envRunner.shutdownFailed = forced
        raise unittest.SkipTest()

    test.create_instance.side_effect = skipped
    with patch.object(Defaults, 'curr_test_name', None), \
         patch.object(env, 'flush'), patch.object(rl, 'printSkip') as skip:
        assert rl.run_single_test(test, lambda: None) == 0
        assert skip.call_count == (0 if forced else 1)
        assert not env.hasShutdownFailure()
        assert rl._runTest(TestMethod(lambda: None, 'following')) == 0
    assert rl.testsFailed == ({'constructor': ['redis process failure']} if forced else {})


@pytest.mark.parametrize('forced', [False, True])
@pytest.mark.parametrize('outcome', ['pass', 'skip', 'constructor_skip'])
def test_result_output_waits_for_environment_teardown(tmp_path, capsys, forced, outcome):
    import unittest
    from RLTest.env import Defaults
    from RLTest.loader import TestMethod
    env = Env.__new__(Env)
    env.envRunner = make_env(tmp_path)
    env.testName = 'teardown'
    env.assertionFailedSummary = []
    rl = RLTest.__new__(RLTest)
    rl.currEnv = env
    rl.testsFailed = {}
    rl.require_clean_exit = False
    rl.args = argparse.Namespace(test_timeout=0, env_reuse=False, check_exitcode=False,
                                 exit_on_failure=False, stop_on_failure=False)

    def stop():
        output = capsys.readouterr().out
        assert '[PASS]' not in output
        assert '[SKIP]' not in output
        env.envRunner.shutdownFailed = forced

    def target():
        if outcome != 'pass':
            raise unittest.SkipTest()

    test = TestMethod(target, 'teardown')
    if outcome == 'constructor_skip':
        test = Mock(is_class=True, env_spec=None)
        test.name = 'teardown'
        test.create_instance.side_effect = target
    with patch.object(Defaults, 'curr_test_name', None), \
         patch.object(Defaults, 'print_verbose_information_on_failure', False), \
         patch.object(env, 'isUp', return_value=False), patch.object(env, 'stop', stop):
        assert rl.run_single_test(test, lambda: None) == (0 if outcome == 'constructor_skip' else 1)
    output = capsys.readouterr().out
    assert ('[PASS]' in output) == (not forced and outcome == 'pass')
    assert ('[SKIP]' in output) == (not forced and outcome != 'pass')
    assert ('[FAIL]' in output) == forced
    assert rl.testsFailed == ({'teardown': ['redis process failure']} if forced else {})
