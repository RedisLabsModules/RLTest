"""Declarative environment requirements for RLTest tests.

A test can declare the Env parameters it needs *before* it runs, so the runner
can construct the env on its behalf and inject it as a parameter. Two benefits:

1. Single source of truth: the declared spec is exactly the shape of the env
   that gets injected, eliminating drift between a "what env I need" hint and
   the in-body ``Env(...)`` call.
2. Future schedulers can read each test's spec at discovery time and route
   same-spec tests adjacently to maximize Redis-instance reuse via
   ``Env.compareEnvs`` (env.py:191).

A spec can be declared at two places, with this precedence (most specific wins):

    @env_spec(...) on the function/class   >   module-level ENV_SPEC

The decorator works on both functions and classes, so users only need to
learn one mechanism.

Example::

    # module-level default for every test in the file
    ENV_SPEC = dict(moduleArgs='DEFAULT_DIALECT 2')

    @env_spec(shardsCount=3)
    def test_cluster(env):
        env.expect('FT.SEARCH', 'idx', '*').noError()

    @env_spec(moduleArgs='WORKERS 1')
    class TestWorkers:
        def __init__(self, env):
            self.env = env

        def test_x(self):
            self.env.expect(...)
"""
import inspect

from RLTest.env import Env

_SPEC_KEYS = frozenset(Env.EnvCompareParams)
_ATTR = '_rltest_env_spec'


def _looks_like_class_method(target):
    """Heuristic: is ``target`` a function defined inside a class body?

    At decoration time the function isn't bound to the class yet, but Python
    has already populated ``__qualname__`` with the enclosing scope. Examples:

        f                  -> top-level function (not a method)
        outer.<locals>.g   -> nested function (not a method)
        C.m                -> class method
        outer.<locals>.C.m -> class defined inside a function; still a method

    The rule: take whatever follows the last ``<locals>.`` (the path *inside*
    the innermost enclosing function scope, or the whole qualname if there's
    no ``<locals>``). If that trailing segment contains a dot, the target is
    qualified by a class name and is therefore a method.
    """
    qn = getattr(target, '__qualname__', '')
    if not qn:
        return False
    trailing = qn.rsplit('<locals>.', 1)[-1]
    return '.' in trailing


def env_spec(**kwargs):
    """Declare the env requirements of a test function or test class.

    Allowed keys are the entries of ``Env.EnvCompareParams``; unknown keys
    raise ``ValueError`` at decoration time so typos can't silently disable
    spec-driven behaviour.

    Applying ``@env_spec`` to a method inside a class is rejected: class tests
    share a single env across all their methods (that's the whole point of a
    class test). If one method needs a different env, lift it out into a
    standalone function or its own class. To declare a class-wide spec, set
    ``env_spec = dict(...)`` as a class attribute, or decorate the class
    itself.
    """
    unknown = set(kwargs) - _SPEC_KEYS
    if unknown:
        raise ValueError(
            "unknown env_spec keys: {}; allowed keys are: {}".format(
                sorted(unknown), sorted(_SPEC_KEYS)
            )
        )

    spec = dict(kwargs)

    def deco(target):
        if inspect.isfunction(target) and _looks_like_class_method(target):
            raise TypeError(
                "@env_spec is not supported on class methods (got {}). "
                "Class tests share one env across all methods; set "
                "`env_spec = dict(...)` as a class attribute, or decorate the "
                "class itself, or move the test out of the class.".format(
                    target.__qualname__
                )
            )
        setattr(target, _ATTR, spec)
        return target

    return deco


def resolve_spec(test_func=None, owner_class=None, module=None):
    """Resolve the effective env spec for a test.

    Merges contributions from module global, class attribute, and per-function
    decorator (in that order, so each layer overrides keys from the previous).

    Returns a dict if any layer declared a spec, otherwise ``None``. Callers
    use the ``None`` return as a sentinel for "legacy test, no declared spec"
    and fall back to existing behaviour (construct ``Env`` with defaults or
    let the test body do it).
    """
    declared = False
    spec = {}

    if module is not None:
        m = getattr(module, 'ENV_SPEC', None)
        if m is not None:
            declared = True
            spec.update(m)

    if owner_class is not None:
        # ``@env_spec`` decoration on the class itself writes to ``_ATTR``.
        c = getattr(owner_class, _ATTR, None)
        if c is not None:
            declared = True
            spec.update(c)

    if test_func is not None:
        f = getattr(test_func, _ATTR, None)
        if f is not None:
            declared = True
            spec.update(f)

    return spec if declared else None


def spec_key(spec):
    """Canonical hashable key for spec equivalence.

    Two tests with the same ``spec_key`` produce envs that satisfy
    ``Env.compareEnvs``, so they're eligible to share a Redis instance via
    RLTest's opportunistic-reuse path (env.py:262). Future schedulers can use
    this as a grouping key.
    """
    if spec is None:
        return ()
    return tuple(sorted(spec.items()))
