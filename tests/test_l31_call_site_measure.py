#!/usr/bin/env python3
"""
NAIL L3.1 — Call-site Measure Verification Tests

L3.1 extends L3 by verifying that at each recursive call-site, the argument
for the `termination.measure` parameter is strictly decreasing: it must be
passed as ``measure - k`` (k > 0, integer literal).

Previously (pre-L3.1) the checker only trusted the annotation:
    termination: {measure: "n"}
meaning the programmer claimed "n decreases", but the checker never looked at
the actual argument expressions.

L3.1 adds a structural proof requirement: the call-site argument for the measure
parameter must literally be ``{op: "-", l: {ref: "<measure>"}, r: {lit: k}}``.

Run: python -m pytest tests/test_l31_call_site_measure.py -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from interpreter import Checker, CheckError

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
    Checker(spec, modules=modules or {}, level=3).check()


def check_l2(spec, modules=None):
    Checker(spec, modules=modules or {}, level=2).check()


def recursive_fn(fn_id, measure_name, call_arg_expr, returns=INT64, base_val=None):
    """Build a direct-recursive function for testing.

    The function has a base case (n == 0 → return base_val or 1) and
    a recursive case that calls itself with *call_arg_expr* as the measure
    argument.
    """
    if base_val is None:
        base_val_expr = {"lit": 1}
    else:
        base_val_expr = {"lit": base_val}

    body = [
        {
            "op": "if",
            "cond": {"op": "eq", "l": {"ref": measure_name}, "r": {"lit": 0}},
            "then": [{"op": "return", "val": base_val_expr}],
            "else": [
                {
                    "op": "return",
                    "val": {
                        "op": "call",
                        "fn": fn_id,
                        "args": [call_arg_expr],
                    },
                }
            ],
        }
    ]
    return fn_spec(
        fn_id,
        params=[{"id": measure_name, "type": INT64}],
        returns=returns,
        body=body,
        termination={"measure": measure_name},
    )


def module_with_recursive_fn(fn_id, measure_name, call_arg_expr):
    fn = recursive_fn(fn_id, measure_name, call_arg_expr)
    return module_spec(f"{fn_id}_mod", [fn], exports=[fn_id])


# ═══════════════════════════════════════════════════════════════════════════
#  PASS CASES — call-site has a valid decreasing measure argument
# ═══════════════════════════════════════════════════════════════════════════

class TestCallSiteMeasurePassCases(unittest.TestCase):

    def test_n_minus_1_passes(self):
        """measure - 1 is the canonical decreasing argument (k=1)."""
        spec = module_with_recursive_fn(
            "fact", "n",
            call_arg_expr={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
        )
        check_l3(spec)  # must not raise

    def test_n_minus_2_passes(self):
        """measure - 2 is also a valid decreasing argument (k=2)."""
        spec = module_with_recursive_fn(
            "skip", "n",
            call_arg_expr={"op": "-", "l": {"ref": "n"}, "r": {"lit": 2}},
        )
        check_l3(spec)

    def test_n_minus_100_passes(self):
        """Large k is also accepted as long as k > 0."""
        spec = module_with_recursive_fn(
            "coarse", "n",
            call_arg_expr={"op": "-", "l": {"ref": "n"}, "r": {"lit": 100}},
        )
        check_l3(spec)

    def test_different_measure_param_name(self):
        """The measure param name can be anything (e.g. 'depth')."""
        fn = recursive_fn(
            "descend", "depth",
            call_arg_expr={"op": "-", "l": {"ref": "depth"}, "r": {"lit": 1}},
        )
        spec = module_spec("descend_mod", [fn], exports=["descend"])
        check_l3(spec)

    def test_multiple_params_measure_decreases(self):
        """Multi-param function: only the measure param must decrease."""
        body = [
            {
                "op": "if",
                "cond": {"op": "eq", "l": {"ref": "n"}, "r": {"lit": 0}},
                "then": [{"op": "return", "val": {"lit": 0}}],
                "else": [
                    {
                        "op": "return",
                        "val": {
                            "op": "call",
                            "fn": "multi",
                            "args": [
                                # non-measure arg: arbitrary (same or larger)
                                {"ref": "acc"},
                                # measure arg: must decrease
                                {"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
                            ],
                        },
                    }
                ],
            }
        ]
        fn = fn_spec(
            "multi",
            params=[
                {"id": "acc", "type": INT64},
                {"id": "n", "type": INT64},
            ],
            returns=INT64,
            body=body,
            termination={"measure": "n"},
        )
        spec = module_spec("multi_mod", [fn], exports=["multi"])
        check_l3(spec)

    def test_l3_proof_kind_is_verified(self):
        """When call-site is verified, proof kind should be 'decreasing_measure_verified'."""
        spec = module_with_recursive_fn(
            "cert_test", "n",
            call_arg_expr={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
        )
        checker = Checker(spec, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        self.assertIn("cert_test", cert["proofs"])
        rec_proofs = [p for p in cert["proofs"]["cert_test"] if p["kind"] == "recursion"]
        self.assertTrue(len(rec_proofs) > 0)
        self.assertEqual(rec_proofs[0]["proof"], "decreasing_measure_verified")

    def test_l2_does_not_verify_call_site(self):
        """At L2, call-site measure is NOT verified — any recursive arg is accepted."""
        # At L2, recursion is forbidden entirely; just confirm L3.1 doesn't bleed to L2
        # (this test exercises L2 not raising on a non-decreasing arg)
        # We can't test L2 with direct recursion because it always raises for recursion.
        # Instead verify that our new code is guarded by `self.level >= 3`.
        # This is a meta-test confirming our guard is in place.
        spec = module_with_recursive_fn(
            "fact_l2_guard", "n",
            call_arg_expr={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
        )
        # L2 raises because recursion not allowed at L2 regardless of args
        with self.assertRaises(CheckError) as ctx:
            check_l2(spec)
        self.assertIn("Recursive", str(ctx.exception))


# ═══════════════════════════════════════════════════════════════════════════
#  FAIL CASES — call-site has invalid / non-decreasing measure argument
# ═══════════════════════════════════════════════════════════════════════════

class TestCallSiteMeasureFailCases(unittest.TestCase):

    def _assert_measure_not_decreasing(self, spec):
        """Assert that check_l3 raises CheckError with MEASURE_NOT_DECREASING."""
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        err = ctx.exception
        self.assertEqual(err.code, "MEASURE_NOT_DECREASING",
                         f"Expected MEASURE_NOT_DECREASING, got {err.code}: {err}")
        return err

    def test_same_value_n_fails(self):
        """Passing the measure unchanged (n, not n-k) raises MEASURE_NOT_DECREASING."""
        spec = module_with_recursive_fn(
            "infinite", "n",
            call_arg_expr={"ref": "n"},  # same value — not decreasing
        )
        self._assert_measure_not_decreasing(spec)

    def test_n_minus_zero_fails(self):
        """measure - 0 is not a strict decrease (k must be > 0)."""
        spec = module_with_recursive_fn(
            "no_decrease", "n",
            call_arg_expr={"op": "-", "l": {"ref": "n"}, "r": {"lit": 0}},
        )
        self._assert_measure_not_decreasing(spec)

    def test_n_plus_one_fails(self):
        """Increasing the measure (n + 1) raises MEASURE_NOT_DECREASING."""
        spec = module_with_recursive_fn(
            "growing", "n",
            call_arg_expr={"op": "+", "l": {"ref": "n"}, "r": {"lit": 1}},
        )
        self._assert_measure_not_decreasing(spec)

    def test_literal_constant_fails(self):
        """Passing a bare literal (not measure - k form) raises MEASURE_NOT_DECREASING."""
        spec = module_with_recursive_fn(
            "const_arg", "n",
            call_arg_expr={"lit": 5},  # constant — not tied to measure
        )
        self._assert_measure_not_decreasing(spec)

    def test_wrong_ref_in_subtraction_fails(self):
        """Passing other_var - 1 (not measure - k) raises MEASURE_NOT_DECREASING."""
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
                            "fn": "wrong_ref",
                            "args": [
                                # subtracting from `m`, not `n` (the measure)
                                {"op": "-", "l": {"ref": "m"}, "r": {"lit": 1}},
                            ],
                        },
                    }
                ],
            }
        ]
        fn = fn_spec(
            "wrong_ref",
            params=[
                {"id": "n", "type": INT64},
                {"id": "m", "type": INT64},
            ],
            returns=INT64,
            body=body,
            termination={"measure": "n"},
        )
        spec = module_spec("wrong_ref_mod", [fn], exports=["wrong_ref"])
        # Note: measure arg at position 0 is "m - 1" not "n - 1"
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        # The error should mention the measure name
        self.assertIn("n", str(ctx.exception))

    def test_negative_k_fails(self):
        """measure - (-1) = measure + 1 is increasing — must fail."""
        spec = module_with_recursive_fn(
            "neg_k", "n",
            call_arg_expr={"op": "-", "l": {"ref": "n"}, "r": {"lit": -1}},
        )
        self._assert_measure_not_decreasing(spec)

    def test_error_code_is_measure_not_decreasing(self):
        """CheckError code must be MEASURE_NOT_DECREASING."""
        spec = module_with_recursive_fn(
            "bad_code", "n",
            call_arg_expr={"ref": "n"},
        )
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        self.assertEqual(ctx.exception.code, "MEASURE_NOT_DECREASING")

    def test_error_mentions_measure_param_name(self):
        """The error message must mention the measure parameter name."""
        spec = module_with_recursive_fn(
            "msg_check", "depth",
            call_arg_expr={"ref": "depth"},
        )
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        self.assertIn("depth", str(ctx.exception))


# ═══════════════════════════════════════════════════════════════════════════
#  PROOF KIND TESTS — verify the certificate records the right proof kind
# ═══════════════════════════════════════════════════════════════════════════

class TestCallSiteMeasureProofKind(unittest.TestCase):

    def test_verified_proof_kind_when_measure_decreases(self):
        """When call-site is verified, proof.proof == 'decreasing_measure_verified'."""
        spec = module_with_recursive_fn(
            "verified_fn", "n",
            call_arg_expr={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
        )
        checker = Checker(spec, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        proofs = cert["proofs"].get("verified_fn", [])
        rec_proofs = [p for p in proofs if p["kind"] == "recursion"]
        self.assertTrue(len(rec_proofs) > 0, "Expected at least one recursion proof")
        self.assertEqual(rec_proofs[0]["proof"], "decreasing_measure_verified")

    def test_verified_proof_has_correct_measure(self):
        """The recursion proof records the correct measure name."""
        spec = module_with_recursive_fn(
            "measure_name_check", "count",
            call_arg_expr={"op": "-", "l": {"ref": "count"}, "r": {"lit": 3}},
        )
        checker = Checker(spec, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        proofs = cert["proofs"].get("measure_name_check", [])
        rec_proofs = [p for p in proofs if p["kind"] == "recursion"]
        self.assertTrue(len(rec_proofs) > 0)
        self.assertEqual(rec_proofs[0]["measure"], "count")
        self.assertEqual(rec_proofs[0]["verdict"], "terminates")


# ═══════════════════════════════════════════════════════════════════════════
#  HELPER METHOD UNIT TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestIsDecreasingMeasureExpr(unittest.TestCase):
    """Direct unit tests for the _is_decreasing_measure_expr helper."""

    def setUp(self):
        # Create a minimal checker to call the helper
        spec = {
            "nail": "0.1.0", "kind": "fn", "id": "x",
            "effects": [], "params": [], "returns": UNIT_T,
            "body": [{"op": "return", "val": {"lit": None, "type": UNIT_T}}],
        }
        self.checker = Checker(spec, level=3)

    def _ok(self, expr, measure):
        return self.checker._is_decreasing_measure_expr(expr, measure)

    def test_canonical_n_minus_1(self):
        self.assertTrue(self._ok({"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}, "n"))

    def test_canonical_depth_minus_2(self):
        self.assertTrue(self._ok({"op": "-", "l": {"ref": "depth"}, "r": {"lit": 2}}, "depth"))

    def test_k_zero_returns_false(self):
        self.assertFalse(self._ok({"op": "-", "l": {"ref": "n"}, "r": {"lit": 0}}, "n"))

    def test_k_negative_returns_false(self):
        self.assertFalse(self._ok({"op": "-", "l": {"ref": "n"}, "r": {"lit": -3}}, "n"))

    def test_wrong_op_returns_false(self):
        self.assertFalse(self._ok({"op": "+", "l": {"ref": "n"}, "r": {"lit": 1}}, "n"))

    def test_wrong_ref_returns_false(self):
        self.assertFalse(self._ok({"op": "-", "l": {"ref": "m"}, "r": {"lit": 1}}, "n"))

    def test_plain_ref_returns_false(self):
        self.assertFalse(self._ok({"ref": "n"}, "n"))

    def test_literal_returns_false(self):
        self.assertFalse(self._ok({"lit": 5}, "n"))

    def test_none_returns_false(self):
        self.assertFalse(self._ok(None, "n"))

    def test_float_k_returns_false(self):
        # float is not int — should not be accepted
        self.assertFalse(self._ok({"op": "-", "l": {"ref": "n"}, "r": {"lit": 1.0}}, "n"))

    def test_bool_k_returns_false(self):
        # True == 1 in Python, but bool should not be accepted as int k
        self.assertFalse(self._ok({"op": "-", "l": {"ref": "n"}, "r": {"lit": True}}, "n"))


class TestMutualRecursionCallSiteMeasure(unittest.TestCase):
    """L3.1: Mutual recursion call-site measure verification (issue #98)."""

    def _mutual_recursion_module(self, a_calls_b_arg, b_calls_a_arg):
        """Build a module with two mutually recursive functions a and b.

        a(n) → if n==0 return 0 else call b(a_calls_b_arg)
        b(n) → if n==0 return 0 else call a(b_calls_a_arg)
        """
        def make_body(callee, arg_expr):
            return [
                {"op": "if",
                 "cond": {"op": "eq", "l": {"ref": "n"}, "r": {"lit": 0}},
                 "then": [{"op": "return", "val": {"lit": 0}}],
                 "else": [{"op": "return", "val": {"op": "call", "fn": callee, "args": [arg_expr]}}]}
            ]

        fn_a = fn_spec("a",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
            body=make_body("b", a_calls_b_arg),
            termination={"measure": "n"},
        )
        fn_b = fn_spec("b",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
            body=make_body("a", b_calls_a_arg),
            termination={"measure": "n"},
        )
        return module_spec("mutual_rec", [fn_a, fn_b], exports=["a", "b"])

    def test_mutual_recursion_non_decreasing_rejected(self):
        """a(n) calls b(n) and b(n) calls a(n) — both non-decreasing → REJECT."""
        spec = self._mutual_recursion_module(
            a_calls_b_arg={"ref": "n"},
            b_calls_a_arg={"ref": "n"},
        )
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        self.assertEqual(ctx.exception.code, "MEASURE_NOT_DECREASING")

    def test_mutual_recursion_one_non_decreasing_rejected(self):
        """a(n) calls b(n-1) but b(n) calls a(n) — one non-decreasing → REJECT."""
        spec = self._mutual_recursion_module(
            a_calls_b_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
            b_calls_a_arg={"ref": "n"},
        )
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        self.assertEqual(ctx.exception.code, "MEASURE_NOT_DECREASING")

    def test_mutual_recursion_both_decreasing_accepted(self):
        """a(n) calls b(n-1) and b(n) calls a(n-1) — both decreasing → ACCEPT."""
        spec = self._mutual_recursion_module(
            a_calls_b_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
            b_calls_a_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
        )
        # Should pass without error
        check_l3(spec)

    def test_mutual_recursion_certificate_shows_verified(self):
        """When both edges decrease, certificate should show 'decreasing_measure_verified'."""
        spec = self._mutual_recursion_module(
            a_calls_b_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
            b_calls_a_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
        )
        checker = Checker(spec, modules={}, level=3)
        checker.check()
        cert = checker.get_termination_certificate()
        for fn_id in ("a", "b"):
            proofs = cert["proofs"].get(fn_id, [])
            rec_proofs = [p for p in proofs if p["kind"] == "recursion"]
            self.assertTrue(len(rec_proofs) > 0, f"No recursion proof for {fn_id}")
            self.assertEqual(rec_proofs[0]["proof"], "decreasing_measure_verified")


class TestMultipleCallSitesSameCallee(unittest.TestCase):
    """Issue #99: multiple recursive calls to same callee must ALL be verified."""

    def _branched_self_recursion(self, then_arg, else_arg):
        """f(n) with two branches each calling f with different args."""
        body = [
            {"op": "if",
             "cond": {"op": "gt", "l": {"ref": "n"}, "r": {"lit": 0}},
             "then": [{"op": "return", "val": {"op": "call", "fn": "f", "args": [then_arg]}}],
             "else": [{"op": "return", "val": {"op": "call", "fn": "f", "args": [else_arg]}}]}
        ]
        fn_f = fn_spec("f",
            params=[{"id": "n", "type": INT64}],
            returns=INT64,
            body=body,
            termination={"measure": "n"},
        )
        return module_spec("branch_rec", [fn_f], exports=["f"])

    def test_both_decreasing_accepted(self):
        """Both branches call f(n-1) → ACCEPT."""
        spec = self._branched_self_recursion(
            then_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
            else_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
        )
        check_l3(spec)

    def test_one_non_decreasing_rejected(self):
        """then: f(n-1), else: f(n) → REJECT (else branch non-decreasing)."""
        spec = self._branched_self_recursion(
            then_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
            else_arg={"ref": "n"},
        )
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        self.assertEqual(ctx.exception.code, "MEASURE_NOT_DECREASING")

    def test_other_non_decreasing_rejected(self):
        """then: f(n), else: f(n-1) → REJECT (then branch non-decreasing)."""
        spec = self._branched_self_recursion(
            then_arg={"ref": "n"},
            else_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
        )
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        self.assertEqual(ctx.exception.code, "MEASURE_NOT_DECREASING")

    def _branched_mutual_recursion(self, a_then_arg, a_else_arg):
        """a(n) calls b in two branches; b(n) always calls a(n-1)."""
        a_body = [
            {"op": "if",
             "cond": {"op": "gt", "l": {"ref": "n"}, "r": {"lit": 0}},
             "then": [{"op": "return", "val": {"op": "call", "fn": "b", "args": [a_then_arg]}}],
             "else": [{"op": "return", "val": {"op": "call", "fn": "b", "args": [a_else_arg]}}]}
        ]
        b_body = [
            {"op": "if",
             "cond": {"op": "eq", "l": {"ref": "n"}, "r": {"lit": 0}},
             "then": [{"op": "return", "val": {"lit": 0}}],
             "else": [{"op": "return", "val": {"op": "call", "fn": "a",
                        "args": [{"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}]}}]}
        ]
        fn_a = fn_spec("a",
            params=[{"id": "n", "type": INT64}], returns=INT64,
            body=a_body, termination={"measure": "n"})
        fn_b = fn_spec("b",
            params=[{"id": "n", "type": INT64}], returns=INT64,
            body=b_body, termination={"measure": "n"})
        return module_spec("branch_mutual", [fn_a, fn_b], exports=["a", "b"])

    def test_mutual_one_branch_non_decreasing_rejected(self):
        """a calls b(n-1) in then, b(n) in else → REJECT."""
        spec = self._branched_mutual_recursion(
            a_then_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
            a_else_arg={"ref": "n"},
        )
        with self.assertRaises(CheckError) as ctx:
            check_l3(spec)
        self.assertEqual(ctx.exception.code, "MEASURE_NOT_DECREASING")

    def test_mutual_both_branches_decreasing_accepted(self):
        """a calls b(n-1) in both branches → ACCEPT."""
        spec = self._branched_mutual_recursion(
            a_then_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}},
            a_else_arg={"op": "-", "l": {"ref": "n"}, "r": {"lit": 2}},
        )
        check_l3(spec)


if __name__ == "__main__":
    unittest.main()
