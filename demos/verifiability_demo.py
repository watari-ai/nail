#!/usr/bin/env python3
"""
NAIL Verifiability Demo
=======================
Three scenarios where NAIL catches bugs at check time that Python only
catches (if at all) at runtime — or never.

Run: python demos/verifiability_demo.py
"""

import json, sys, textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from interpreter import Checker, CheckError
from interpreter.types import NailEffectError

SEP = "─" * 64


def section(title: str):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


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
# Scenario 1 — Hidden side effect
# ══════════════════════════════════════════════════════════════════════
section("Scenario 1: Hidden side effect")

print("""
  Python (no static analysis):
  ─────────────────────────────
  def process(path: str) -> str:
      import os
      os.system(f"log.sh {path}")   # ← side effect hidden inside pure fn
      return path.upper()

  mypy: OK  |  pylint: OK  |  runtime: executes shell command silently
""")

# NAIL equivalent: declared pure but tries to use read_file (FS effect)
nail_hidden_effect = {
    "nail": "0.2", "kind": "fn", "id": "process",
    "effects": [],          # declared pure
    "params": [{"id": "path", "type": {"type": "string", "encoding": "utf8"}}],
    "returns": {"type": "string", "encoding": "utf8"},
    "body": [
        # Attempting FS read without declaring FS effect
        {"op": "read_file", "path": {"ref": "path"}, "effect": "FS", "into": "content"},
        {"op": "return", "val": {"ref": "content"}},
    ],
}
check_nail(nail_hidden_effect, "hidden FS effect in pure fn")

# NAIL correct version: declare FS
nail_correct_effect = {
    "nail": "0.2", "kind": "fn", "id": "process",
    "effects": ["FS"],      # correctly declared
    "params": [{"id": "path", "type": {"type": "string", "encoding": "utf8"}}],
    "returns": {"type": "string", "encoding": "utf8"},
    "body": [
        {"op": "read_file", "path": {"ref": "path"}, "effect": "FS", "into": "content"},
        {"op": "return", "val": {"ref": "content"}},
    ],
}
check_nail(nail_correct_effect, "FS declared correctly")


# ══════════════════════════════════════════════════════════════════════
# Scenario 2 — Missing return path
# ══════════════════════════════════════════════════════════════════════
section("Scenario 2: Missing return path (not all branches return)")

print("""
  Python:
  ───────
  def abs_val(x: int) -> int:
      if x < 0:
          return -x
      # else branch missing → returns None implicitly

  mypy: reports error  |  but only if you run mypy
  Runtime: returns None, causes TypeError later — sometimes silently
""")

nail_partial_return = {
    "nail": "0.2", "kind": "fn", "id": "abs_val",
    "effects": [],
    "params": [{"id": "x", "type": {"type": "int", "bits": 64, "overflow": "panic"}}],
    "returns": {"type": "int", "bits": 64, "overflow": "panic"},
    "body": [
        {"op": "if",
         "cond": {"op": "lt", "l": {"ref": "x"}, "r": {"lit": 0}},
         "then": [{"op": "return", "val": {"op": "-", "l": {"lit": 0}, "r": {"ref": "x"}}}],
         "else": []},   # ← else is empty, no return
    ],
}
check_nail(nail_partial_return, "missing else-return")

nail_full_return = {
    "nail": "0.2", "kind": "fn", "id": "abs_val",
    "effects": [],
    "params": [{"id": "x", "type": {"type": "int", "bits": 64, "overflow": "panic"}}],
    "returns": {"type": "int", "bits": 64, "overflow": "panic"},
    "body": [
        {"op": "if",
         "cond": {"op": "lt", "l": {"ref": "x"}, "r": {"lit": 0}},
         "then": [{"op": "return", "val": {"op": "-", "l": {"lit": 0}, "r": {"ref": "x"}}}],
         "else": [{"op": "return", "val": {"ref": "x"}}]},
    ],
}
check_nail(nail_full_return, "all paths return")


# ══════════════════════════════════════════════════════════════════════
# Scenario 3 — Type mismatch
# ══════════════════════════════════════════════════════════════════════
section("Scenario 3: Return type mismatch")

print("""
  Python:
  ───────
  def is_positive(x: int) -> int:   # declared int, returns bool
      return x > 0                  # True/False — silently accepted

  Python: no error (bool is subclass of int)
  But downstream int arithmetic on the result is semantically wrong
""")

nail_type_mismatch = {
    "nail": "0.2", "kind": "fn", "id": "is_positive",
    "effects": [],
    "params": [{"id": "x", "type": {"type": "int", "bits": 64, "overflow": "panic"}}],
    "returns": {"type": "int", "bits": 64, "overflow": "panic"},   # declared int
    "body": [
        {"op": "return", "val": {"op": "gt", "l": {"ref": "x"}, "r": {"lit": 0}}},  # returns bool
    ],
}
check_nail(nail_type_mismatch, "declared int, returns bool")

nail_type_correct = {
    "nail": "0.2", "kind": "fn", "id": "is_positive",
    "effects": [],
    "params": [{"id": "x", "type": {"type": "int", "bits": 64, "overflow": "panic"}}],
    "returns": {"type": "bool"},
    "body": [
        {"op": "return", "val": {"op": "gt", "l": {"ref": "x"}, "r": {"lit": 0}}},
    ],
}
check_nail(nail_type_correct, "declared bool, returns bool")


# ══════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════
section("Summary")
print(textwrap.dedent("""
  NAIL's checker (L0–L2) catches all three categories at check time:

  ┌────────────────────────────┬──────────────────┬──────────────┐
  │ Bug class                  │ Python static    │ NAIL checker │
  ├────────────────────────────┼──────────────────┼──────────────┤
  │ Hidden side effect         │ Never (optional) │ Always       │
  │ Missing return path        │ mypy only        │ Always       │
  │ Return type mismatch       │ mypy only        │ Always       │
  └────────────────────────────┴──────────────────┴──────────────┘

  "No runtime needed. The contract is violated at check time."
"""))
