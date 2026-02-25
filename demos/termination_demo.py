#!/usr/bin/env python3
"""
NAIL Termination Prover Demo
==============================
"Does this code run forever?"

Level 3 checker proves termination for loops (literal step) and recursion
(decreasing-measure annotation).  Five scenarios show PROVED, CAUGHT, and
REFUSED outcomes.

Run: python demos/termination_demo.py
"""

import json, sys, textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from interpreter import Checker, CheckError
from interpreter.types import NailEffectError

SEP = "─" * 64
INT_T = {"type": "int", "bits": 64, "overflow": "panic"}


def section(title: str):
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print(f"{'═' * 64}")


def check_nail_l3(spec: dict, label: str) -> bool:
    """Run L3 check → print certificate JSON on success."""
    raw = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    try:
        c = Checker(spec, raw_text=raw, level=3)
        c.check()
        cert = c.get_termination_certificate()
        print(f"  ✅ L3 checker: PROVED  ({label})")
        print(f"     Certificate: {json.dumps(cert, indent=2)}")
        return True
    except (CheckError, NailEffectError) as e:
        tag = "CAUGHT" if "zero" in str(e).lower() or "infinite" in str(e).lower() else "REFUSED"
        print(f"  ❌ L3 checker: {tag}  ({label})")
        print(f"     → {e}")
        return False


# ══════════════════════════════════════════════════════════════════════
# Scenario 1 — Bounded loop, step=1 → PROVED
# ══════════════════════════════════════════════════════════════════════
section("Scenario 1: Bounded loop (step=1)")

print(textwrap.dedent("""\
  A simple loop from 0 to 10 with step 1.
  L3 can prove this terminates: step is a non-zero literal.
"""))

nail_bounded = {
    "nail": "0.4", "kind": "fn", "id": "sum_to_10",
    "effects": [],
    "params": [],
    "returns": INT_T,
    "body": [
        {"op": "let", "id": "total", "type": INT_T, "val": {"lit": 0}, "mut": True},
        {"op": "loop", "bind": "i",
         "from": {"lit": 0}, "to": {"lit": 10}, "step": {"lit": 1},
         "body": [
             {"op": "assign", "id": "total",
              "val": {"op": "+", "l": {"ref": "total"}, "r": {"ref": "i"}}}
         ]},
        {"op": "return", "val": {"ref": "total"}},
    ],
}
check_nail_l3(nail_bounded, "step=1, bounded loop")


# ══════════════════════════════════════════════════════════════════════
# Scenario 2 — Zero step → CAUGHT (infinite loop)
# ══════════════════════════════════════════════════════════════════════
section("Scenario 2: Zero step (infinite loop)")

print(textwrap.dedent("""\
  The same loop but with step=0.
  This would run forever — L3 catches it immediately.
"""))

nail_zero_step = {
    "nail": "0.4", "kind": "fn", "id": "infinite_loop",
    "effects": [],
    "params": [],
    "returns": INT_T,
    "body": [
        {"op": "let", "id": "total", "type": INT_T, "val": {"lit": 0}, "mut": True},
        {"op": "loop", "bind": "i",
         "from": {"lit": 0}, "to": {"lit": 10}, "step": {"lit": 0},
         "body": [
             {"op": "assign", "id": "total",
              "val": {"op": "+", "l": {"ref": "total"}, "r": {"ref": "i"}}}
         ]},
        {"op": "return", "val": {"ref": "total"}},
    ],
}
check_nail_l3(nail_zero_step, "step=0 → infinite loop")


# ══════════════════════════════════════════════════════════════════════
# Scenario 3 — Variable step → REFUSED (can't prove)
# ══════════════════════════════════════════════════════════════════════
section("Scenario 3: Variable step (proof refused)")

print(textwrap.dedent("""\
  The step is a variable reference, not a literal.
  L3 cannot prove termination — the step could be zero at runtime.
"""))

nail_var_step = {
    "nail": "0.4", "kind": "fn", "id": "dynamic_loop",
    "effects": [],
    "params": [{"id": "step", "type": INT_T}],
    "returns": INT_T,
    "body": [
        {"op": "let", "id": "total", "type": INT_T, "val": {"lit": 0}, "mut": True},
        {"op": "loop", "bind": "i",
         "from": {"lit": 0}, "to": {"lit": 10}, "step": {"ref": "step"},
         "body": [
             {"op": "assign", "id": "total",
              "val": {"op": "+", "l": {"ref": "total"}, "r": {"ref": "i"}}}
         ]},
        {"op": "return", "val": {"ref": "total"}},
    ],
}
check_nail_l3(nail_var_step, "step=ref → proof impossible")


# ══════════════════════════════════════════════════════════════════════
# Scenario 4 — Recursive factorial with termination annotation → PROVED
# ══════════════════════════════════════════════════════════════════════
section("Scenario 4: Recursive factorial (annotated)")

print(textwrap.dedent("""\
  Recursive factorial with termination: {measure: "n"}.
  L3 trusts the programmer's annotation that 'n' decreases on each call.
"""))

nail_rec_annotated = {
    "nail": "0.4", "kind": "module", "id": "rec_fact_mod",
    "exports": ["factorial"],
    "defs": [
        {
            "nail": "0.4", "kind": "fn", "id": "factorial",
            "effects": [],
            "params": [{"id": "n", "type": INT_T}],
            "returns": INT_T,
            "termination": {"measure": "n"},
            "body": [
                {"op": "if",
                 "cond": {"op": "lte", "l": {"ref": "n"}, "r": {"lit": 1}},
                 "then": [{"op": "return", "val": {"lit": 1}}],
                 "else": [
                     {"op": "let", "id": "sub", "type": INT_T,
                      "val": {"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}},
                     {"op": "let", "id": "rec", "type": INT_T,
                      "val": {"op": "call", "fn": "factorial", "args": [{"ref": "sub"}]}},
                     {"op": "return",
                      "val": {"op": "*", "l": {"ref": "n"}, "r": {"ref": "rec"}}},
                 ]},
            ],
        }
    ],
}
check_nail_l3(nail_rec_annotated, "recursive factorial with measure annotation")


# ══════════════════════════════════════════════════════════════════════
# Scenario 5 — Recursive factorial WITHOUT annotation → REFUSED
# ══════════════════════════════════════════════════════════════════════
section("Scenario 5: Recursive factorial (no annotation)")

print(textwrap.dedent("""\
  Same recursive factorial, but without the termination annotation.
  L3 detects the recursion cycle but cannot prove it terminates.
"""))

nail_rec_no_annot = {
    "nail": "0.4", "kind": "module", "id": "rec_fact_mod2",
    "exports": ["factorial"],
    "defs": [
        {
            "nail": "0.4", "kind": "fn", "id": "factorial",
            "effects": [],
            "params": [{"id": "n", "type": INT_T}],
            "returns": INT_T,
            # No termination annotation!
            "body": [
                {"op": "if",
                 "cond": {"op": "lte", "l": {"ref": "n"}, "r": {"lit": 1}},
                 "then": [{"op": "return", "val": {"lit": 1}}],
                 "else": [
                     {"op": "let", "id": "sub", "type": INT_T,
                      "val": {"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}},
                     {"op": "let", "id": "rec", "type": INT_T,
                      "val": {"op": "call", "fn": "factorial", "args": [{"ref": "sub"}]}},
                     {"op": "return",
                      "val": {"op": "*", "l": {"ref": "n"}, "r": {"ref": "rec"}}},
                 ]},
            ],
        }
    ],
}
check_nail_l3(nail_rec_no_annot, "recursive factorial WITHOUT annotation")


# ══════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════
section("Summary")
print(textwrap.dedent("""\
  NAIL's L3 Termination Prover:

  ┌──────────────────────────────────┬──────────────┐
  │ Scenario                         │ L3 Result    │
  ├──────────────────────────────────┼──────────────┤
  │ Bounded loop (step=1)            │ ✅ PROVED    │
  │ Zero step (step=0)               │ ❌ CAUGHT    │
  │ Variable step (step=ref)         │ ❌ REFUSED   │
  │ Recursive factorial (annotated)  │ ✅ PROVED    │
  │ Recursive factorial (bare)       │ ❌ REFUSED   │
  └──────────────────────────────────┴──────────────┘

  "If the prover can't prove it terminates, the code doesn't ship."
"""))
