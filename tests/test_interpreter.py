#!/usr/bin/env python3
"""
NAIL Interpreter Test Suite — Phase 1

Covers: L0 schema, L1 types, L2 effects, runtime execution.
Run: python3 -m pytest tests/ -v
  or: python3 tests/test_interpreter.py
"""

import sys
import json
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter import Checker, Runtime, CheckError, NailTypeError, NailEffectError, NailRuntimeError
from interpreter.runtime import UNIT


def run_file(filename: str, args: dict | None = None, call_fn: str | None = None):
    """Helper: check + run a .nail file, return result."""
    path = Path(__file__).parent.parent / "examples" / filename
    with open(path) as f:
        spec = json.load(f)
    Checker(spec).check()
    rt = Runtime(spec)
    if call_fn:
        return rt.run_fn(call_fn, args or {})
    return rt.run(args)


def run_spec(spec: dict, args: dict | None = None, call_fn: str | None = None):
    """Helper: check + run a spec dict, return result."""
    Checker(spec).check()
    rt = Runtime(spec)
    if call_fn:
        return rt.run_fn(call_fn, args or {})
    return rt.run(args)


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


# ──────────────────────────────────────────────
#  L0 Tests — Schema Validation
# ──────────────────────────────────────────────

class TestL0Schema(unittest.TestCase):

    def test_missing_nail_version(self):
        spec = {"kind": "fn", "id": "f", "effects": [], "params": [], "returns": UNIT_T, "body": []}
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_missing_kind(self):
        spec = {"nail": "0.1.0", "id": "f", "effects": [], "params": [], "returns": UNIT_T, "body": []}
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_unknown_kind(self):
        spec = {"nail": "0.1.0", "kind": "class", "id": "f", "effects": [], "params": [], "returns": UNIT_T, "body": []}
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_unknown_effect(self):
        spec = fn_spec("f", [], UNIT_T, [], effects=["MAGIC"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_valid_fn(self):
        spec = fn_spec("f", [], UNIT_T,
                       [{"op": "return", "val": {"lit": None, "type": UNIT_T}}])
        Checker(spec).check()  # Should not raise

    def test_valid_module(self):
        spec = {
            "nail": "0.1.0", "kind": "module", "id": "m", "exports": [],
            "defs": [fn_spec("f", [], UNIT_T,
                             [{"op": "return", "val": {"lit": None, "type": UNIT_T}}])]
        }
        Checker(spec).check()


# ──────────────────────────────────────────────
#  L1 Tests — Type Checking
# ──────────────────────────────────────────────

class TestL1Types(unittest.TestCase):

    def test_return_type_mismatch(self):
        spec = fn_spec("f", [], INT64, [{"op": "return", "val": {"lit": True}}])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_arithmetic_type_mismatch(self):
        spec = fn_spec("f", [], BOOL_T, [
            {"op": "return", "val": {"op": "+", "l": {"lit": 1}, "r": {"lit": True}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_undefined_variable(self):
        spec = fn_spec("f", [], INT64, [
            {"op": "return", "val": {"ref": "undefined_var"}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_let_type_annotation_mismatch(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "let", "id": "x", "type": INT64, "val": {"lit": True}},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_int_to_str_type(self):
        spec = fn_spec("f", [], STR_T, [
            {"op": "return", "val": {"op": "int_to_str", "v": {"lit": 42}}}
        ])
        Checker(spec).check()

    def test_concat_type(self):
        spec = fn_spec("f", [], STR_T, [
            {"op": "return", "val": {"op": "concat", "l": {"lit": "hello "}, "r": {"lit": "world"}}}
        ])
        Checker(spec).check()

    def test_concat_type_mismatch(self):
        spec = fn_spec("f", [], STR_T, [
            {"op": "return", "val": {"op": "concat", "l": {"lit": "hello "}, "r": {"lit": 42}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()


# ──────────────────────────────────────────────
#  L2 Tests — Effect Checking
# ──────────────────────────────────────────────

class TestL2Effects(unittest.TestCase):

    def test_print_without_io_effect(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "print", "val": {"lit": "hi"}, "effect": "IO"},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=[])  # IO NOT declared
        with self.assertRaises(NailEffectError):
            Checker(spec).check()

    def test_print_with_io_effect(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "print", "val": {"lit": "hi"}, "effect": "IO"},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["IO"])
        Checker(spec).check()  # Should not raise

    def test_print_without_effect_field(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "print", "val": {"lit": "hi"}},  # missing "effect" field
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["IO"])
        with self.assertRaises(CheckError):
            Checker(spec).check()


# ──────────────────────────────────────────────
#  Runtime Tests
# ──────────────────────────────────────────────

class TestRuntime(unittest.TestCase):

    def test_hello_world(self, capsys=None):
        result = run_file("hello.nail")
        self.assertIs(result, UNIT)

    def test_add(self):
        result = run_file("add.nail", {"a": 3, "b": 5})
        self.assertEqual(result, 8)

    def test_add_negative(self):
        result = run_file("add.nail", {"a": -10, "b": 3})
        self.assertEqual(result, -7)

    def test_sum_loop(self):
        result = run_file("sum_loop.nail")
        self.assertIs(result, UNIT)

    def test_max_of_two_a_larger(self):
        result = run_file("max_of_two.nail", {"a": 100, "b": 42})
        self.assertEqual(result, 100)

    def test_max_of_two_b_larger(self):
        result = run_file("max_of_two.nail", {"a": 3, "b": 99})
        self.assertEqual(result, 99)

    def test_max_of_two_equal(self):
        result = run_file("max_of_two.nail", {"a": 7, "b": 7})
        self.assertEqual(result, 7)

    def test_is_even_true(self):
        result = run_file("is_even.nail", {"n": 8})
        self.assertEqual(result, True)

    def test_is_even_false(self):
        result = run_file("is_even.nail", {"n": 7})
        self.assertEqual(result, False)

    def test_is_even_zero(self):
        result = run_file("is_even.nail", {"n": 0})
        self.assertEqual(result, True)

    def test_factorial_0(self):
        result = run_file("factorial.nail", {"n": 0})
        self.assertEqual(result, 1)

    def test_factorial_1(self):
        result = run_file("factorial.nail", {"n": 1})
        self.assertEqual(result, 1)

    def test_factorial_5(self):
        result = run_file("factorial.nail", {"n": 5})
        self.assertEqual(result, 120)

    def test_factorial_10(self):
        result = run_file("factorial.nail", {"n": 10})
        self.assertEqual(result, 3628800)

    def test_fibonacci_0(self):
        result = run_file("fibonacci.nail", {"n": 0})
        self.assertEqual(result, 0)

    def test_fibonacci_1(self):
        result = run_file("fibonacci.nail", {"n": 1})
        self.assertEqual(result, 1)

    def test_fibonacci_10(self):
        result = run_file("fibonacci.nail", {"n": 10})
        self.assertEqual(result, 55)

    def test_fibonacci_20(self):
        result = run_file("fibonacci.nail", {"n": 20})
        self.assertEqual(result, 6765)

    def test_math_module_add(self):
        result = run_file("math_module.nail", {"a": 3, "b": 4}, call_fn="add")
        self.assertEqual(result, 7)

    def test_math_module_multiply(self):
        result = run_file("math_module.nail", {"a": 6, "b": 7}, call_fn="multiply")
        self.assertEqual(result, 42)

    def test_math_module_abs_positive(self):
        result = run_file("math_module.nail", {"x": 5}, call_fn="abs_val")
        self.assertEqual(result, 5)

    def test_math_module_abs_negative(self):
        result = run_file("math_module.nail", {"x": -5}, call_fn="abs_val")
        self.assertEqual(result, 5)

    def test_math_module_clamp_below(self):
        result = run_file("math_module.nail", {"val": -10, "lo": 0, "hi": 100}, call_fn="clamp")
        self.assertEqual(result, 0)

    def test_math_module_clamp_above(self):
        result = run_file("math_module.nail", {"val": 150, "lo": 0, "hi": 100}, call_fn="clamp")
        self.assertEqual(result, 100)

    def test_math_module_clamp_within(self):
        result = run_file("math_module.nail", {"val": 50, "lo": 0, "hi": 100}, call_fn="clamp")
        self.assertEqual(result, 50)


# ──────────────────────────────────────────────
#  Runtime Error Tests
# ──────────────────────────────────────────────

class TestRuntimeErrors(unittest.TestCase):

    def test_missing_argument(self):
        spec = fn_spec("f", [{"id": "x", "type": INT64}], INT64, [
            {"op": "return", "val": {"ref": "x"}}
        ])
        with self.assertRaises(NailRuntimeError):
            Runtime(spec).run()  # Missing 'x'

    def test_division_by_zero(self):
        spec = fn_spec("f", [], INT64, [
            {"op": "return", "val": {"op": "/", "l": {"lit": 10}, "r": {"lit": 0}}}
        ])
        Checker(spec).check()
        with self.assertRaises(NailRuntimeError):
            Runtime(spec).run()

    def test_overflow_detection(self):
        MAX64 = (1 << 63) - 1
        spec = fn_spec("f", [], INT64, [
            {"op": "return", "val": {"op": "+", "l": {"lit": MAX64}, "r": {"lit": 1}}}
        ])
        Checker(spec).check()
        from interpreter.runtime import NailOverflowError
        with self.assertRaises(NailOverflowError):
            Runtime(spec).run()

    def test_assign_to_undeclared(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "assign", "id": "ghost", "val": {"lit": 1}},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ])
        with self.assertRaises((CheckError, NailRuntimeError)):
            run_spec(spec)

    def test_module_call_nonexistent_fn(self):
        spec = {
            "nail": "0.1.0", "kind": "module", "id": "m", "exports": [],
            "defs": [fn_spec("foo", [], INT64, [{"op": "return", "val": {"lit": 1}}])]
        }
        Checker(spec).check()
        rt = Runtime(spec)
        with self.assertRaises(NailRuntimeError):
            rt.run_fn("nonexistent")


# ──────────────────────────────────────────────
#  String Ops Tests
# ──────────────────────────────────────────────

class TestStringOps(unittest.TestCase):

    def test_concat(self):
        spec = fn_spec("f", [], STR_T, [
            {"op": "return", "val": {"op": "concat", "l": {"lit": "foo"}, "r": {"lit": "bar"}}}
        ])
        result = run_spec(spec)
        self.assertEqual(result, "foobar")

    def test_int_to_str(self):
        spec = fn_spec("f", [], STR_T, [
            {"op": "return", "val": {"op": "int_to_str", "v": {"lit": 42}}}
        ])
        result = run_spec(spec)
        self.assertEqual(result, "42")

    def test_bool_to_str_true(self):
        spec = fn_spec("f", [], STR_T, [
            {"op": "return", "val": {"op": "bool_to_str", "v": {"lit": True}}}
        ])
        result = run_spec(spec)
        self.assertEqual(result, "true")

    def test_bool_to_str_false(self):
        spec = fn_spec("f", [], STR_T, [
            {"op": "return", "val": {"op": "bool_to_str", "v": {"lit": False}}}
        ])
        result = run_spec(spec)
        self.assertEqual(result, "false")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
