"""
Demo #106: Verify-Fix Loop
==========================
Demonstrates how NAIL's Checker enables automated LLM-driven fix loops.

An LLM generates a NAIL spec → Checker validates it → if it fails,
the error is sent back to the LLM for correction → repeat until valid.

This demo uses an offline mock (no API key required).
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from interpreter.checker import Checker, CheckError

DEMO_DIR = Path(__file__).parent


def load_spec(path: Path) -> dict:
    """Load a NAIL spec from a JSON file."""
    with open(path) as f:
        return json.load(f)


def verify(spec: dict) -> CheckError | None:
    """Run Checker on the spec. Returns CheckError if invalid, None if valid."""
    c = Checker(spec)
    try:
        c.check()
        return None
    except CheckError as e:
        return e


def simulate_llm_fix(error: CheckError) -> dict:
    """
    Simulate LLM fixing the spec based on the error message.
    In a real pipeline, you'd call an LLM API here with the error details.
    For this demo, we simply load the pre-written fixed spec.
    """
    return load_spec(DEMO_DIR / "fixed_spec.nail")


def main():
    print("=" * 60)
    print("  NAIL Demo #106: Verify-Fix Loop")
    print("=" * 60)
    print()

    # Step 1: Load the initial (broken) spec — simulating LLM output
    spec = load_spec(DEMO_DIR / "broken_spec.nail")
    attempts = 0
    max_attempts = 5

    while attempts < max_attempts:
        attempts += 1
        print(f"🔍 Attempt {attempts}: Verifying spec...")

        error = verify(spec)

        if error is None:
            # ✅ Valid!
            print("  ✅ Spec is valid!")
            print()
            break
        else:
            # ❌ Found an error
            print(f"  ❌ CheckError: {error}")
            print(f"  → Sending error to LLM for fix...")
            print()

            # Simulate LLM fix (loads fixed_spec.nail)
            spec = simulate_llm_fix(error)
    else:
        print("  ❌ Max attempts reached. Fix loop failed.")
        sys.exit(1)

    print(f"✨ Verify-Fix loop completed in {attempts} attempts.")
    print("   NAIL Checker caught the error before it reached production.")


if __name__ == "__main__":
    main()
