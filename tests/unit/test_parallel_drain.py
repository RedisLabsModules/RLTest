"""Regression test for a hang in the parallel test coordinator.

The parallel coordinator uses a single ``results`` queue carrying one message
per test. Workers push these messages while the coordinator drains them in its
progressbar loop. If the coordinator ever stops draining before workers stop
pushing, large per-test outputs saturate the pipe (~64 KiB on Linux), worker
``put()`` calls block in ``pipe_write``, and ``p.join()`` hangs indefinitely.

This test reproduces the saturation scenario by spawning workers that each
push many large messages, then asserts that a coordinator that drains
continuously throughout the workers' lifetime finishes promptly with every
message accounted for and every worker cleanly exited.
"""

import multiprocessing as mp
import sys
import time
from unittest import TestCase


# ~32 KiB per message × 8 workers × 8 messages = 2 MiB total, well over the
# typical 64 KiB pipe buffer on Linux, so writers will block on ``pipe_write``
# unless the parent is actively reading throughout.
_PAYLOAD_BYTES = 32 * 1024
_NUM_WORKERS = 8
_MSGS_PER_WORKER = 8
_JOIN_TIMEOUT_SECS = 30.0


def _worker_puts_many_results(results, n_msgs, payload_bytes):
    # Queue.put is async (via a feeder thread), but at process exit the feeder
    # must flush the buffered items to the pipe before the worker can exit. If
    # the parent is not draining, that flush blocks forever.
    payload = 'x' * payload_bytes
    for i in range(n_msgs):
        results.put({'test_name': 't%d' % i, 'output': payload,
                     'done': 1, 'failures': {}})


class TestParallelResultsDrain(TestCase):

    def setUp(self):
        if sys.platform == 'win32':
            self.skipTest('fork start method is unavailable on Windows')
        self._ctx = mp.get_context('fork')
        self._procs = []

    def tearDown(self):
        # Safety net: if the test ever hangs despite the fix, make sure the
        # pytest session can still exit cleanly.
        for p in self._procs:
            if p.is_alive():
                p.kill()
                p.join(timeout=5)

    def test_continuous_drain_does_not_hang(self):
        results = self._ctx.Queue()
        self._procs = [
            self._ctx.Process(
                target=_worker_puts_many_results,
                args=(results, _MSGS_PER_WORKER, _PAYLOAD_BYTES),
            )
            for _ in range(_NUM_WORKERS)
        ]
        for p in self._procs:
            p.start()

        # Mimic the coordinator's progressbar loop: drain every per-test
        # message live, in the same thread, while workers are still running.
        expected = _NUM_WORKERS * _MSGS_PER_WORKER
        start = time.monotonic()
        collected = [results.get(timeout=_JOIN_TIMEOUT_SECS) for _ in range(expected)]
        for p in self._procs:
            p.join(timeout=_JOIN_TIMEOUT_SECS)
        elapsed = time.monotonic() - start

        for p in self._procs:
            self.assertFalse(
                p.is_alive(),
                'worker still alive after join; results pipe likely saturated',
            )
            self.assertEqual(p.exitcode, 0)
        self.assertEqual(len(collected), expected)
        # The drain should return well under its own timeout; we only assert a
        # loose upper bound to avoid flakiness on slow machines.
        self.assertLess(elapsed, _JOIN_TIMEOUT_SECS)
