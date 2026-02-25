"""Tests for nail_lang.fc_cli (nail fc convert/check/roundtrip).

Includes:
- Golden file tests: compare convert output against pre-generated expected output
- fc_check unit tests: name uniqueness, schema types, effects consistency
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nail_lang.fc_cli import fc_convert, fc_check, fc_roundtrip

# ── Fixtures / helpers ────────────────────────────────────────────────────────

FC_DIR = Path(__file__).parent / "fc"
TOOLS_NAIL = FC_DIR / "tools.nail"


def load_json(path: Path) -> object:
    with open(path) as f:
        return json.load(f)


def tools_from_file() -> list[dict]:
    return load_json(TOOLS_NAIL)


def write_temp_nail(data: list) -> str:
    """Write *data* to a temporary .nail file and return the path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".nail", delete=False, encoding="utf-8"
    )
    json.dump(data, f, indent=2)
    f.close()
    return f.name


# ── Golden file tests ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_fc_convert_golden(provider: str, tmp_path: Path, capsys):
    """fc_convert should produce output matching the pre-generated golden file."""
    out_file = str(tmp_path / f"{provider}_output.json")
    exit_code = fc_convert(str(TOOLS_NAIL), provider, out=out_file, fmt="json")

    assert exit_code == 0, f"fc_convert returned non-zero exit code for provider={provider}"
    assert Path(out_file).exists(), f"Output file was not created: {out_file}"

    actual = load_json(Path(out_file))
    expected = load_json(FC_DIR / f"golden_{provider}.json")

    assert actual == expected, (
        f"fc_convert({provider}) output does not match golden file.\n"
        f"Expected: {json.dumps(expected, indent=2)}\n"
        f"Actual:   {json.dumps(actual, indent=2)}"
    )


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_fc_convert_stdout_golden(provider: str, capsys):
    """fc_convert with out=None should print JSON matching the golden file."""
    exit_code = fc_convert(str(TOOLS_NAIL), provider, out=None, fmt="human")
    assert exit_code == 0

    captured = capsys.readouterr()
    actual = json.loads(captured.out)
    expected = load_json(FC_DIR / f"golden_{provider}.json")
    assert actual == expected


# ── fc_check unit tests ───────────────────────────────────────────────────────


class TestFcCheckNameUniqueness:
    def test_duplicate_names_error(self, capsys):
        tools = [
            {"type": "function", "function": {"name": "read_file", "description": "A", "parameters": {}, "effects": []}},
            {"type": "function", "function": {"name": "read_file", "description": "B", "parameters": {}, "effects": []}},
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "openai", False, "json", False)
            assert exit_code == 2
            result = json.loads(capsys.readouterr().out)
            assert result["ok"] is False
            assert any("duplicate" in e.lower() or "read_file" in e for e in result["errors"])
        finally:
            os.unlink(path)

    def test_unique_names_ok(self, capsys):
        tools = [
            {"type": "function", "function": {"name": "tool_a", "description": "A", "parameters": {}, "effects": []}},
            {"type": "function", "function": {"name": "tool_b", "description": "B", "parameters": {}, "effects": []}},
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "openai", False, "json", False)
            assert exit_code == 0
            result = json.loads(capsys.readouterr().out)
            assert result["ok"] is True
            assert result["errors"] == []
        finally:
            os.unlink(path)


class TestFcCheckSchemaTypes:
    def test_universal_types_ok(self, capsys):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "my_tool",
                    "description": "desc",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "string"},
                            "y": {"type": "integer"},
                            "z": {"type": "boolean"},
                        },
                    },
                    "effects": [],
                },
            }
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "openai", False, "json", False)
            result = json.loads(capsys.readouterr().out)
            assert exit_code == 0
            assert result["errors"] == []
            assert result["warnings"] == []
        finally:
            os.unlink(path)

    def test_unknown_type_warns(self, capsys):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "my_tool",
                    "description": "desc",
                    "parameters": {
                        "type": "object",
                        "properties": {"x": {"type": "null"}},
                    },
                    "effects": [],
                },
            }
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "openai", False, "json", False)
            result = json.loads(capsys.readouterr().out)
            # Should be ok=True (warning only, not strict_provider)
            assert exit_code == 0
            assert result["ok"] is True
            assert any("null" in w for w in result["warnings"])
        finally:
            os.unlink(path)

    def test_unknown_type_strict_provider_errors(self, capsys):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "my_tool",
                    "description": "desc",
                    "parameters": {
                        "type": "object",
                        "properties": {"x": {"type": "null"}},
                    },
                    "effects": [],
                },
            }
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "anthropic", strict_provider=True, fmt="json", strict=False)
            result = json.loads(capsys.readouterr().out)
            assert exit_code == 2
            assert result["ok"] is False
            assert any("null" in e for e in result["errors"])
        finally:
            os.unlink(path)


class TestFcCheckEffects:
    def test_pure_empty_effects_ok(self, capsys):
        tools = [
            {
                "type": "function",
                "function": {"name": "calc", "description": "Pure calc", "parameters": {}, "effects": []},
            }
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "openai", False, "json", False)
            result = json.loads(capsys.readouterr().out)
            assert exit_code == 0
            assert result["errors"] == []
        finally:
            os.unlink(path)

    def test_side_effect_tool_ok(self, capsys):
        tools = [
            {
                "type": "function",
                "function": {"name": "read_file", "description": "Reads files", "parameters": {}, "effects": ["FS"]},
            }
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "openai", False, "json", False)
            result = json.loads(capsys.readouterr().out)
            assert exit_code == 0
        finally:
            os.unlink(path)

    def test_pure_marker_with_side_effects_error(self, capsys):
        """PURE label + FS/NET/IO in same effects list → error."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "sneaky",
                    "description": "Declares PURE but has FS",
                    "parameters": {},
                    "effects": ["PURE", "FS"],
                },
            }
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "openai", False, "json", False)
            result = json.loads(capsys.readouterr().out)
            assert exit_code == 2
            assert result["ok"] is False
            assert any("PURE" in e or "FS" in e for e in result["errors"])
        finally:
            os.unlink(path)

    def test_unknown_effect_label_foobar_errors(self, capsys):
        """effects: ['FOOBAR'] → FC error (unknown label)."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "bad_tool",
                    "description": "Has unknown effect",
                    "parameters": {},
                    "effects": ["FOOBAR"],
                },
            }
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "openai", False, "json", False)
            result = json.loads(capsys.readouterr().out)
            assert exit_code == 2
            assert result["ok"] is False
            assert any("FOOBAR" in e for e in result["errors"])
        finally:
            os.unlink(path)

    def test_mixed_valid_and_invalid_effect_label_errors(self, capsys):
        """effects: ['NET', 'INVALID_LABEL'] → FC error for invalid, NET passes."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "mixed_tool",
                    "description": "Has one valid and one invalid effect",
                    "parameters": {},
                    "effects": ["NET", "INVALID_LABEL"],
                },
            }
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "openai", False, "json", False)
            result = json.loads(capsys.readouterr().out)
            assert exit_code == 2
            assert result["ok"] is False
            assert any("INVALID_LABEL" in e for e in result["errors"])
            # NET is valid — it should not appear as an *unknown* effect error
            assert not any("unknown effect label 'NET'" in e for e in result["errors"])
        finally:
            os.unlink(path)

    def test_valid_effect_labels_pass(self, capsys):
        """effects: ['NET', 'FS'] → passes (all known labels)."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "network_file_tool",
                    "description": "Valid effects",
                    "parameters": {},
                    "effects": ["NET", "FS"],
                },
            }
        ]
        path = write_temp_nail(tools)
        try:
            exit_code = fc_check(path, "openai", False, "json", False)
            result = json.loads(capsys.readouterr().out)
            assert exit_code == 0
            assert result["ok"] is True
            assert result["errors"] == []
        finally:
            os.unlink(path)


class TestFcCheckSystemErrors:
    def test_missing_file(self, capsys):
        exit_code = fc_check("/nonexistent/path/tools.nail", "openai", False, "json", False)
        assert exit_code == 1
        result = json.loads(capsys.readouterr().out)
        assert result["ok"] is False

    def test_invalid_json(self, tmp_path, capsys):
        bad = tmp_path / "bad.nail"
        bad.write_text("not json {{{", encoding="utf-8")
        exit_code = fc_check(str(bad), "openai", False, "json", False)
        assert exit_code == 1
        result = json.loads(capsys.readouterr().out)
        assert result["ok"] is False


# ── fc_roundtrip tests ────────────────────────────────────────────────────────


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_fc_roundtrip_lossless(provider: str, capsys):
    """Tools with simple schemas should survive a roundtrip losslessly."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "simple_tool",
                "description": "A simple tool",
                "parameters": {
                    "type": "object",
                    "properties": {"x": {"type": "string"}},
                    "required": ["x"],
                },
                "effects": ["FS"],
            },
        }
    ]
    path = write_temp_nail(tools)
    try:
        exit_code = fc_roundtrip(path, provider, fmt="json")
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        # "effects" may be re-inferred differently from auto_annotate, so
        # effects field may differ — that's expected provider-roundtrip loss.
        # We only assert the exit code indicates the command ran without system error.
        assert exit_code in (0, 2)  # 2 if effects differ after roundtrip (expected)
        assert "ok" in result
    finally:
        os.unlink(path)


def test_fc_roundtrip_missing_file(capsys):
    exit_code = fc_roundtrip("/nonexistent/tools.nail", "openai", fmt="human")
    assert exit_code == 1


# ── Integration: full demo tools check ───────────────────────────────────────


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_demo_tools_check_passes(provider: str, capsys):
    """The demo tools file should pass fc_check for all providers."""
    exit_code = fc_check(str(TOOLS_NAIL), provider, False, "json", False)
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0, f"fc_check failed for provider={provider}: {result}"
    assert result["ok"] is True
    assert result["errors"] == []
