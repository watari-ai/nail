#!/usr/bin/env python3
"""
Nail-Lens Test Suite — v0.1.0

Tests for: inspect_spec, diff, validate, effects commands.
Run: python3 -m pytest tests/test_nail_lens.py -v
"""

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from nail_lens.inspector import (
    format_type,
    inspect_spec,
    _get_functions,
    _get_all_effects,
    _get_types,
    _collect_calls_body,
)

# ---------------------------------------------------------------------------
# Spec fixtures
# ---------------------------------------------------------------------------

INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
BOOL_T = {"type": "bool"}
STR_T = {"type": "string"}
UNIT_T = {"type": "unit"}
FLOAT64 = {"type": "float", "bits": 64}


def make_fn_spec(fn_id, params, returns, body=None, effects=None, nail="0.1.0", meta=None):
    spec = {
        "nail": nail,
        "kind": "fn",
        "id": fn_id,
        "effects": effects or [],
        "params": params,
        "returns": returns,
        "body": body or [{"op": "return", "val": {"lit": 0}}],
    }
    if meta:
        spec["meta"] = meta
    return spec


def make_module_spec(mod_id, defs, exports=None, types=None, nail="0.1.0", meta=None, termination=None):
    spec = {
        "nail": nail,
        "kind": "module",
        "id": mod_id,
        "defs": defs,
        "exports": exports or [d["id"] for d in defs],
    }
    if types:
        spec["types"] = types
    if meta:
        spec["meta"] = meta
    if termination:
        spec["termination"] = termination
    return spec


# ---------------------------------------------------------------------------
# Test 1: format_type — basic scalar types
# ---------------------------------------------------------------------------

class TestFormatType(unittest.TestCase):
    def test_int(self):
        self.assertEqual(format_type({"type": "int", "bits": 64, "overflow": "panic"}), "int64")

    def test_int_32(self):
        self.assertEqual(format_type({"type": "int", "bits": 32, "overflow": "panic"}), "int32")

    def test_float(self):
        self.assertEqual(format_type({"type": "float", "bits": 64}), "float64")

    def test_bool(self):
        self.assertEqual(format_type({"type": "bool"}), "bool")

    def test_string(self):
        self.assertEqual(format_type({"type": "string"}), "str")

    def test_unit(self):
        self.assertEqual(format_type({"type": "unit"}), "unit")

    def test_option(self):
        t = {"type": "option", "inner": INT64}
        self.assertEqual(format_type(t), "option<int64>")

    def test_list(self):
        t = {"type": "list", "inner": INT64, "len": "dynamic"}
        self.assertEqual(format_type(t), "list<int64>")

    def test_map(self):
        t = {"type": "map", "key": STR_T, "value": INT64}
        self.assertEqual(format_type(t), "map<str, int64>")

    def test_alias(self):
        t = {"type": "alias", "name": "Color"}
        self.assertEqual(format_type(t), "Color")

    def test_result(self):
        t = {"type": "result", "ok": INT64, "err": STR_T}
        self.assertEqual(format_type(t), "result<int64, str>")

    def test_non_dict(self):
        self.assertEqual(format_type("str"), "str")


# ---------------------------------------------------------------------------
# Test 2: inspect_spec — single function spec
# ---------------------------------------------------------------------------

class TestInspectSpecFunction(unittest.TestCase):
    def setUp(self):
        self.spec = make_fn_spec(
            "fibonacci",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
            nail="0.2",
            meta={"spec_version": "0.9.0"},
        )
        self.report = inspect_spec(self.spec)

    def test_contains_spec_name(self):
        self.assertIn("fibonacci", self.report)

    def test_contains_kind(self):
        self.assertIn("fn", self.report)

    def test_contains_nail_version(self):
        self.assertIn("0.2", self.report)

    def test_contains_spec_version(self):
        self.assertIn("0.9.0", self.report)

    def test_contains_param(self):
        self.assertIn("n: int64", self.report)

    def test_contains_return_type(self):
        self.assertIn("int64", self.report)

    def test_contains_effects_pure(self):
        self.assertIn("pure", self.report)

    def test_contains_summary(self):
        self.assertIn("SUMMARY", self.report)

    def test_contains_functions_header(self):
        self.assertIn("FUNCTIONS", self.report)

    def test_contains_termination_not_verified(self):
        self.assertIn("Not verified", self.report)


# ---------------------------------------------------------------------------
# Test 3: inspect_spec — module spec
# ---------------------------------------------------------------------------

class TestInspectSpecModule(unittest.TestCase):
    def setUp(self):
        fns = [
            make_fn_spec("add", [{"id": "a", "type": INT64}, {"id": "b", "type": INT64}], INT64),
            make_fn_spec("multiply", [{"id": "a", "type": INT64}, {"id": "b", "type": INT64}], INT64),
        ]
        self.spec = make_module_spec(
            "math",
            defs=fns,
            exports=["add", "multiply"],
            meta={"spec_version": "0.9.0"},
        )
        self.report = inspect_spec(self.spec)

    def test_module_name(self):
        self.assertIn("math", self.report)

    def test_module_kind(self):
        self.assertIn("module", self.report)

    def test_exports_shown(self):
        self.assertIn("add", self.report)
        self.assertIn("multiply", self.report)

    def test_function_count(self):
        self.assertIn("FUNCTIONS (2)", self.report)

    def test_summary_functions(self):
        self.assertIn("Functions : 2", self.report)

    def test_summary_types_zero(self):
        self.assertIn("Types     : 0", self.report)


# ---------------------------------------------------------------------------
# Test 4: inspect_spec — effects
# ---------------------------------------------------------------------------

class TestInspectSpecEffects(unittest.TestCase):
    def setUp(self):
        self.spec = make_fn_spec(
            "print_hello",
            params=[],
            returns=UNIT_T,
            effects=["IO"],
            body=[
                {"op": "print", "effect": "IO", "val": {"lit": "hello"}},
                {"op": "return", "val": {"lit": None, "type": UNIT_T}},
            ],
        )
        self.report = inspect_spec(self.spec)

    def test_effect_in_function(self):
        self.assertIn("IO", self.report)

    def test_not_pure(self):
        self.assertNotIn("[pure]", self.report)

    def test_summary_effects(self):
        self.assertIn("IO", self.report)


# ---------------------------------------------------------------------------
# Test 5: inspect_spec — termination
# ---------------------------------------------------------------------------

class TestInspectSpecTermination(unittest.TestCase):
    def setUp(self):
        fn = make_fn_spec(
            "countdown",
            params=[{"id": "n", "type": INT64}],
            returns=UNIT_T,
        )
        self.spec = make_module_spec(
            "term_module",
            defs=[fn],
            termination={"measure": "n"},
        )
        self.report = inspect_spec(self.spec)

    def test_termination_verified(self):
        self.assertIn("✓ Verified", self.report)

    def test_measure_shown(self):
        self.assertIn("Measure : n", self.report)

    def test_termination_in_summary(self):
        self.assertIn("Termination verified : yes", self.report)


# ---------------------------------------------------------------------------
# Test 6: inspect_spec — types (enum)
# ---------------------------------------------------------------------------

class TestInspectSpecTypes(unittest.TestCase):
    def setUp(self):
        fn = make_fn_spec(
            "color_code",
            params=[{"id": "c", "type": {"type": "alias", "name": "Color"}}],
            returns=INT64,
        )
        types = {
            "Color": {
                "type": "enum",
                "variants": [
                    {"tag": "Red"},
                    {"tag": "Green"},
                    {"tag": "Blue"},
                ],
            }
        }
        self.spec = make_module_spec(
            "color_module",
            defs=[fn],
            types=types,
        )
        self.report = inspect_spec(self.spec)

    def test_types_header(self):
        self.assertIn("TYPES", self.report)

    def test_enum_name(self):
        self.assertIn("Color", self.report)

    def test_enum_variants(self):
        self.assertIn("Red", self.report)
        self.assertIn("Green", self.report)
        self.assertIn("Blue", self.report)

    def test_type_count_in_summary(self):
        self.assertIn("Types     : 1", self.report)


# ---------------------------------------------------------------------------
# Test 7: inspect_spec — call graph
# ---------------------------------------------------------------------------

class TestInspectSpecCallGraph(unittest.TestCase):
    def setUp(self):
        factorial_fn = make_fn_spec(
            "factorial",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
        )
        main_fn = make_fn_spec(
            "main",
            params=[],
            returns=INT64,
            body=[
                {
                    "op": "return",
                    "val": {
                        "op": "call",
                        "fn": "factorial",
                        "args": [{"lit": 5}],
                    },
                }
            ],
        )
        self.spec = make_module_spec("call_test", defs=[factorial_fn, main_fn])
        self.report = inspect_spec(self.spec)

    def test_call_graph_header(self):
        self.assertIn("CALL GRAPH", self.report)

    def test_call_shown(self):
        self.assertIn("main → factorial", self.report)


# ---------------------------------------------------------------------------
# Test 8: _get_functions helper
# ---------------------------------------------------------------------------

class TestGetFunctions(unittest.TestCase):
    def test_single_fn_spec(self):
        spec = make_fn_spec("add", [{"id": "a", "type": INT64}], INT64)
        fns = _get_functions(spec)
        self.assertEqual(len(fns), 1)
        self.assertEqual(fns[0]["id"], "add")

    def test_module_spec(self):
        fn1 = make_fn_spec("add", [], INT64)
        fn2 = make_fn_spec("sub", [], INT64)
        spec = make_module_spec("m", defs=[fn1, fn2])
        fns = _get_functions(spec)
        self.assertEqual(len(fns), 2)

    def test_empty_module(self):
        spec = make_module_spec("empty", defs=[])
        fns = _get_functions(spec)
        self.assertEqual(fns, [])

    def test_unknown_kind(self):
        spec = {"kind": "unknown", "id": "x"}
        fns = _get_functions(spec)
        self.assertEqual(fns, [])


# ---------------------------------------------------------------------------
# Test 9: _get_all_effects helper
# ---------------------------------------------------------------------------

class TestGetAllEffects(unittest.TestCase):
    def test_pure_fn(self):
        spec = make_fn_spec("pure_fn", [], INT64, effects=[])
        effects = _get_all_effects(spec)
        self.assertEqual(effects, set())

    def test_io_effect(self):
        spec = make_fn_spec("io_fn", [], UNIT_T, effects=["IO"])
        effects = _get_all_effects(spec)
        self.assertIn("IO", effects)

    def test_multiple_effects(self):
        fn1 = make_fn_spec("fn1", [], UNIT_T, effects=["IO"])
        fn2 = make_fn_spec("fn2", [], UNIT_T, effects=["NET", "IO"])
        spec = make_module_spec("m", defs=[fn1, fn2])
        effects = _get_all_effects(spec)
        self.assertEqual(effects, {"IO", "NET"})


# ---------------------------------------------------------------------------
# Test 10: _collect_calls_body — call graph extraction
# ---------------------------------------------------------------------------

class TestCollectCallsBody(unittest.TestCase):
    def test_direct_call_in_return(self):
        body = [
            {
                "op": "return",
                "val": {"op": "call", "fn": "helper", "args": []},
            }
        ]
        calls: set[str] = set()
        _collect_calls_body(body, calls)
        self.assertIn("helper", calls)

    def test_nested_call_in_if(self):
        body = [
            {
                "op": "if",
                "cond": {"op": "lt", "l": {"ref": "n"}, "r": {"lit": 0}},
                "then": [
                    {
                        "op": "return",
                        "val": {"op": "call", "fn": "negate", "args": []},
                    }
                ],
                "else": [{"op": "return", "val": {"lit": 0}}],
            }
        ]
        calls: set[str] = set()
        _collect_calls_body(body, calls)
        self.assertIn("negate", calls)

    def test_no_calls(self):
        body = [
            {"op": "return", "val": {"lit": 42}},
        ]
        calls: set[str] = set()
        _collect_calls_body(body, calls)
        self.assertEqual(calls, set())

    def test_call_in_loop_body(self):
        body = [
            {
                "op": "loop",
                "bind": "i",
                "from": {"lit": 0},
                "to": {"lit": 10},
                "step": {"lit": 1},
                "body": [
                    {
                        "op": "let",
                        "id": "x",
                        "type": INT64,
                        "val": {"op": "call", "fn": "step_fn", "args": [{"ref": "i"}]},
                    }
                ],
            }
        ]
        calls: set[str] = set()
        _collect_calls_body(body, calls)
        self.assertIn("step_fn", calls)


# ---------------------------------------------------------------------------
# Test 11: CLI via file — inspect command
# ---------------------------------------------------------------------------

class TestCLIInspect(unittest.TestCase):
    def setUp(self):
        self.spec = make_fn_spec(
            "clamp",
            params=[
                {"id": "val", "type": INT64},
                {"id": "lo", "type": INT64},
                {"id": "hi", "type": INT64},
            ],
            returns=INT64,
            meta={"spec_version": "0.9.0"},
        )

    def test_inspect_with_real_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".nail", delete=False) as f:
            json.dump(self.spec, f)
            tmp_path = f.name
        try:
            with patch("sys.argv", ["nail-lens", "inspect", tmp_path]):
                from nail_lens.cli import main
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()
                    output = mock_out.getvalue()
            self.assertIn("clamp", output)
            self.assertIn("val: int64", output)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Test 12: CLI — file not found error
# ---------------------------------------------------------------------------

class TestCLIFileNotFound(unittest.TestCase):
    def test_nonexistent_file_exits(self):
        with patch("sys.argv", ["nail-lens", "inspect", "/nonexistent/path.nail"]):
            from nail_lens.cli import main
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertEqual(ctx.exception.code, 1)


# ---------------------------------------------------------------------------
# Test 13: CLI — diff command detects added function
# ---------------------------------------------------------------------------

class TestCLIDiff(unittest.TestCase):
    def _write_temp(self, spec: dict):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".nail", delete=False)
        json.dump(spec, f)
        f.close()
        return f.name

    def test_diff_added_function(self):
        spec1 = make_module_spec("m", defs=[
            make_fn_spec("add", [{"id": "a", "type": INT64}], INT64),
        ])
        spec2 = make_module_spec("m", defs=[
            make_fn_spec("add", [{"id": "a", "type": INT64}], INT64),
            make_fn_spec("sub", [{"id": "a", "type": INT64}], INT64),
        ])
        p1 = self._write_temp(spec1)
        p2 = self._write_temp(spec2)
        try:
            with patch("sys.argv", ["nail-lens", "diff", p1, p2]):
                from nail_lens.cli import main
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()
                    output = mock_out.getvalue()
            self.assertIn("+ fn sub", output)
        finally:
            Path(p1).unlink(missing_ok=True)
            Path(p2).unlink(missing_ok=True)

    def test_diff_removed_function(self):
        spec1 = make_module_spec("m", defs=[
            make_fn_spec("add", [{"id": "a", "type": INT64}], INT64),
            make_fn_spec("old_fn", [], INT64),
        ])
        spec2 = make_module_spec("m", defs=[
            make_fn_spec("add", [{"id": "a", "type": INT64}], INT64),
        ])
        p1 = self._write_temp(spec1)
        p2 = self._write_temp(spec2)
        try:
            with patch("sys.argv", ["nail-lens", "diff", p1, p2]):
                from nail_lens.cli import main
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()
                    output = mock_out.getvalue()
            self.assertIn("- fn old_fn", output)
        finally:
            Path(p1).unlink(missing_ok=True)
            Path(p2).unlink(missing_ok=True)

    def test_diff_changed_signature(self):
        spec1 = make_module_spec("m", defs=[
            make_fn_spec("compute", [{"id": "n", "type": INT64}], INT64),
        ])
        spec2 = make_module_spec("m", defs=[
            make_fn_spec("compute", [{"id": "n", "type": FLOAT64}], FLOAT64),
        ])
        p1 = self._write_temp(spec1)
        p2 = self._write_temp(spec2)
        try:
            with patch("sys.argv", ["nail-lens", "diff", p1, p2]):
                from nail_lens.cli import main
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()
                    output = mock_out.getvalue()
            self.assertIn("~ fn compute", output)
            self.assertIn("params changed", output)
        finally:
            Path(p1).unlink(missing_ok=True)
            Path(p2).unlink(missing_ok=True)

    def test_diff_no_changes(self):
        spec = make_module_spec("m", defs=[
            make_fn_spec("add", [{"id": "a", "type": INT64}], INT64),
        ])
        p1 = self._write_temp(spec)
        p2 = self._write_temp(spec)
        try:
            with patch("sys.argv", ["nail-lens", "diff", p1, p2]):
                from nail_lens.cli import main
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()
                    output = mock_out.getvalue()
            self.assertIn("No differences", output)
        finally:
            Path(p1).unlink(missing_ok=True)
            Path(p2).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Test 14: CLI — effects command
# ---------------------------------------------------------------------------

class TestCLIEffects(unittest.TestCase):
    def _write_temp(self, spec: dict):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".nail", delete=False)
        json.dump(spec, f)
        f.close()
        return f.name

    def test_effects_pure(self):
        spec = make_fn_spec("pure_fn", [], INT64)
        p = self._write_temp(spec)
        try:
            with patch("sys.argv", ["nail-lens", "effects", p]):
                from nail_lens.cli import main
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()
                    output = mock_out.getvalue()
            self.assertIn("pure", output.lower())
        finally:
            Path(p).unlink(missing_ok=True)

    def test_effects_io(self):
        spec = make_fn_spec("io_fn", [], UNIT_T, effects=["IO"])
        p = self._write_temp(spec)
        try:
            with patch("sys.argv", ["nail-lens", "effects", p]):
                from nail_lens.cli import main
                with patch("sys.stdout", new_callable=StringIO) as mock_out:
                    main()
                    output = mock_out.getvalue()
            self.assertIn("IO", output)
        finally:
            Path(p).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Test 15: CLI — validate command with real spec
# ---------------------------------------------------------------------------

class TestCLIValidate(unittest.TestCase):
    def _write_temp(self, spec: dict):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".nail", delete=False)
        json.dump(spec, f)
        f.close()
        return f.name

    def test_validate_real_file(self):
        """Validate examples/factorial.nail at L2."""
        examples_dir = Path(__file__).parent.parent / "examples"
        factorial_path = examples_dir / "factorial.nail"
        if not factorial_path.exists():
            self.skipTest("examples/factorial.nail not found")

        with patch("sys.argv", ["nail-lens", "validate", "--level", "L2",
                                 str(factorial_path)]):
            from nail_lens.cli import main
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                try:
                    main()
                except SystemExit as e:
                    if e.code != 0:
                        self.fail(f"validate exited with code {e.code}")
                output = mock_out.getvalue()
        self.assertIn("✓", output)

    def test_validate_bad_effect(self):
        """Validate examples/bad_effect.nail should fail at L2."""
        examples_dir = Path(__file__).parent.parent / "examples"
        bad_path = examples_dir / "bad_effect.nail"
        if not bad_path.exists():
            self.skipTest("examples/bad_effect.nail not found")

        with patch("sys.argv", ["nail-lens", "validate", "--level", "L2",
                                 str(bad_path)]):
            from nail_lens.cli import main
            with patch("sys.stdout", new_callable=StringIO) as mock_out:
                with self.assertRaises(SystemExit) as ctx:
                    main()
                output = mock_out.getvalue()
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("✗", output)


# ---------------------------------------------------------------------------
# Test 16: inspect_spec — real factorial.nail file
# ---------------------------------------------------------------------------

class TestInspectRealFile(unittest.TestCase):
    def test_inspect_factorial(self):
        factorial_path = Path(__file__).parent.parent / "examples" / "factorial.nail"
        if not factorial_path.exists():
            self.skipTest("examples/factorial.nail not found")

        with open(factorial_path) as f:
            spec = json.load(f)
        report = inspect_spec(spec)

        self.assertIn("factorial", report)
        self.assertIn("n: int64", report)
        self.assertIn("SUMMARY", report)

    def test_inspect_call_demo(self):
        path = Path(__file__).parent.parent / "examples" / "call_demo.nail"
        if not path.exists():
            self.skipTest("examples/call_demo.nail not found")

        with open(path) as f:
            spec = json.load(f)
        report = inspect_spec(spec)

        self.assertIn("call_demo", report)
        self.assertIn("CALL GRAPH", report)
        self.assertIn("main → factorial", report)


if __name__ == "__main__":
    unittest.main()
