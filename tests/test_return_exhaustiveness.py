"""
Tests for return-path exhaustiveness checking (Issue #43).
Verifies that checker.py rejects functions where not all code paths return.
"""
import json
import pytest
from interpreter.checker import Checker, CheckError


def make_fn(body, return_type=None, params=None, effects=None):
    """Helper: build a minimal NAIL fn spec."""
    if return_type is None:
        return_type = {"type": "int", "bits": 64, "overflow": "panic"}
    return {
        "nail": "0.4",
        "kind": "fn",
        "id": "test_fn",
        "effects": effects or [],
        "params": params or [{"id": "x", "type": {"type": "int", "bits": 64, "overflow": "panic"}}],
        "returns": return_type,
        "body": body,
    }


class TestIfExhaustiveness:
    def test_if_without_else_fails(self):
        """if without else is always rejected (NAIL requires explicit else)."""
        spec = make_fn([
            {"op": "if",
             "cond": {"op": "gt", "l": {"ref": "x"}, "r": {"lit": 0}},
             "then": [{"op": "return", "val": {"ref": "x"}}]}
        ])
        with pytest.raises(CheckError, match="missing 'else'"):
            Checker(spec).check()

    def test_if_with_both_branches_passes(self):
        """if/else where both branches return is valid."""
        spec = make_fn([
            {"op": "if",
             "cond": {"op": "gt", "l": {"ref": "x"}, "r": {"lit": 0}},
             "then": [{"op": "return", "val": {"ref": "x"}}],
             "else": [{"op": "return", "val": {"lit": 0}}]}
        ])
        Checker(spec).check()  # should not raise

    def test_if_else_neither_branch_returns_fails(self):
        """if/else where neither branch returns → not all paths return."""
        spec = make_fn([
            {"op": "if",
             "cond": {"op": "gt", "l": {"ref": "x"}, "r": {"lit": 0}},
             "then": [{"op": "let", "id": "a", "val": {"lit": 1}}],
             "else": [{"op": "let", "id": "b", "val": {"lit": 2}}]}
        ])
        with pytest.raises(CheckError, match="Not all code paths"):
            Checker(spec).check()


class TestBodyExhaustiveness:
    def test_empty_body_nonunit_fails(self):
        """Empty body with non-unit return type is rejected."""
        spec = make_fn([])
        with pytest.raises(CheckError, match="Not all code paths"):
            Checker(spec).check()

    def test_only_let_ops_fails(self):
        """Body with only let ops and no return is rejected."""
        spec = make_fn([
            {"op": "let", "id": "y", "val": {"lit": 42}}
        ])
        with pytest.raises(CheckError, match="Not all code paths"):
            Checker(spec).check()

    def test_explicit_return_passes(self):
        """Simple body ending in return is valid."""
        spec = make_fn([
            {"op": "return", "val": {"ref": "x"}}
        ])
        Checker(spec).check()  # should not raise


class TestMatchEnumExhaustiveness:
    def test_match_enum_case_missing_return_fails(self):
        """match_enum where one case body doesn't return is rejected."""
        spec = {
            "nail": "0.4", "kind": "module", "id": "test_mod",
            "exports": ["classify"],
            "types": {
                "Sign": {
                    "type": "enum",
                    "variants": [{"tag": "Pos"}, {"tag": "Neg"}, {"tag": "Zero"}]
                }
            },
            "defs": [{
                "nail": "0.4", "kind": "fn", "id": "classify",
                "effects": [], "params": [{"id": "s", "type": {"type": "alias", "name": "Sign"}}],
                "returns": {"type": "int", "bits": 64, "overflow": "panic"},
                "body": [{
                    "op": "match_enum", "val": {"ref": "s"}, "cases": [
                        {"tag": "Pos", "body": [{"op": "return", "val": {"lit": 1}}]},
                        {"tag": "Neg", "body": [{"op": "return", "val": {"lit": -1}}]},
                        {"tag": "Zero", "body": [{"op": "let", "id": "z", "val": {"lit": 0}}]}
                        # Zero case missing return → should fail
                    ]
                }]
            }]
        }
        with pytest.raises(CheckError):
            Checker(spec).check()


class TestReturnVoid:
    def test_return_void_in_unit_fn_passes(self):
        """return_void in a unit-return function is valid."""
        spec = {
            "nail": "0.4",
            "kind": "fn",
            "id": "test_fn",
            "effects": [],
            "params": [],
            "returns": {"type": "unit"},
            "body": [{"op": "return_void"}],
        }
        Checker(spec).check()  # should not raise

    def test_return_void_guarantees_return(self):
        """return_void counts as a guaranteed return path."""
        spec = {
            "nail": "0.4",
            "kind": "fn",
            "id": "test_fn",
            "effects": [],
            "params": [{"id": "x", "type": {"type": "bool"}}],
            "returns": {"type": "unit"},
            "body": [
                {
                    "op": "if",
                    "cond": {"ref": "x"},
                    "then": [{"op": "return_void"}],
                    "else": [{"op": "return_void"}],
                }
            ],
        }
        Checker(spec).check()  # should not raise

    def test_return_void_in_non_unit_fn_fails(self):
        """return_void in a function that returns int is rejected."""
        spec = {
            "nail": "0.4",
            "kind": "fn",
            "id": "test_fn",
            "effects": [],
            "params": [],
            "returns": {"type": "int", "bits": 64, "overflow": "panic"},
            "body": [{"op": "return_void"}],
        }
        with pytest.raises(CheckError, match="non-unit return type"):
            Checker(spec).check()

    def test_return_void_produces_unit_return_type(self):
        """A unit-return fn using return_void satisfies the unit return constraint."""
        # Build a module where main calls a helper that uses return_void.
        spec = {
            "nail": "0.4",
            "kind": "module",
            "id": "test_mod",
            "exports": ["run"],
            "defs": [
                {
                    "nail": "0.4",
                    "kind": "fn",
                    "id": "helper",
                    "effects": [],
                    "params": [],
                    "returns": {"type": "unit"},
                    "body": [{"op": "return_void"}],
                },
                {
                    "nail": "0.4",
                    "kind": "fn",
                    "id": "run",
                    "effects": [],
                    "params": [],
                    "returns": {"type": "unit"},
                    "body": [
                        {"op": "call", "fn": "helper", "args": []},
                        {"op": "return_void"},
                    ],
                },
            ],
        }
        Checker(spec).check()  # should not raise


class TestUnitReturnExemption:
    def test_unit_fn_if_without_else_still_fails(self):
        """Even unit-return functions need explicit else (NAIL zero-ambiguity)."""
        spec = make_fn(
            body=[
                {"op": "if",
                 "cond": {"op": "gt", "l": {"ref": "x"}, "r": {"lit": 0}},
                 "then": [{"op": "let", "id": "a", "val": {"lit": 1}}]}
            ],
            return_type={"type": "unit"},
            effects=[]
        )
        with pytest.raises(CheckError, match="missing 'else'"):
            Checker(spec).check()

    def test_unit_fn_no_return_passes(self):
        """Unit-return function with no return op is valid."""
        spec = make_fn(
            body=[{"op": "let", "id": "a", "val": {"lit": 42}}],
            return_type={"type": "unit"},
            effects=[]
        )
        Checker(spec).check()  # should not raise
