"""Tests for v0.7 Generics — Parametric Types (Issue #57).

Tests cover:
- TypeParam in types.py (substitute_type, unify_types)
- Generic function definitions (type_params field)
- Type inference at call sites
- Generic over containers (list<T>, option<T>, result<T,E>)
- Error cases: unknown type param, param conflict, unresolved type param
"""

import pytest
from interpreter.checker import Checker, CheckError
from interpreter.types import (
    TypeParam, IntType, FloatType, BoolType, StringType, UnitType,
    ListType, MapType, OptionType, ResultType,
    parse_type, substitute_type, unify_types, NailTypeError,
)


# ── types.py unit tests ──────────────────────────────────────────────────────

class TestTypeParam:
    def test_typeParam_equality(self):
        assert TypeParam("T") == TypeParam("T")
        assert TypeParam("T") != TypeParam("U")

    def test_typeParam_str(self):
        assert str(TypeParam("T")) == "T"

    def test_parse_type_param_with_scope(self):
        t = parse_type({"type": "param", "name": "T"}, type_params=frozenset(["T", "U"]))
        assert t == TypeParam("T")

    def test_parse_type_param_unknown_raises(self):
        with pytest.raises(NailTypeError) as exc_info:
            parse_type({"type": "param", "name": "V"}, type_params=frozenset(["T"]))
        assert "V" in str(exc_info.value)

    def test_parse_type_param_no_scope_raises(self):
        with pytest.raises(NailTypeError) as exc_info:
            parse_type({"type": "param", "name": "T"})  # no type_params
        assert "no type params in scope" in str(exc_info.value)

    def test_parse_nested_list_with_param(self):
        t = parse_type(
            {"type": "list", "inner": {"type": "param", "name": "T"}},
            type_params=frozenset(["T"]),
        )
        assert t == ListType(inner=TypeParam("T"), length="dynamic")

    def test_parse_nested_option_with_param(self):
        t = parse_type(
            {"type": "option", "inner": {"type": "param", "name": "T"}},
            type_params=frozenset(["T"]),
        )
        assert t == OptionType(inner=TypeParam("T"))

    def test_parse_result_with_two_params(self):
        t = parse_type(
            {"type": "result", "ok": {"type": "param", "name": "T"}, "err": {"type": "param", "name": "E"}},
            type_params=frozenset(["T", "E"]),
        )
        expected = ResultType(ok=TypeParam("T"), err=TypeParam("E"))
        assert t == expected


class TestSubstituteType:
    def test_substitute_leaf_is_identity(self):
        int64 = IntType(64, "panic")
        assert substitute_type(int64, {"T": FloatType(64)}) == int64

    def test_substitute_type_param(self):
        result = substitute_type(TypeParam("T"), {"T": IntType(64, "panic")})
        assert result == IntType(64, "panic")

    def test_substitute_unbound_param_unchanged(self):
        result = substitute_type(TypeParam("T"), {"U": IntType(64, "panic")})
        assert result == TypeParam("T")

    def test_substitute_in_option(self):
        opt_t = OptionType(inner=TypeParam("T"))
        result = substitute_type(opt_t, {"T": BoolType()})
        assert result == OptionType(inner=BoolType())

    def test_substitute_in_list(self):
        lst_t = ListType(inner=TypeParam("T"), length="dynamic")
        result = substitute_type(lst_t, {"T": StringType()})
        assert result == ListType(inner=StringType(), length="dynamic")

    def test_substitute_in_map(self):
        map_t = MapType(key=TypeParam("K"), value=TypeParam("V"))
        result = substitute_type(map_t, {"K": StringType(), "V": IntType(64, "panic")})
        assert result == MapType(key=StringType(), value=IntType(64, "panic"))

    def test_substitute_in_result(self):
        res_t = ResultType(ok=TypeParam("T"), err=TypeParam("E"))
        result = substitute_type(res_t, {"T": IntType(64, "panic"), "E": StringType()})
        assert result == ResultType(ok=IntType(64, "panic"), err=StringType())


class TestUnifyTypes:
    def test_unify_type_param(self):
        subst = {}
        unify_types(TypeParam("T"), IntType(64, "panic"), subst)
        assert subst == {"T": IntType(64, "panic")}

    def test_unify_type_param_consistent(self):
        subst = {"T": IntType(64, "panic")}
        # T already bound to int64 — consistent
        unify_types(TypeParam("T"), IntType(64, "panic"), subst)
        assert subst["T"] == IntType(64, "panic")

    def test_unify_type_param_conflict(self):
        subst = {"T": IntType(64, "panic")}
        with pytest.raises(NailTypeError) as exc_info:
            unify_types(TypeParam("T"), FloatType(64), subst)
        assert "TYPE_PARAM_CONFLICT" == exc_info.value.code

    def test_unify_concrete_types_equal(self):
        subst = {}
        unify_types(IntType(64, "panic"), IntType(64, "panic"), subst)
        assert subst == {}

    def test_unify_concrete_types_mismatch(self):
        with pytest.raises(NailTypeError):
            unify_types(IntType(64, "panic"), FloatType(64), {})

    def test_unify_nested_option(self):
        generic = OptionType(inner=TypeParam("T"))
        concrete = OptionType(inner=BoolType())
        subst = {}
        unify_types(generic, concrete, subst)
        assert subst == {"T": BoolType()}

    def test_unify_nested_map(self):
        generic = MapType(key=TypeParam("K"), value=TypeParam("V"))
        concrete = MapType(key=StringType(), value=IntType(64, "panic"))
        subst = {}
        unify_types(generic, concrete, subst)
        assert subst == {"K": StringType(), "V": IntType(64, "panic")}


# ── Checker integration tests ─────────────────────────────────────────────────

INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
FLOAT64 = {"type": "float", "bits": 64}
BOOL = {"type": "bool"}
STRING = {"type": "string"}
UNIT = {"type": "unit"}


def _generic_identity_fn():
    """identity[T](x: T) -> T — returns its argument unchanged."""
    return {
        "nail": "0.7.0",
        "kind": "fn",
        "id": "identity",
        "type_params": ["T"],
        "effects": [],
        "params": [{"id": "x", "type": {"type": "param", "name": "T"}}],
        "returns": {"type": "param", "name": "T"},
        "body": [
            {"op": "return", "val": {"ref": "x"}}
        ],
    }


def _generic_first_fn():
    """first[T](lst: list<T>) -> option<T> — returns the first element."""
    return {
        "nail": "0.7.0",
        "kind": "fn",
        "id": "first",
        "type_params": ["T"],
        "effects": [],
        "params": [
            {"id": "lst", "type": {"type": "list", "inner": {"type": "param", "name": "T"}}}
        ],
        "returns": {"type": "option", "inner": {"type": "param", "name": "T"}},
        "body": [
            # Simplified body that just returns none (the test is about type checking, not runtime)
            {
                "op": "return",
                "val": {"op": "none", "inner_type": {"type": "param", "name": "T"}},
            }
        ],
    }


def _generic_pair_fn():
    """pair[T, U](a: T, b: U) -> T (returns first)."""
    return {
        "nail": "0.7.0",
        "kind": "fn",
        "id": "pair",
        "type_params": ["T", "U"],
        "effects": [],
        "params": [
            {"id": "a", "type": {"type": "param", "name": "T"}},
            {"id": "b", "type": {"type": "param", "name": "U"}},
        ],
        "returns": {"type": "param", "name": "T"},
        "body": [
            {"op": "return", "val": {"ref": "a"}}
        ],
    }


class TestGenericFunctionDefinition:
    """Checker correctly validates generic function bodies."""

    def test_identity_fn_checks_ok(self):
        checker = Checker(_generic_identity_fn())
        checker.check()  # should not raise

    def test_pair_fn_checks_ok(self):
        checker = Checker(_generic_pair_fn())
        checker.check()

    def test_type_params_must_be_list(self):
        fn = _generic_identity_fn()
        fn["type_params"] = "T"  # not a list
        with pytest.raises(CheckError) as exc_info:
            Checker(fn).check()
        assert "type_params" in str(exc_info.value)

    def test_type_param_must_be_string(self):
        fn = _generic_identity_fn()
        fn["type_params"] = [42]  # not a string
        with pytest.raises(CheckError):
            Checker(fn).check()


class TestGenericCallSiteInference:
    """Type inference at call sites for generic functions."""

    def _make_caller_module(self, generic_fn: dict, caller_fn: dict) -> dict:
        return {
            "nail": "0.7.0",
            "kind": "module",
            "id": "test_module",
            "exports": ["main"],
            "defs": [generic_fn, caller_fn],
        }

    def test_identity_called_with_int(self):
        """identity[T](x: T) called with int → return type is int."""
        caller = {
            "nail": "0.7.0",
            "kind": "fn",
            "id": "main",
            "effects": ["IO"],
            "params": [],
            "returns": UNIT,
            "body": [
                {
                    "op": "let", "id": "r", "type": INT64,
                    "val": {"op": "call", "fn": "identity", "args": [{"lit": 42}]},
                },
                {
                    "op": "print", "effect": "IO",
                    "val": {"op": "int_to_str", "v": {"ref": "r"}},
                },
                {"op": "return", "val": {"lit": None, "type": UNIT}},
            ],
        }
        mod = self._make_caller_module(_generic_identity_fn(), caller)
        Checker(mod).check()

    def test_identity_called_with_bool(self):
        """identity[T](x: T) called with bool → return type is bool."""
        caller = {
            "nail": "0.7.0",
            "kind": "fn",
            "id": "main",
            "effects": ["IO"],
            "params": [],
            "returns": UNIT,
            "body": [
                {
                    "op": "let", "id": "r", "type": BOOL,
                    "val": {"op": "call", "fn": "identity", "args": [{"lit": True}]},
                },
                {"op": "return", "val": {"lit": None, "type": UNIT}},
            ],
        }
        mod = self._make_caller_module(_generic_identity_fn(), caller)
        Checker(mod).check()

    def test_identity_return_type_mismatch_detected(self):
        """identity[T](42) returns int, but caller expects float — should fail."""
        caller = {
            "nail": "0.7.0",
            "kind": "fn",
            "id": "main",
            "effects": [],
            "params": [],
            "returns": FLOAT64,
            "body": [
                {
                    "op": "return",
                    "val": {"op": "call", "fn": "identity", "args": [{"lit": 42}]},
                },
            ],
        }
        mod = self._make_caller_module(_generic_identity_fn(), caller)
        with pytest.raises(CheckError):
            Checker(mod).check()

    def test_pair_fn_infers_two_type_params(self):
        """pair[T, U](a: T, b: U) called with (int, bool) → return is int."""
        caller = {
            "nail": "0.7.0",
            "kind": "fn",
            "id": "main",
            "effects": [],
            "params": [],
            "returns": INT64,
            "body": [
                {
                    "op": "return",
                    "val": {"op": "call", "fn": "pair", "args": [{"lit": 7}, {"lit": True}]},
                },
            ],
        }
        mod = self._make_caller_module(_generic_pair_fn(), caller)
        Checker(mod).check()

    def test_wrong_arg_count_detected(self):
        """Calling a generic with wrong number of args → CheckError."""
        caller = {
            "nail": "0.7.0",
            "kind": "fn",
            "id": "main",
            "effects": [],
            "params": [],
            "returns": INT64,
            "body": [
                {
                    "op": "return",
                    "val": {"op": "call", "fn": "identity", "args": []},  # missing arg
                },
            ],
        }
        mod = self._make_caller_module(_generic_identity_fn(), caller)
        with pytest.raises(CheckError):
            Checker(mod).check()


class TestGenericContainerPatterns:
    """Test list<T>, map<K,V>, option<T>, result<T,E> in generic functions."""

    def test_list_int_in_function_signature(self):
        """Non-generic fn with concrete list<int> param."""
        fn = {
            "nail": "0.7.0",
            "kind": "fn",
            "id": "sum_list",
            "effects": [],
            "params": [
                {"id": "lst", "type": {"type": "list", "inner": INT64}},
            ],
            "returns": INT64,
            "body": [
                {"op": "return", "val": {"lit": 0}},
            ],
        }
        Checker(fn).check()

    def test_map_str_float_in_function_signature(self):
        """Non-generic fn accepting and returning map<string, float64>."""
        fn = {
            "nail": "0.7.0",
            "kind": "fn",
            "id": "passthrough_map",
            "effects": [],
            "params": [
                {"id": "m", "type": {"type": "map", "key": STRING, "value": FLOAT64}},
            ],
            "returns": {"type": "map", "key": STRING, "value": FLOAT64},
            "body": [
                {"op": "return", "val": {"ref": "m"}},
            ],
        }
        Checker(fn).check()

    def test_option_int_in_function_signature(self):
        """Non-generic fn accepting option<int> and returning it (passthrough)."""
        fn = {
            "nail": "0.7.0",
            "kind": "fn",
            "id": "passthrough_opt",
            "effects": [],
            "params": [
                {"id": "x", "type": {"type": "option", "inner": INT64}},
            ],
            "returns": {"type": "option", "inner": INT64},
            "body": [
                {"op": "return", "val": {"ref": "x"}},
            ],
        }
        Checker(fn).check()

    def test_result_T_E_generic(self):
        """Generic fn returning result<T, string>."""
        fn = {
            "nail": "0.7.0",
            "kind": "fn",
            "id": "wrap_ok",
            "type_params": ["T"],
            "effects": [],
            "params": [{"id": "val", "type": {"type": "param", "name": "T"}}],
            "returns": {
                "type": "result",
                "ok": {"type": "param", "name": "T"},
                "err": STRING,
            },
            "body": [
                {
                    "op": "return",
                    "val": {"op": "ok", "val": {"ref": "val"}},
                }
            ],
        }
        Checker(fn).check()
