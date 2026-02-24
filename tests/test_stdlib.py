#!/usr/bin/env python3
"""
NAIL Standard Library Test Suite — v0.5
Tests for: abs, min2, max2, clamp, str_len, str_upper, str_lower, str_contains,
           bool_to_int, int_to_bool
Run: python3 -m pytest tests/test_stdlib.py -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter import Checker, Runtime, CheckError, NailTypeError, NailRuntimeError
from interpreter.runtime import UNIT

INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
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


def run_spec(spec: dict, args: dict | None = None, call_fn: str | None = None):
    """Helper: check + run a spec dict, return result."""
    Checker(spec).check()
    rt = Runtime(spec)
    if call_fn:
        return rt.run_fn(call_fn, args or {})
    return rt.run(args)


# ─────────────────────────────────────────────────────────
#  abs
# ─────────────────────────────────────────────────────────

class TestAbs(unittest.TestCase):

    def test_abs_positive(self):
        spec = fn_spec("f", [{"id": "x", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "abs", "val": {"ref": "x"}}}
        ])
        self.assertEqual(run_spec(spec, {"x": 5}), 5)

    def test_abs_negative(self):
        spec = fn_spec("f", [{"id": "x", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "abs", "val": {"ref": "x"}}}
        ])
        self.assertEqual(run_spec(spec, {"x": -7}), 7)

    def test_abs_zero(self):
        spec = fn_spec("f", [{"id": "x", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "abs", "val": {"ref": "x"}}}
        ])
        self.assertEqual(run_spec(spec, {"x": 0}), 0)

    def test_abs_type_error_checker(self):
        """abs on bool should fail type check."""
        spec = fn_spec("f", [{"id": "x", "type": BOOL_T}], INT64, [
            {"op": "return", "val": {"op": "abs", "val": {"ref": "x"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_abs_type_error_string_checker(self):
        """abs on string should fail type check."""
        spec = fn_spec("f", [{"id": "x", "type": STR_T}], STR_T, [
            {"op": "return", "val": {"op": "abs", "val": {"ref": "x"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()


# ─────────────────────────────────────────────────────────
#  min2 / max2
# ─────────────────────────────────────────────────────────

class TestMin2Max2(unittest.TestCase):

    def test_min2_first_smaller(self):
        spec = fn_spec("f", [{"id": "a", "type": INT64}, {"id": "b", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "min2", "l": {"ref": "a"}, "r": {"ref": "b"}}}
        ])
        self.assertEqual(run_spec(spec, {"a": 3, "b": 7}), 3)

    def test_min2_second_smaller(self):
        spec = fn_spec("f", [{"id": "a", "type": INT64}, {"id": "b", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "min2", "l": {"ref": "a"}, "r": {"ref": "b"}}}
        ])
        self.assertEqual(run_spec(spec, {"a": 10, "b": 2}), 2)

    def test_min2_equal(self):
        spec = fn_spec("f", [{"id": "a", "type": INT64}, {"id": "b", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "min2", "l": {"ref": "a"}, "r": {"ref": "b"}}}
        ])
        self.assertEqual(run_spec(spec, {"a": 5, "b": 5}), 5)

    def test_max2_first_larger(self):
        spec = fn_spec("f", [{"id": "a", "type": INT64}, {"id": "b", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "max2", "l": {"ref": "a"}, "r": {"ref": "b"}}}
        ])
        self.assertEqual(run_spec(spec, {"a": 9, "b": 4}), 9)

    def test_max2_second_larger(self):
        spec = fn_spec("f", [{"id": "a", "type": INT64}, {"id": "b", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "max2", "l": {"ref": "a"}, "r": {"ref": "b"}}}
        ])
        self.assertEqual(run_spec(spec, {"a": 1, "b": 100}), 100)

    def test_min2_negative_values(self):
        spec = fn_spec("f", [{"id": "a", "type": INT64}, {"id": "b", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "min2", "l": {"ref": "a"}, "r": {"ref": "b"}}}
        ])
        self.assertEqual(run_spec(spec, {"a": -3, "b": -10}), -10)

    def test_max2_type_mismatch_checker(self):
        """min2/max2 with mismatched types should fail type check."""
        spec = fn_spec("f", [{"id": "a", "type": INT64}, {"id": "b", "type": BOOL_T}], INT64, [
            {"op": "return", "val": {"op": "max2", "l": {"ref": "a"}, "r": {"ref": "b"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()


# ─────────────────────────────────────────────────────────
#  clamp
# ─────────────────────────────────────────────────────────

class TestClamp(unittest.TestCase):

    def test_clamp_within_range(self):
        spec = fn_spec("f", [
            {"id": "x", "type": INT64}, {"id": "lo", "type": INT64}, {"id": "hi", "type": INT64}
        ], INT64, [
            {"op": "return", "val": {"op": "clamp", "val": {"ref": "x"}, "lo": {"ref": "lo"}, "hi": {"ref": "hi"}}}
        ])
        self.assertEqual(run_spec(spec, {"x": 5, "lo": 0, "hi": 10}), 5)

    def test_clamp_below_lo(self):
        spec = fn_spec("f", [
            {"id": "x", "type": INT64}, {"id": "lo", "type": INT64}, {"id": "hi", "type": INT64}
        ], INT64, [
            {"op": "return", "val": {"op": "clamp", "val": {"ref": "x"}, "lo": {"ref": "lo"}, "hi": {"ref": "hi"}}}
        ])
        self.assertEqual(run_spec(spec, {"x": -5, "lo": 0, "hi": 10}), 0)

    def test_clamp_above_hi(self):
        spec = fn_spec("f", [
            {"id": "x", "type": INT64}, {"id": "lo", "type": INT64}, {"id": "hi", "type": INT64}
        ], INT64, [
            {"op": "return", "val": {"op": "clamp", "val": {"ref": "x"}, "lo": {"ref": "lo"}, "hi": {"ref": "hi"}}}
        ])
        self.assertEqual(run_spec(spec, {"x": 20, "lo": 0, "hi": 10}), 10)

    def test_clamp_at_boundary_lo(self):
        spec = fn_spec("f", [
            {"id": "x", "type": INT64}, {"id": "lo", "type": INT64}, {"id": "hi", "type": INT64}
        ], INT64, [
            {"op": "return", "val": {"op": "clamp", "val": {"ref": "x"}, "lo": {"ref": "lo"}, "hi": {"ref": "hi"}}}
        ])
        self.assertEqual(run_spec(spec, {"x": 0, "lo": 0, "hi": 10}), 0)

    def test_clamp_at_boundary_hi(self):
        spec = fn_spec("f", [
            {"id": "x", "type": INT64}, {"id": "lo", "type": INT64}, {"id": "hi", "type": INT64}
        ], INT64, [
            {"op": "return", "val": {"op": "clamp", "val": {"ref": "x"}, "lo": {"ref": "lo"}, "hi": {"ref": "hi"}}}
        ])
        self.assertEqual(run_spec(spec, {"x": 10, "lo": 0, "hi": 10}), 10)

    def test_clamp_type_mismatch_checker(self):
        """clamp with mismatched val/lo/hi types should fail type check."""
        spec = fn_spec("f", [
            {"id": "x", "type": INT64}, {"id": "lo", "type": BOOL_T}, {"id": "hi", "type": INT64}
        ], INT64, [
            {"op": "return", "val": {"op": "clamp", "val": {"ref": "x"}, "lo": {"ref": "lo"}, "hi": {"ref": "hi"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_clamp_non_numeric_checker(self):
        """clamp on string should fail type check."""
        spec = fn_spec("f", [
            {"id": "x", "type": STR_T}, {"id": "lo", "type": STR_T}, {"id": "hi", "type": STR_T}
        ], STR_T, [
            {"op": "return", "val": {"op": "clamp", "val": {"ref": "x"}, "lo": {"ref": "lo"}, "hi": {"ref": "hi"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()


# ─────────────────────────────────────────────────────────
#  str_len / str_upper / str_lower / str_contains
# ─────────────────────────────────────────────────────────

class TestStringOps(unittest.TestCase):

    def test_str_len_basic(self):
        spec = fn_spec("f", [{"id": "s", "type": STR_T}], INT64, [
            {"op": "return", "val": {"op": "str_len", "val": {"ref": "s"}}}
        ])
        self.assertEqual(run_spec(spec, {"s": "hello"}), 5)

    def test_str_len_empty(self):
        spec = fn_spec("f", [{"id": "s", "type": STR_T}], INT64, [
            {"op": "return", "val": {"op": "str_len", "val": {"ref": "s"}}}
        ])
        self.assertEqual(run_spec(spec, {"s": ""}), 0)

    def test_str_upper_basic(self):
        spec = fn_spec("f", [{"id": "s", "type": STR_T}], STR_T, [
            {"op": "return", "val": {"op": "str_upper", "val": {"ref": "s"}}}
        ])
        self.assertEqual(run_spec(spec, {"s": "hello"}), "HELLO")

    def test_str_lower_basic(self):
        spec = fn_spec("f", [{"id": "s", "type": STR_T}], STR_T, [
            {"op": "return", "val": {"op": "str_lower", "val": {"ref": "s"}}}
        ])
        self.assertEqual(run_spec(spec, {"s": "WORLD"}), "world")

    def test_str_contains_true(self):
        spec = fn_spec("f", [{"id": "s", "type": STR_T}, {"id": "sub", "type": STR_T}], BOOL_T, [
            {"op": "return", "val": {"op": "str_contains", "val": {"ref": "s"}, "sub": {"ref": "sub"}}}
        ])
        self.assertTrue(run_spec(spec, {"s": "hello world", "sub": "world"}))

    def test_str_contains_false(self):
        spec = fn_spec("f", [{"id": "s", "type": STR_T}, {"id": "sub", "type": STR_T}], BOOL_T, [
            {"op": "return", "val": {"op": "str_contains", "val": {"ref": "s"}, "sub": {"ref": "sub"}}}
        ])
        self.assertFalse(run_spec(spec, {"s": "hello", "sub": "xyz"}))

    def test_str_len_type_error_checker(self):
        """str_len on int should fail type check."""
        spec = fn_spec("f", [{"id": "x", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "str_len", "val": {"ref": "x"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_str_upper_type_error_checker(self):
        """str_upper on int should fail type check."""
        spec = fn_spec("f", [{"id": "x", "type": INT64}], STR_T, [
            {"op": "return", "val": {"op": "str_upper", "val": {"ref": "x"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_str_contains_type_error_checker(self):
        """str_contains with int sub should fail type check."""
        spec = fn_spec("f", [{"id": "s", "type": STR_T}, {"id": "sub", "type": INT64}], BOOL_T, [
            {"op": "return", "val": {"op": "str_contains", "val": {"ref": "s"}, "sub": {"ref": "sub"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()


# ─────────────────────────────────────────────────────────
#  bool_to_int / int_to_bool
# ─────────────────────────────────────────────────────────

class TestTypeConversions(unittest.TestCase):

    def test_bool_to_int_true(self):
        spec = fn_spec("f", [{"id": "b", "type": BOOL_T}], INT64, [
            {"op": "return", "val": {"op": "bool_to_int", "val": {"ref": "b"}}}
        ])
        self.assertEqual(run_spec(spec, {"b": True}), 1)

    def test_bool_to_int_false(self):
        spec = fn_spec("f", [{"id": "b", "type": BOOL_T}], INT64, [
            {"op": "return", "val": {"op": "bool_to_int", "val": {"ref": "b"}}}
        ])
        self.assertEqual(run_spec(spec, {"b": False}), 0)

    def test_int_to_bool_zero(self):
        spec = fn_spec("f", [{"id": "n", "type": INT64}], BOOL_T, [
            {"op": "return", "val": {"op": "int_to_bool", "val": {"ref": "n"}}}
        ])
        self.assertFalse(run_spec(spec, {"n": 0}))

    def test_int_to_bool_nonzero(self):
        spec = fn_spec("f", [{"id": "n", "type": INT64}], BOOL_T, [
            {"op": "return", "val": {"op": "int_to_bool", "val": {"ref": "n"}}}
        ])
        self.assertTrue(run_spec(spec, {"n": 42}))

    def test_int_to_bool_negative(self):
        spec = fn_spec("f", [{"id": "n", "type": INT64}], BOOL_T, [
            {"op": "return", "val": {"op": "int_to_bool", "val": {"ref": "n"}}}
        ])
        self.assertTrue(run_spec(spec, {"n": -1}))

    def test_bool_to_int_type_error_checker(self):
        """bool_to_int on int should fail type check."""
        spec = fn_spec("f", [{"id": "x", "type": INT64}], INT64, [
            {"op": "return", "val": {"op": "bool_to_int", "val": {"ref": "x"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_int_to_bool_type_error_checker(self):
        """int_to_bool on bool should fail type check."""
        spec = fn_spec("f", [{"id": "b", "type": BOOL_T}], BOOL_T, [
            {"op": "return", "val": {"op": "int_to_bool", "val": {"ref": "b"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_bool_to_int_string_type_error_checker(self):
        """bool_to_int on string should fail type check."""
        spec = fn_spec("f", [{"id": "s", "type": STR_T}], INT64, [
            {"op": "return", "val": {"op": "bool_to_int", "val": {"ref": "s"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_int_to_bool_string_type_error_checker(self):
        """int_to_bool on string should fail type check."""
        spec = fn_spec("f", [{"id": "s", "type": STR_T}], BOOL_T, [
            {"op": "return", "val": {"op": "int_to_bool", "val": {"ref": "s"}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()


if __name__ == "__main__":
    unittest.main()
