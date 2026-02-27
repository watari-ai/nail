"""
Tests for Demo #106: Verify-Fix Loop
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from interpreter.checker import Checker, CheckError

DEMO_DIR = Path(__file__).resolve().parents[1]


# ── File existence ────────────────────────────────────────────────────────────

def test_broken_spec_exists():
    """broken_spec.nail must exist."""
    assert (DEMO_DIR / "broken_spec.nail").is_file()


def test_fixed_spec_exists():
    """fixed_spec.nail must exist."""
    assert (DEMO_DIR / "fixed_spec.nail").is_file()


# ── Checker behaviour ─────────────────────────────────────────────────────────

def test_broken_spec_raises_check_error():
    """Checker.check() must raise CheckError for broken_spec.nail."""
    spec = json.loads((DEMO_DIR / "broken_spec.nail").read_text())
    c = Checker(spec)
    with pytest.raises(CheckError):
        c.check()


def test_fixed_spec_passes_checker():
    """Checker.check() must pass without error for fixed_spec.nail."""
    spec = json.loads((DEMO_DIR / "fixed_spec.nail").read_text())
    c = Checker(spec)
    # Should not raise
    c.check()


# ── demo.py execution ─────────────────────────────────────────────────────────

def _run_demo():
    """Helper: run demo.py and return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(DEMO_DIR / "demo.py")],
        capture_output=True,
        text=True,
    )


def test_demo_exits_zero():
    """demo.py must exit with returncode 0."""
    result = _run_demo()
    assert result.returncode == 0, (
        f"demo.py exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_demo_output_contains_attempt():
    """demo.py output must contain 'Attempt'."""
    result = _run_demo()
    assert "Attempt" in result.stdout, f"'Attempt' not found in output:\n{result.stdout}"


def test_demo_output_contains_checkmark():
    """demo.py output must contain '✅'."""
    result = _run_demo()
    assert "✅" in result.stdout, f"'✅' not found in output:\n{result.stdout}"


def test_demo_output_contains_verify_fix():
    """demo.py output must contain 'Verify-Fix'."""
    result = _run_demo()
    assert "Verify-Fix" in result.stdout, f"'Verify-Fix' not found in output:\n{result.stdout}"
