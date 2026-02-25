#!/usr/bin/env python3
"""
Tests for Issue #72: propagate level and source_path to imported module checker.

_check_imported_module_body() must pass level=self.level (and source_path) to
the sub-Checker it creates, so that L3 termination checks and path-relative
import resolution work correctly for nested imports.

Run: python -m pytest tests/test_issue_72_propagate_level.py -v
"""

import json
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter.checker import Checker, CheckError

# ── Type shorthands ────────────────────────────────────────────────────────

INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
UNIT_T = {"type": "unit"}


# ── Helpers ────────────────────────────────────────────────────────────────

def _loop_fn(fn_id, step_expr):
    """Return a fn-kind spec containing a single loop."""
    return {
        "nail": "0.1.0",
        "kind": "fn",
        "id": fn_id,
        "effects": [],
        "params": [],
        "returns": UNIT_T,
        "body": [
            {
                "op": "loop",
                "bind": "i",
                "from": {"lit": 0},
                "to": {"lit": 10},
                "step": step_expr,
                "body": [],
            },
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ],
    }


def _recursive_fn(fn_id, with_termination: bool):
    """Return a fn-kind spec for a simple recursive countdown."""
    body = [
        {
            "op": "if",
            "cond": {"op": "eq", "l": {"ref": "n"}, "r": {"lit": 0}},
            "then": [{"op": "return", "val": {"lit": 1}}],
            "else": [
                {
                    "op": "return",
                    "val": {
                        "op": "call",
                        "fn": fn_id,
                        "args": [{"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}],
                    },
                }
            ],
        }
    ]
    spec = {
        "nail": "0.1.0",
        "kind": "fn",
        "id": fn_id,
        "effects": [],
        "params": [{"id": "n", "type": INT64}],
        "returns": INT64,
        "body": body,
    }
    if with_termination:
        spec["termination"] = {"measure": "n"}
    return spec


def _module_spec(module_id, defs, exports=None):
    return {
        "nail": "0.1.0",
        "kind": "module",
        "id": module_id,
        "exports": exports or [],
        "defs": defs,
    }


def _caller_spec(imported_module_id, imported_fn_id, from_path=None):
    """A minimal module that just imports one function from another module."""
    imp = {"module": imported_module_id, "fns": [imported_fn_id]}
    if from_path is not None:
        imp["from"] = from_path
    return {
        "nail": "0.1.0",
        "kind": "module",
        "id": "caller",
        "imports": [imp],
        "exports": ["entry"],
        "defs": [
            {
                "nail": "0.1.0",
                "kind": "fn",
                "id": "entry",
                "effects": [],
                "params": [],
                "returns": UNIT_T,
                "body": [{"op": "return", "val": {"lit": None, "type": UNIT_T}}],
            }
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Issue #72 — level propagation
# ═══════════════════════════════════════════════════════════════════════════

class TestLevelPropagationToImportedModule(unittest.TestCase):
    """L3 level must be propagated into the imported module's sub-checker."""

    # ── Loop termination in imported module ───────────────────────────────

    def test_l3_passes_for_imported_module_with_terminating_loop(self):
        """L3 parent: imported module with a literal-step loop must pass."""
        lib = _module_spec("lib", [_loop_fn("count", {"lit": 1})], exports=["count"])
        caller = _caller_spec("lib", "count")
        # Must not raise — loop in imported module terminates
        Checker(caller, modules={"lib": lib}, level=3).check()

    def test_l3_rejects_imported_module_with_zero_step_loop(self):
        """L3 parent: imported module with step=0 loop must raise CheckError."""
        lib = _module_spec("lib", [_loop_fn("inf", {"lit": 0})], exports=["inf"])
        caller = _caller_spec("lib", "inf")
        with self.assertRaises(CheckError) as ctx:
            Checker(caller, modules={"lib": lib}, level=3).check()
        self.assertIn("infinite loop", str(ctx.exception).lower())

    def test_l3_rejects_imported_module_with_variable_step_loop(self):
        """L3 parent: imported module with variable step must raise CheckError."""
        # build a fn that has a variable step loop
        fn = {
            "nail": "0.1.0",
            "kind": "fn",
            "id": "var_loop",
            "effects": [],
            "params": [{"id": "s", "type": INT64}],
            "returns": UNIT_T,
            "body": [
                {
                    "op": "loop",
                    "bind": "i",
                    "from": {"lit": 0},
                    "to": {"lit": 10},
                    "step": {"ref": "s"},  # variable — not provably non-zero
                    "body": [],
                },
                {"op": "return", "val": {"lit": None, "type": UNIT_T}},
            ],
        }
        lib = _module_spec("lib", [fn], exports=["var_loop"])
        caller = _caller_spec("lib", "var_loop")
        with self.assertRaises(CheckError) as ctx:
            Checker(caller, modules={"lib": lib}, level=3).check()
        self.assertIn("literal", str(ctx.exception).lower())

    def test_l2_does_not_enforce_termination_in_imported_module(self):
        """L2 parent: step=0 in imported module is not checked (L3-only rule)."""
        lib = _module_spec("lib", [_loop_fn("no_proof", {"lit": 0})], exports=["no_proof"])
        caller = _caller_spec("lib", "no_proof")
        # Must not raise — termination checking is L3-only
        Checker(caller, modules={"lib": lib}, level=2).check()

    # ── Recursive termination in imported module ──────────────────────────

    def test_l3_passes_for_imported_module_with_annotated_recursion(self):
        """L3 parent: recursive function in imported module with annotation passes."""
        lib = _module_spec(
            "lib",
            [_recursive_fn("countdown", with_termination=True)],
            exports=["countdown"],
        )
        caller = _caller_spec("lib", "countdown")
        # Must not raise — termination annotation is present
        Checker(caller, modules={"lib": lib}, level=3).check()

    def test_l3_rejects_imported_module_with_unannotated_recursion(self):
        """L3 parent: recursive function in imported module without annotation must raise."""
        lib = _module_spec(
            "lib",
            [_recursive_fn("unannotated", with_termination=False)],
            exports=["unannotated"],
        )
        caller = _caller_spec("lib", "unannotated")
        with self.assertRaises(CheckError) as ctx:
            Checker(caller, modules={"lib": lib}, level=3).check()
        msg = str(ctx.exception).lower()
        self.assertTrue("recursive" in msg or "termination" in msg)

    def test_l2_does_not_reject_unannotated_recursion_in_imported_module(self):
        """L2 parent: unannotated recursion in imported module IS still rejected (L2 rule)."""
        # At L2, recursive calls without annotation are also rejected
        lib = _module_spec(
            "lib",
            [_recursive_fn("unannotated", with_termination=False)],
            exports=["unannotated"],
        )
        caller = _caller_spec("lib", "unannotated")
        # L2 also raises for recursion (just not for loop termination)
        with self.assertRaises(CheckError):
            Checker(caller, modules={"lib": lib}, level=2).check()

    # ── visited-set is still shared (no duplicate checks / infinite loops) ─

    def test_visited_set_prevents_double_checking(self):
        """Importing the same module twice must not cause duplicate checks."""
        lib = _module_spec("lib", [_loop_fn("once", {"lit": 1})], exports=["once"])
        caller = {
            "nail": "0.1.0",
            "kind": "module",
            "id": "caller",
            "imports": [
                {"module": "lib", "fns": ["once"]},
            ],
            "exports": ["a", "b"],
            "defs": [
                {
                    "nail": "0.1.0", "kind": "fn", "id": "a",
                    "effects": [], "params": [], "returns": UNIT_T,
                    "body": [{"op": "return", "val": {"lit": None, "type": UNIT_T}}],
                },
                {
                    "nail": "0.1.0", "kind": "fn", "id": "b",
                    "effects": [], "params": [], "returns": UNIT_T,
                    "body": [{"op": "return", "val": {"lit": None, "type": UNIT_T}}],
                },
            ],
        }
        # Should complete without infinite recursion or duplicate CheckError
        Checker(caller, modules={"lib": lib}, level=3).check()


# ═══════════════════════════════════════════════════════════════════════════
#  Issue #72 — source_path propagation for nested relative imports
# ═══════════════════════════════════════════════════════════════════════════

class TestSourcePathPropagationToImportedModule:
    """source_path of imported module must flow into sub-checker for nested relative imports."""

    def test_nested_relative_import_resolves_via_propagated_source_path(self, tmp_path):
        """A→B→C where B uses a relative 'from' path; sub-checker must resolve C correctly."""
        # C: a trivial utility module
        c_spec = {
            "nail": "0.1.0",
            "kind": "module",
            "id": "c",
            "exports": ["double"],
            "defs": [
                {
                    "nail": "0.1.0", "kind": "fn", "id": "double",
                    "effects": [], "params": [{"id": "n", "type": INT64}],
                    "returns": INT64,
                    "body": [{"op": "return", "val": {"op": "*", "l": {"ref": "n"}, "r": {"lit": 2}}}],
                }
            ],
        }
        c_path = tmp_path / "c.nail"
        c_path.write_text(json.dumps(c_spec), encoding="utf-8")

        # B: imports C via a relative path ("c.nail" resolved relative to B's location)
        b_spec = {
            "nail": "0.1.0",
            "kind": "module",
            "id": "b",
            "imports": [{"module": "c", "fns": ["double"], "from": "c.nail"}],
            "exports": ["triple"],
            "defs": [
                {
                    "nail": "0.1.0", "kind": "fn", "id": "triple",
                    "effects": [], "params": [{"id": "n", "type": INT64}],
                    "returns": INT64,
                    "body": [
                        {
                            "op": "return",
                            "val": {
                                "op": "call", "fn": "double", "module": "c",
                                "args": [{"op": "+", "l": {"ref": "n"}, "r": {"ref": "n"}}],
                            },
                        }
                    ],
                }
            ],
        }
        b_path = tmp_path / "b.nail"
        b_path.write_text(json.dumps(b_spec), encoding="utf-8")

        # A: imports B via absolute path; B's sub-checker must get B's source_path
        a_spec = {
            "nail": "0.1.0",
            "kind": "module",
            "id": "a",
            "imports": [{"module": "b", "fns": ["triple"], "from": str(b_path)}],
            "exports": ["entry"],
            "defs": [
                {
                    "nail": "0.1.0", "kind": "fn", "id": "entry",
                    "effects": [], "params": [], "returns": UNIT_T,
                    "body": [{"op": "return", "val": {"lit": None, "type": UNIT_T}}],
                }
            ],
        }
        # Should not raise — nested relative import resolves because source_path propagates
        Checker(a_spec, level=2).check()

    def test_l3_nested_import_with_terminating_loop(self, tmp_path):
        """L3 check propagates through two levels of file-based imports."""
        lib_spec = {
            "nail": "0.1.0",
            "kind": "module",
            "id": "lib",
            "exports": ["loop_fn"],
            "defs": [
                {
                    "nail": "0.1.0", "kind": "fn", "id": "loop_fn",
                    "effects": [], "params": [], "returns": UNIT_T,
                    "body": [
                        {
                            "op": "loop", "bind": "i",
                            "from": {"lit": 0}, "to": {"lit": 5}, "step": {"lit": 1},
                            "body": [],
                        },
                        {"op": "return", "val": {"lit": None, "type": UNIT_T}},
                    ],
                }
            ],
        }
        lib_path = tmp_path / "lib.nail"
        lib_path.write_text(json.dumps(lib_spec), encoding="utf-8")

        caller_spec = {
            "nail": "0.1.0",
            "kind": "module",
            "id": "caller",
            "imports": [{"module": "lib", "fns": ["loop_fn"], "from": str(lib_path)}],
            "exports": ["main"],
            "defs": [
                {
                    "nail": "0.1.0", "kind": "fn", "id": "main",
                    "effects": [], "params": [], "returns": UNIT_T,
                    "body": [{"op": "return", "val": {"lit": None, "type": UNIT_T}}],
                }
            ],
        }
        # L3: must pass because lib's loop has a literal step
        Checker(caller_spec, level=3).check()

    def test_l3_nested_import_with_zero_step_raises(self, tmp_path):
        """L3 check via file import: zero-step loop in imported module raises."""
        lib_spec = {
            "nail": "0.1.0",
            "kind": "module",
            "id": "lib",
            "exports": ["bad_loop"],
            "defs": [
                {
                    "nail": "0.1.0", "kind": "fn", "id": "bad_loop",
                    "effects": [], "params": [], "returns": UNIT_T,
                    "body": [
                        {
                            "op": "loop", "bind": "i",
                            "from": {"lit": 0}, "to": {"lit": 10}, "step": {"lit": 0},
                            "body": [],
                        },
                        {"op": "return", "val": {"lit": None, "type": UNIT_T}},
                    ],
                }
            ],
        }
        lib_path = tmp_path / "lib.nail"
        lib_path.write_text(json.dumps(lib_spec), encoding="utf-8")

        caller_spec = {
            "nail": "0.1.0",
            "kind": "module",
            "id": "caller",
            "imports": [{"module": "lib", "fns": ["bad_loop"], "from": str(lib_path)}],
            "exports": ["main"],
            "defs": [
                {
                    "nail": "0.1.0", "kind": "fn", "id": "main",
                    "effects": [], "params": [], "returns": UNIT_T,
                    "body": [{"op": "return", "val": {"lit": None, "type": UNIT_T}}],
                }
            ],
        }
        with pytest.raises(CheckError) as exc_info:
            Checker(caller_spec, level=3).check()
        assert "infinite loop" in str(exc_info.value).lower()


if __name__ == "__main__":
    unittest.main()
