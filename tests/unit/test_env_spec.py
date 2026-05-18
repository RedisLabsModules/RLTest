"""Unit tests for the declarative env_spec mechanism."""
import pytest

from RLTest.env_spec import env_spec, resolve_spec, spec_key, _ATTR


# -- env_spec decorator -------------------------------------------------------

def test_decorator_accepts_allowed_keys():
    @env_spec(moduleArgs='FOO 1', shardsCount=3)
    def t(env):
        pass

    assert getattr(t, _ATTR) == {'moduleArgs': 'FOO 1', 'shardsCount': 3}


def test_decorator_rejects_unknown_keys():
    with pytest.raises(ValueError, match='unknown env_spec keys'):
        @env_spec(badkey=1)
        def t(env):
            pass


def test_decorator_rejects_class_methods():
    with pytest.raises(TypeError, match='not supported on class methods'):
        class C:
            @env_spec(moduleArgs='X')
            def test_x(self):
                pass


def test_decorator_allows_nested_functions():
    # Inner functions inside a function (not a class) should be fine; they
    # appear in the qualname as ``outer.<locals>.inner``.
    def outer():
        @env_spec(moduleArgs='X')
        def inner(env):
            pass
        return inner

    assert getattr(outer(), _ATTR) == {'moduleArgs': 'X'}


def test_decorator_on_class_is_allowed():
    # Decorating the class itself (rather than one of its methods) is the
    # supported alternative to a class attribute. The spec lands on the class.
    @env_spec(moduleArgs='X')
    class C:
        def __init__(self, env):
            self.env = env

    assert getattr(C, _ATTR) == {'moduleArgs': 'X'}


# -- resolve_spec precedence --------------------------------------------------

def test_resolve_returns_none_when_nothing_declared():
    def f(env):
        pass

    assert resolve_spec(test_func=f, module=None, owner_class=None) is None


def test_resolve_uses_module_global():
    class FakeModule:
        ENV_SPEC = {'moduleArgs': 'FROM_MODULE'}

    def f(env):
        pass

    assert resolve_spec(test_func=f, module=FakeModule()) == {'moduleArgs': 'FROM_MODULE'}


def test_resolve_function_overrides_class_overrides_module():
    class FakeModule:
        ENV_SPEC = {'moduleArgs': 'FROM_MODULE', 'shardsCount': 1}

    @env_spec(moduleArgs='FROM_CLASS', protocol=3)
    class FakeOwner:
        pass

    @env_spec(moduleArgs='FROM_FUNC')
    def f(env):
        pass

    resolved = resolve_spec(test_func=f, owner_class=FakeOwner, module=FakeModule())
    assert resolved == {
        'moduleArgs': 'FROM_FUNC',  # func wins for shared key
        'shardsCount': 1,           # only module declared this
        'protocol': 3,              # only class declared this
    }


def test_resolve_picks_up_class_decoration():
    @env_spec(moduleArgs='FROM_CLASS_DECO')
    class C:
        pass

    assert resolve_spec(owner_class=C) == {'moduleArgs': 'FROM_CLASS_DECO'}


def test_resolve_ignores_plain_class_attribute():
    # ``env_spec = {...}`` as a plain attribute is NOT recognised — only the
    # decorator ``@env_spec(...)`` is. This keeps the API surface small.
    class C:
        env_spec = {'moduleArgs': 'IGNORED'}

    assert resolve_spec(owner_class=C) is None


def test_resolve_empty_spec_is_distinct_from_undeclared():
    # An explicit empty spec means "declared, no overrides"; it should produce
    # an empty dict, not None. This lets callers treat any non-None as opt-in.
    class FakeModule:
        ENV_SPEC = {}

    assert resolve_spec(module=FakeModule()) == {}


# -- spec_key -----------------------------------------------------------------

def test_spec_key_is_order_independent():
    a = {'moduleArgs': 'X', 'shardsCount': 3}
    b = {'shardsCount': 3, 'moduleArgs': 'X'}
    assert spec_key(a) == spec_key(b)


def test_spec_key_distinguishes_specs():
    a = {'moduleArgs': 'X'}
    b = {'moduleArgs': 'Y'}
    assert spec_key(a) != spec_key(b)


def test_spec_key_none_is_empty_tuple():
    assert spec_key(None) == ()
