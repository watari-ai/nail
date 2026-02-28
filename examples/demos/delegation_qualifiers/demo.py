"""Delegation Qualifiers Demo

Shows how NAIL's fc_ir_v2 detects Zone of Indifference violations
in multi-agent delegation chains.

Zone of Indifference: as A→B→C→D chains grow, irreversible
capabilities can propagate without explicit re-authorization.
NAIL blocks this at type-check time with FC-E010.

Chain modelled here:
    Reporter  (A)  write_summary    — calls Analyzer
    Analyzer  (B)  generate_report  — calls Processor
    Processor (C)  run_pipeline     — calls Writer
    Writer    (D)  write_output     — owns FS:write_file (explicit)

Run:
    cd examples/demos/delegation_qualifiers
    python3 demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from anywhere in the repo without an editable install
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import nail_lang.fc_ir_v2 as fc_ir_v2  # noqa: E402 (available on feat/delegation-effect-qualifiers)

DEMO_DIR = Path(__file__).parent
VALID_SPEC = DEMO_DIR / "agent_chain.nail"
BROKEN_SPEC = DEMO_DIR / "agent_chain_broken.nail"


def load_defs(path: Path) -> list[dict]:
    """Load function definitions from a delegation-chain .nail file."""
    with path.open() as f:
        spec = json.load(f)
    defs: list[dict] = spec.get("defs", [])
    if not defs:
        raise ValueError(f"No 'defs' found in {path}")
    return defs


def _print_header(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def demo_valid_chain() -> None:
    """All agents properly declare grants — no FC-E010."""
    _print_header("Demo: Valid delegation chain (FC-E010 free)")

    defs = load_defs(VALID_SPEC)
    print(f"\n📄 Loaded {len(defs)} function def(s) from {VALID_SPEC.name}")

    print("\nChain: write_summary → generate_report → run_pipeline → write_output")
    print("Each agent declares  grants: ['FS:write_file']  ✓")

    errors = fc_ir_v2.check_program(defs)

    if not errors:
        print("\n✅ check_program() → 0 errors (chain is safe)")
    else:
        print(f"\n❌ Unexpected errors ({len(errors)}):")
        for err in errors:
            print(f"   [{err.code}] {err.message}")
        sys.exit(1)


def demo_broken_chain() -> None:
    """Processor (C) missing grants — FC-E010 fires."""
    _print_header("Demo: Broken delegation chain (FC-E010 expected)")

    defs = load_defs(BROKEN_SPEC)
    print(f"\n📄 Loaded {len(defs)} function def(s) from {BROKEN_SPEC.name}")

    print("\nChain: write_summary → generate_report → run_pipeline → write_output")
    print("Processor (run_pipeline) has NO grants field  ✗")

    errors = fc_ir_v2.check_program(defs)

    if errors:
        print(f"\n🚨 check_program() → {len(errors)} error(s) detected:")
        for err in errors:
            print(f"\n   Code    : {err.code}")
            print(f"   Callee  : {err.callee}")
            print(f"   Op      : {err.op}")
            print(f"   Message : {err.message}")
        print("\n💡 Zone of Indifference prevented — NAIL blocked the chain at type-check time.")
    else:
        print("\n⚠️  Expected FC-E010 but got 0 errors (check your spec!).")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 60)
    print("  NAIL Demo — Delegation Qualifiers")
    print("  Zone of Indifference detection via fc_ir_v2")
    print("=" * 60)

    demo_valid_chain()
    demo_broken_chain()

    print()
    print("=" * 60)
    print("  Demo complete.")
    print("=" * 60)
