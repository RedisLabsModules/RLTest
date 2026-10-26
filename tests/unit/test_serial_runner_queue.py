"""Regression test: the serial runner must run every test even when a
multiprocessing.Queue's feeder thread has not flushed yet.

It used to read tests back from a multiprocessing.Queue with
get(timeout=0.1) and stop on Empty, so a starved feeder thread made it run
zero tests and exit 0.
"""

import argparse
import multiprocessing as mp
import queue
import sys
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import RLTest.__main__ as rlmain
from RLTest.__main__ import RLTest


class _StarvedQueue:
    """A queue whose feeder thread never gets to flush."""

    def put(self, obj, block=True, timeout=None):
        pass

    def get(self, block=True, timeout=None):
        raise queue.Empty


def _make_rltest(tests, parallelism, run_single_test):
    rl = RLTest.__new__(RLTest)
    rl.args = argparse.Namespace(env_only=False, interactive_debugger=False,
                                 no_output_catch=True, no_progress=True,
                                 failed_tests_file=None)
    rl.loader = tests
    rl.parallelism = parallelism
    rl.currEnv = None
    rl.testsFailed = {}
    rl.github_actions_group_open = False
    rl.run_single_test = run_single_test
    return rl


class TestRunnerQueue(TestCase):

    def test_serial_runs_every_test_with_a_starved_queue(self):
        ran = []

        def run_single_test(test, on_timeout):
            ran.append(test)
            return 1

        rl = _make_rltest(['t1', 't2', 't3'], 1, run_single_test)
        with patch.object(rlmain, 'Queue', _StarvedQueue):
            rl.execute()
        self.assertEqual(ran, ['t1', 't2', 't3'])

    def test_parallel_runs_every_test(self):
        if sys.platform == 'win32':
            self.skipTest('fork start method is unavailable on Windows')
        ctx = mp.get_context('fork')
        tests = [SimpleNamespace(name='t%d' % i) for i in range(20)]
        rl = _make_rltest(tests, 3, lambda test, on_timeout: 1)
        with patch.object(rlmain, 'Queue', ctx.Queue), \
             patch.object(rlmain, 'Process', ctx.Process), \
             patch('sys.stdout') as out:
            rl.execute()
        summary = ''.join(c.args[0] for c in out.write.call_args_list)
        self.assertIn('Total Tests Run: 20,', summary)
