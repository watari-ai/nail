"""Tests for Demo #104 — Multi-Provider API Routing.

Verifies that the api_routing demo spec converts cleanly to all three
provider formats using the nail_lang FC Standard API.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import nail_lang as nail

SPEC_PATH = Path(__file__).resolve().parents[1] / "tool_spec.nail"


@pytest.fixture()
def tools() -> list[dict]:
    with SPEC_PATH.open() as f:
        spec = json.load(f)
    return spec["tools"]


def test_spec_file_exists():
    assert SPEC_PATH.exists(), f"Spec file not found: {SPEC_PATH}"


def test_spec_has_one_tool(tools):
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "web_search"


def test_effects_valid(tools):
    for tool in tools:
        effects = tool.get("function", {}).get("effects", [])
        nail.validate_effects(effects)  # should not raise


def test_convert_to_openai(tools):
    result = nail.convert_tools(tools, source="nail", target="openai")
    assert len(result) == 1
    assert result[0]["type"] == "function"
    assert "effects" not in result[0]["function"]
    assert result[0]["function"]["name"] == "web_search"


def test_convert_to_anthropic(tools):
    result = nail.convert_tools(tools, source="nail", target="anthropic")
    assert len(result) == 1
    assert "input_schema" in result[0]
    assert "type" not in result[0]  # no wrapper
    assert result[0]["name"] == "web_search"


def test_convert_to_gemini(tools):
    result = nail.convert_tools(tools, source="nail", target="gemini")
    assert len(result) == 1
    assert "parameters" in result[0]
    assert "type" not in result[0]  # no wrapper
    assert result[0]["name"] == "web_search"


def test_required_params_preserved(tools):
    for provider in ("openai", "anthropic", "gemini"):
        result = nail.convert_tools(tools, source="nail", target=provider)
        tool = result[0]
        if provider == "openai":
            params = tool["function"]["parameters"]
        elif provider == "anthropic":
            params = tool["input_schema"]
        else:  # gemini
            params = tool["parameters"]
        assert "query" in params["properties"]
        assert "query" in params["required"]
