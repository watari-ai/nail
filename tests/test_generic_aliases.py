"""Tests for generic type aliases — module-level types with type_params (Issue #62, #71).

Covers:
- Basic generic alias definition and instantiation
- Multi-param generics (Pair[A, B])
- Nested generic aliases
- Generic alias in function signatures
- Error cases: arity mismatch, unknown param
- Generic aliases imported from another module (Issue #71)
"""

import pytest
from interpreter.checker import Checker, CheckError


def check(spec):
    c = Checker(spec)
    c.check()
    return c


INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
STRING = {"type": "string"}
BOOL = {"type": "bool"}
UNIT = {"type": "unit"}


def make_fn(id: str, params: list, returns: dict, body: list, effects: list = None) -> dict:
    return {
        "nail": "0.7.1",
        "kind": "fn",
        "id": id,
        "effects": effects or [],
        "params": params,
        "returns": returns,
        "body": body,
    }


def make_module(types: dict, fns: list = None) -> dict:
    m = {
        "nail": "0.7.1",
        "kind": "module",
        "id": "test",
        "exports": [f["id"] for f in (fns or [])],
        "types": types,
        "defs": fns or [],
    }
    return m


# ── Basic single-param alias ──────────────────────────────────────────────────

class TestBasicGenericAlias:

    def test_list_wrapper_alias(self):
        """type NumList[T] = list<T>; fn f(xs: NumList<int>) -> NumList<int>"""
        mod = make_module(
            types={
                "NumList": {
                    "type_params": ["T"],
                    "type": "list",
                    "inner": {"type": "param", "name": "T"},
                }
            },
            fns=[make_fn(
                "f",
                params=[{"id": "xs", "type": {"type": "alias", "name": "NumList", "args": [INT64]}}],
                effects=[],
                returns={"type": "alias", "name": "NumList", "args": [INT64]},
                body=[{"op": "return", "val": {"ref": "xs"}}],
            )]
        )
        check(mod)  # Should not raise

    def test_option_wrapper_alias(self):
        """type Maybe[T] = option<T>; fn f() -> Maybe<string>"""
        mod = make_module(
            types={
                "Maybe": {
                    "type_params": ["T"],
                    "type": "option",
                    "inner": {"type": "param", "name": "T"},
                }
            },
            fns=[make_fn(
                "f", params=[], effects=[],
                returns={"type": "alias", "name": "Maybe", "args": [STRING]},
                body=[{"op": "return", "val": {"lit": None, "type": {"type": "option", "inner": STRING}}}],
            )]
        )
        check(mod)  # Should not raise

    def test_non_generic_alias_still_works(self):
        """Non-generic aliases are unaffected."""
        mod = make_module(
            types={"UserId": {"type": "int", "bits": 64, "overflow": "panic"}},
            fns=[make_fn(
                "f",
                params=[{"id": "x", "type": {"type": "alias", "name": "UserId"}}],
                returns={"type": "alias", "name": "UserId"},
                effects=[],
                body=[{"op": "return", "val": {"ref": "x"}}],
            )]
        )
        check(mod)


# ── Two-param alias ───────────────────────────────────────────────────────────

class TestTwoParamAlias:

    def test_pair_alias_as_param(self):
        """type Pair[A, B] = map<A, B>; use as param type."""
        mod = make_module(
            types={
                "Pair": {
                    "type_params": ["A", "B"],
                    "type": "map",
                    "key": {"type": "param", "name": "A"},
                    "value": {"type": "param", "name": "B"},
                }
            },
            fns=[make_fn(
                "lookup",
                params=[{
                    "id": "m",
                    "type": {
                        "type": "alias",
                        "name": "Pair",
                        "args": [STRING, INT64],
                    }
                }],
                returns=INT64,
                effects=[],
                body=[{"op": "return", "val": {"lit": 0, "type": INT64}}],
            )]
        )
        check(mod)

    def test_pair_alias_as_return(self):
        """Generic alias as return type — fn accepts and passes through a Pair."""
        mod = make_module(
            types={
                "Pair": {
                    "type_params": ["A", "B"],
                    "type": "map",
                    "key": {"type": "param", "name": "A"},
                    "value": {"type": "param", "name": "B"},
                }
            },
            fns=[make_fn(
                "passthrough",
                params=[{"id": "p", "type": {
                    "type": "alias", "name": "Pair", "args": [STRING, BOOL],
                }}],
                returns={
                    "type": "alias", "name": "Pair", "args": [STRING, BOOL],
                },
                effects=[],
                body=[{"op": "return", "val": {"ref": "p"}}],
            )]
        )
        check(mod)


# ── Mixed generic + non-generic aliases ──────────────────────────────────────

class TestMixedAliases:

    def test_generic_and_non_generic_coexist(self):
        """A module can have both generic and plain aliases."""
        mod = make_module(
            types={
                "Name": {"type": "string"},
                "Box": {
                    "type_params": ["T"],
                    "type": "option",
                    "inner": {"type": "param", "name": "T"},
                },
            },
            fns=[make_fn(
                "greet",
                params=[{"id": "n", "type": {"type": "alias", "name": "Name"}}],
                returns={"type": "alias", "name": "Box", "args": [STRING]},
                effects=[],
                body=[{"op": "return", "val": {"lit": None, "type": {"type": "option", "inner": STRING}}}],
            )]
        )
        check(mod)

    def test_generic_alias_multiple_instantiations(self):
        """Same generic alias instantiated with different types in two fns."""
        mod = make_module(
            types={
                "Bag": {
                    "type_params": ["T"],
                    "type": "list",
                    "inner": {"type": "param", "name": "T"},
                }
            },
            fns=[
                make_fn(
                    "int_bag",
                    params=[{"id": "xs", "type": {"type": "alias", "name": "Bag", "args": [INT64]}}],
                    returns={"type": "alias", "name": "Bag", "args": [INT64]},
                    effects=[],
                    body=[{"op": "return", "val": {"ref": "xs"}}],
                ),
                make_fn(
                    "str_bag",
                    params=[{"id": "xs", "type": {"type": "alias", "name": "Bag", "args": [STRING]}}],
                    returns={"type": "alias", "name": "Bag", "args": [STRING]},
                    effects=[],
                    body=[{"op": "return", "val": {"ref": "xs"}}],
                ),
            ]
        )
        check(mod)


# ── Error cases ───────────────────────────────────────────────────────────────

class TestGenericAliasErrors:

    def test_missing_args_for_generic_alias(self):
        """Instantiating a generic alias without args raises an error."""
        mod = make_module(
            types={
                "Box": {
                    "type_params": ["T"],
                    "type": "option",
                    "inner": {"type": "param", "name": "T"},
                }
            },
            fns=[make_fn(
                "f", params=[],
                returns={"type": "alias", "name": "Box"},  # no args!
                effects=[],
                body=[{"op": "return", "val": {"lit": None, "type": {"type": "option", "inner": STRING}}}],
            )]
        )
        with pytest.raises(CheckError, match="GENERIC_ALIAS_ARITY|requires.*type argument"):
            check(mod)

    def test_too_few_args(self):
        """Too few type args for a 2-param generic alias."""
        mod = make_module(
            types={
                "Pair": {
                    "type_params": ["A", "B"],
                    "type": "map",
                    "key": {"type": "param", "name": "A"},
                    "value": {"type": "param", "name": "B"},
                }
            },
            fns=[make_fn(
                "f", params=[],
                returns={
                    "type": "alias", "name": "Pair",
                    "args": [STRING],  # only 1 arg, needs 2
                },
                effects=[],
                body=[{"op": "return", "val": {"lit": {}, "type": {"type": "map", "key": STRING, "value": STRING}}}],
            )]
        )
        with pytest.raises(CheckError, match="GENERIC_ALIAS_ARITY|requires.*type argument"):
            check(mod)

    def test_too_many_args(self):
        """Too many type args raises an error."""
        mod = make_module(
            types={
                "Box": {
                    "type_params": ["T"],
                    "type": "option",
                    "inner": {"type": "param", "name": "T"},
                }
            },
            fns=[make_fn(
                "f", params=[],
                returns={
                    "type": "alias", "name": "Box",
                    "args": [STRING, INT64],  # 2 args, needs 1
                },
                effects=[],
                body=[{"op": "return", "val": {"lit": None, "type": {"type": "option", "inner": STRING}}}],
            )]
        )
        with pytest.raises(CheckError, match="GENERIC_ALIAS_ARITY|requires.*type argument"):
            check(mod)

    def test_args_on_non_generic_alias_ignored(self):
        """Providing args on a non-generic alias: spurious args silently ignored."""
        # Non-generic aliases ignore the 'args' field since they have no type_params.
        mod = make_module(
            types={"UserId": INT64},
            fns=[make_fn(
                "f", params=[],
                returns={
                    "type": "alias", "name": "UserId",
                    "args": [STRING],   # spurious args on a non-generic alias
                },
                effects=[],
                body=[{"op": "return", "val": {"lit": 0, "type": INT64}}],
            )]
        )
        check(mod)  # Should not raise


# ── Generic aliases via module imports (Issue #71) ────────────────────────────

def _make_generic_lib_module():
    """A library module that exports generic type aliases."""
    return {
        "nail": "0.7.1",
        "kind": "module",
        "id": "generic_lib",
        "exports": ["wrap"],
        "types": {
            "Box": {
                "type_params": ["T"],
                "type": "option",
                "inner": {"type": "param", "name": "T"},
            },
            "Pair": {
                "type_params": ["A", "B"],
                "type": "map",
                "key": {"type": "param", "name": "A"},
                "value": {"type": "param", "name": "B"},
            },
            # Non-generic alias in same module — must still be eagerly resolved
            "Name": {"type": "string"},
        },
        "defs": [
            {
                "nail": "0.7.1",
                "kind": "fn",
                "id": "wrap",
                "effects": [],
                "params": [{"id": "x", "type": INT64}],
                "returns": {"type": "option", "inner": INT64},
                "body": [
                    {
                        "op": "return",
                        "val": {"lit": None, "type": {"type": "option", "inner": INT64}},
                    }
                ],
            }
        ],
    }


class TestImportedGenericAliases:
    """Issue #71: _process_imports() must skip eager resolution for generic aliases.

    Before the fix, importing a module that contained a generic alias (one with
    ``type_params``) caused _resolve_alias_spec() to be called without the
    required ``type_args``, resulting in a spurious GENERIC_ALIAS_ARITY error
    at import time rather than at instantiation sites.
    """

    def _check_with_lib(self, caller_spec):
        """Run checker with generic_lib pre-loaded as an external module."""
        c = Checker(caller_spec, modules={"generic_lib": _make_generic_lib_module()})
        c.check()
        return c

    def test_import_module_with_generic_alias_does_not_crash(self):
        """Importing a module that has a generic alias should not raise at import time."""
        caller = {
            "nail": "0.7.1",
            "kind": "module",
            "id": "caller",
            "imports": [{"module": "generic_lib", "fns": ["wrap"]}],
            "exports": ["main"],
            "defs": [
                make_fn(
                    "main",
                    params=[],
                    returns={"type": "unit"},
                    effects=[],
                    body=[{"op": "return", "val": {"lit": None, "type": {"type": "unit"}}}],
                )
            ],
        }
        self._check_with_lib(caller)  # Must not raise

    def test_import_module_with_multiple_generic_aliases_does_not_crash(self):
        """Importing a module with multiple generic aliases (1-param and 2-param) should not raise."""
        # This specifically tests Issue #71: before the fix, _process_imports() called
        # _resolve_alias_spec() for every alias including generic ones, which crashed
        # because generic aliases require type_args at instantiation time.
        caller = {
            "nail": "0.7.1",
            "kind": "module",
            "id": "caller",
            "imports": [{"module": "generic_lib", "fns": ["wrap"]}],
            "exports": ["main"],
            "defs": [
                make_fn(
                    "main",
                    params=[{"id": "n", "type": INT64}],
                    returns={"type": "option", "inner": INT64},
                    effects=[],
                    body=[
                        {
                            "op": "return",
                            "val": {
                                "op": "call",
                                "fn": "wrap",
                                "module": "generic_lib",
                                "args": [{"ref": "n"}],
                            },
                        }
                    ],
                )
            ],
        }
        self._check_with_lib(caller)  # Must not raise (regression for Issue #71)

    def test_imported_module_non_generic_alias_still_eagerly_resolved(self):
        """Non-generic aliases in an imported module are still eagerly resolved (cache populated)."""
        caller = {
            "nail": "0.7.1",
            "kind": "module",
            "id": "caller",
            "imports": [{"module": "generic_lib", "fns": ["wrap"]}],
            "exports": [],
            "defs": [],
        }
        c = self._check_with_lib(caller)
        # "Name" is a non-generic alias — it must have been resolved into the cache
        assert "Name" in c._module_alias_spec_cache.get("generic_lib", {}), (
            "Non-generic alias 'Name' should be eagerly resolved into the module alias spec cache"
        )

    def test_imported_module_generic_alias_skipped_in_cache(self):
        """Generic aliases from an imported module are NOT in the eager-resolve cache."""
        caller = {
            "nail": "0.7.1",
            "kind": "module",
            "id": "caller",
            "imports": [{"module": "generic_lib", "fns": ["wrap"]}],
            "exports": [],
            "defs": [],
        }
        c = self._check_with_lib(caller)
        cache = c._module_alias_spec_cache.get("generic_lib", {})
        assert "Box" not in cache, (
            "Generic alias 'Box' should be skipped (not eagerly resolved) in the import cache"
        )
        assert "Pair" not in cache, (
            "Generic alias 'Pair' should be skipped (not eagerly resolved) in the import cache"
        )
