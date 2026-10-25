"""Hooks that run around each function test that takes an ``env``."""
import contextlib
import inspect

_hooks = []


def add_test_hook(hook):
    """
    Run ``hook(env, test)`` around every function test that takes an
    ``env``; ``test`` is the test function, so a hook can honour markers set
    on it.

    ``hook`` returns a context manager, such as a generator decorated with
    ``contextlib.contextmanager``: it is entered before the test and exited
    after it. Failed assertions and exceptions in the hook fail the test, as
    the test's own would. Hooks run in the order added.

    RLTest re-imports a test file before each of its tests, so a top-level
    function added again with the same module and name replaces the copy
    added before. Any other hook (a lambda, closure, bound method or other
    callable) counts as the same only if it is the same object, so add those
    from a module that is imported once.
    """
    key = _key(hook)
    for i, added in enumerate(_hooks):
        if added is hook or _key(added) == key:
            _hooks[i] = hook
            return
    _hooks.append(hook)


def _key(hook):
    name = getattr(hook, '__qualname__', '')
    if inspect.isfunction(hook) and name.isidentifier():
        return (hook.__module__, name)
    return (id(hook),)


def run_with_hooks(target, env):
    with contextlib.ExitStack() as stack:
        for hook in list(_hooks):
            stack.enter_context(hook(env, target))
        return target(env)
