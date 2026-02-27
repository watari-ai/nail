"""Tests for NAIL Demo #105 — Agent Handoff.

Covers:
1. agent_tools.nail file exists
2. Every tool has an effects annotation
3. filter_by_effects returns correct planner tools (read-only FS)
4. filter_by_effects returns correct executor tools (FS + NET)
5. Excluded tools are not present in restricted subsets
6. demo.py exits with returncode 0
7. demo.py output contains "Agent"
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
SPEC_PATH = DEMO_DIR / "agent_tools.nail"
DEMO_PY = DEMO_DIR / "demo.py"

# Make nail_lang importable when running from any directory
sys.path.insert(0, str(DEMO_DIR.parents[2]))  # repo root
import nail_lang as nail


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def all_tools() -> list[dict]:
    with SPEC_PATH.open() as f:
        spec = json.load(f)
    return spec["tools"]


# ---------------------------------------------------------------------------
# 1. Spec file exists
# ---------------------------------------------------------------------------

def test_spec_file_exists():
    """agent_tools.nail must exist in the demo directory."""
    assert SPEC_PATH.exists(), f"Expected {SPEC_PATH} to exist"


# ---------------------------------------------------------------------------
# 2. Every tool has effects
# ---------------------------------------------------------------------------

def test_all_tools_have_effects(all_tools):
    """Every tool in agent_tools.nail must carry an 'effects' annotation."""
    for tool in all_tools:
        fn = tool.get("function", {})
        effects = fn.get("effects")
        assert effects is not None and len(effects) > 0, (
            f"Tool '{fn.get('name')}' has no effects annotation"
        )


# ---------------------------------------------------------------------------
# 3. Planner tools (FS only, read_file subset)
# ---------------------------------------------------------------------------

def test_planner_tools(all_tools):
    """filter_by_effects(['FS']) should include read_file and write_file."""
    fs_tools = nail.filter_by_effects(all_tools, allowed=["FS"])
    names = {t["function"]["name"] for t in fs_tools}
    # Planner further restricts to read_file only; but the filter itself
    # must return both FS tools so the post-filter makes sense.
    assert "read_file" in names, "read_file must be in FS-filtered tools"
    # write_file is also FS — the planner demo post-filters it out by name;
    # the filter API itself returns it (correct behaviour).
    assert "write_file" in names, "write_file must also be in FS-filtered tools"


# ---------------------------------------------------------------------------
# 4. Executor tools (FS + NET)
# ---------------------------------------------------------------------------

def test_executor_tools(all_tools):
    """filter_by_effects(['FS','NET']) should include read_file, write_file, fetch_url."""
    executor_tools = nail.filter_by_effects(all_tools, allowed=["FS", "NET"])
    names = {t["function"]["name"] for t in executor_tools}
    assert "read_file" in names, "read_file missing from executor tools"
    assert "write_file" in names, "write_file missing from executor tools"
    assert "fetch_url" in names, "fetch_url missing from executor tools"


# ---------------------------------------------------------------------------
# 5. Excluded tools are not present in restricted subsets
# ---------------------------------------------------------------------------

def test_excluded_tools_absent(all_tools):
    """fetch_url (NET) must not appear in FS-only filter."""
    fs_tools = nail.filter_by_effects(all_tools, allowed=["FS"])
    names = {t["function"]["name"] for t in fs_tools}
    assert "fetch_url" not in names, "fetch_url (NET) must be excluded from FS-only filter"
    assert "log_result" not in names, "log_result (IO) must be excluded from FS-only filter"


def test_reporter_excludes_non_io(all_tools):
    """IO-only filter must exclude FS and NET tools."""
    reporter_tools = nail.filter_by_effects(all_tools, allowed=["IO"])
    names = {t["function"]["name"] for t in reporter_tools}
    assert "log_result" in names, "log_result must be in IO-only tools"
    assert "read_file" not in names, "read_file (FS) must be excluded from IO-only filter"
    assert "write_file" not in names, "write_file (FS) must be excluded from IO-only filter"
    assert "fetch_url" not in names, "fetch_url (NET) must be excluded from IO-only filter"


# ---------------------------------------------------------------------------
# 6. demo.py exits with returncode 0
# ---------------------------------------------------------------------------

def test_demo_runs():
    """demo.py must execute successfully (returncode 0)."""
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
# 7. demo.py output contains "Agent"
# ---------------------------------------------------------------------------

def test_demo_output_contains_agent():
    """demo.py stdout must contain the word 'Agent'."""
    result = subprocess.run(
        [sys.executable, str(DEMO_PY)],
        capture_output=True,
        text=True,
    )
    assert "Agent" in result.stdout, (
        f"Expected 'Agent' in demo output, got:\n{result.stdout}"
    )
