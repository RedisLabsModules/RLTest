import contextlib

from RLTest import add_test_hook


# Added at import, as a test file would. RLTest re-imports this file before
# each of its tests, so a hook added more than once would run more than once.
@contextlib.contextmanager
def count_calls(env, test):
    calls = env.__dict__.setdefault('_hook_calls', {})
    calls[test.__name__] = calls.get(test.__name__, 0) + 1
    yield


add_test_hook(count_calls)


def test_hook_runs_once_per_test(env):
    env.assertEqual(env._hook_calls.get('test_hook_runs_once_per_test'), 1)


def test_hook_runs_once_per_later_test(env):
    env.assertEqual(env._hook_calls.get('test_hook_runs_once_per_later_test'), 1)
