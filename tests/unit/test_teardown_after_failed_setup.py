"""Regression test for a worker crash when tearDown assumes setUp succeeded.

RLTest._runTest ran a class-based test's tearDown unconditionally in a bare
``finally``, even when setUp itself raised. A tearDown written against a
successful setUp (e.g. one that calls ``self.env.flush()``) then raises its
own exception -- typically AttributeError, since the attribute setUp would
have assigned was never set. That second exception escaped _runTest uncaught,
which in the parallel coordinator kills the whole worker process instead of
just failing the one test.
"""

import argparse
from unittest import TestCase

from RLTest.__main__ import RLTest
from RLTest.loader import TestMethod


def _make_rltest():
    # Bypass __init__ (argparse over sys.argv, config-file lookup): _runTest
    # only touches self.args.exit_on_failure, self.currEnv and self.testsFailed.
    rl = RLTest.__new__(RLTest)
    rl.args = argparse.Namespace(exit_on_failure=False, stop_on_failure=False,
                                  interactive_debugger=False)
    rl.currEnv = None
    rl.testsFailed = {}
    return rl


class _EnvUser:
    """Mimics a test class whose setUp fails before assigning self.env."""

    def setUp(self):
        raise ConnectionError('simulated env startup failure')

    def tearDown(self):
        # A real test class does this unconditionally; if setUp never ran to
        # completion, self.env does not exist.
        self.env.flush()

    def test_something(self):
        raise AssertionError('should never run: setUp already failed')


class TestTearDownAfterFailedSetup(TestCase):

    def test_failed_setup_skips_teardown_without_crashing(self):
        rl = _make_rltest()
        instance = _EnvUser()
        test = TestMethod(instance.test_something, name='fake:test_something')

        # Must not raise: a failed setUp should be reported like any other
        # test failure, not escape as an unhandled exception.
        numFailed = rl._runTest(test, before=instance.setUp, after=instance.tearDown)

        self.assertEqual(numFailed, 1)
        self.assertIn('fake:test_something', rl.testsFailed)
        self.assertIn('simulated env startup failure', str(rl.testsFailed['fake:test_something']))

    def test_teardown_failure_after_successful_test_is_reported_not_raised(self):
        rl = _make_rltest()

        class _BrokenTeardown:
            def setUp(self):
                pass

            def tearDown(self):
                raise RuntimeError('teardown blew up')

            def test_something(self):
                pass

        instance = _BrokenTeardown()
        test = TestMethod(instance.test_something, name='fake:test_something2')

        rl._runTest(test, before=instance.setUp, after=instance.tearDown)

        self.assertIn('fake:test_something2', rl.testsFailed)
        self.assertIn('teardown blew up', str(rl.testsFailed['fake:test_something2']))
