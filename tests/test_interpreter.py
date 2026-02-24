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
import tempfile
from pathlib import Path
from unittest.mock import patch

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
LIST_INT = {"type": "list", "inner": INT64, "len": "dynamic"}
MAP_STR_INT = {"type": "map", "key": STR_T, "value": INT64}


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

    def test_malformed_import_missing_from_fails_l0(self):
        spec = {
            "nail": "0.3",
            "kind": "module",
            "id": "main",
            "imports": [{"module": "math_utils"}],
            "defs": [],
        }
        with self.assertRaises(CheckError):
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


class TestTypeAliasesV04(unittest.TestCase):

    def test_alias_in_function_signature(self):
        spec = module_spec(
            "m",
            defs=[
                fn_spec(
                    "identity",
                    [{"id": "user_id", "type": {"type": "alias", "name": "UserId"}}],
                    {"type": "alias", "name": "UserId"},
                    [{"op": "return", "val": {"ref": "user_id"}}],
                ),
            ],
            exports=["identity"],
            types={
                "UserId": {"type": "int", "bits": 64, "overflow": "panic"},
            },
        )
        result = run_spec(spec, args={"user_id": 42}, call_fn="identity")
        self.assertEqual(result, 42)

    def test_circular_alias_detection_raises(self):
        spec = module_spec(
            "m",
            defs=[],
            types={
                "A": {"type": "alias", "name": "B"},
                "B": {"type": "alias", "name": "A"},
            },
        )
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


class TestEffectfulOpContract(unittest.TestCase):

    def test_read_file_with_effect_declared_happy_path(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "read_file", "path": {"lit": "/tmp/demo.txt"}, "effect": "FS", "into": "contents"},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["FS"])
        Checker(spec).check()

    def test_http_get_with_effect_declared_happy_path(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "http_get", "url": {"lit": "https://example.com"}, "effect": "NET", "into": "body"},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["NET"])
        Checker(spec).check()

    def test_read_file_without_effect_field_fails(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "read_file", "path": {"lit": "/tmp/demo.txt"}},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["FS"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_http_get_without_effect_field_fails(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "http_get", "url": {"lit": "https://example.com"}},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["NET"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_read_file_operand_type_validation(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "read_file", "path": {"lit": 123}, "effect": "FS"},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["FS"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_http_get_operand_type_validation(self):
        spec = fn_spec("f", [], UNIT_T, [
            {"op": "http_get", "url": {"lit": True}, "effect": "NET"},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ], effects=["NET"])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_granular_fs_effect_allowed_path_happy_path(self):
        with tempfile.TemporaryDirectory() as td:
            allowed_root = Path(td) / "data"
            allowed_root.mkdir(parents=True, exist_ok=True)
            target_file = allowed_root / "ok.txt"
            target_file.write_text("ok", encoding="utf-8")
            spec = fn_spec("f", [], STR_T, [
                {"op": "read_file", "path": {"lit": str(target_file)}, "effect": "FS", "into": "contents"},
                {"op": "return", "val": {"ref": "contents"}},
            ], effects=[{"kind": "FS", "allow": [str(allowed_root)], "ops": ["read"]}])
            Checker(spec).check()
            result = Runtime(spec).run()
            self.assertEqual(result, "ok")

    def test_granular_fs_effect_denied_path_raises(self):
        with tempfile.TemporaryDirectory() as td:
            allowed_root = Path(td) / "allowed"
            denied_root = Path(td) / "denied"
            allowed_root.mkdir(parents=True, exist_ok=True)
            denied_root.mkdir(parents=True, exist_ok=True)
            denied_file = denied_root / "secret.txt"
            denied_file.write_text("nope", encoding="utf-8")
            spec = fn_spec("f", [], UNIT_T, [
                {"op": "read_file", "path": {"lit": str(denied_file)}, "effect": "FS"},
                {"op": "return", "val": {"lit": None, "type": UNIT_T}},
            ], effects=[{"kind": "FS", "allow": [str(allowed_root)], "ops": ["read"]}])
            with self.assertRaises(CheckError):
                Checker(spec).check()

    def test_granular_net_effect_allowed_domain_happy_path(self):
        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"payload"

        spec = fn_spec("f", [], STR_T, [
            {"op": "http_get", "url": {"lit": "https://api.example.com/v1"}, "effect": "NET", "into": "body"},
            {"op": "return", "val": {"ref": "body"}},
        ], effects=[{"kind": "Net", "allow": ["api.example.com"]}])
        Checker(spec).check()
        with patch("interpreter.runtime.urlopen", return_value=_FakeResponse()):
            result = Runtime(spec).run()
        self.assertEqual(result, "payload")

    def test_backward_compat_string_fs_still_works(self):
        with tempfile.TemporaryDirectory() as td:
            target_file = Path(td) / "legacy.txt"
            target_file.write_text("legacy", encoding="utf-8")
            spec = fn_spec("f", [], STR_T, [
                {"op": "read_file", "path": {"lit": str(target_file)}, "effect": "FS", "into": "contents"},
                {"op": "return", "val": {"ref": "contents"}},
            ], effects=["FS"])
            Checker(spec).check()
            result = Runtime(spec).run()
            self.assertEqual(result, "legacy")


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


class TestCollectionOpsV04(unittest.TestCase):

    def test_list_get_happy(self):
        spec = fn_spec("f", [{"id": "xs", "type": LIST_INT}], INT64, [
            {"op": "return", "val": {"op": "list_get", "list": {"ref": "xs"}, "index": {"lit": 1}}}
        ])
        result = run_spec(spec, args={"xs": [10, 20, 30]})
        self.assertEqual(result, 20)

    def test_list_push_happy(self):
        spec = fn_spec("f", [{"id": "xs", "type": LIST_INT}], INT64, [
            {"op": "list_push", "list": {"ref": "xs"}, "value": {"lit": 7}},
            {"op": "return", "val": {"op": "list_len", "list": {"ref": "xs"}}},
        ])
        result = run_spec(spec, args={"xs": [1, 2]})
        self.assertEqual(result, 3)

    def test_list_len_happy(self):
        spec = fn_spec("f", [{"id": "xs", "type": LIST_INT}], INT64, [
            {"op": "return", "val": {"op": "list_len", "list": {"ref": "xs"}}}
        ])
        result = run_spec(spec, args={"xs": [1, 2, 3, 4]})
        self.assertEqual(result, 4)

    def test_map_get_happy(self):
        spec = fn_spec("f", [{"id": "m", "type": MAP_STR_INT}], INT64, [
            {"op": "return", "val": {"op": "map_get", "map": {"ref": "m"}, "key": {"lit": "answer"}}}
        ])
        result = run_spec(spec, args={"m": {"answer": 42}})
        self.assertEqual(result, 42)

    def test_list_get_empty_list_raises(self):
        spec = fn_spec("f", [{"id": "xs", "type": LIST_INT}], INT64, [
            {"op": "return", "val": {"op": "list_get", "list": {"ref": "xs"}, "index": {"lit": 0}}}
        ])
        Checker(spec).check()
        with self.assertRaises(NailRuntimeError):
            Runtime(spec).run({"xs": []})

    def test_list_get_out_of_bounds_raises(self):
        spec = fn_spec("f", [{"id": "xs", "type": LIST_INT}], INT64, [
            {"op": "return", "val": {"op": "list_get", "list": {"ref": "xs"}, "index": {"lit": 2}}}
        ])
        Checker(spec).check()
        with self.assertRaises(NailRuntimeError):
            Runtime(spec).run({"xs": [1]})

    def test_list_push_type_mismatch_checker_raises(self):
        spec = fn_spec("f", [{"id": "xs", "type": LIST_INT}], UNIT_T, [
            {"op": "list_push", "list": {"ref": "xs"}, "value": {"lit": "bad"}},
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_map_get_key_type_mismatch_checker_raises(self):
        spec = fn_spec("f", [{"id": "m", "type": MAP_STR_INT}], INT64, [
            {"op": "return", "val": {"op": "map_get", "map": {"ref": "m"}, "key": {"lit": 1}}}
        ])
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_list_len_runtime_type_mismatch_raises_nail_type_error(self):
        spec = fn_spec("f", [{"id": "xs", "type": LIST_INT}], INT64, [
            {"op": "return", "val": {"op": "list_len", "list": {"ref": "xs"}}}
        ])
        Checker(spec).check()
        with self.assertRaises(NailTypeError):
            Runtime(spec).run({"xs": "not-a-list"})

    def test_map_get_runtime_key_type_mismatch_raises_nail_type_error(self):
        spec = fn_spec("f", [{"id": "m", "type": MAP_STR_INT}], INT64, [
            {"op": "return", "val": {"op": "map_get", "map": {"ref": "m"}, "key": {"lit": "x"}}}
        ])
        Checker(spec).check()
        with self.assertRaises(NailTypeError):
            Runtime(spec).run({"m": {1: 100}})


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

    # ------------------------------------------------------------------
    # Result type (v0.3 feature, Issue #3)
    # ------------------------------------------------------------------

    def _safe_div_spec(self) -> dict:
        INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
        STR   = {"type": "string", "encoding": "utf8"}
        return {
            "nail": "0.3", "kind": "fn", "id": "safe_div",
            "effects": [], "params": [
                {"id": "a", "type": INT64},
                {"id": "b", "type": INT64},
            ],
            "returns": {"type": "result", "ok": INT64, "err": STR},
            "body": [
                {"op": "if",
                 "cond": {"op": "eq", "l": {"ref": "b"}, "r": {"lit": 0}},
                 "then": [{"op": "return", "val": {"op": "err", "val": {"lit": "division by zero"}}}],
                 "else": [{"op": "return", "val": {"op": "ok",  "val": {"op": "/", "l": {"ref": "a"}, "r": {"ref": "b"}}}}]},
            ],
        }

    def test_result_checker_passes(self):
        """safe_div must pass checker."""
        Checker(self._safe_div_spec()).check()

    def test_result_ok_path(self):
        """safe_div(10, 2) → ok(5)."""
        from interpreter.runtime import NailResult
        r = Runtime(self._safe_div_spec()).run({"a": 10, "b": 2})
        self.assertIsInstance(r, NailResult)
        self.assertTrue(r.is_ok)
        self.assertEqual(r._val, 5)

    def test_result_err_path(self):
        """safe_div(5, 0) → err('division by zero')."""
        from interpreter.runtime import NailResult
        r = Runtime(self._safe_div_spec()).run({"a": 5, "b": 0})
        self.assertIsInstance(r, NailResult)
        self.assertTrue(r.is_err)
        self.assertEqual(r._val, "division by zero")

    def test_result_type_mismatch_raises(self):
        """Returning wrong ok type should raise CheckError."""
        spec = {
            "nail": "0.3", "kind": "fn", "id": "bad_result",
            "effects": [], "params": [],
            "returns": {"type": "result",
                        "ok": {"type": "int", "bits": 64, "overflow": "panic"},
                        "err": {"type": "string", "encoding": "utf8"}},
            "body": [
                # ok() with a bool — mismatch: declared ok is int
                {"op": "return", "val": {"op": "ok", "val": {"lit": True}}},
            ],
        }
        with self.assertRaises(CheckError):
            Checker(spec).check()

    # ------------------------------------------------------------------
    # Cross-module imports (v0.3 feature, Issue #4)
    # ------------------------------------------------------------------

    def _math_utils_spec(self) -> dict:
        INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
        return {
            "nail": "0.3", "kind": "module", "id": "math_utils", "imports": [],
            "defs": [
                {"nail": "0.3", "kind": "fn", "id": "add", "effects": [],
                 "params": [{"id": "a", "type": INT64}, {"id": "b", "type": INT64}],
                 "returns": INT64,
                 "body": [{"op": "return", "val": {"op": "+", "l": {"ref": "a"}, "r": {"ref": "b"}}}]},
                {"nail": "0.3", "kind": "fn", "id": "square", "effects": [],
                 "params": [{"id": "x", "type": INT64}], "returns": INT64,
                 "body": [{"op": "return", "val": {"op": "*", "l": {"ref": "x"}, "r": {"ref": "x"}}}]},
            ],
        }

    def _main_spec(self) -> dict:
        INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
        return {
            "nail": "0.3", "kind": "module", "id": "main",
            "imports": [{"module": "math_utils", "from": "math_utils.nail", "fns": ["add", "square"]}],
            "defs": [
                {"nail": "0.3", "kind": "fn", "id": "sum_of_squares", "effects": [],
                 "params": [{"id": "a", "type": INT64}, {"id": "b", "type": INT64}],
                 "returns": INT64,
                 "body": [
                     {"op": "let", "id": "sq_a", "type": INT64,
                      "val": {"op": "call", "module": "math_utils", "fn": "square", "args": [{"ref": "a"}]}},
                     {"op": "let", "id": "sq_b", "type": INT64,
                      "val": {"op": "call", "module": "math_utils", "fn": "square", "args": [{"ref": "b"}]}},
                     {"op": "return", "val": {"op": "call", "module": "math_utils", "fn": "add",
                                              "args": [{"ref": "sq_a"}, {"ref": "sq_b"}]}},
                 ]},
            ],
        }

    def test_cross_module_checker_passes(self):
        """Cross-module import checker must pass."""
        modules = {"math_utils": self._math_utils_spec()}
        Checker(self._main_spec(), modules=modules).check()

    def test_cross_module_runtime(self):
        """sum_of_squares(3, 4) should return 25."""
        modules = {"math_utils": self._math_utils_spec()}
        rt = Runtime(self._main_spec(), modules=modules)
        self.assertEqual(rt.run_fn("sum_of_squares", {"a": 3, "b": 4}), 25)

    def test_cross_module_missing_module_raises(self):
        """Calling without providing the module should raise CheckError."""
        with self.assertRaises(CheckError):
            Checker(self._main_spec()).check()  # no modules provided

    def test_cross_module_missing_fn_raises(self):
        """Importing a function that doesn't exist in the module must raise."""
        INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
        main = {
            "nail": "0.3", "kind": "module", "id": "main",
            "imports": [{"module": "math_utils", "from": "math_utils.nail", "fns": ["nonexistent_fn"]}],
            "defs": [],
        }
        modules = {"math_utils": self._math_utils_spec()}
        with self.assertRaises(CheckError):
            Checker(main, modules=modules).check()

    def test_cross_module_effect_propagation_raises(self):
        """Cross-module call to IO fn from pure fn must raise CheckError."""
        INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
        io_mod = {
            "nail": "0.3", "kind": "module", "id": "io_utils", "imports": [],
            "defs": [
                {"nail": "0.3", "kind": "fn", "id": "print_num", "effects": ["IO"],
                 "params": [{"id": "n", "type": INT64}], "returns": {"type": "unit"},
                 "body": []},
            ],
        }
        main = {
            "nail": "0.3", "kind": "module", "id": "main",
            "imports": [{"module": "io_utils", "from": "io_utils.nail", "fns": ["print_num"]}],
            "defs": [
                {"nail": "0.3", "kind": "fn", "id": "pure_fn", "effects": [],  # pure!
                 "params": [{"id": "n", "type": INT64}], "returns": INT64,
                 "body": [
                     {"op": "call", "module": "io_utils", "fn": "print_num", "args": [{"ref": "n"}]},
                     {"op": "return", "val": {"ref": "n"}},
                 ]},
            ],
        }
        with self.assertRaises(CheckError):
            Checker(main, modules={"io_utils": io_mod}).check()

    def test_cross_module_circular_import_raises(self):
        """Circular imports must raise CheckError."""
        a_mod = {
            "nail": "0.3", "kind": "module", "id": "a",
            "imports": [{"module": "b", "from": "b.nail", "fns": []}],
            "defs": [],
        }
        b_mod = {
            "nail": "0.3", "kind": "module", "id": "b",
            "imports": [{"module": "a", "from": "a.nail", "fns": []}],
            "defs": [],
        }
        with self.assertRaises(CheckError):
            Checker(a_mod, modules={"a": a_mod, "b": b_mod}).check()

    def test_match_result_both_branches_required(self):
        """match_result guarantees return if both branches return."""
        INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
        STR   = {"type": "string", "encoding": "utf8"}
        spec = {
            "nail": "0.3", "kind": "fn", "id": "unwrap_or",
            "effects": [], "params": [
                {"id": "res", "type": {"type": "result", "ok": INT64, "err": STR}},
            ],
            "returns": INT64,
            "body": [
                {"op": "match_result", "val": {"ref": "res"},
                 "ok_bind": "v",   "ok_body":  [{"op": "return", "val": {"ref": "v"}}],
                 "err_bind": "_e", "err_body": [{"op": "return", "val": {"lit": -1}}]},
            ],
        }
        Checker(spec).check()  # must not raise
        from interpreter.runtime import NailResult
        r_ok  = Runtime(spec).run({"res": NailResult("ok",  42)})
        r_err = Runtime(spec).run({"res": NailResult("err", "oops")})
        self.assertEqual(r_ok,  42)
        self.assertEqual(r_err, -1)


class TestV05EnumADT(unittest.TestCase):

    def _color_type(self):
        return {
            "type": "enum",
            "variants": [
                {"tag": "Red"},
                {"tag": "Green"},
                {"tag": "Blue"},
            ],
        }

    def _shape_type(self):
        f64 = {"type": "float", "bits": 64}
        return {
            "type": "enum",
            "variants": [
                {"tag": "Circle", "fields": [{"name": "radius", "type": f64}]},
                {"tag": "Rectangle", "fields": [{"name": "w", "type": f64}, {"name": "h", "type": f64}]},
            ],
        }

    def test_enum_unit_construct_and_match(self):
        spec = module_spec(
            "enum_mod",
            defs=[
                fn_spec(
                    "main",
                    [],
                    INT64,
                    [
                        {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
                        {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                            {"tag": "Red", "body": [{"op": "return", "val": {"lit": 1}}]},
                            {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                            {"tag": "Blue", "body": [{"op": "return", "val": {"lit": 3}}]},
                        ]},
                    ],
                )
            ],
            types={"Color": self._color_type()},
        )
        self.assertEqual(run_spec(spec, call_fn="main"), 1)

    def test_enum_with_fields_construct_and_match(self):
        spec = module_spec(
            "enum_mod",
            defs=[
                fn_spec(
                    "main",
                    [],
                    {"type": "float", "bits": 64},
                    [
                        {
                            "op": "enum_make",
                            "tag": "Circle",
                            "fields": {"radius": {"lit": 3.5, "type": {"type": "float", "bits": 64}}},
                            "into": "shape",
                        },
                        {"op": "match_enum", "val": {"ref": "shape"}, "cases": [
                            {"tag": "Circle", "binds": {"radius": "r"}, "body": [{"op": "return", "val": {"ref": "r"}}]},
                            {
                                "tag": "Rectangle",
                                "binds": {"w": "width", "h": "height"},
                                "body": [{"op": "return", "val": {"op": "+", "l": {"ref": "width"}, "r": {"ref": "height"}}}],
                            },
                        ]},
                    ],
                )
            ],
            types={"Shape": self._shape_type()},
        )
        self.assertEqual(run_spec(spec, call_fn="main"), 3.5)

    def test_match_enum_exhaustiveness_missing_tag_without_default_raises(self):
        spec = module_spec(
            "enum_mod",
            defs=[
                fn_spec(
                    "main",
                    [],
                    INT64,
                    [
                        {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
                        {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                            {"tag": "Red", "body": [{"op": "return", "val": {"lit": 1}}]},
                            {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                        ]},
                    ],
                )
            ],
            types={"Color": self._color_type()},
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_enum_make_wrong_tag_raises(self):
        spec = module_spec(
            "enum_mod",
            defs=[
                fn_spec(
                    "main",
                    [],
                    INT64,
                    [
                        {"op": "enum_make", "tag": "Purple", "fields": {}, "into": "c"},
                        {"op": "return", "val": {"lit": 0}},
                    ],
                )
            ],
            types={"Color": self._color_type()},
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_enum_make_field_type_mismatch_raises(self):
        spec = module_spec(
            "enum_mod",
            defs=[
                fn_spec(
                    "main",
                    [],
                    INT64,
                    [
                        {"op": "enum_make", "tag": "Circle", "fields": {"radius": {"lit": True}}, "into": "shape"},
                        {"op": "return", "val": {"lit": 0}},
                    ],
                )
            ],
            types={"Shape": self._shape_type()},
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()

    def test_match_enum_binds_introduce_typed_vars(self):
        int_enum = {
            "type": "enum",
            "variants": [
                {"tag": "I", "fields": [{"name": "v", "type": INT64}]},
                {"tag": "None"},
            ],
        }
        spec = module_spec(
            "enum_mod",
            defs=[
                fn_spec(
                    "main",
                    [],
                    INT64,
                    [
                        {"op": "enum_make", "tag": "I", "fields": {"v": {"lit": 41}}, "into": "x"},
                        {"op": "match_enum", "val": {"ref": "x"}, "cases": [
                            {
                                "tag": "I",
                                "binds": {"v": "n"},
                                "body": [{"op": "return", "val": {"op": "+", "l": {"ref": "n"}, "r": {"lit": 1}}}],
                            },
                            {"tag": "None", "body": [{"op": "return", "val": {"lit": 0}}]},
                        ]},
                    ],
                )
            ],
            types={"IntWrap": int_enum},
        )
        self.assertEqual(run_spec(spec, call_fn="main"), 42)

    def test_match_enum_default_allows_non_exhaustive_cases(self):
        spec = module_spec(
            "enum_mod",
            defs=[
                fn_spec(
                    "main",
                    [],
                    INT64,
                    [
                        {"op": "enum_make", "tag": "Blue", "fields": {}, "into": "c"},
                        {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                            {"tag": "Red", "body": [{"op": "return", "val": {"lit": 1}}]},
                        ], "default": [{"op": "return", "val": {"lit": 9}}]},
                    ],
                )
            ],
            types={"Color": self._color_type()},
        )
        self.assertEqual(run_spec(spec, call_fn="main"), 9)

    def test_match_enum_invalid_bind_field_raises(self):
        spec = module_spec(
            "enum_mod",
            defs=[
                fn_spec(
                    "main",
                    [],
                    INT64,
                    [
                        {"op": "enum_make", "tag": "Red", "fields": {}, "into": "c"},
                        {"op": "match_enum", "val": {"ref": "c"}, "cases": [
                            {"tag": "Red", "binds": {"radius": "r"}, "body": [{"op": "return", "val": {"lit": 1}}]},
                            {"tag": "Green", "body": [{"op": "return", "val": {"lit": 2}}]},
                            {"tag": "Blue", "body": [{"op": "return", "val": {"lit": 3}}]},
                        ]},
                    ],
                )
            ],
            types={"Color": self._color_type()},
        )
        with self.assertRaises(CheckError):
            Checker(spec).check()


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
