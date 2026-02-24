"""Tests for nail_lang._fc_standard (Issue #64 — FC Standard).

Covers:
 - to_openai_tool / to_anthropic_tool / to_gemini_tool  (NAIL → provider)
 - from_openai_tool / from_anthropic_tool / from_gemini_tool  (provider → NAIL)
 - convert_tools  (batch helper, all source×target combinations)
 - Effect removal / preservation
 - Round-trip fidelity
"""

from __future__ import annotations

import pytest
from nail_lang._fc_standard import (
    to_openai_tool,
    to_anthropic_tool,
    to_gemini_tool,
    from_openai_tool,
    from_anthropic_tool,
    from_gemini_tool,
    convert_tools,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

READ_FILE_NAIL = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from disk",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        "effects": ["FS"],
    },
}

HTTP_GET_NAIL = {
    "type": "function",
    "function": {
        "name": "http_get",
        "description": "Fetch a URL over HTTP",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        "effects": ["NET"],
    },
}

GREET_NAIL = {
    "type": "function",
    "function": {
        "name": "greet",
        "description": "Say hello",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": [],
        },
        "effects": ["IO"],
    },
}

# Corresponding standard-OpenAI format (no effects)
READ_FILE_OPENAI = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from disk",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
}

# Anthropic format
READ_FILE_ANTHROPIC = {
    "name": "read_file",
    "description": "Read a file from disk",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}

# Gemini format
READ_FILE_GEMINI = {
    "name": "read_file",
    "description": "Read a file from disk",
    "parameters": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}


# ── to_openai_tool ────────────────────────────────────────────────────────────

def test_to_openai_strips_effects():
    """Effects must be removed in standard OpenAI output."""
    result = to_openai_tool(READ_FILE_NAIL)
    assert "effects" not in result["function"]


def test_to_openai_preserves_structure():
    """to_openai_tool must return the standard envelope."""
    result = to_openai_tool(READ_FILE_NAIL)
    assert result["type"] == "function"
    assert result["function"]["name"] == "read_file"
    assert result["function"]["description"] == "Read a file from disk"
    assert result["function"]["parameters"]["required"] == ["path"]


def test_to_openai_does_not_mutate_input():
    """to_openai_tool must not modify the original tool dict."""
    import copy
    original = copy.deepcopy(READ_FILE_NAIL)
    to_openai_tool(READ_FILE_NAIL)
    assert READ_FILE_NAIL == original


# ── to_anthropic_tool ─────────────────────────────────────────────────────────

def test_to_anthropic_has_input_schema():
    """Anthropic output must use 'input_schema', not 'parameters'."""
    result = to_anthropic_tool(READ_FILE_NAIL)
    assert "input_schema" in result
    assert "parameters" not in result


def test_to_anthropic_no_type_wrapper():
    """Anthropic format is flat (no 'type' key)."""
    result = to_anthropic_tool(READ_FILE_NAIL)
    assert "type" not in result


def test_to_anthropic_strips_effects():
    """Effects must not appear in Anthropic output."""
    result = to_anthropic_tool(READ_FILE_NAIL)
    assert "effects" not in result


def test_to_anthropic_schema_content():
    """The input_schema must contain the original parameter schema."""
    result = to_anthropic_tool(READ_FILE_NAIL)
    assert result["input_schema"]["properties"]["path"] == {"type": "string"}
    assert result["input_schema"]["required"] == ["path"]


# ── to_gemini_tool ────────────────────────────────────────────────────────────

def test_to_gemini_has_parameters():
    """Gemini output keeps 'parameters' key (same schema as OpenAI)."""
    result = to_gemini_tool(READ_FILE_NAIL)
    assert "parameters" in result


def test_to_gemini_no_type_wrapper():
    """Gemini format is flat (no 'type' key)."""
    result = to_gemini_tool(READ_FILE_NAIL)
    assert "type" not in result


def test_to_gemini_strips_effects():
    """Effects must not appear in Gemini output."""
    result = to_gemini_tool(READ_FILE_NAIL)
    assert "effects" not in result


def test_to_gemini_schema_content():
    """Gemini parameters must match original schema."""
    result = to_gemini_tool(READ_FILE_NAIL)
    assert result["parameters"]["properties"]["path"] == {"type": "string"}


# ── from_openai_tool ──────────────────────────────────────────────────────────

def test_from_openai_adds_effects():
    """from_openai_tool must auto-infer effects."""
    result = from_openai_tool(READ_FILE_OPENAI)
    assert "effects" in result["function"]
    assert result["function"]["effects"] == ["FS"]


def test_from_openai_standard_envelope():
    """from_openai_tool returns the NAIL OpenAI FC envelope."""
    result = from_openai_tool(READ_FILE_OPENAI)
    assert result["type"] == "function"
    assert "function" in result


def test_from_openai_no_annotate():
    """With auto_annotate=False, effects must NOT be added."""
    result = from_openai_tool(READ_FILE_OPENAI, auto_annotate=False)
    assert "effects" not in result["function"]


# ── from_anthropic_tool ───────────────────────────────────────────────────────

def test_from_anthropic_converts_input_schema():
    """from_anthropic_tool must map input_schema → parameters."""
    result = from_anthropic_tool(READ_FILE_ANTHROPIC)
    assert "parameters" in result["function"]
    assert "input_schema" not in result["function"]


def test_from_anthropic_adds_effects():
    """from_anthropic_tool must auto-infer effects."""
    result = from_anthropic_tool(READ_FILE_ANTHROPIC)
    assert result["function"]["effects"] == ["FS"]


def test_from_anthropic_standard_envelope():
    """from_anthropic_tool returns standard NAIL envelope."""
    result = from_anthropic_tool(READ_FILE_ANTHROPIC)
    assert result["type"] == "function"
    assert result["function"]["name"] == "read_file"


# ── from_gemini_tool ──────────────────────────────────────────────────────────

def test_from_gemini_preserves_parameters():
    """from_gemini_tool keeps 'parameters' field."""
    result = from_gemini_tool(READ_FILE_GEMINI)
    assert "parameters" in result["function"]


def test_from_gemini_adds_effects():
    """from_gemini_tool must auto-infer effects."""
    result = from_gemini_tool(READ_FILE_GEMINI)
    assert result["function"]["effects"] == ["FS"]


def test_from_gemini_standard_envelope():
    """from_gemini_tool wraps result in NAIL envelope."""
    result = from_gemini_tool(READ_FILE_GEMINI)
    assert result["type"] == "function"
    assert result["function"]["name"] == "read_file"


# ── Round-trip tests ──────────────────────────────────────────────────────────

def test_roundtrip_nail_to_openai_and_back():
    """NAIL → OpenAI → NAIL should preserve name/description/parameters."""
    openai = to_openai_tool(READ_FILE_NAIL)
    nail_back = from_openai_tool(openai)
    fn = nail_back["function"]
    assert fn["name"] == "read_file"
    assert fn["description"] == "Read a file from disk"
    assert fn["parameters"]["required"] == ["path"]
    assert "effects" in fn  # re-inferred


def test_roundtrip_nail_to_anthropic_and_back():
    """NAIL → Anthropic → NAIL should restore parameters and infer effects."""
    anthropic = to_anthropic_tool(READ_FILE_NAIL)
    nail_back = from_anthropic_tool(anthropic)
    fn = nail_back["function"]
    assert fn["name"] == "read_file"
    assert "parameters" in fn
    assert fn["effects"] == ["FS"]


def test_roundtrip_nail_to_gemini_and_back():
    """NAIL → Gemini → NAIL should restore the tool faithfully."""
    gemini = to_gemini_tool(READ_FILE_NAIL)
    nail_back = from_gemini_tool(gemini)
    fn = nail_back["function"]
    assert fn["name"] == "read_file"
    assert fn["parameters"]["properties"]["path"] == {"type": "string"}
    assert fn["effects"] == ["FS"]


# ── convert_tools ─────────────────────────────────────────────────────────────

def test_convert_tools_nail_to_openai():
    """convert_tools(source='nail', target='openai') strips effects."""
    tools = [READ_FILE_NAIL, HTTP_GET_NAIL]
    result = convert_tools(tools, source="nail", target="openai")
    assert len(result) == 2
    assert all("effects" not in t["function"] for t in result)
    assert result[0]["function"]["name"] == "read_file"


def test_convert_tools_nail_to_anthropic():
    """convert_tools(target='anthropic') produces Anthropic format."""
    result = convert_tools([READ_FILE_NAIL], target="anthropic")
    assert result[0].get("input_schema") is not None
    assert "type" not in result[0]


def test_convert_tools_nail_to_gemini():
    """convert_tools(target='gemini') produces Gemini format."""
    result = convert_tools([HTTP_GET_NAIL], target="gemini")
    assert "parameters" in result[0]
    assert "type" not in result[0]


def test_convert_tools_nail_to_nail():
    """convert_tools(target='nail') preserves NAIL annotations."""
    result = convert_tools([GREET_NAIL], source="nail", target="nail")
    assert result[0]["function"]["effects"] == ["IO"]


def test_convert_tools_openai_to_anthropic():
    """Cross-provider: OpenAI → Anthropic."""
    result = convert_tools([READ_FILE_OPENAI], source="openai", target="anthropic")
    assert "input_schema" in result[0]
    assert result[0]["name"] == "read_file"


def test_convert_tools_anthropic_to_gemini():
    """Cross-provider: Anthropic → Gemini."""
    result = convert_tools([READ_FILE_ANTHROPIC], source="anthropic", target="gemini")
    assert "parameters" in result[0]
    assert result[0]["name"] == "read_file"


def test_convert_tools_gemini_to_openai():
    """Cross-provider: Gemini → OpenAI."""
    result = convert_tools([READ_FILE_GEMINI], source="gemini", target="openai")
    assert result[0]["type"] == "function"
    assert "effects" not in result[0]["function"]


def test_convert_tools_invalid_source():
    """convert_tools raises ValueError for unknown source."""
    with pytest.raises(ValueError, match="Unknown source format"):
        convert_tools([], source="unknown", target="openai")


def test_convert_tools_invalid_target():
    """convert_tools raises ValueError for unknown target."""
    with pytest.raises(ValueError, match="Unknown target format"):
        convert_tools([], source="nail", target="unknown")


def test_convert_tools_batch_size():
    """convert_tools handles a batch of multiple tools."""
    tools = [READ_FILE_NAIL, HTTP_GET_NAIL, GREET_NAIL]
    result = convert_tools(tools, target="anthropic")
    assert len(result) == 3


def test_convert_tools_empty_list():
    """convert_tools handles an empty tool list."""
    result = convert_tools([], target="openai")
    assert result == []


def test_convert_tools_no_auto_annotate():
    """With auto_annotate=False, nail target should have no effects on converted tools."""
    openai_tools = [READ_FILE_OPENAI]
    result = convert_tools(openai_tools, source="openai", target="nail", auto_annotate=False)
    assert "effects" not in result[0]["function"]
