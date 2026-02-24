#!/usr/bin/env python3
"""
NAIL L3 Termination Proof Test Suite

Tests the L3 verification level: loop termination proofs and recursive
decreasing-measure annotations.

Run: python -m pytest tests/test_l3_termination.py -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter import Checker, CheckError, NailTypeError, NailEffectError

# ── Type shorthands ────────────────────────────────────────────────────────

INT64 = {"type": "int", "bits": 64, "overflow": "panic"}
BOOL_T = {"type": "bool"}
STR_T = {"type": "string"}
UNIT_T = {"type": "unit"}


def fn_spec(fn_id, params, returns, body, effects=None, termination=None):
    spec = {
        "nail": "0.1.0",
        "kind": "fn",
        "id": fn_id,
        "effects": effects or [],
        "params": params,
        "returns": returns,
        "body": body,
    }
    if termination is not None:
        spec["termination"] = termination
    return spec


def module_spec(module_id, defs, exports=None):
    return {
        "nail": "0.1.0",
        "kind": "module",
        "id": module_id,
        "exports": exports or [],
        "defs": defs,
    }


def check_l3(spec, modules=None):
    """Run a level-3 check; raises CheckError on failure."""
    Checker(spec, modules=modules or {}, level=3).check()


def check_l2(spec, modules=None):
    """Run a level-2 check (default)."""
    Checker(spec, modules=modules or {}, level=2).check()


# ── Helper specs ────────────────────────────────────────────────────────────

def loop_fn(fn_id, from_expr, to_expr, step_expr, bind="i"):
    """Build a fn-kind spec with a single loop statement."""
    body = [
        {
            "op": "loop",
            "bind": bind,
            "from": from_expr,
            "to": to_expr,
            "step": step_expr,
            "body": [],
        },
        {"op": "return", "val": {"lit": None, "type": UNIT_T}},
    ]
    return fn_spec(fn_id, [], UNIT_T, body)


def loop_module(fn_id, from_expr, to_expr, step_expr, bind="i"):
    """Build a module spec with a single function containing one loop."""
    body = [
        {
            "op": "loop",
            "bind": bind,
            "from": from_expr,
            "to": to_expr,
            "step": step_expr,
            "body": [],
        },
        {"op": "return", "val": {"lit": None, "type": UNIT_T}},
    ]
    fn = fn_spec(fn_id, [], UNIT_T, body)
    return module_spec("mod", [fn], exports=[fn_id])


# ═══════════════════════════════════════════════════════════════════════════
#  PASS CASES — level=3 should succeed
# ═══════════════════════════════════════════════════════════════════════════

class TestL3PassCases(unittest.TestCase):

    def test_step_positive_literal(self):
        """step=1, from=0, to=10 — trivially terminates."""
        spec = loop_fn("count_up",
                       from_expr={"lit": 0},
                       to_expr={"lit": 10},
                       step_expr={"lit": 1})
        check_l3(spec)  # must not raise

    def test_step_negative_literal(self):
        """step=-1, from=10, to=0 — terminates (counts down)."""
        spec = loop_fn("count_down",
                       from_expr={"lit": 10},
                       to_expr={"lit": 0},
                       step_expr={"lit": -1})
        check_l3(spec)  # must not raise

    def test_step_two_variable_bounds(self):
        """step=2 with variable from/to — step is literal so proof succeeds."""
        body = [
            {
                "op": "loop",
                "bind": "i",
                "from": {"ref": "start"},
                "to": {"ref": "end"},
                "step": {"lit": 2},
                "body": [],
            },
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ]
        fn = fn_spec(
            "skip_two",
            params=[
                {"id": "start", "type": INT64},
                {"id": "end", "type": INT64},
            ],
            returns=UNIT_T,
            body=body,
        )
        check_l3(fn)

    def test_step_large_positive(self):
        """step=100 — non-zero literal, passes L3."""
        spec = loop_fn("big_step",
                       from_expr={"lit": 0},
                       to_expr={"lit": 1000},
                       step_expr={"lit": 100})
        check_l3(spec)

    def test_step_negative_five(self):
        """step=-5 — non-zero literal, passes L3."""
        spec = loop_fn("neg_five",
                       from_expr={"lit": 100},
                       to_expr={"lit": 0},
                       step_expr={"lit": -5})
        check_l3(spec)

    def test_trivially_empty_loop_positive_step_from_gt_to(self):
        """step>0 but from>to — loop never executes, trivially terminates.
        L3 should still pass (contradiction is noted but not an error)."""
        spec = loop_fn("empty_fwd",
                       from_expr={"lit": 10},
                       to_expr={"lit": 0},
                       step_expr={"lit": 1})
        check_l3(spec)  # trivially terminates — OK

    def test_trivially_empty_loop_negative_step_from_lt_to(self):
        """step<0 but from<to — loop never executes, trivially terminates."""
        spec = loop_fn("empty_bwd",
                       from_expr={"lit": 0},
                       to_expr={"lit": 10},
                       step_expr={"lit": -1})
        check_l3(spec)  # trivially terminates — OK

    def test_module_loop_terminates(self):
        """Module-level function with terminating loop passes L3."""
        spec = loop_module("sum_up",
                           from_expr={"lit": 0},
                           to_expr={"lit": 100},
                           step_expr={"lit": 1})
        check_l3(spec)

    def test_termination_certificate_populated(self):
        """get_termination_certificate() returns correct data after check."""
        spec = loop_module("verify_cert",
                           from_expr={"lit": 0},
                           to_expr={"lit": 5},
                           step_expr={"lit": 1})
        checker = Checker(spec, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        self.assertEqual(cert["level"], 3)
        self.assertEqual(cert["verdict"], "all_loops_terminate")
        self.assertGreater(cert["functions_verified"], 0)
        proofs = cert["proofs"]
        self.assertIn("verify_cert", proofs)
        loop_proof = proofs["verify_cert"][0]
        self.assertEqual(loop_proof["kind"], "loop")
        self.assertEqual(loop_proof["verdict"], "terminates")
        self.assertEqual(loop_proof["proof"], "step_nonzero_literal")
        self.assertTrue(loop_proof["step_literal"])

    def test_recursive_function_with_termination_annotation(self):
        """Recursive function with termination annotation passes L3."""
        # factorial-like: calls itself with n-1
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
                            "fn": "fact",
                            "args": [
                                {"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}
                            ],
                        },
                    }
                ],
            }
        ]
        fn = fn_spec(
            "fact",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
            body=body,
            termination={"measure": "n"},
        )
        spec = module_spec("fact_mod", [fn], exports=["fact"])
        check_l3(spec)  # must not raise

    def test_recursive_certificate_populated(self):
        """Recursive function termination proof appears in certificate."""
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
                            "fn": "rec",
                            "args": [
                                {"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}
                            ],
                        },
                    }
                ],
            }
        ]
        fn = fn_spec(
            "rec",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
            body=body,
            termination={"measure": "n"},
        )
        spec = module_spec("rec_mod", [fn], exports=["rec"])
        checker = Checker(spec, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        self.assertIn("rec", cert["proofs"])
        rec_proofs = cert["proofs"]["rec"]
        recursion_proofs = [p for p in rec_proofs if p["kind"] == "recursion"]
        self.assertTrue(len(recursion_proofs) > 0)
        self.assertEqual(recursion_proofs[0]["measure"], "n")
        self.assertEqual(recursion_proofs[0]["verdict"], "terminates")

    def test_l2_does_not_check_step_zero(self):
        """At level=2, step=0 is allowed (L3-only check)."""
        spec = loop_fn("zero_step_l2",
                       from_expr={"lit": 0},
                       to_expr={"lit": 10},
                       step_expr={"lit": 0})
        check_l2(spec)  # must NOT raise at L2

    def test_l2_does_not_check_variable_step(self):
        """At level=2, variable step is allowed (L3-only check)."""
        body = [
            {
                "op": "loop",
                "bind": "i",
                "from": {"lit": 0},
                "to": {"lit": 10},
                "step": {"ref": "s"},
                "body": [],
            },
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ]
        fn = fn_spec(
            "var_step_l2",
            params=[{"id": "s", "type": INT64}],
            returns=UNIT_T,
            body=body,
        )
        check_l2(fn)  # must NOT raise at L2

    def test_l3_empty_certificate_when_no_loops(self):
        """When there are no loops, certificate has functions_verified=0."""
        fn = fn_spec("no_loops", [], UNIT_T,
                     [{"op": "return", "val": {"lit": None, "type": UNIT_T}}])
        checker = Checker(fn, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        self.assertEqual(cert["functions_verified"], 0)
        self.assertEqual(cert["verdict"], "all_loops_terminate")


# ═══════════════════════════════════════════════════════════════════════════
#  FAIL CASES — level=3 should raise CheckError
# ═══════════════════════════════════════════════════════════════════════════

class TestL3FailCases(unittest.TestCase):

    def test_step_zero_raises(self):
        """step=0 is an infinite loop — CheckError at L3."""
        spec = loop_fn("inf_loop",
                       from_expr={"lit": 0},
                       to_expr={"lit": 10},
                       step_expr={"lit": 0})
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        self.assertIn("infinite loop", str(ctx.exception).lower())

    def test_step_variable_raises(self):
        """Variable step has no proof of non-zero — CheckError at L3."""
        body = [
            {
                "op": "loop",
                "bind": "i",
                "from": {"lit": 0},
                "to": {"lit": 10},
                "step": {"ref": "s"},
                "body": [],
            },
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ]
        fn = fn_spec(
            "var_step",
            params=[{"id": "s", "type": INT64}],
            returns=UNIT_T,
            body=body,
        )
        with self.assertRaises(CheckError) as ctx:
            check_l3(fn)
        self.assertIn("literal", str(ctx.exception).lower())

    def test_recursive_without_annotation_raises(self):
        """Recursive function without termination annotation → CheckError at L3."""
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
                            "fn": "unannotated",
                            "args": [
                                {"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}
                            ],
                        },
                    }
                ],
            }
        ]
        fn = fn_spec(
            "unannotated",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
            body=body,
            # No termination annotation
        )
        spec = module_spec("mod", [fn], exports=["unannotated"])
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        msg = str(ctx.exception).lower()
        self.assertTrue("recursive" in msg or "termination" in msg)

    def test_termination_measure_nonexistent_param_raises(self):
        """termination.measure references a param that doesn't exist → CheckError."""
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
                            "fn": "bad_measure",
                            "args": [
                                {"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}
                            ],
                        },
                    }
                ],
            }
        ]
        fn = fn_spec(
            "bad_measure",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
            body=body,
            termination={"measure": "nonexistent_param"},
        )
        spec = module_spec("mod", [fn], exports=["bad_measure"])
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        self.assertIn("nonexistent_param", str(ctx.exception))

    def test_recursive_l2_still_raises_without_annotation(self):
        """At L2, recursion is still forbidden (no annotation bypass at L2)."""
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
                            "fn": "rec_l2",
                            "args": [
                                {"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}
                            ],
                        },
                    }
                ],
            }
        ]
        fn = fn_spec(
            "rec_l2",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
            body=body,
        )
        spec = module_spec("mod", [fn], exports=["rec_l2"])
        with self.assertRaises(CheckError) as ctx:
            check_l2(spec)
        self.assertIn("Recursive", str(ctx.exception))

    def test_step_float_raises(self):
        """step literal must be int, not float — CheckError at L3."""
        spec = loop_fn("float_step",
                       from_expr={"lit": 0},
                       to_expr={"lit": 10},
                       step_expr={"lit": 1.5})
        # Note: this will fail at L1 (type check) since step must be int
        # OR at L3 if L1 passed; either way a CheckError is expected
        with self.assertRaises((CheckError, NailTypeError)):
            check_l3(spec)

    def test_termination_annotation_missing_measure_field_raises(self):
        """termination present but measure is empty string → CheckError."""
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
                            "fn": "no_measure",
                            "args": [
                                {"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}
                            ],
                        },
                    }
                ],
            }
        ]
        fn = fn_spec(
            "no_measure",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
            body=body,
            termination={"measure": ""},  # empty string = missing
        )
        spec = module_spec("mod", [fn], exports=["no_measure"])
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        self.assertIn("measure", str(ctx.exception).lower())


# ═══════════════════════════════════════════════════════════════════════════
#  CERTIFICATE CONTENT TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestL3Certificate(unittest.TestCase):

    def test_certificate_has_correct_structure(self):
        """Certificate always contains level, verdict, functions_verified, proofs."""
        fn = fn_spec("empty_fn", [], UNIT_T,
                     [{"op": "return", "val": {"lit": None, "type": UNIT_T}}])
        checker = Checker(fn, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        self.assertIn("level", cert)
        self.assertIn("verdict", cert)
        self.assertIn("functions_verified", cert)
        self.assertIn("proofs", cert)
        self.assertEqual(cert["level"], 3)

    def test_positive_step_loop_proof_fields(self):
        """Loop proof dict contains expected fields."""
        spec = loop_fn("loop_fields",
                       from_expr={"lit": 0},
                       to_expr={"lit": 5},
                       step_expr={"lit": 1})
        checker = Checker(spec, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        proof = cert["proofs"]["loop_fields"][0]
        self.assertEqual(proof["kind"], "loop")
        self.assertEqual(proof["step"], 1)
        self.assertTrue(proof["step_literal"])
        self.assertEqual(proof["verdict"], "terminates")
        self.assertEqual(proof["proof"], "step_nonzero_literal")

    def test_contradiction_noted_in_proof(self):
        """When step>0 but from>to, the note field records the contradiction."""
        spec = loop_fn("contradicted",
                       from_expr={"lit": 10},
                       to_expr={"lit": 0},
                       step_expr={"lit": 1})
        checker = Checker(spec, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        proof = cert["proofs"]["contradicted"][0]
        self.assertIsNotNone(proof["note"])
        self.assertIn("positive", proof["note"])

    def test_no_contradiction_when_direction_correct(self):
        """When step/from/to are consistent, note is None."""
        spec = loop_fn("consistent",
                       from_expr={"lit": 0},
                       to_expr={"lit": 10},
                       step_expr={"lit": 1})
        checker = Checker(spec, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        proof = cert["proofs"]["consistent"][0]
        self.assertIsNone(proof["note"])

    def test_multiple_loops_all_in_certificate(self):
        """Multiple loops in one function are all recorded."""
        body = [
            {
                "op": "loop", "bind": "i",
                "from": {"lit": 0}, "to": {"lit": 3}, "step": {"lit": 1},
                "body": [],
            },
            {
                "op": "loop", "bind": "j",
                "from": {"lit": 10}, "to": {"lit": 0}, "step": {"lit": -2},
                "body": [],
            },
            {"op": "return", "val": {"lit": None, "type": UNIT_T}},
        ]
        fn = fn_spec("two_loops", [], UNIT_T, body)
        checker = Checker(fn, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        self.assertEqual(len(cert["proofs"]["two_loops"]), 2)


if __name__ == "__main__":
    unittest.main()
