#!/usr/bin/env python3
"""
Phase 2 Experiment Runner
Compares NAIL vs Python on L0-L2 check pass rate, token count, and correctness.
"""

import sys
import json
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from interpreter import Checker, CheckError, NailTypeError, NailEffectError
from interpreter.runtime import Runtime, NailRuntimeError, UNIT

# ---------------------------------------------------------------------------
# Test cases (spec-defined expected outputs)
# ---------------------------------------------------------------------------

TEST_CASES = {
    "is_even": [
        ({"n": 4},   True),
        ({"n": 7},   False),
        ({"n": 0},   True),
        ({"n": -2},  True),
        ({"n": -3},  False),
    ],
    "abs_val": [
        ({"n": 5},    5),
        ({"n": -5},   5),
        ({"n": 0},    0),
        ({"n": -100}, 100),
    ],
    "max_of_two": [
        ({"a": 3, "b": 7},   7),
        ({"a": 7, "b": 3},   7),
        ({"a": 5, "b": 5},   5),
        ({"a": -1, "b": -5}, -1),
    ],
    "clamp": [
        ({"val": 5,  "lo": 1, "hi": 10}, 5),
        ({"val": 0,  "lo": 1, "hi": 10}, 1),
        ({"val": 15, "lo": 1, "hi": 10}, 10),
        ({"val": 1,  "lo": 1, "hi": 1},  1),
    ],
    "factorial": [
        ({"n": 0},  1),
        ({"n": 1},  1),
        ({"n": 5},  120),
        ({"n": 10}, 3628800),
    ],
}

# Python implementations for testing
def is_even(n): return n % 2 == 0
def abs_val(n): return -n if n < 0 else n
def max_of_two(a, b): return a if a >= b else b
def clamp(val, lo, hi): return lo if val < lo else (hi if val > hi else val)
def factorial(n):
    acc = 1
    for i in range(1, n + 1):
        acc *= i
    return acc

PYTHON_FNS = {
    "is_even": is_even,
    "abs_val": abs_val,
    "max_of_two": max_of_two,
    "clamp": clamp,
    "factorial": factorial,
}

NAIL_FILES = {
    "is_even":    "nail/p1_is_even.nail",
    "abs_val":    "nail/p2_abs_val.nail",
    "max_of_two": "nail/p3_max_of_two.nail",
    "clamp":      "nail/p4_clamp.nail",
    "factorial":  "nail/p5_factorial.nail",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def count_tokens_approx(text: str) -> int:
    """Approximate token count: words + punctuation."""
    import re
    tokens = re.findall(r'["\w]+|[{}\[\]:,]', text)
    return len(tokens)

def check_nail(path: str):
    with open(path) as f:
        spec = json.load(f)
    checker = Checker(spec)
    checker.check()
    return spec

def run_nail(spec: dict, args: dict):
    runtime = Runtime(spec)
    # Inject args into the spec's param context
    fn_spec = dict(spec)
    runtime2 = Runtime(fn_spec)
    return runtime2._run_fn(fn_spec, args)

# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def run():
    base = Path(__file__).parent
    results = []

    print("=" * 60)
    print("NAIL vs Python — Phase 2 Experiment")
    print("=" * 60)

    for name, cases in TEST_CASES.items():
        nail_path = base / NAIL_FILES[name]

        # --- NAIL ---
        nail_tokens = count_tokens_approx(nail_path.read_text())
        nail_check_pass = False
        nail_errors = []
        nail_test_results = []
        nail_spec = None

        try:
            nail_spec = check_nail(nail_path)
            nail_check_pass = True
        except Exception as e:
            nail_errors.append(f"CHECK: {e}")

        if nail_check_pass and nail_spec:
            for args, expected in cases:
                try:
                    result = run_nail(nail_spec, args)
                    if result == expected:
                        nail_test_results.append("✓")
                    else:
                        nail_test_results.append(f"✗ (got {result!r}, expected {expected!r})")
                except Exception as e:
                    nail_test_results.append(f"✗ RUNTIME: {e}")

        # --- Python ---
        py_fn = PYTHON_FNS[name]
        py_src = Path(base / "python/implementations.py").read_text()
        py_tokens = count_tokens_approx(py_src)  # whole file for comparison
        py_test_results = []

        for args, expected in cases:
            try:
                result = py_fn(**args)
                if result == expected:
                    py_test_results.append("✓")
                else:
                    py_test_results.append(f"✗ (got {result!r}, expected {expected!r})")
            except Exception as e:
                py_test_results.append(f"✗ RUNTIME: {e}")

        # --- Report ---
        nail_pass_count = sum(1 for r in nail_test_results if r == "✓")
        py_pass_count = sum(1 for r in py_test_results if r == "✓")
        total = len(cases)

        print(f"\n{'─'*60}")
        print(f"  {name.upper()}")
        print(f"{'─'*60}")
        print(f"  NAIL:")
        print(f"    L0-L2 check: {'✓ PASS' if nail_check_pass else '✗ FAIL: ' + str(nail_errors)}")
        print(f"    Tests:       {nail_pass_count}/{total}  {nail_test_results}")
        print(f"    Tokens:      {nail_tokens}")
        print(f"  Python:")
        print(f"    Tests:       {py_pass_count}/{total}  {py_test_results}")

        results.append({
            "problem": name,
            "nail": {"check": nail_check_pass, "tests": f"{nail_pass_count}/{total}", "tokens": nail_tokens},
            "python": {"tests": f"{py_pass_count}/{total}"},
        })

    # --- Summary ---
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    nail_check_total = sum(1 for r in results if r["nail"]["check"])
    nail_test_total = sum(int(r["nail"]["tests"].split("/")[0]) for r in results)
    nail_test_max = sum(int(r["nail"]["tests"].split("/")[1]) for r in results)
    py_test_total = sum(int(r["python"]["tests"].split("/")[0]) for r in results)
    py_test_max = sum(int(r["python"]["tests"].split("/")[1]) for r in results)
    avg_nail_tokens = sum(r["nail"]["tokens"] for r in results) / len(results)

    print(f"  NAIL  L0-L2 check:  {nail_check_total}/{len(results)}")
    print(f"  NAIL  test pass:    {nail_test_total}/{nail_test_max}")
    print(f"  Python test pass:   {py_test_total}/{py_test_max}")
    print(f"  Avg NAIL tokens/fn: {avg_nail_tokens:.0f}")

    # Save results
    out = base / "results.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved: {out}")

if __name__ == "__main__":
    run()
