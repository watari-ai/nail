"""Tests for NAIL Demo — Delegation Qualifiers.

Covers:
1. Valid chain passes check_program with zero errors
2. Broken chain raises FC-E010
3. Writer (D) has explicit delegation qualifier
4. Processor (C) missing grants in broken spec
5. Processor (C) with grants passes check (isolated)
6. All four agents appear in the valid chain spec
7. FC-E010 error message content
8. Backward-compatible string "allow" form works alongside explicit form
9. demo.py runs successfully (returncode 0)
10. demo.py output contains expected keywords
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEMO_DIR = Path(__file__).resolve().parents[1]
VALID_SPEC = DEMO_DIR / "agent_chain.nail"
BROKEN_SPEC = DEMO_DIR / "agent_chain_broken.nail"
DEMO_PY = DEMO_DIR / "demo.py"

# Make nail_lang importable when running from any directory
sys.path.insert(0, str(DEMO_DIR.parents[2]))  # repo root
import nail_lang.fc_ir_v2 as fc_ir_v2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_defs(path: Path) -> list[dict]:
    with path.open() as f:
        spec = json.load(f)
    return spec["defs"]


# ---------------------------------------------------------------------------
# 1. Valid chain passes check_program with zero errors
# ---------------------------------------------------------------------------

def test_valid_chain_passes_check():
    """check_program() must return an empty list for agent_chain.nail."""
    defs = _load_defs(VALID_SPEC)
    errors = fc_ir_v2.check_program(defs)
    assert errors == [], (
        f"Expected no errors for valid chain, got: {[e.message for e in errors]}"
    )


# ---------------------------------------------------------------------------
# 2. Broken chain raises FC-E010
# ---------------------------------------------------------------------------

def test_broken_chain_raises_fc_e010():
    """check_program() must return exactly one FC-E010 for agent_chain_broken.nail."""
    defs = _load_defs(BROKEN_SPEC)
    errors = fc_ir_v2.check_program(defs)
    assert len(errors) == 1, (
        f"Expected exactly 1 FC-E010 error, got {len(errors)}: "
        f"{[e.message for e in errors]}"
    )
    assert errors[0].code == "FC-E010", (
        f"Expected error code FC-E010, got {errors[0].code!r}"
    )


# ---------------------------------------------------------------------------
# 3. Writer (D) has explicit delegation qualifier
# ---------------------------------------------------------------------------

def test_writer_has_explicit_delegation():
    """Writer (write_output) must declare FS:write_file with delegation='explicit'."""
    defs = _load_defs(VALID_SPEC)
    writer = next((d for d in defs if d["name"] == "write_output"), None)
    assert writer is not None, "write_output not found in agent_chain.nail"

    allow = writer["effects"]["allow"]
    explicit_ops = [
        item for item in allow
        if isinstance(item, dict) and item.get("delegation") == "explicit"
    ]
    assert any(item["op"] == "FS:write_file" for item in explicit_ops), (
        "write_output must have FS:write_file with delegation='explicit'"
    )


# ---------------------------------------------------------------------------
# 4. Processor (C) missing grants in broken spec
# ---------------------------------------------------------------------------

def test_processor_missing_grants():
    """Processor (run_pipeline) must not have a 'grants' key in agent_chain_broken.nail."""
    defs = _load_defs(BROKEN_SPEC)
    processor = next((d for d in defs if d["name"] == "run_pipeline"), None)
    assert processor is not None, "run_pipeline not found in agent_chain_broken.nail"
    # The broken spec omits "grants" entirely — check_program enforces the gap.
    grants = processor.get("grants", None)
    assert not grants, (
        f"run_pipeline should have no/empty grants in broken spec, got {grants!r}"
    )


# ---------------------------------------------------------------------------
# 5. Processor (C) with grants passes check (isolated)
# ---------------------------------------------------------------------------

def test_processor_with_grants_passes():
    """When Processor explicitly declares grants, check_call returns no errors."""
    writer = {
        "op": "def",
        "name": "write_output",
        "effects": {
            "allow": [{"op": "FS:write_file", "reversible": False, "delegation": "explicit"}]
        },
        "grants": ["FS:write_file"],
        "body": [],
    }
    processor_fixed = {
        "op": "def",
        "name": "run_pipeline",
        "effects": {
            "allow": [{"op": "FS:write_file", "reversible": False, "delegation": "explicit"}]
        },
        "grants": ["FS:write_file"],
        "body": [{"op": "call", "fn": "write_output"}],
    }
    errors = fc_ir_v2.check_call(processor_fixed, writer)
    assert errors == [], (
        f"Processor with grants should pass, got: {[e.message for e in errors]}"
    )


# ---------------------------------------------------------------------------
# 6. All four agents appear in the valid chain spec
# ---------------------------------------------------------------------------

def test_all_agents_in_valid_chain():
    """agent_chain.nail must define all four agent functions."""
    defs = _load_defs(VALID_SPEC)
    names = {d["name"] for d in defs}
    expected = {"write_summary", "generate_report", "run_pipeline", "write_output"}
    assert expected <= names, (
        f"Missing agent functions: {expected - names}"
    )


# ---------------------------------------------------------------------------
# 7. FC-E010 error message content
# ---------------------------------------------------------------------------

def test_fc_e010_error_message():
    """The FC-E010 error must mention 'run_pipeline' and 'FS:write_file'."""
    defs = _load_defs(BROKEN_SPEC)
    errors = fc_ir_v2.check_program(defs)
    assert errors, "Expected at least one error"
    err = errors[0]
    assert "run_pipeline" in err.message, (
        f"Error message should mention 'run_pipeline', got: {err.message!r}"
    )
    assert "FS:write_file" in err.message, (
        f"Error message should mention 'FS:write_file', got: {err.message!r}"
    )


# ---------------------------------------------------------------------------
# 8. Backward-compatible string "allow" form works alongside explicit form
# ---------------------------------------------------------------------------

def test_backward_compat_string_allow_in_demo():
    """parse_effect_qualifier handles the legacy string form (delegation defaults to implicit)."""
    # Simulating a function that uses the old string form — must not raise FC-E010
    legacy_def = {
        "op": "def",
        "name": "old_writer",
        "effects": {"allow": ["FS:write_file"]},  # string form → implicit delegation
        "grants": [],
        "body": [],
    }
    caller_def = {
        "op": "def",
        "name": "caller",
        "effects": {"allow": []},
        "grants": [],
        "body": [{"op": "call", "fn": "old_writer"}],
    }
    errors = fc_ir_v2.check_call(caller_def, legacy_def)
    assert errors == [], (
        f"String-form 'allow' should be implicit delegation (no FC-E010), got: {errors}"
    )

    # Sanity-check: parsed qualifier is indeed implicit
    qualifier = fc_ir_v2.parse_effect_qualifier("FS:write_file")
    assert qualifier.delegation == "implicit"
    assert qualifier.op == "FS:write_file"
    assert not qualifier.is_explicit()


# ---------------------------------------------------------------------------
# 9. demo.py runs successfully (returncode 0)
# ---------------------------------------------------------------------------

def test_demo_runs():
    """demo.py must execute without errors (returncode 0)."""
    result = subprocess.run(
        [sys.executable, str(DEMO_PY)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"demo.py exited with {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# 10. demo.py output contains expected keywords
# ---------------------------------------------------------------------------

def test_demo_output_contains_keywords():
    """demo.py stdout must contain FC-E010 and Zone of Indifference."""
    result = subprocess.run(
        [sys.executable, str(DEMO_PY)],
        capture_output=True,
        text=True,
    )
    assert "FC-E010" in result.stdout, (
        f"Expected 'FC-E010' in demo output, got:\n{result.stdout}"
    )
    assert "Zone of Indifference" in result.stdout, (
        f"Expected 'Zone of Indifference' in demo output, got:\n{result.stdout}"
    )
