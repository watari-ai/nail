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


def module_spec(module_id, defs, exports=None):
    return {
        "nail": "0.1.0",
        "kind": "module",
        "id": module_id,
        "exports": exports or [],
        "defs": defs,
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


class TestFunctionCalls(unittest.TestCase):

    def test_pure_calls_pure_ok(self):
        callee = fn_spec("add", [
            {"id": "a", "type": INT64},
            {"id": "b", "type": INT64},
        ], INT64, [{"op": "return", "val": {"op": "+", "l": {"ref": "a"}, "r": {"ref": "b"}}}])
        caller = fn_spec("main", [], INT64, [
            {"op": "return", "val": {"op": "call", "fn": "add", "args": [{"lit": 1}, {"lit": 2}]}}
        ])
        spec = module_spec("m", [caller, callee], exports=["main", "add"])
        result = run_spec(spec, call_fn="main")
        self.assertEqual(result, 3)

    def test_io_calls_io_ok(self):
        printer = fn_spec("print_header", [{"id": "s", "type": STR_T}], UNIT_T, [
            {"op": "print", "val": {"ref": "s"}, "effect": "IO"},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["IO"])
        caller = fn_spec("main", [], UNIT_T, [
            {"op": "call", "fn": "print_header", "args": [{"lit": "hello"}]},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["IO"])
        spec = module_spec("m", [caller, printer], exports=["main"])
        result = run_spec(spec, call_fn="main")
        self.assertIs(result, UNIT)

    def test_pure_calls_io_fails(self):
        io_fn = fn_spec("io_fn", [], UNIT_T, [
            {"op": "print", "val": {"lit": "x"}, "effect": "IO"},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["IO"])
        pure_main = fn_spec("main", [], UNIT_T, [
            {"op": "call", "fn": "io_fn", "args": []},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=[])
        spec = module_spec("m", [pure_main, io_fn], exports=["main"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_call_arg_type_mismatch_fails(self):
        callee = fn_spec("id_int", [{"id": "x", "type": INT64}], INT64, [
            {"op": "return", "val": {"ref": "x"}}
        ])
        caller = fn_spec("main", [], INT64, [
            {"op": "return", "val": {"op": "call", "fn": "id_int", "args": [{"lit": "oops"}]}}
        ])
        spec = module_spec("m", [caller, callee], exports=["main"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_call_arg_count_mismatch_fails(self):
        callee = fn_spec("one_arg", [{"id": "x", "type": INT64}], INT64, [
            {"op": "return", "val": {"ref": "x"}}
        ])
        caller = fn_spec("main", [], INT64, [
            {"op": "return", "val": {"op": "call", "fn": "one_arg", "args": [{"lit": 1}, {"lit": 2}]}}
        ])
        spec = module_spec("m", [caller, callee], exports=["main"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_call_unknown_function_fails(self):
        main = fn_spec("main", [], INT64, [
            {"op": "return", "val": {"op": "call", "fn": "missing", "args": []}}
        ])
        spec = module_spec("m", [main], exports=["main"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_direct_recursion_fails(self):
        loop_fn = fn_spec("a", [], INT64, [
            {"op": "return", "val": {"op": "call", "fn": "a", "args": []}}
        ])
        spec = module_spec("m", [loop_fn], exports=["a"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_mutual_recursion_fails(self):
        fn_a = fn_spec("a", [], INT64, [
            {"op": "return", "val": {"op": "call", "fn": "b", "args": []}}
        ])
        fn_b = fn_spec("b", [], INT64, [
            {"op": "return", "val": {"op": "call", "fn": "a", "args": []}}
        ])
        spec = module_spec("m", [fn_a, fn_b], exports=["a"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_call_in_fn_kind_fails(self):
        spec = fn_spec("main", [], INT64, [
            {"op": "return", "val": {"op": "call", "fn": "main", "args": []}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()


class TestCallOpV024(unittest.TestCase):

    def test_call_returns_value(self):
        result = run_file("call_demo.nail")
        self.assertEqual(result, 120)

    def test_effect_propagation_main_pure_calls_io_fails(self):
        path = Path(__file__).parent.parent / "examples" / "bad_effect_call.nail"
        with open(path) as f:
            spec = json.load(f)
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_unknown_function_call_raises(self):
        helper = fn_spec("helper", [], INT64, [{"op": "return", "val": {"lit": 1}}])
        main = fn_spec("main", [], INT64, [
            {"op": "return", "val": {"op": "call", "fn": "does_not_exist", "args": []}}
        ])
        spec = module_spec("m", [main, helper], exports=["main"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_call_arg_type_mismatch_raises(self):
        helper = fn_spec("helper", [{"id": "n", "type": INT64}], INT64, [
            {"op": "return", "val": {"ref": "n"}}
        ])
        main = fn_spec("main", [], INT64, [
            {"op": "return", "val": {"op": "call", "fn": "helper", "args": [{"lit": "bad"}]}}
        ])
        spec = module_spec("m", [main, helper], exports=["main"])
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


# ──────────────────────────────────────────────
#  v0.2 Tests — Checker Fixes
# ──────────────────────────────────────────────

class TestMutValidation(unittest.TestCase):
    """Test that assign to immutable variable raises CheckError."""

    def test_assign_to_immutable_raises(self):
        """assign to a variable declared without mut: true must fail."""
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "let", "id": "x", "type": INT64, "val": {"lit": 5}},
            # no "mut": true above → x is immutable
            {"op": "assign", "id": "x", "val": {"lit": 10}},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_assign_to_mutable_ok(self):
        """assign to a mut: true variable must succeed."""
        spec = fn_spec("f", [], INT64, [
            {"op": "let", "id": "x", "type": INT64, "val": {"lit": 5}, "mut": True},
            {"op": "assign", "id": "x", "val": {"lit": 10}},
            {"op": "return", "val": {"ref": "x"}},
        ])
        result = run_spec(spec)
        assert result == 10

    def test_assign_mutable_in_loop(self):
        """assign inside loop body to outer mutable variable must succeed."""
        spec = fn_spec("f", [], INT64, [
            {"op": "let", "id": "total", "type": INT64, "val": {"lit": 0}, "mut": True},
            {
                "op": "loop", "bind": "i",
                "from": {"lit": 1}, "to": {"lit": 4}, "step": {"lit": 1},
                "body": [
                    {"op": "assign", "id": "total",
                     "val": {"op": "+", "l": {"ref": "total"}, "r": {"ref": "i"}}}
                ]
            },
            {"op": "return", "val": {"ref": "total"}},
        ])
        result = run_spec(spec)
        assert result == 6  # 1+2+3

    def test_immutable_in_loop_raises(self):
        """assign inside loop body to outer immutable variable must fail."""
        spec = fn_spec("f", [], INT64, [
            {"op": "let", "id": "total", "type": INT64, "val": {"lit": 0}},  # no mut
            {
                "op": "loop", "bind": "i",
                "from": {"lit": 1}, "to": {"lit": 4}, "step": {"lit": 1},
                "body": [
                    {"op": "assign", "id": "total",
                     "val": {"op": "+", "l": {"ref": "total"}, "r": {"ref": "i"}}}
                ]
            },
            {"op": "return", "val": {"ref": "total"}},
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()


class TestUnknownOp(unittest.TestCase):
    """Test that unknown ops raise CheckError (Zero Ambiguity)."""

    def test_unknown_op_raises(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "frobnicate", "val": {"lit": 42}},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_unknown_expr_op_raises(self):
        spec = fn_spec("f", [], INT64, [
            {"op": "return", "val": {"op": "quantum_add", "l": {"lit": 1}, "r": {"lit": 2}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()


class TestCanonicalForm(unittest.TestCase):
    """Test JCS canonical form checking."""

    def _canonical_spec(self):
        return {
            "nail": "0.1.0",
            "kind": "fn",
            "id": "f",
            "effects": [],
            "params": [],
            "returns": {"type": "unit"},
            "body": [{"op": "return", "val": {"lit": None, "type": {"type": "unit"}}}],
        }

    def test_strict_canonical_ok(self):
        spec = self._canonical_spec()
        canonical_text = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        checker = Checker(spec, raw_text=canonical_text, strict=True)
        checker.check()  # should not raise

    def test_strict_non_canonical_raises(self):
        spec = self._canonical_spec()
        # pretty-printed is NOT canonical
        pretty_text = json.dumps(spec, indent=2)
        checker = Checker(spec, raw_text=pretty_text, strict=True)
        with self.assertRaises(CheckError):
            checker.check()

    def test_non_strict_non_canonical_ok(self):
        spec = self._canonical_spec()
        pretty_text = json.dumps(spec, indent=2)
        checker = Checker(spec, raw_text=pretty_text, strict=False)
        checker.check()  # non-strict: should not raise

    def test_canonicalize_output(self):
        """nail canonicalize should produce sort_keys, no-spaces output."""
        spec = {"z": 1, "a": 2, "m": [3, 1, 2]}
        out = json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        self.assertEqual(out, '{"a":2,"m":[3,1,2],"z":1}')

    # ------------------------------------------------------------------
    # Return guarantee (Codex/Opus High #1)
    # ------------------------------------------------------------------

    def test_missing_return_raises(self):
        """Function with no return statement must raise CheckError."""
        spec = {
            "nail": "0.2", "kind": "fn", "id": "no_return",
            "effects": [], "params": [],
            "returns": {"type": "int", "bits": 64, "overflow": "panic"},
            "body": [
                {"op": "let", "id": "x", "type": {"type": "int", "bits": 64, "overflow": "panic"}, "val": {"lit": 1}},
            ],
        }
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_partial_return_in_if_raises(self):
        """If only one branch returns, checker must raise."""
        spec = {
            "nail": "0.2", "kind": "fn", "id": "partial",
            "effects": [],
            "params": [{"id": "b", "type": {"type": "bool"}}],
            "returns": {"type": "int", "bits": 64, "overflow": "panic"},
            "body": [
                {"op": "if",
                 "cond": {"ref": "b"},
                 "then": [{"op": "return", "val": {"lit": 1}}],
                 "else": []},  # else doesn't return
            ],
        }
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_both_branches_return_ok(self):
        """If both then and else return, checker must pass."""
        spec = {
            "nail": "0.2", "kind": "fn", "id": "both_return",
            "effects": [],
            "params": [{"id": "b", "type": {"type": "bool"}}],
            "returns": {"type": "int", "bits": 64, "overflow": "panic"},
            "body": [
                {"op": "if",
                 "cond": {"ref": "b"},
                 "then": [{"op": "return", "val": {"lit": 1}}],
                 "else": [{"op": "return", "val": {"lit": 0}}]},
            ],
        }
        Checker(spec).check()  # must not raise

    # ------------------------------------------------------------------
    # Overflow mode (Codex Medium #5)
    # ------------------------------------------------------------------

    def test_overflow_wrap_raises(self):
        """v0.2: overflow:'wrap' must raise NailTypeError."""
        from interpreter.types import NailTypeError
        with self.assertRaises(NailTypeError):
            from interpreter.types import IntType
            IntType(bits=64, overflow="wrap")

    def test_overflow_sat_raises(self):
        """v0.2: overflow:'sat' must raise NailTypeError."""
        from interpreter.types import NailTypeError, IntType
        with self.assertRaises(NailTypeError):
            IntType(bits=64, overflow="sat")

    # ------------------------------------------------------------------
    # Expression-level overflow (v0.3 feature, Issue #2)
    # ------------------------------------------------------------------

    def _make_overflow_fn(self, overflow_mode: str) -> dict:
        """Helper: fn that does INT64_MAX + 1 with given overflow mode."""
        INT64_MAX = (1 << 63) - 1
        return {
            "nail": "0.3", "kind": "fn", "id": "overflow_test",
            "effects": [], "params": [],
            "returns": {"type": "int", "bits": 64, "overflow": "panic"},
            "body": [
                {"op": "return", "val": {
                    "op": "+", "overflow": overflow_mode,
                    "l": {"lit": INT64_MAX}, "r": {"lit": 1},
                }},
            ],
        }

    def test_overflow_wrap(self):
        """overflow:wrap on INT64_MAX+1 should give INT64_MIN."""
        spec = self._make_overflow_fn("wrap")
        Checker(spec).check()
        result = Runtime(spec).run({})
        self.assertEqual(result, -(1 << 63))  # INT64_MIN

    def test_overflow_sat(self):
        """overflow:sat on INT64_MAX+1 should give INT64_MAX (clamped)."""
        spec = self._make_overflow_fn("sat")
        Checker(spec).check()
        result = Runtime(spec).run({})
        self.assertEqual(result, (1 << 63) - 1)  # INT64_MAX

    def test_overflow_panic_raises(self):
        """overflow:panic (default) on INT64_MAX+1 should raise NailOverflowError."""
        from interpreter.runtime import NailOverflowError
        spec = self._make_overflow_fn("panic")
        Checker(spec).check()
        with self.assertRaises(NailOverflowError):
            Runtime(spec).run({})

    def test_overflow_invalid_mode_raises(self):
        """Invalid overflow mode on expression should raise CheckError."""
        spec = {
            "nail": "0.3", "kind": "fn", "id": "bad_overflow_mode",
            "effects": [], "params": [],
            "returns": {"type": "int", "bits": 64, "overflow": "panic"},
            "body": [
                {"op": "return", "val": {
                    "op": "+", "overflow": "truncate",  # invalid
                    "l": {"lit": 1}, "r": {"lit": 1},
                }},
            ],
        }
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_overflow_on_float_raises(self):
        """overflow mode on float arithmetic should raise CheckError."""
        spec = {
            "nail": "0.3", "kind": "fn", "id": "float_overflow",
            "effects": [], "params": [],
            "returns": {"type": "float", "bits": 64},
            "body": [
                {"op": "return", "val": {
                    "op": "+", "overflow": "sat",  # invalid on float
                    "l": {"lit": 1.0}, "r": {"lit": 2.0},
                }},
            ],
        }
        with self.assertRaises(CheckError):
            Checker(spec).check()


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
