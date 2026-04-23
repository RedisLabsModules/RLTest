"""Regression test for a hang in the parallel test coordinator.

Prior to the fix, the coordinator joined all worker processes before draining
the ``summary`` queue. With enough data queued (or a single large
``self.testsFailed`` dict), the summary pipe buffer (~64 KiB on Linux)
saturates and worker feeder threads block in ``pipe_write`` during Python's
end-of-process queue finalization (and similarly inside ``on_timeout``'s
``summary.join_thread()``). That causes the coordinator's ``p.join()`` to
hang indefinitely.

The fix drains ``summary`` from a background thread while workers are being
joined. This test reproduces the saturation scenario and asserts the helper
completes within a bounded time with every worker cleanly exited.
"""

import multiprocessing as mp
import sys
import time
from unittest import TestCase

from RLTest.__main__ import _join_workers_with_summary_drain


# ~32 KiB per message × 8 workers = 256 KiB total, comfortably exceeding the
# typical 64 KiB pipe buffer on Linux, so at least some feeder threads will
# block on ``pipe_write`` unless the parent is actively reading.
_PAYLOAD_BYTES = 32 * 1024
_NUM_WORKERS = 8
_JOIN_TIMEOUT_SECS = 30.0


def _worker_puts_large_summary(summary):
    summary.put({
        'done': 1,
        'failures': {},
        'payload': 'x' * _PAYLOAD_BYTES,
    })
    # Return normally; Python finalization will join the feeder thread,
    # which is where a non-draining parent would cause the hang.


class TestJoinWorkersWithSummaryDrain(TestCase):

    def setUp(self):
        if sys.platform == 'win32':
            self.skipTest('fork start method is unavailable on Windows')
        self._ctx = mp.get_context('fork')
        self._procs = []
        self._summary = None

    def tearDown(self):
        # Safety net: if the helper ever hangs despite the fix, make sure the
        # pytest session can still exit cleanly.
        for p in self._procs:
            if p.is_alive():
                p.kill()
                p.join(timeout=5)

    def test_large_summary_does_not_hang(self):
        self._summary = self._ctx.Queue()
        self._procs = [
            self._ctx.Process(
                target=_worker_puts_large_summary,
                args=(self._summary,),
            )
            for _ in range(_NUM_WORKERS)
        ]
        for p in self._procs:
            p.start()

        start = time.time()
        collected = _join_workers_with_summary_drain(
            self._procs, self._summary, timeout=_JOIN_TIMEOUT_SECS,
        )
        elapsed = time.time() - start

        for p in self._procs:
            self.assertFalse(
                p.is_alive(),
                'worker still alive after drain-join; summary pipe likely saturated',
            )
            self.assertEqual(p.exitcode, 0)
        self.assertEqual(len(collected), _NUM_WORKERS)
        # The helper should return well under its own timeout; we only assert a
        # loose upper bound to avoid flakiness on slow machines.
        self.assertLess(elapsed, _JOIN_TIMEOUT_SECS)
