#!/usr/bin/env python3
"""
NAIL AI Code Reviewer Demo
============================
"AI generated this NAIL code. Let's review it with the checker."

Four common LLM coding mistakes — each caught at check time.
Then the corrected version passes cleanly.

Run: python demos/ai_review_demo.py
"""

import json, sys, textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from interpreter import Checker, CheckError
from interpreter.types import NailEffectError

SEP = "─" * 64
INT_T = {"type": "int", "bits": 64, "overflow": "panic"}
STR_T = {"type": "string", "encoding": "utf8"}


def section(title: str):
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print(f"{'═' * 64}")


def check_nail(spec: dict, label: str) -> bool:
    raw = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    try:
        Checker(spec, raw_text=raw).check()
        print(f"  ✅ NAIL checker: PASSED  ({label})")
        return True
    except (CheckError, NailEffectError) as e:
        print(f"  ❌ NAIL checker: CAUGHT  ({label})")
        print(f"     → {e}")
        return False


# ══════════════════════════════════════════════════════════════════════
# Scenario 1 — Effect leak: print in a pure function
# ══════════════════════════════════════════════════════════════════════
section("AI Mistake 1: Effect Leak (debug print in pure fn)")

print(textwrap.dedent("""\
  The AI left a debug print() inside a pure function.
  In Python this silently executes. NAIL catches the IO effect leak.

  AI-generated code:
  ──────────────────
  fn double(x: int) -> int:      # effects: [] (pure)
      print("debug: x =", x)     # ← IO effect leak!
      return x * 2
"""))

nail_effect_leak = {
    "nail": "0.4", "kind": "fn", "id": "double",
    "effects": [],          # declared pure
    "params": [{"id": "x", "type": INT_T}],
    "returns": INT_T,
    "body": [
        {"op": "print", "val": {"ref": "x"}, "effect": "IO"},  # IO in pure fn!
        {"op": "return", "val": {"op": "*", "l": {"ref": "x"}, "r": {"lit": 2}}},
    ],
}
check_nail(nail_effect_leak, "IO effect in pure function")


# ══════════════════════════════════════════════════════════════════════
# Scenario 2 — Type mix-up: declared int, returns bool
# ══════════════════════════════════════════════════════════════════════
section("AI Mistake 2: Type Mix-up (int declared, bool returned)")

print(textwrap.dedent("""\
  The AI declares the return type as int but actually returns a boolean.
  Python allows this (bool is a subclass of int). NAIL does not.

  AI-generated code:
  ──────────────────
  fn is_adult(age: int) -> int:   # ← should be bool
      return age >= 18            # returns bool
"""))

nail_type_mixup = {
    "nail": "0.4", "kind": "fn", "id": "is_adult",
    "effects": [],
    "params": [{"id": "age", "type": INT_T}],
    "returns": INT_T,           # declared int
    "body": [
        {"op": "return",
         "val": {"op": "gte", "l": {"ref": "age"}, "r": {"lit": 18}}},  # returns bool
    ],
}
check_nail(nail_type_mixup, "declared int, returns bool")


# ══════════════════════════════════════════════════════════════════════
# Scenario 3 — Missing branch: else has no return
# ══════════════════════════════════════════════════════════════════════
section("AI Mistake 3: Missing Branch (else has no return)")

print(textwrap.dedent("""\
  The AI forgot to add a return in the else branch.
  In Python this returns None silently. NAIL requires exhaustive returns.

  AI-generated code:
  ──────────────────
  fn clamp_positive(x: int) -> int:
      if x > 0:
          return x
      else:
          pass              # ← forgot to return 0!
"""))

nail_missing_branch = {
    "nail": "0.4", "kind": "fn", "id": "clamp_positive",
    "effects": [],
    "params": [{"id": "x", "type": INT_T}],
    "returns": INT_T,
    "body": [
        {"op": "if",
         "cond": {"op": "gt", "l": {"ref": "x"}, "r": {"lit": 0}},
         "then": [{"op": "return", "val": {"ref": "x"}}],
         "else": []},        # empty else — no return!
    ],
}
check_nail(nail_missing_branch, "else branch has no return")


# ══════════════════════════════════════════════════════════════════════
# Scenario 4 — Argument type mismatch: string passed to int param
# ══════════════════════════════════════════════════════════════════════
section("AI Mistake 4: Arg Type Mismatch (string → int)")

print(textwrap.dedent("""\
  The AI calls a function with a string argument where int is expected.
  Python only catches this at runtime (TypeError). NAIL catches at check time.

  AI-generated code:
  ──────────────────
  fn double(x: int) -> int:
      return x * 2

  fn main():
      double("hello")       # ← string where int expected!
"""))

nail_arg_mismatch = {
    "nail": "0.4", "kind": "module", "id": "arg_mismatch_mod",
    "exports": ["main"],
    "defs": [
        {
            "nail": "0.4", "kind": "fn", "id": "double",
            "effects": [],
            "params": [{"id": "x", "type": INT_T}],
            "returns": INT_T,
            "body": [
                {"op": "return",
                 "val": {"op": "*", "l": {"ref": "x"}, "r": {"lit": 2}}},
            ],
        },
        {
            "nail": "0.4", "kind": "fn", "id": "main",
            "effects": ["IO"],
            "params": [],
            "returns": {"type": "unit"},
            "body": [
                {"op": "let", "id": "result", "type": INT_T,
                 "val": {"op": "call", "fn": "double",
                         "args": [{"lit": "hello"}]}},  # string!
                {"op": "print", "val": {"op": "int_to_str", "v": {"ref": "result"}}, "effect": "IO"},
                {"op": "return", "val": {"lit": None, "type": {"type": "unit"}}},
            ],
        }
    ],
}
check_nail(nail_arg_mismatch, "string arg to int param")


# ══════════════════════════════════════════════════════════════════════
# Scenario 5 — All fixed: the corrected version
# ══════════════════════════════════════════════════════════════════════
section("All Fixed: Corrected AI Code")

print(textwrap.dedent("""\
  After the AI fixes all four mistakes:
  1. Remove debug print (or declare IO effect)
  2. Return type matches actual return
  3. All branches return a value
  4. Correct argument types at call sites
"""))

nail_all_fixed = {
    "nail": "0.4", "kind": "module", "id": "fixed_mod",
    "exports": ["main"],
    "defs": [
        {
            "nail": "0.4", "kind": "fn", "id": "double",
            "effects": [],
            "params": [{"id": "x", "type": INT_T}],
            "returns": INT_T,
            "body": [
                # No print — pure function
                {"op": "return",
                 "val": {"op": "*", "l": {"ref": "x"}, "r": {"lit": 2}}},
            ],
        },
        {
            "nail": "0.4", "kind": "fn", "id": "is_adult",
            "effects": [],
            "params": [{"id": "age", "type": INT_T}],
            "returns": {"type": "bool"},   # correct: bool
            "body": [
                {"op": "return",
                 "val": {"op": "gte", "l": {"ref": "age"}, "r": {"lit": 18}}},
            ],
        },
        {
            "nail": "0.4", "kind": "fn", "id": "clamp_positive",
            "effects": [],
            "params": [{"id": "x", "type": INT_T}],
            "returns": INT_T,
            "body": [
                {"op": "if",
                 "cond": {"op": "gt", "l": {"ref": "x"}, "r": {"lit": 0}},
                 "then": [{"op": "return", "val": {"ref": "x"}}],
                 "else": [{"op": "return", "val": {"lit": 0}}]},  # fixed!
            ],
        },
        {
            "nail": "0.4", "kind": "fn", "id": "main",
            "effects": ["IO"],
            "params": [],
            "returns": {"type": "unit"},
            "body": [
                {"op": "let", "id": "result", "type": INT_T,
                 "val": {"op": "call", "fn": "double",
                         "args": [{"lit": 21}]}},   # correct: int
                {"op": "print",
                 "val": {"op": "concat",
                         "l": {"lit": "double(21) = "},
                         "r": {"op": "int_to_str", "v": {"ref": "result"}}},
                 "effect": "IO"},
                {"op": "return", "val": {"lit": None, "type": {"type": "unit"}}},
            ],
        }
    ],
}
check_nail(nail_all_fixed, "all four mistakes fixed")


# ══════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════
section("Summary")
print(textwrap.dedent("""\
  NAIL catches common AI code-generation mistakes at check time:

  ┌──────────────────────────────────┬────────────────┬──────────────┐
  │ AI Mistake                       │ Python         │ NAIL Checker │
  ├──────────────────────────────────┼────────────────┼──────────────┤
  │ Debug print in pure fn           │ Runs silently  │ ❌ Effect leak│
  │ int declared, bool returned      │ Allowed (!)    │ ❌ Type error │
  │ Missing else return              │ Returns None   │ ❌ Branch gap │
  │ String passed to int param       │ TypeError      │ ❌ Arg type   │
  │ All fixed                        │ —              │ ✅ PASSED     │
  └──────────────────────────────────┴────────────────┴──────────────┘

  "NAIL reviews AI-generated code the same way it reviews human code."
"""))
