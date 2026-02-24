#!/usr/bin/env python3
"""
NAIL Transpiler Test Suite

Tests Python (typed subset) → NAIL IR transpilation.
Verifies:
  - Basic function transpilation (pure functions)
  - Type annotation conversion (int, float, bool, str, None)
  - Effect inference (FS, NET, IO)
  - Control flow (if/else, for-range)
  - Variable assignment (let, assign, augmented)
  - Integration with NAIL Checker (end-to-end roundtrip)
  - Error cases (missing annotations, unsupported constructs)

Run: python3 -m pytest tests/test_transpiler.py -v
  or: python3 tests/test_transpiler.py
"""

import sys
import json
import unittest
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from transpiler.python_to_nail import transpile_function, transpile_to_json, TranspilerError
from interpreter import Checker, Runtime
from interpreter.types import NailTypeError
from interpreter.checker import CheckError


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def check_and_run(spec: dict, args: dict | None = None) -> object:
    """Run NAIL checker + runtime on a spec dict. Returns runtime result."""
    Checker(spec).check()
    rt = Runtime(spec)
    return rt.run(args or {})


# ---------------------------------------------------------------------------
# Test Case 1: Pure arithmetic function
# ---------------------------------------------------------------------------

class TestPureFunctions(unittest.TestCase):
    """Test 1: Pure functions with no side effects."""

    def test_add_integers(self):
        """Transpile and verify integer addition function."""
        source = """
def add(a: int, b: int) -> int:
    return a + b
"""
        spec = transpile_function(source)

        # Structure checks
        self.assertEqual(spec["nail"], "0.1.0")
        self.assertEqual(spec["kind"], "fn")
        self.assertEqual(spec["id"], "add")
        self.assertEqual(spec["effects"], [])
        self.assertEqual(len(spec["params"]), 2)
        self.assertEqual(spec["params"][0]["id"], "a")
        self.assertEqual(spec["params"][0]["type"], {"type": "int", "bits": 64, "overflow": "panic"})
        self.assertEqual(spec["params"][1]["id"], "b")
        self.assertEqual(spec["returns"], {"type": "int", "bits": 64, "overflow": "panic"})

        # Body: single return of a + b
        self.assertEqual(len(spec["body"]), 1)
        ret = spec["body"][0]
        self.assertEqual(ret["op"], "return")
        self.assertEqual(ret["val"]["op"], "+")
        self.assertEqual(ret["val"]["l"], {"ref": "a"})
        self.assertEqual(ret["val"]["r"], {"ref": "b"})

        # End-to-end: NAIL checker passes, runtime gives correct result
        result = check_and_run(spec, {"a": 3, "b": 5})
        self.assertEqual(result, 8)

    def test_is_even(self):
        """Transpile a boolean-returning function."""
        source = """
def is_even(n: int) -> bool:
    return n % 2 == 0
"""
        spec = transpile_function(source)
        self.assertEqual(spec["id"], "is_even")
        self.assertEqual(spec["effects"], [])
        self.assertEqual(spec["returns"], {"type": "bool"})

        # Check the body: return (n % 2 == 0)
        ret = spec["body"][0]
        self.assertEqual(ret["op"], "return")
        self.assertEqual(ret["val"]["op"], "eq")
        self.assertEqual(ret["val"]["l"]["op"], "%")
        self.assertEqual(ret["val"]["r"], {"lit": 0})

        # Runtime verification
        result_even = check_and_run(spec, {"n": 4})
        result_odd  = check_and_run(spec, {"n": 7})
        self.assertTrue(result_even)
        self.assertFalse(result_odd)

    def test_float_multiply(self):
        """Transpile a float arithmetic function."""
        source = """
def area(radius: float) -> float:
    pi: float = 3.14159
    return pi * radius * radius
"""
        spec = transpile_function(source)
        self.assertEqual(spec["returns"], {"type": "float", "bits": 64})
        self.assertEqual(spec["effects"], [])

        # Body: let pi + return
        self.assertEqual(len(spec["body"]), 2)
        let_stmt = spec["body"][0]
        self.assertEqual(let_stmt["op"], "let")
        self.assertEqual(let_stmt["id"], "pi")
        self.assertAlmostEqual(let_stmt["val"]["lit"], 3.14159)

        # NAIL checker must pass
        Checker(spec).check()

    def test_max_of_two(self):
        """Transpile a function with if/else control flow."""
        source = """
def max_of_two(a: int, b: int) -> int:
    if a > b:
        return a
    else:
        return b
"""
        spec = transpile_function(source)
        self.assertEqual(spec["id"], "max_of_two")
        self.assertEqual(spec["effects"], [])

        # Body: single if statement
        self.assertEqual(len(spec["body"]), 1)
        if_stmt = spec["body"][0]
        self.assertEqual(if_stmt["op"], "if")
        self.assertEqual(if_stmt["cond"]["op"], "gt")
        self.assertEqual(len(if_stmt["then"]), 1)
        self.assertEqual(len(if_stmt["else"]), 1)

        # Runtime: 5 > 3 → 5; 2 > 7 → 7
        result1 = check_and_run(spec, {"a": 5, "b": 3})
        result2 = check_and_run(spec, {"a": 2, "b": 7})
        self.assertEqual(result1, 5)
        self.assertEqual(result2, 7)


# ---------------------------------------------------------------------------
# Test Case 2: Effect inference
# ---------------------------------------------------------------------------

class TestEffectInference(unittest.TestCase):
    """Test 2: Automatic effect detection from Python builtins."""

    def test_fs_effect_from_open(self):
        """open() usage → FS effect inferred."""
        source = """
def read_config(path: str) -> str:
    f = open(path)
    return path
"""
        spec = transpile_function(source)
        self.assertIn("FS", spec["effects"])
        self.assertNotIn("NET", spec["effects"])
        self.assertNotIn("IO", spec["effects"])

    def test_net_effect_from_requests(self):
        """requests.get() usage → NET effect inferred."""
        source = """
def fetch_url(url: str) -> str:
    requests.get(url)
    return url
"""
        spec = transpile_function(source)
        self.assertIn("NET", spec["effects"])
        self.assertNotIn("FS", spec["effects"])

    def test_io_effect_from_print(self):
        """print() usage → IO effect inferred."""
        source = """
def greet(name: str) -> str:
    print(name)
    return name
"""
        spec = transpile_function(source)
        self.assertIn("IO", spec["effects"])
        self.assertNotIn("FS", spec["effects"])
        self.assertNotIn("NET", spec["effects"])

    def test_multiple_effects(self):
        """Functions using open() + requests → FS + NET effects."""
        source = """
def fetch_and_log(url: str, path: str) -> str:
    requests.get(url)
    open(path)
    return url
"""
        spec = transpile_function(source)
        self.assertIn("FS", spec["effects"])
        self.assertIn("NET", spec["effects"])
        # Effects must be sorted (canonical)
        self.assertEqual(spec["effects"], sorted(spec["effects"]))

    def test_pure_no_effects(self):
        """Pure function has empty effects list."""
        source = """
def square(n: int) -> int:
    return n * n
"""
        spec = transpile_function(source)
        self.assertEqual(spec["effects"], [])

    def test_print_io_passes_checker(self):
        """print() generates IO effect and NAIL checker accepts it."""
        source = """
def greet(name: str) -> str:
    print(name)
    return name
"""
        spec = transpile_function(source)
        # Must pass NAIL checker (IO effect properly declared)
        Checker(spec).check()


# ---------------------------------------------------------------------------
# Test Case 3: Control flow (if/else, for-range)
# ---------------------------------------------------------------------------

class TestControlFlow(unittest.TestCase):
    """Test 3: Control flow transpilation."""

    def test_if_else(self):
        """if/else transpiles to NAIL if op with both then/else branches."""
        source = """
def abs_val(n: int) -> int:
    if n >= 0:
        return n
    else:
        return -n
"""
        spec = transpile_function(source)
        body = spec["body"]
        self.assertEqual(len(body), 1)

        if_stmt = body[0]
        self.assertEqual(if_stmt["op"], "if")
        self.assertEqual(if_stmt["cond"]["op"], "gte")

        # then: return n
        self.assertEqual(if_stmt["then"][0]["op"], "return")
        self.assertEqual(if_stmt["then"][0]["val"], {"ref": "n"})

        # else: return 0 - n (unary minus)
        self.assertEqual(if_stmt["else"][0]["op"], "return")
        neg = if_stmt["else"][0]["val"]
        self.assertEqual(neg["op"], "-")
        self.assertEqual(neg["l"], {"lit": 0})
        self.assertEqual(neg["r"], {"ref": "n"})

        # Runtime: abs(-5) = 5, abs(3) = 3
        result1 = check_and_run(spec, {"n": -5})
        result2 = check_and_run(spec, {"n": 3})
        self.assertEqual(result1, 5)
        self.assertEqual(result2, 3)

    def test_for_range_single_arg(self):
        """for i in range(n) → NAIL loop from 0 to n step 1."""
        source = """
def sum_up_to(n: int) -> int:
    total: int = 0
    for i in range(n):
        total += i
    return total
"""
        spec = transpile_function(source)
        # Find the loop statement
        loop_stmt = None
        for stmt in spec["body"]:
            if stmt.get("op") == "loop":
                loop_stmt = stmt
                break
        self.assertIsNotNone(loop_stmt, "Expected a loop statement")
        self.assertEqual(loop_stmt["bind"], "i")
        self.assertEqual(loop_stmt["from"], {"lit": 0})
        self.assertEqual(loop_stmt["to"], {"ref": "n"})
        self.assertEqual(loop_stmt["step"], {"lit": 1})

        # Checker + runtime
        result = check_and_run(spec, {"n": 5})
        self.assertEqual(result, 10)  # 0+1+2+3+4 = 10

    def test_for_range_two_args(self):
        """for i in range(start, end) → NAIL loop with explicit from/to."""
        source = """
def sum_range(start: int, end: int) -> int:
    total: int = 0
    for i in range(start, end):
        total += i
    return total
"""
        spec = transpile_function(source)
        loop_stmt = next(s for s in spec["body"] if s.get("op") == "loop")
        self.assertEqual(loop_stmt["from"], {"ref": "start"})
        self.assertEqual(loop_stmt["to"],   {"ref": "end"})
        self.assertEqual(loop_stmt["step"], {"lit": 1})

        # Checker must pass
        Checker(spec).check()

    def test_nested_if_in_loop(self):
        """if inside a loop body transpiles correctly."""
        source = """
def count_positives(n: int) -> int:
    count: int = 0
    for i in range(n):
        if i > 0:
            count += 1
        else:
            count += 0
    return count
"""
        spec = transpile_function(source)
        Checker(spec).check()
        result = check_and_run(spec, {"n": 5})
        self.assertEqual(result, 4)  # 1, 2, 3, 4 are positive (0 is not)


# ---------------------------------------------------------------------------
# Test Case 4: Type annotations
# ---------------------------------------------------------------------------

class TestTypeAnnotations(unittest.TestCase):
    """Test 4: Type hint → NAIL type conversion."""

    def test_int_annotation(self):
        """int → int64(panic)."""
        source = "def f(x: int) -> int:\n    return x\n"
        spec = transpile_function(source)
        expected = {"type": "int", "bits": 64, "overflow": "panic"}
        self.assertEqual(spec["params"][0]["type"], expected)
        self.assertEqual(spec["returns"], expected)

    def test_float_annotation(self):
        """float → float64."""
        source = "def f(x: float) -> float:\n    return x\n"
        spec = transpile_function(source)
        expected = {"type": "float", "bits": 64}
        self.assertEqual(spec["params"][0]["type"], expected)
        self.assertEqual(spec["returns"], expected)

    def test_bool_annotation(self):
        """bool → bool."""
        source = "def f(x: bool) -> bool:\n    return x\n"
        spec = transpile_function(source)
        expected = {"type": "bool"}
        self.assertEqual(spec["params"][0]["type"], expected)
        self.assertEqual(spec["returns"], expected)

    def test_str_annotation(self):
        """str → string."""
        source = "def f(x: str) -> str:\n    return x\n"
        spec = transpile_function(source)
        expected = {"type": "string"}
        self.assertEqual(spec["params"][0]["type"], expected)
        self.assertEqual(spec["returns"], expected)

    def test_none_return_annotation(self):
        """-> None → unit."""
        source = """
def noop() -> None:
    return
"""
        spec = transpile_function(source)
        self.assertEqual(spec["returns"], {"type": "unit"})
        # Return body should have unit literal
        ret = spec["body"][0]
        self.assertEqual(ret["op"], "return")
        self.assertEqual(ret["val"]["lit"], None)
        self.assertEqual(ret["val"]["type"], {"type": "unit"})

    def test_fn_selection_by_name(self):
        """transpile_function with fn_name selects the right function."""
        source = """
def add(a: int, b: int) -> int:
    return a + b

def subtract(a: int, b: int) -> int:
    return a - b
"""
        spec_add = transpile_function(source, fn_name="add")
        spec_sub = transpile_function(source, fn_name="subtract")
        self.assertEqual(spec_add["id"], "add")
        self.assertEqual(spec_sub["id"], "subtract")
        self.assertEqual(spec_sub["body"][0]["val"]["op"], "-")


# ---------------------------------------------------------------------------
# Test Case 5: Variable assignment patterns
# ---------------------------------------------------------------------------

class TestVariableAssignment(unittest.TestCase):
    """Test 5: let, assign, augmented assignment."""

    def test_plain_assignment_becomes_let(self):
        """First plain assignment → NAIL let (mut=true)."""
        source = """
def f(n: int) -> int:
    x = n
    return x
"""
        spec = transpile_function(source)
        let_stmt = spec["body"][0]
        self.assertEqual(let_stmt["op"], "let")
        self.assertEqual(let_stmt["id"], "x")
        self.assertTrue(let_stmt.get("mut", False))

    def test_annotated_assignment_includes_type(self):
        """Annotated assignment includes type field in NAIL let."""
        source = """
def f(n: int) -> int:
    x: int = n
    return x
"""
        spec = transpile_function(source)
        let_stmt = spec["body"][0]
        self.assertEqual(let_stmt["op"], "let")
        self.assertEqual(let_stmt["type"], {"type": "int", "bits": 64, "overflow": "panic"})

    def test_reassignment_becomes_assign(self):
        """Re-assignment to same variable → NAIL assign op."""
        source = """
def f(n: int) -> int:
    x: int = n
    x = n + 1
    return x
"""
        spec = transpile_function(source)
        self.assertEqual(spec["body"][0]["op"], "let")
        self.assertEqual(spec["body"][1]["op"], "assign")
        self.assertEqual(spec["body"][1]["id"], "x")

    def test_augmented_assignment(self):
        """x += 1 → assign with op +."""
        source = """
def f(n: int) -> int:
    total: int = 0
    total += n
    return total
"""
        spec = transpile_function(source)
        aug = spec["body"][1]
        self.assertEqual(aug["op"], "assign")
        self.assertEqual(aug["val"]["op"], "+")
        self.assertEqual(aug["val"]["l"], {"ref": "total"})
        self.assertEqual(aug["val"]["r"], {"ref": "n"})


# ---------------------------------------------------------------------------
# Test Case 6: Canonical JSON output
# ---------------------------------------------------------------------------

class TestCanonicalOutput(unittest.TestCase):
    """Test 6: transpile_to_json produces canonical NAIL JSON."""

    def test_canonical_json_is_sorted(self):
        """Output JSON has sorted keys (canonical form)."""
        source = """
def add(a: int, b: int) -> int:
    return a + b
"""
        json_str = transpile_to_json(source)
        # Parse and re-serialize — should be identical
        parsed = json.loads(json_str)
        canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
        self.assertEqual(json_str, canonical)

    def test_json_is_valid(self):
        """Output is valid JSON."""
        source = """
def square(n: int) -> int:
    return n * n
"""
        json_str = transpile_to_json(source)
        spec = json.loads(json_str)
        self.assertIsInstance(spec, dict)
        self.assertEqual(spec["id"], "square")

    def test_checker_accepts_json_output(self):
        """transpile_to_json output passes NAIL checker."""
        source = """
def factorial(n: int) -> int:
    result: int = 1
    for i in range(1, n):
        result = result * i
    return result
"""
        json_str = transpile_to_json(source)
        spec = json.loads(json_str)
        Checker(spec).check()


# ---------------------------------------------------------------------------
# Test Case 7: Error cases
# ---------------------------------------------------------------------------

class TestErrorCases(unittest.TestCase):
    """Test 7: TranspilerError for unsupported constructs."""

    def test_missing_param_annotation_raises(self):
        """Unannotated parameter → TranspilerError."""
        source = """
def f(x) -> int:
    return x
"""
        with self.assertRaises(TranspilerError):
            transpile_function(source)

    def test_missing_return_annotation_raises(self):
        """Missing return annotation → TranspilerError."""
        source = """
def f(x: int):
    return x
"""
        with self.assertRaises(TranspilerError):
            transpile_function(source)

    def test_while_loop_raises(self):
        """while loops → TranspilerError (use for-range instead)."""
        source = """
def f(n: int) -> int:
    i: int = 0
    while i < n:
        i += 1
    return i
"""
        with self.assertRaises(TranspilerError):
            transpile_function(source)

    def test_unknown_type_annotation_raises(self):
        """Unknown type annotation (e.g. 'MyClass') → TranspilerError."""
        source = """
def f(x: MyClass) -> int:
    return 0
"""
        with self.assertRaises(TranspilerError):
            transpile_function(source)

    def test_function_not_found_raises(self):
        """fn_name that doesn't exist → TranspilerError."""
        source = """
def f(x: int) -> int:
    return x
"""
        with self.assertRaises(TranspilerError):
            transpile_function(source, fn_name="nonexistent")

    def test_no_functions_raises(self):
        """Source with no function definitions → TranspilerError."""
        source = "x = 1 + 2\n"
        with self.assertRaises(TranspilerError):
            transpile_function(source)


# ---------------------------------------------------------------------------
# Test Case 8: End-to-end roundtrip (Python → NAIL → runtime result)
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):
    """Test 8: Full roundtrip - transpile, check, run, verify result."""

    def test_fibonacci_like_loop(self):
        """Fibonacci-style accumulator loop."""
        source = """
def sum_squares(n: int) -> int:
    total: int = 0
    for i in range(1, n + 1):
        total = total + i * i
    return total
"""
        spec = transpile_function(source)
        Checker(spec).check()
        result = check_and_run(spec, {"n": 3})
        # 1^2 + 2^2 + 3^2 = 1 + 4 + 9 = 14
        self.assertEqual(result, 14)

    def test_bool_logic_function(self):
        """Boolean logic with and/or operators."""
        source = """
def both_positive(a: int, b: int) -> bool:
    return a > 0 and b > 0
"""
        spec = transpile_function(source)
        Checker(spec).check()
        self.assertTrue(check_and_run(spec, {"a": 3, "b": 5}))
        self.assertFalse(check_and_run(spec, {"a": -1, "b": 5}))

    def test_string_return(self):
        """Function with str parameter and return."""
        source = """
def identity_str(s: str) -> str:
    return s
"""
        spec = transpile_function(source)
        Checker(spec).check()
        result = check_and_run(spec, {"s": "hello"})
        self.assertEqual(result, "hello")

    def test_clamp_function(self):
        """Clamp: min-max limiting with nested if."""
        source = """
def clamp(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    else:
        if value > hi:
            return hi
        else:
            return value
"""
        spec = transpile_function(source)
        Checker(spec).check()
        self.assertEqual(check_and_run(spec, {"value": -5, "lo": 0, "hi": 10}), 0)
        self.assertEqual(check_and_run(spec, {"value": 15, "lo": 0, "hi": 10}), 10)
        self.assertEqual(check_and_run(spec, {"value":  7, "lo": 0, "hi": 10}), 7)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
