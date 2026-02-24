#!/usr/bin/env python3
"""
NAIL Type Aliases Test Suite — v0.4

Covers the `types` dict at module level (SPEC.md §3 "Type Aliases (v0.4)"):
  - Basic alias definition and usage
  - Alias-of-alias (transitivity)
  - Aliases in nested types (option, list, map, result)
  - Circular alias detection (multiple scenarios)
  - Unknown alias reference detection
  - Alias in return type
  - Multiple functions sharing an alias
  - Runtime: alias resolves to concrete type at execution time

Run: python3 -m pytest tests/test_type_aliases.py -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter import Checker, Runtime, CheckError, NailTypeError
from interpreter.runtime import UNIT


# ── helpers ──────────────────────────────────────────────────────────────────

INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
INT32 = {"type": "int", "bits": 32, "overflow": "panic"}
BOOL_T = {"type": "bool"}
STR_T = {"type": "string"}
UNIT_T = {"type": "unit"}


def fn_spec(fn_id, params, returns, body, effects=None):
    return {
        "nail": "0.1.0",
        "kind": "fn",
        "id": fn_id,
        "effects": effects or [],
        "params": params,
        "returns": returns,
        "body": body,
    }


def module_spec(module_id, defs, exports=None, types=None):
    spec = {
        "nail": "0.1.0",
        "kind": "module",
        "id": module_id,
        "exports": exports or [],
        "defs": defs,
    }
    if types is not None:
        spec["types"] = types
    return spec


def run_spec(spec: dict, args: dict | None = None, call_fn: str | None = None):
    """Check + run a spec dict, return result."""
    Checker(spec).check()
    rt = Runtime(spec)
    if call_fn:
        return rt.run_fn(call_fn, args or {})
    return rt.run(args)


# ── Test cases ────────────────────────────────────────────────────────────────


class TestTypeAliasBasics(unittest.TestCase):
    """Basic alias definition and single-level usage."""

    def test_alias_used_as_param_type(self):
        """Alias resolves correctly when used as a parameter type."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "double",
                    [{"id": "n", "type": {"type": "alias", "name": "Count"}}],
                    INT64,
                    [{"op": "return", "val": {"op": "+", "l": {"ref": "n"}, "r": {"ref": "n"}}}],
                ),
            ],
            exports=["double"],
            types={"Count": INT64},
        )
        result = run_spec(spec, args={"n": 21}, call_fn="double")
        self.assertEqual(result, 42)

    def test_alias_used_as_return_type(self):
        """Alias resolves correctly when used as a return type."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "get_id",
                    [],
                    {"type": "alias", "name": "UserId"},
                    [{"op": "return", "val": {"lit": 99}}],
                ),
            ],
            exports=["get_id"],
            types={"UserId": INT64},
        )
        result = run_spec(spec, call_fn="get_id")
        self.assertEqual(result, 99)

    def test_alias_in_let_binding_type_annotation(self):
        """Alias can annotate a let binding's declared type."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "f",
                    [],
                    INT64,
                    [
                        {
                            "op": "let",
                            "id": "x",
                            "type": {"type": "alias", "name": "Score"},
                            "val": {"lit": 100},
                        },
                        {"op": "return", "val": {"ref": "x"}},
                    ],
                ),
            ],
            exports=["f"],
            types={"Score": INT64},
        )
        result = run_spec(spec, call_fn="f")
        self.assertEqual(result, 100)

    def test_string_alias(self):
        """Alias of string type works correctly."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "greet",
                    [{"id": "name", "type": {"type": "alias", "name": "Name"}}],
                    {"type": "alias", "name": "Name"},
                    [{"op": "return", "val": {"ref": "name"}}],
                ),
            ],
            exports=["greet"],
            types={"Name": STR_T},
        )
        result = run_spec(spec, args={"name": "Alice"}, call_fn="greet")
        self.assertEqual(result, "Alice")

    def test_bool_alias(self):
        """Alias of bool type works correctly."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "negate",
                    [{"id": "flag", "type": {"type": "alias", "name": "Flag"}}],
                    BOOL_T,
                    [{"op": "return", "val": {"op": "not", "v": {"ref": "flag"}}}],
                ),
            ],
            exports=["negate"],
            types={"Flag": BOOL_T},
        )
        result = run_spec(spec, args={"flag": True}, call_fn="negate")
        self.assertEqual(result, False)


class TestTypeAliasTransitivity(unittest.TestCase):
    """Alias-of-alias: chains and multi-level resolution."""

    def test_alias_of_alias_resolves(self):
        """B = alias(A), A = int64 → B resolves to int64."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "f",
                    [{"id": "x", "type": {"type": "alias", "name": "B"}}],
                    INT64,
                    [{"op": "return", "val": {"ref": "x"}}],
                ),
            ],
            exports=["f"],
            types={
                "A": INT64,
                "B": {"type": "alias", "name": "A"},
            },
        )
        result = run_spec(spec, args={"x": 7}, call_fn="f")
        self.assertEqual(result, 7)

    def test_three_level_alias_chain(self):
        """C = alias(B), B = alias(A), A = string — three hops."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "id",
                    [{"id": "s", "type": {"type": "alias", "name": "C"}}],
                    {"type": "alias", "name": "C"},
                    [{"op": "return", "val": {"ref": "s"}}],
                ),
            ],
            exports=["id"],
            types={
                "A": STR_T,
                "B": {"type": "alias", "name": "A"},
                "C": {"type": "alias", "name": "B"},
            },
        )
        result = run_spec(spec, args={"s": "hello"}, call_fn="id")
        self.assertEqual(result, "hello")


class TestTypeAliasNested(unittest.TestCase):
    """Aliases used inside container types (option, list, map, result)."""

    def test_alias_inside_option(self):
        """option<alias(UserId)> resolves to option<int64>."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "f",
                    [],
                    {"type": "option", "inner": {"type": "alias", "name": "UserId"}},
                    [
                        {
                            "op": "return",
                            "val": {
                                "lit": None,
                                "type": {"type": "option", "inner": {"type": "alias", "name": "UserId"}},
                            },
                        }
                    ],
                ),
            ],
            exports=["f"],
            types={"UserId": INT64},
        )
        # Should check without errors
        Checker(spec).check()

    def test_alias_inside_list(self):
        """list<alias(Score)> resolves to list<int64>."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "list_len",
                    [
                        {
                            "id": "scores",
                            "type": {
                                "type": "list",
                                "inner": {"type": "alias", "name": "Score"},
                                "len": "dynamic",
                            },
                        }
                    ],
                    INT64,
                    [
                        {
                            "op": "return",
                            "val": {
                                "op": "list_len",
                                "list": {"ref": "scores"},
                            },
                        }
                    ],
                ),
            ],
            exports=["list_len"],
            types={"Score": INT64},
        )
        Checker(spec).check()

    def test_alias_inside_map_value(self):
        """map<string, alias(Count)> resolves correctly."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "get_count",
                    [
                        {
                            "id": "m",
                            "type": {
                                "type": "map",
                                "key": STR_T,
                                "value": {"type": "alias", "name": "Count"},
                            },
                        },
                        {"id": "key", "type": STR_T},
                    ],
                    {"type": "alias", "name": "Count"},
                    [
                        {
                            "op": "return",
                            "val": {
                                "op": "map_get",
                                "map": {"ref": "m"},
                                "key": {"ref": "key"},
                            },
                        }
                    ],
                ),
            ],
            exports=["get_count"],
            types={"Count": INT64},
        )
        Checker(spec).check()

    def test_alias_of_option_type(self):
        """Alias wraps an option type itself: MaybeInt = option<int64>."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "f",
                    [],
                    {"type": "alias", "name": "MaybeInt"},
                    [
                        {
                            "op": "return",
                            "val": {
                                "lit": None,
                                "type": {"type": "alias", "name": "MaybeInt"},
                            },
                        }
                    ],
                ),
            ],
            exports=["f"],
            types={"MaybeInt": {"type": "option", "inner": INT64}},
        )
        Checker(spec).check()


class TestTypeAliasCycleDetection(unittest.TestCase):
    """Circular alias detection — must always raise CheckError."""

    def test_direct_two_node_cycle(self):
        """A = alias(B), B = alias(A) — direct cycle must raise."""
        spec = module_spec(
            "m",
            defs=[],
            types={
                "A": {"type": "alias", "name": "B"},
                "B": {"type": "alias", "name": "A"},
            },
        )
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()
        self.assertIn("Circular", str(ctx.exception))

    def test_three_node_cycle(self):
        """A → B → C → A — three-node cycle must raise."""
        spec = module_spec(
            "m",
            defs=[],
            types={
                "A": {"type": "alias", "name": "B"},
                "B": {"type": "alias", "name": "C"},
                "C": {"type": "alias", "name": "A"},
            },
        )
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()
        self.assertIn("Circular", str(ctx.exception))

    def test_self_referencing_alias(self):
        """A = alias(A) — self-reference must raise."""
        spec = module_spec(
            "m",
            defs=[],
            types={
                "A": {"type": "alias", "name": "A"},
            },
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_cycle_inside_nested_type(self):
        """Cycle via option wrapper: A = option<alias(B)>, B = alias(A)."""
        spec = module_spec(
            "m",
            defs=[],
            types={
                "A": {"type": "option", "inner": {"type": "alias", "name": "B"}},
                "B": {"type": "alias", "name": "A"},
            },
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_cycle_in_list_inner(self):
        """Cycle via list inner: A = list<alias(B)>, B = alias(A)."""
        spec = module_spec(
            "m",
            defs=[],
            types={
                "A": {"type": "list", "inner": {"type": "alias", "name": "B"}, "len": "dynamic"},
                "B": {"type": "alias", "name": "A"},
            },
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()


class TestTypeAliasErrors(unittest.TestCase):
    """Error cases for unknown aliases and type mismatches."""

    def test_unknown_alias_in_types_raises(self):
        """Referencing an alias that doesn't exist must raise."""
        spec = module_spec(
            "m",
            defs=[],
            types={
                "A": {"type": "alias", "name": "DoesNotExist"},
            },
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_unknown_alias_in_param_type_raises(self):
        """Using an alias name that is not declared raises CheckError."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "f",
                    [{"id": "x", "type": {"type": "alias", "name": "Ghost"}}],
                    INT64,
                    [{"op": "return", "val": {"ref": "x"}}],
                ),
            ],
            exports=["f"],
            types={},  # "Ghost" not declared
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_alias_type_mismatch_in_return_raises(self):
        """Returning a string when alias resolves to int64 must raise."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "f",
                    [],
                    {"type": "alias", "name": "UserId"},  # resolves to int64
                    [{"op": "return", "val": {"lit": "not_an_int"}}],  # wrong type
                ),
            ],
            exports=["f"],
            types={"UserId": INT64},
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()


class TestTypeAliasMultiFunction(unittest.TestCase):
    """Multiple functions in one module sharing type aliases."""

    def test_multiple_functions_share_alias(self):
        """Two functions can both use the same alias independently."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "make_id",
                    [],
                    {"type": "alias", "name": "UserId"},
                    [{"op": "return", "val": {"lit": 1}}],
                ),
                fn_spec(
                    "double_id",
                    [{"id": "uid", "type": {"type": "alias", "name": "UserId"}}],
                    {"type": "alias", "name": "UserId"},
                    [
                        {
                            "op": "return",
                            "val": {
                                "op": "*",
                                "l": {"ref": "uid"},
                                "r": {"lit": 2},
                            },
                        }
                    ],
                ),
            ],
            exports=["make_id", "double_id"],
            types={"UserId": INT64},
        )
        Checker(spec).check()
        rt = Runtime(spec)
        self.assertEqual(rt.run_fn("make_id", {}), 1)
        self.assertEqual(rt.run_fn("double_id", {"uid": 5}), 10)

    def test_alias_used_in_if_branch(self):
        """Alias-typed variable used inside if/else branches."""
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "max_id",
                    [
                        {"id": "a", "type": {"type": "alias", "name": "UserId"}},
                        {"id": "b", "type": {"type": "alias", "name": "UserId"}},
                    ],
                    {"type": "alias", "name": "UserId"},
                    [
                        {
                            "op": "if",
                            "cond": {"op": "gt", "l": {"ref": "a"}, "r": {"ref": "b"}},
                            "then": [{"op": "return", "val": {"ref": "a"}}],
                            "else": [{"op": "return", "val": {"ref": "b"}}],
                        }
                    ],
                ),
            ],
            exports=["max_id"],
            types={"UserId": INT64},
        )
        result = run_spec(spec, args={"a": 10, "b": 7}, call_fn="max_id")
        self.assertEqual(result, 10)
        result2 = run_spec(spec, args={"a": 3, "b": 9}, call_fn="max_id")
        self.assertEqual(result2, 9)


if __name__ == "__main__":
    unittest.main()
