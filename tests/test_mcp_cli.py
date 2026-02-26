"""Tests for nail_lang.mcp_cli and MCP helper utilities."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nail_lang.mcp_cli import mcp_check, mcp_convert, mcp_a2a
from nail_lang._mcp import to_a2a_agent_card, validate_for_mcp


FC_DIR = Path(__file__).parent / "fc"
TOOLS_NAIL = FC_DIR / "tools.nail"


def load_json(path: Path) -> object:
    with open(path) as f:
        return json.load(f)


def write_temp_nail(data: object) -> str:
    f = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".nail",
        delete=False,
        encoding="utf-8",
    )
    json.dump(data, f, indent=2)
    f.close()
    return f.name


def test_mcp_check_valid_tools_returns_0(capsys):
    exit_code = mcp_check(str(TOOLS_NAIL), fmt="json")
    assert exit_code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True
    assert result["errors"] == []


def test_mcp_check_missing_description_returns_2(capsys):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "tool_a",
                "parameters": {"type": "object", "properties": {}},
                "effects": [],
            },
        }
    ]
    path = write_temp_nail(tools)
    try:
        exit_code = mcp_check(path, fmt="json")
        result = json.loads(capsys.readouterr().out)
        assert exit_code == 2
        assert result["ok"] is False
        assert any("description" in e for e in result["errors"])
    finally:
        os.unlink(path)


def test_mcp_check_duplicate_names_returns_2(capsys):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "dup",
                "description": "A",
                "parameters": {"type": "object", "properties": {}},
                "effects": [],
            },
        },
        {
            "type": "function",
            "function": {
                "name": "dup",
                "description": "B",
                "parameters": {"type": "object", "properties": {}},
                "effects": [],
            },
        },
    ]
    path = write_temp_nail(tools)
    try:
        exit_code = mcp_check(path, fmt="json")
        result = json.loads(capsys.readouterr().out)
        assert exit_code == 2
        assert result["ok"] is False
        assert any("duplicate" in e.lower() for e in result["errors"])
    finally:
        os.unlink(path)


def test_mcp_convert_output_json_shape(capsys):
    exit_code = mcp_convert(str(TOOLS_NAIL), out=None, fmt="json")
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "tools" in payload
    assert isinstance(payload["tools"], list)
    assert len(payload["tools"]) >= 1
    for tool in payload["tools"]:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool


def test_mcp_a2a_output_card_shape(capsys):
    exit_code = mcp_a2a(
        str(TOOLS_NAIL),
        name="Test Agent",
        url="http://localhost:8080",
        fmt="human",
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    card = json.loads(captured.out)
    assert card["name"] == "Test Agent"
    assert card["url"] == "http://localhost:8080"
    assert "skills" in card
    assert isinstance(card["skills"], list)
    assert len(card["skills"]) == 3
    assert "A2A Agent Card generated" in captured.err


def test_mcp_a2a_effect_to_tag_mapping():
    tools = [
        {"type": "function", "function": {"name": "t_fs", "description": "d", "parameters": {"type": "object"}, "effects": ["FS"]}},
        {"type": "function", "function": {"name": "t_net", "description": "d", "parameters": {"type": "object"}, "effects": ["NET"]}},
        {"type": "function", "function": {"name": "t_proc", "description": "d", "parameters": {"type": "object"}, "effects": ["PROC"]}},
        {"type": "function", "function": {"name": "t_time", "description": "d", "parameters": {"type": "object"}, "effects": ["TIME"]}},
        {"type": "function", "function": {"name": "t_rand", "description": "d", "parameters": {"type": "object"}, "effects": ["RAND"]}},
        {"type": "function", "function": {"name": "t_io", "description": "d", "parameters": {"type": "object"}, "effects": ["IO"]}},
        {"type": "function", "function": {"name": "t_pure", "description": "d", "parameters": {"type": "object"}, "effects": []}},
    ]
    card = to_a2a_agent_card(tools, name="A", url="http://x")
    tags = {s["id"]: s["tags"][0] for s in card["skills"]}
    assert tags["t_fs"] == "storage"
    assert tags["t_net"] == "web"
    assert tags["t_proc"] == "execution"
    assert tags["t_time"] == "scheduling"
    assert tags["t_rand"] == "generation"
    assert tags["t_io"] == "interface"
    assert tags["t_pure"] == "computation"


def test_to_a2a_agent_card_direct():
    tools = load_json(TOOLS_NAIL)
    card = to_a2a_agent_card(
        tools,
        name="Direct Card",
        url="http://localhost:9999",
        description="desc",
        version="1.2.3",
    )
    assert card["name"] == "Direct Card"
    assert card["description"] == "desc"
    assert card["version"] == "1.2.3"
    assert card["url"] == "http://localhost:9999"
    assert card["capabilities"]["streaming"] is False
    assert len(card["skills"]) == len(tools)


def test_validate_for_mcp_direct():
    good_tools = [
        {
            "type": "function",
            "function": {
                "name": "tool",
                "description": "desc",
                "parameters": {"type": "object", "properties": {}},
                "effects": [],
            },
        }
    ]
    assert validate_for_mcp(good_tools) == []

    bad_tools = [
        {
            "type": "function",
            "function": {
                "name": "dup",
                "description": "",
                "parameters": {"type": "string"},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "dup",
                "description": "ok",
                "parameters": {"type": "object"},
            },
        },
    ]
    errors = validate_for_mcp(bad_tools)
    assert any("description" in e for e in errors)
    assert any("duplicate" in e.lower() for e in errors)
    assert any("parameters" in e for e in errors)
