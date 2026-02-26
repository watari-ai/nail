#!/usr/bin/env python3
"""
NAIL Collection Operations Test Suite — v0.4

Covers Issue #26: built-in operations on lists and maps:
  list_map   — transform each element with a named function
  list_filter — keep elements satisfying a predicate function
  list_fold  — left-fold a list into a single accumulator value
  map_values — extract map values as a list
  map_set    — mutate a map entry (key → value)

Also covers FnType in types.py (used internally by the checker for error messages).

Run: python3 -m pytest tests/test_collection_ops.py -v
  or: python3 -m pytest tests/ -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter import Checker, Runtime, CheckError, NailTypeError
from interpreter.runtime import UNIT
from interpreter.types import FnType, IntType, BoolType, ListType, StringType


# ── type shorthand helpers ────────────────────────────────────────────────────

INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
BOOL_T = {"type": "bool"}
STR_T = {"type": "string"}
UNIT_T = {"type": "unit"}
LIST_INT = {"type": "list", "inner": INT64, "len": "dynamic"}
LIST_STR = {"type": "list", "inner": STR_T, "len": "dynamic"}
MAP_STR_INT = {"type": "map", "key": STR_T, "value": INT64}


# ── spec builder helpers ──────────────────────────────────────────────────────

def fn_def(fn_id, params, returns, body, effects=None):
    """Build a function definition dict for use inside a module."""
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


def run_module_fn(spec, fn_id, args=None):
    """Check + run a named function from a module spec."""
    Checker(spec).check()
    rt = Runtime(spec)
    return rt.run_fn(fn_id, args or {})


# ── helper function definitions ───────────────────────────────────────────────

# fn double(x: int64) -> int64  { return x * 2 }
DOUBLE_FN = fn_def(
    "double",
    params=[{"id": "x", "type": INT64}],
    returns=INT64,
    body=[
        {"op": "return", "val": {"op": "*", "l": {"ref": "x"}, "r": {"lit": 2}}}
    ],
)

# fn is_positive(x: int64) -> bool  { return x > 0 }
IS_POSITIVE_FN = fn_def(
    "is_positive",
    params=[{"id": "x", "type": INT64}],
    returns=BOOL_T,
    body=[
        {"op": "return", "val": {"op": "gt", "l": {"ref": "x"}, "r": {"lit": 0}}}
    ],
)

# fn add(acc: int64, x: int64) -> int64  { return acc + x }
ADD_FN = fn_def(
    "add",
    params=[{"id": "acc", "type": INT64}, {"id": "x", "type": INT64}],
    returns=INT64,
    body=[
        {"op": "return", "val": {"op": "+", "l": {"ref": "acc"}, "r": {"ref": "x"}}}
    ],
)

# fn str_len_fn(s: string) -> int64  { return str_len(s) }
STR_LEN_FN = fn_def(
    "str_len_fn",
    params=[{"id": "s", "type": STR_T}],
    returns=INT64,
    body=[
        {"op": "return", "val": {"op": "str_len", "val": {"ref": "s"}}}
    ],
)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. FnType — types.py addition
# ═══════════════════════════════════════════════════════════════════════════════

class TestFnType(unittest.TestCase):
    """FnType is a new type added to types.py for v0.4 collection ops.
    It represents a function signature used in checker error messages.
    """

    def test_fn_type_str_single_param(self):
        ft = FnType(param_types=(IntType(bits=64, overflow="panic"),), return_type=BoolType())
        self.assertEqual(str(ft), "fn(int64(panic)) -> bool")

    def test_fn_type_str_two_params(self):
        i64 = IntType(bits=64, overflow="panic")
        ft = FnType(param_types=(i64, i64), return_type=i64)
        self.assertEqual(str(ft), "fn(int64(panic), int64(panic)) -> int64(panic)")

    def test_fn_type_equality(self):
        i64 = IntType(bits=64, overflow="panic")
        ft1 = FnType(param_types=(i64,), return_type=BoolType())
        ft2 = FnType(param_types=(i64,), return_type=BoolType())
        self.assertEqual(ft1, ft2)

    def test_fn_type_inequality_return(self):
        i64 = IntType(bits=64, overflow="panic")
        ft1 = FnType(param_types=(i64,), return_type=BoolType())
        ft2 = FnType(param_types=(i64,), return_type=i64)
        self.assertNotEqual(ft1, ft2)

    def test_fn_type_is_frozen(self):
        i64 = IntType(bits=64, overflow="panic")
        ft = FnType(param_types=(i64,), return_type=BoolType())
        with self.assertRaises(Exception):
            ft.return_type = i64  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════════
# 2. list_map — transform list elements
# ═══════════════════════════════════════════════════════════════════════════════

class TestListMap(unittest.TestCase):
    """list_map applies a 1-argument function to every element of a list."""

    def _make_spec(self):
        """Module with double() helper and main() that uses list_map."""
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=LIST_INT,
            body=[
                {
                    "op": "let",
                    "id": "result",
                    "val": {"op": "list_map", "list": {"ref": "nums"}, "fn": "double"},
                },
                {"op": "return", "val": {"ref": "result"}},
            ],
        )
        return module_spec("test_list_map", [DOUBLE_FN, main_fn], exports=["main"])

    def test_list_map_doubles_all_elements(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"nums": [1, 2, 3, 4, 5]})
        self.assertEqual(result, [2, 4, 6, 8, 10])

    def test_list_map_empty_list(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"nums": []})
        self.assertEqual(result, [])

    def test_list_map_negative_values(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"nums": [-3, 0, 7]})
        self.assertEqual(result, [-6, 0, 14])

    def test_list_map_string_elements(self):
        """list_map works with string lists too (e.g., str_len_fn)."""
        main_fn = fn_def(
            "main",
            params=[{"id": "words", "type": LIST_STR}],
            returns=LIST_INT,
            body=[
                {
                    "op": "let",
                    "id": "lengths",
                    "val": {"op": "list_map", "list": {"ref": "words"}, "fn": "str_len_fn"},
                },
                {"op": "return", "val": {"ref": "lengths"}},
            ],
        )
        spec = module_spec("test_list_map_str", [STR_LEN_FN, main_fn], exports=["main"])
        result = run_module_fn(spec, "main", {"words": ["hi", "nail", "world"]})
        self.assertEqual(result, [2, 4, 5])

    def test_list_map_checker_wrong_fn_param_type_raises(self):
        """Checker rejects list_map when fn's param type doesn't match list element type."""
        # str_len_fn takes string, but we pass a list of int → type mismatch
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=LIST_INT,
            body=[
                {
                    "op": "let",
                    "id": "result",
                    "val": {"op": "list_map", "list": {"ref": "nums"}, "fn": "str_len_fn"},
                },
                {"op": "return", "val": {"ref": "result"}},
            ],
        )
        spec = module_spec("test_list_map_bad", [STR_LEN_FN, main_fn], exports=["main"])
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()

        self.assertIn('signature mismatch', str(ctx.exception))
    def test_list_map_checker_unknown_fn_raises(self):
        """Checker rejects list_map that references an undefined function."""
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=LIST_INT,
            body=[
                {
                    "op": "let",
                    "id": "result",
                    "val": {"op": "list_map", "list": {"ref": "nums"}, "fn": "nonexistent_fn"},
                },
                {"op": "return", "val": {"ref": "result"}},
            ],
        )
        spec = module_spec("test_list_map_unknown", [main_fn], exports=["main"])
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()


        self.assertIn('nonexistent_fn', str(ctx.exception))
# ═══════════════════════════════════════════════════════════════════════════════
# 3. list_filter — keep elements matching a predicate
# ═══════════════════════════════════════════════════════════════════════════════

class TestListFilter(unittest.TestCase):
    """list_filter returns a new list containing only elements where fn(elem) is true."""

    def _make_spec(self):
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=LIST_INT,
            body=[
                {
                    "op": "let",
                    "id": "positives",
                    "val": {"op": "list_filter", "list": {"ref": "nums"}, "fn": "is_positive"},
                },
                {"op": "return", "val": {"ref": "positives"}},
            ],
        )
        return module_spec("test_list_filter", [IS_POSITIVE_FN, main_fn], exports=["main"])

    def test_list_filter_keeps_positives(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"nums": [-2, -1, 0, 1, 2, 3]})
        self.assertEqual(result, [1, 2, 3])

    def test_list_filter_all_negative_returns_empty(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"nums": [-5, -4, -3]})
        self.assertEqual(result, [])

    def test_list_filter_all_positive_returns_all(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"nums": [1, 2, 3, 4, 5]})
        self.assertEqual(result, [1, 2, 3, 4, 5])

    def test_list_filter_empty_list(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"nums": []})
        self.assertEqual(result, [])

    def test_list_filter_checker_non_bool_return_raises(self):
        """Checker rejects list_filter when fn returns non-bool."""
        # double returns int, not bool → invalid predicate
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=LIST_INT,
            body=[
                {
                    "op": "let",
                    "id": "result",
                    "val": {"op": "list_filter", "list": {"ref": "nums"}, "fn": "double"},
                },
                {"op": "return", "val": {"ref": "result"}},
            ],
        )
        spec = module_spec("test_list_filter_bad", [DOUBLE_FN, main_fn], exports=["main"])
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()
        self.assertIn("bool", str(ctx.exception))

    def test_list_filter_checker_wrong_param_type_raises(self):
        """Checker rejects list_filter when fn param type doesn't match list element."""
        # is_positive takes int, but we pass list of string
        main_fn = fn_def(
            "main",
            params=[{"id": "words", "type": LIST_STR}],
            returns=LIST_STR,
            body=[
                {
                    "op": "let",
                    "id": "result",
                    "val": {"op": "list_filter", "list": {"ref": "words"}, "fn": "is_positive"},
                },
                {"op": "return", "val": {"ref": "result"}},
            ],
        )
        spec = module_spec("test_list_filter_bad2", [IS_POSITIVE_FN, main_fn], exports=["main"])
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()


        self.assertIn('signature mismatch', str(ctx.exception))
# ═══════════════════════════════════════════════════════════════════════════════
# 4. list_fold — left-fold / reduce a list
# ═══════════════════════════════════════════════════════════════════════════════

class TestListFold(unittest.TestCase):
    """list_fold reduces a list to a single value using a 2-argument combiner function."""

    def _make_spec(self):
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=INT64,
            body=[
                {
                    "op": "let",
                    "id": "total",
                    "val": {
                        "op": "list_fold",
                        "list": {"ref": "nums"},
                        "init": {"lit": 0},
                        "fn": "add",
                    },
                },
                {"op": "return", "val": {"ref": "total"}},
            ],
        )
        return module_spec("test_list_fold", [ADD_FN, main_fn], exports=["main"])

    def test_list_fold_sums_list(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"nums": [1, 2, 3, 4, 5]})
        self.assertEqual(result, 15)

    def test_list_fold_empty_returns_init(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"nums": []})
        self.assertEqual(result, 0)

    def test_list_fold_single_element(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"nums": [42]})
        self.assertEqual(result, 42)

    def test_list_fold_with_init_value(self):
        """list_fold with non-zero init value."""
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=INT64,
            body=[
                {
                    "op": "let",
                    "id": "total",
                    "val": {
                        "op": "list_fold",
                        "list": {"ref": "nums"},
                        "init": {"lit": 100},
                        "fn": "add",
                    },
                },
                {"op": "return", "val": {"ref": "total"}},
            ],
        )
        spec = module_spec("test_list_fold_init", [ADD_FN, main_fn], exports=["main"])
        result = run_module_fn(spec, "main", {"nums": [1, 2, 3]})
        self.assertEqual(result, 106)  # 100 + 1 + 2 + 3

    def test_list_fold_checker_wrong_param_count_raises(self):
        """Checker rejects list_fold when fn doesn't take exactly 2 params."""
        # double takes 1 param, not 2
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=INT64,
            body=[
                {
                    "op": "let",
                    "id": "total",
                    "val": {
                        "op": "list_fold",
                        "list": {"ref": "nums"},
                        "init": {"lit": 0},
                        "fn": "double",
                    },
                },
                {"op": "return", "val": {"ref": "total"}},
            ],
        )
        spec = module_spec("test_list_fold_bad", [DOUBLE_FN, main_fn], exports=["main"])
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()
        self.assertIn("2 parameter", str(ctx.exception))

    def test_list_fold_checker_accum_type_mismatch_raises(self):
        """Checker rejects list_fold when init type doesn't match fn's first param."""
        # add expects (int64, int64), but init is a bool literal — type mismatch
        # Note: We can't actually have a bool literal in this position without a type annotation,
        # so we'll craft a scenario where the fn's first param type doesn't match init.
        # We create a fn where the first param is string but init is int.
        wrong_fold_fn = fn_def(
            "concat_fold",
            params=[{"id": "acc", "type": STR_T}, {"id": "x", "type": INT64}],
            returns=STR_T,
            body=[
                {"op": "return", "val": {"ref": "acc"}}
            ],
        )
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=STR_T,
            body=[
                {
                    "op": "let",
                    "id": "total",
                    "val": {
                        "op": "list_fold",
                        "list": {"ref": "nums"},
                        "init": {"lit": 0},   # int, but fn expects string acc
                        "fn": "concat_fold",
                    },
                },
                {"op": "return", "val": {"ref": "total"}},
            ],
        )
        spec = module_spec("test_list_fold_accum", [wrong_fold_fn, main_fn], exports=["main"])
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()
        self.assertIn("accumulator", str(ctx.exception))


# ═══════════════════════════════════════════════════════════════════════════════
# 5. map_values — extract map values as a list
# ═══════════════════════════════════════════════════════════════════════════════

class TestMapValues(unittest.TestCase):
    """map_values returns all values of a map as a dynamic list."""

    def _make_spec(self):
        main_fn = fn_def(
            "main",
            params=[{"id": "m", "type": MAP_STR_INT}],
            returns=LIST_INT,
            body=[
                {
                    "op": "let",
                    "id": "vals",
                    "val": {"op": "map_values", "map": {"ref": "m"}},
                },
                {"op": "return", "val": {"ref": "vals"}},
            ],
        )
        return module_spec("test_map_values", [main_fn], exports=["main"])

    def test_map_values_extracts_values(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"m": {"a": 1, "b": 2, "c": 3}})
        self.assertIsInstance(result, list)
        self.assertEqual(sorted(result), [1, 2, 3])

    def test_map_values_empty_map(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"m": {}})
        self.assertEqual(result, [])

    def test_map_values_checker_non_map_raises(self):
        """Checker rejects map_values when applied to a non-map type."""
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=LIST_INT,
            body=[
                {
                    "op": "let",
                    "id": "vals",
                    "val": {"op": "map_values", "map": {"ref": "nums"}},
                },
                {"op": "return", "val": {"ref": "vals"}},
            ],
        )
        spec = module_spec("test_map_values_bad", [main_fn], exports=["main"])
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()
        self.assertIn("map", str(ctx.exception).lower())

    def test_map_values_return_type_is_list_of_value_type(self):
        """Checker correctly types map_values result as list<value_type>."""
        # If map is map<string, int64>, map_values should return list<int64>
        # Verify by checking the result can be used where list<int64> is expected
        main_fn = fn_def(
            "main",
            params=[{"id": "m", "type": MAP_STR_INT}],
            returns=LIST_INT,  # expects list<int64>
            body=[
                {
                    "op": "let",
                    "id": "vals",
                    "val": {"op": "map_values", "map": {"ref": "m"}},
                },
                {"op": "return", "val": {"ref": "vals"}},
            ],
        )
        spec = module_spec("test_map_values_type", [main_fn], exports=["main"])
        # Should not raise
        Checker(spec).check()


# ═══════════════════════════════════════════════════════════════════════════════
# 6. map_set — mutate a map entry
# ═══════════════════════════════════════════════════════════════════════════════

class TestMapSet(unittest.TestCase):
    """map_set writes a key-value pair into a map (mutates in place, returns unit)."""

    def _make_spec(self):
        """Module with a function that sets a key in a map and returns the updated map."""
        main_fn = fn_def(
            "main",
            params=[
                {"id": "m", "type": MAP_STR_INT},
                {"id": "k", "type": STR_T},
                {"id": "v", "type": INT64},
            ],
            returns=MAP_STR_INT,
            body=[
                {
                    "op": "map_set",
                    "map": {"ref": "m"},
                    "key": {"ref": "k"},
                    "value": {"ref": "v"},
                },
                {"op": "return", "val": {"ref": "m"}},
            ],
        )
        return module_spec("test_map_set", [main_fn], exports=["main"])

    def test_map_set_adds_new_key(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"m": {"a": 1}, "k": "b", "v": 2})
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_map_set_overwrites_existing_key(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"m": {"a": 1}, "k": "a", "v": 99})
        self.assertEqual(result, {"a": 99})

    def test_map_set_empty_map(self):
        spec = self._make_spec()
        result = run_module_fn(spec, "main", {"m": {}, "k": "x", "v": 42})
        self.assertEqual(result, {"x": 42})

    def test_map_set_checker_key_type_mismatch_raises(self):
        """Checker rejects map_set when key type doesn't match map's key type."""
        # map is map<string, int64> but key is int64
        main_fn = fn_def(
            "main",
            params=[
                {"id": "m", "type": MAP_STR_INT},
                {"id": "k", "type": INT64},   # wrong key type
                {"id": "v", "type": INT64},
            ],
            returns=UNIT_T,
            body=[
                {
                    "op": "map_set",
                    "map": {"ref": "m"},
                    "key": {"ref": "k"},
                    "value": {"ref": "v"},
                },
                {"op": "return", "val": {"lit": None, "type": UNIT_T}},
            ],
        )
        spec = module_spec("test_map_set_bad_key", [main_fn], exports=["main"])
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()
        self.assertIn("key", str(ctx.exception).lower())

    def test_map_set_checker_value_type_mismatch_raises(self):
        """Checker rejects map_set when value type doesn't match map's value type."""
        # map is map<string, int64> but value is string
        main_fn = fn_def(
            "main",
            params=[
                {"id": "m", "type": MAP_STR_INT},
                {"id": "k", "type": STR_T},
                {"id": "v", "type": STR_T},   # wrong value type
            ],
            returns=UNIT_T,
            body=[
                {
                    "op": "map_set",
                    "map": {"ref": "m"},
                    "key": {"ref": "k"},
                    "value": {"ref": "v"},
                },
                {"op": "return", "val": {"lit": None, "type": UNIT_T}},
            ],
        )
        spec = module_spec("test_map_set_bad_val", [main_fn], exports=["main"])
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()
        self.assertIn("value", str(ctx.exception).lower())


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Integration — pipeline: filter → map → fold
# ═══════════════════════════════════════════════════════════════════════════════

class TestCollectionOpsPipeline(unittest.TestCase):
    """Integration tests combining multiple collection ops in sequence."""

    def test_filter_then_fold_sum_positives(self):
        """filter negatives out, then fold-sum the remaining positives."""
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=INT64,
            body=[
                {
                    "op": "let",
                    "id": "pos",
                    "val": {"op": "list_filter", "list": {"ref": "nums"}, "fn": "is_positive"},
                },
                {
                    "op": "let",
                    "id": "total",
                    "val": {
                        "op": "list_fold",
                        "list": {"ref": "pos"},
                        "init": {"lit": 0},
                        "fn": "add",
                    },
                },
                {"op": "return", "val": {"ref": "total"}},
            ],
        )
        spec = module_spec(
            "test_pipeline",
            [IS_POSITIVE_FN, ADD_FN, main_fn],
            exports=["main"],
        )
        result = run_module_fn(spec, "main", {"nums": [-3, 1, -2, 4, 0, 5]})
        self.assertEqual(result, 10)  # 1 + 4 + 5

    def test_map_then_fold(self):
        """Double all elements, then sum."""
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=INT64,
            body=[
                {
                    "op": "let",
                    "id": "doubled",
                    "val": {"op": "list_map", "list": {"ref": "nums"}, "fn": "double"},
                },
                {
                    "op": "let",
                    "id": "total",
                    "val": {
                        "op": "list_fold",
                        "list": {"ref": "doubled"},
                        "init": {"lit": 0},
                        "fn": "add",
                    },
                },
                {"op": "return", "val": {"ref": "total"}},
            ],
        )
        spec = module_spec(
            "test_map_fold",
            [DOUBLE_FN, ADD_FN, main_fn],
            exports=["main"],
        )
        result = run_module_fn(spec, "main", {"nums": [1, 2, 3]})
        self.assertEqual(result, 12)  # (1+2+3)*2 = 12

    def test_map_values_then_fold(self):
        """Extract map values, then sum them."""
        main_fn = fn_def(
            "main",
            params=[{"id": "m", "type": MAP_STR_INT}],
            returns=INT64,
            body=[
                {
                    "op": "let",
                    "id": "vals",
                    "val": {"op": "map_values", "map": {"ref": "m"}},
                },
                {
                    "op": "let",
                    "id": "total",
                    "val": {
                        "op": "list_fold",
                        "list": {"ref": "vals"},
                        "init": {"lit": 0},
                        "fn": "add",
                    },
                },
                {"op": "return", "val": {"ref": "total"}},
            ],
        )
        spec = module_spec(
            "test_map_values_fold",
            [ADD_FN, main_fn],
            exports=["main"],
        )
        result = run_module_fn(spec, "main", {"m": {"a": 10, "b": 20, "c": 30}})
        self.assertEqual(result, 60)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Edge cases and additional checker coverage
# ═══════════════════════════════════════════════════════════════════════════════

class TestCollectionOpsEdgeCases(unittest.TestCase):

    def test_map_set_returns_unit_type_at_checker(self):
        """map_set is a unit-returning op — checker should see it as unit."""
        # We verify by using map_set as statement (checker should not reject it)
        main_fn = fn_def(
            "main",
            params=[{"id": "m", "type": MAP_STR_INT}],
            returns=UNIT_T,
            body=[
                {
                    "op": "map_set",
                    "map": {"ref": "m"},
                    "key": {"lit": "hello"},
                    "value": {"lit": 42},
                },
                {"op": "return", "val": {"lit": None, "type": UNIT_T}},
            ],
        )
        spec = module_spec("test_map_set_unit", [main_fn], exports=["main"])
        Checker(spec).check()  # should pass

    def test_list_map_chained_with_list_len(self):
        """list_map result can be measured with list_len."""
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=INT64,
            body=[
                {
                    "op": "let",
                    "id": "doubled",
                    "val": {"op": "list_map", "list": {"ref": "nums"}, "fn": "double"},
                },
                {
                    "op": "let",
                    "id": "length",
                    "val": {"op": "list_len", "list": {"ref": "doubled"}},
                },
                {"op": "return", "val": {"ref": "length"}},
            ],
        )
        spec = module_spec("test_map_len", [DOUBLE_FN, main_fn], exports=["main"])
        result = run_module_fn(spec, "main", {"nums": [1, 2, 3, 4]})
        self.assertEqual(result, 4)

    def test_list_fold_missing_fn_raises(self):
        """Checker rejects list_fold when 'fn' field is absent."""
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=INT64,
            body=[
                {
                    "op": "let",
                    "id": "total",
                    "val": {
                        "op": "list_fold",
                        "list": {"ref": "nums"},
                        "init": {"lit": 0},
                        # "fn" is intentionally omitted
                    },
                },
                {"op": "return", "val": {"ref": "total"}},
            ],
        )
        spec = module_spec("test_list_fold_no_fn", [main_fn], exports=["main"])
        with self.assertRaises(CheckError) as ctx:
            Checker(spec).check()

        self.assertIn('list_fold', str(ctx.exception))
    def test_list_filter_preserves_element_type(self):
        """After list_filter, the element type is unchanged (no coercion)."""
        # filter → fold should type-check cleanly
        main_fn = fn_def(
            "main",
            params=[{"id": "nums", "type": LIST_INT}],
            returns=INT64,
            body=[
                {
                    "op": "let",
                    "id": "pos",
                    "val": {"op": "list_filter", "list": {"ref": "nums"}, "fn": "is_positive"},
                },
                {
                    "op": "let",
                    "id": "s",
                    "val": {"op": "list_fold", "list": {"ref": "pos"}, "init": {"lit": 0}, "fn": "add"},
                },
                {"op": "return", "val": {"ref": "s"}},
            ],
        )
        spec = module_spec("test_filter_type", [IS_POSITIVE_FN, ADD_FN, main_fn], exports=["main"])
        # Checker should pass — result of filter is still list<int64>
        Checker(spec).check()
        result = run_module_fn(spec, "main", {"nums": [1, 2, -1, 3]})
        self.assertEqual(result, 6)


if __name__ == "__main__":
    unittest.main()
