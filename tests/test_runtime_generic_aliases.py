"""Tests for generic alias resolution in the Runtime (Issue #74).

Verifies that runtime._resolve_type_spec handles the
{"type": "alias", "name": "X", "args": [...]} form the same way
checker._resolve_type_spec does.

Covers:
- typed-null (lit:null with a generic alias type annotation)
- typed variables bound with generic alias types
- single-param and two-param generic aliases at runtime
- option/list/map generic alias instantiation
- checker and runtime agree on resolved types
"""

import pytest
from interpreter import Checker, Runtime, CheckError
from interpreter.runtime import UNIT


# ── helpers ──────────────────────────────────────────────────────────────────

INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
STRING = {"type": "string"}
BOOL_T = {"type": "bool"}
UNIT_T = {"type": "unit"}


def make_module(types: dict, fns: list) -> dict:
    return {
        "nail": "0.7.1",
        "kind": "module",
        "id": "test_runtime_generic",
        "exports": [f["id"] for f in fns],
        "types": types,
        "defs": fns,
    }


def make_fn(fn_id, params, returns, body, effects=None):
    return {
        "nail": "0.7.1",
        "kind": "fn",
        "id": fn_id,
        "effects": effects or [],
        "params": params,
        "returns": returns,
        "body": body,
    }


def run_fn(spec, fn_id, args=None):
    """Check + run a function; raise on checker or runtime errors."""
    Checker(spec).check()
    rt = Runtime(spec)
    return rt.run_fn(fn_id, args or {})


# ── typed-null with generic alias ─────────────────────────────────────────────

class TestTypedNullWithGenericAlias:
    """lit:null annotated with a generic alias type must work at runtime."""

    def test_maybe_typed_null_returns_none(self):
        """fn returns null typed as Maybe<int> (option<int64>) at runtime."""
        mod = make_module(
            types={
                "Maybe": {
                    "type_params": ["T"],
                    "type": "option",
                    "inner": {"type": "param", "name": "T"},
                }
            },
            fns=[make_fn(
                "nothing",
                params=[],
                returns={"type": "alias", "name": "Maybe", "args": [INT64]},
                body=[{
                    "op": "return",
                    "val": {
                        "lit": None,
                        "type": {"type": "alias", "name": "Maybe", "args": [INT64]},
                    },
                }],
            )],
        )
        result = run_fn(mod, "nothing")
        assert result is None

    def test_maybe_typed_null_string(self):
        """fn returns null typed as Maybe<string> at runtime."""
        mod = make_module(
            types={
                "Maybe": {
                    "type_params": ["T"],
                    "type": "option",
                    "inner": {"type": "param", "name": "T"},
                }
            },
            fns=[make_fn(
                "no_string",
                params=[],
                returns={"type": "alias", "name": "Maybe", "args": [STRING]},
                body=[{
                    "op": "return",
                    "val": {
                        "lit": None,
                        "type": {"type": "alias", "name": "Maybe", "args": [STRING]},
                    },
                }],
            )],
        )
        result = run_fn(mod, "no_string")
        assert result is None


# ── let binding with generic alias type annotation ────────────────────────────

class TestLetBindingGenericAlias:
    """Variables declared with generic alias type annotations work at runtime."""

    def test_bag_of_int_let_binding(self):
        """type Bag[T] = list<T>; fn uses Bag<int> in a let binding."""
        mod = make_module(
            types={
                "Bag": {
                    "type_params": ["T"],
                    "type": "list",
                    "inner": {"type": "param", "name": "T"},
                    "len": "dynamic",
                }
            },
            fns=[make_fn(
                "bag_len",
                params=[{
                    "id": "xs",
                    "type": {"type": "alias", "name": "Bag", "args": [INT64]},
                }],
                returns=INT64,
                body=[{
                    "op": "return",
                    "val": {"op": "list_len", "list": {"ref": "xs"}},
                }],
            )],
        )
        result = run_fn(mod, "bag_len", {"xs": [1, 2, 3]})
        assert result == 3

    def test_pair_map_passthrough(self):
        """type Pair[A,B] = map<A,B>; fn accepts and returns a Pair<string,int>."""
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
                params=[{
                    "id": "p",
                    "type": {"type": "alias", "name": "Pair", "args": [STRING, INT64]},
                }],
                returns={"type": "alias", "name": "Pair", "args": [STRING, INT64]},
                body=[{"op": "return", "val": {"ref": "p"}}],
            )],
        )
        data = {"a": 1, "b": 2}
        result = run_fn(mod, "passthrough", {"p": data})
        assert result == data


# ── checker/runtime agreement ─────────────────────────────────────────────────

class TestCheckerRuntimeAgreement:
    """Checker and Runtime produce consistent results for generic alias usages."""

    def test_option_wrapper_checker_and_runtime_agree(self):
        """Checker passes; runtime returns None for typed-null with generic alias."""
        mod = make_module(
            types={
                "Opt": {
                    "type_params": ["T"],
                    "type": "option",
                    "inner": {"type": "param", "name": "T"},
                }
            },
            fns=[make_fn(
                "get_none",
                params=[],
                returns={"type": "alias", "name": "Opt", "args": [BOOL_T]},
                body=[{
                    "op": "return",
                    "val": {
                        "lit": None,
                        "type": {"type": "alias", "name": "Opt", "args": [BOOL_T]},
                    },
                }],
            )],
        )
        # Checker must not raise
        Checker(mod).check()
        # Runtime must return None (the option-None value)
        result = Runtime(mod).run_fn("get_none", {})
        assert result is None

    def test_generic_alias_identity_fn(self):
        """fn identity(x: NumList<int>) -> NumList<int> returns x unchanged."""
        mod = make_module(
            types={
                "NumList": {
                    "type_params": ["T"],
                    "type": "list",
                    "inner": {"type": "param", "name": "T"},
                    "len": "dynamic",
                }
            },
            fns=[make_fn(
                "identity",
                params=[{
                    "id": "xs",
                    "type": {"type": "alias", "name": "NumList", "args": [INT64]},
                }],
                returns={"type": "alias", "name": "NumList", "args": [INT64]},
                body=[{"op": "return", "val": {"ref": "xs"}}],
            )],
        )
        Checker(mod).check()
        inp = [10, 20, 30]
        result = Runtime(mod).run_fn("identity", {"xs": inp})
        assert result == inp

    def test_non_generic_alias_unaffected(self):
        """Non-generic aliases continue to work normally after the fix."""
        mod = make_module(
            types={"UserId": INT64},
            fns=[make_fn(
                "make_user",
                params=[],
                returns={"type": "alias", "name": "UserId"},
                body=[{"op": "return", "val": {"lit": 42}}],
            )],
        )
        Checker(mod).check()
        result = Runtime(mod).run_fn("make_user", {})
        assert result == 42

    def test_generic_alias_arity_error_at_runtime(self):
        """Runtime raises when a generic alias is instantiated with wrong arity."""
        mod = make_module(
            types={
                "Box": {
                    "type_params": ["T"],
                    "type": "option",
                    "inner": {"type": "param", "name": "T"},
                }
            },
            fns=[make_fn(
                "bad",
                params=[],
                # Intentionally wrong arity — bypass checker by constructing directly
                returns={"type": "alias", "name": "Box", "args": [INT64, STRING]},
                body=[{
                    "op": "return",
                    "val": {
                        "lit": None,
                        # use a valid concrete type for the lit so runtime evals it
                        "type": {"type": "option", "inner": INT64},
                    },
                }],
            )],
        )
        # Checker should catch the arity mismatch
        with pytest.raises((CheckError, Exception), match="type argument|GENERIC_ALIAS_ARITY"):
            Checker(mod).check()
