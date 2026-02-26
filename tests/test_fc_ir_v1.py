"""Tests for nail_lang.fc_ir_v1 — parser, validator, canonicalizer, provider converters."""

from __future__ import annotations

import json

import pytest

from nail_lang.fc_ir_v1 import (
    Diagnostic,
    ParseResult,
    canonicalize,
    parse_fc_ir_v1,
    sanitize_name,
    to_anthropic,
    to_gemini,
    to_openai,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_tool(
    id="weather.get",
    doc="Retrieves current weather data for the specified city via an external API.",
    effects=None,
    input=None,
    **kwargs,
) -> dict:
    tool: dict = {"id": id, "doc": doc}
    tool["effects"] = effects if effects is not None else {"kind": "capabilities", "allow": []}
    tool["input"] = input if input is not None else {
        "type": "object",
        "properties": {"city": {"type": "string"}},
        "required": ["city"],
    }
    tool.update(kwargs)
    return tool


def _make_root(tools=None, meta=None) -> dict:
    return {
        "kind": "fc_ir_v1",
        "tools": tools if tools is not None else [_make_tool()],
        "meta": meta or {"nail_version": "0.9.0"},
    }


def _diag_codes(result: ParseResult) -> list[str]:
    return [d.code for d in result.diagnostics]


def _error_codes(result: ParseResult) -> list[str]:
    return [d.code for d in result.errors]


def _warn_codes(result: ParseResult) -> list[str]:
    return [d.code for d in result.warnings]


# ── 基本パース ────────────────────────────────────────────────────────────────

def test_parse_valid_root():
    root = _make_root()
    result = parse_fc_ir_v1(root)
    assert result.ok
    assert result.errors == []


def test_parse_invalid_kind():
    root = {"kind": "not_fc_ir_v1", "tools": [], "meta": {}}
    result = parse_fc_ir_v1(root)
    assert not result.ok
    assert "FC001" in _error_codes(result)


def test_parse_missing_required_fields():
    # Tool is missing doc, effects, input
    tool = {"id": "bare.tool"}
    root = {"kind": "fc_ir_v1", "tools": [tool], "meta": {}}
    result = parse_fc_ir_v1(root)
    assert not result.ok
    error_codes = _error_codes(result)
    assert "FC001" in error_codes  # missing doc / effects / input


# ── 名前サニタイズ §4 ─────────────────────────────────────────────────────────

def test_sanitize_dots():
    name, err = sanitize_name("weather.get")
    assert name == "weather_get"
    assert err is None


def test_sanitize_dashes():
    name, err = sanitize_name("my-tool")
    assert name == "my_tool"
    assert err is None


def test_sanitize_leading_digit():
    name, err = sanitize_name("123abc")
    assert name == "t_123abc"
    assert err is None


def test_sanitize_uppercase():
    name, err = sanitize_name("File/Reader")
    assert name == "file_reader"
    assert err is None


def test_sanitize_double_dot():
    name, err = sanitize_name("my..double.dot")
    assert name == "my_double_dot"
    assert err is None


def test_sanitize_empty():
    name, err = sanitize_name("---")
    assert name == ""
    assert err is not None
    assert err.code == "FC002"
    assert err.level == "ERROR"


# ── Additional sanitize cases from spec table ─────────────────────────────────

def test_sanitize_hello_world():
    name, err = sanitize_name("hello world")
    assert name == "hello_world"
    assert err is None


def test_sanitize_net_http_GET():
    name, err = sanitize_name("net.http.GET")
    assert name == "net_http_get"
    assert err is None


# ── エラーコード ──────────────────────────────────────────────────────────────

def test_fc001_duplicate_id():
    tools = [_make_tool(id="dup.tool"), _make_tool(id="dup.tool")]
    root = _make_root(tools=tools)
    result = parse_fc_ir_v1(root)
    assert not result.ok
    assert "FC001" in _error_codes(result)


def test_fc002_name_collision():
    # weather.get → weather_get; weather_get → weather_get (collision)
    tool1 = _make_tool(id="weather.get")
    tool2 = _make_tool(id="weather_get")
    root = _make_root(tools=[tool1, tool2])
    result = parse_fc_ir_v1(root)
    assert not result.ok
    assert "FC002" in _error_codes(result)


def test_fc003_input_not_object():
    tool = _make_tool(input={"type": "string"})
    root = _make_root(tools=[tool])
    result = parse_fc_ir_v1(root)
    assert not result.ok
    assert "FC003" in _error_codes(result)


def test_fc006_output_missing_warn():
    tool = _make_tool()  # no output field
    assert "output" not in tool
    root = _make_root(tools=[tool])
    result = parse_fc_ir_v1(root)
    assert result.ok  # only a warning
    assert "FC006" in _warn_codes(result)


def test_fc009_legacy_effects_warn():
    tool = _make_tool(effects=["FS", "NET"])  # legacy list format
    root = _make_root(tools=[tool])
    result = parse_fc_ir_v1(root)
    assert result.ok  # only a warning
    assert "FC009" in _warn_codes(result)


def test_fc010_doc_too_short_warn():
    tool = _make_tool(doc="Short doc")  # < 20 chars
    root = _make_root(tools=[tool])
    result = parse_fc_ir_v1(root)
    assert result.ok  # only a warning
    assert "FC010" in _warn_codes(result)


# ── 型変換 ───────────────────────────────────────────────────────────────────

def _openai_params_for(input_def: dict) -> dict:
    """Helper: convert a single tool with given input to OpenAI and return parameters."""
    tool = _make_tool(
        doc="A sufficiently long documentation string for the test tool.",
        output={"type": "string"},
        input=input_def,
    )
    root = _make_root(tools=[tool])
    converted = to_openai(root)
    return converted[0]["function"]["parameters"]


def test_type_bool_to_openai():
    input_def = {
        "type": "object",
        "properties": {"flag": {"type": "bool"}},
        "required": ["flag"],
    }
    params = _openai_params_for(input_def)
    assert params["properties"]["flag"] == {"type": "boolean"}


def test_type_int_to_openai():
    input_def = {
        "type": "object",
        "properties": {"count": {"type": "int"}},
        "required": ["count"],
    }
    params = _openai_params_for(input_def)
    assert params["properties"]["count"] == {"type": "integer"}


def test_type_float_to_openai():
    input_def = {
        "type": "object",
        "properties": {"value": {"type": "float"}},
        "required": ["value"],
    }
    params = _openai_params_for(input_def)
    assert params["properties"]["value"] == {"type": "number"}


def test_type_optional_excludes_required():
    input_def = {
        "type": "object",
        "properties": {
            "required_field": {"type": "string"},
            "optional_field": {"type": "optional", "inner": {"type": "string"}},
        },
        "required": ["required_field"],
    }
    params = _openai_params_for(input_def)
    assert "required_field" in params.get("required", [])
    assert "optional_field" not in params.get("required", [])
    # optional_field should still appear in properties as a string
    assert params["properties"]["optional_field"]["type"] == "string"
    assert "__optional__" not in params["properties"]["optional_field"]


def test_type_enum_to_openai():
    input_def = {
        "type": "object",
        "properties": {
            "units": {"type": "enum", "values": ["celsius", "fahrenheit"]},
        },
        "required": ["units"],
    }
    params = _openai_params_for(input_def)
    assert params["properties"]["units"] == {"type": "string", "enum": ["celsius", "fahrenheit"]}


def test_type_array_to_openai():
    input_def = {
        "type": "object",
        "properties": {
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["tags"],
    }
    params = _openai_params_for(input_def)
    assert params["properties"]["tags"] == {"type": "array", "items": {"type": "string"}}


def test_type_object_recursive():
    input_def = {
        "type": "object",
        "properties": {
            "nested": {
                "type": "object",
                "properties": {
                    "x": {"type": "int"},
                    "y": {"type": "float"},
                },
                "required": ["x"],
            }
        },
        "required": ["nested"],
    }
    params = _openai_params_for(input_def)
    nested = params["properties"]["nested"]
    assert nested["type"] == "object"
    assert nested["properties"]["x"] == {"type": "integer"}
    assert nested["properties"]["y"] == {"type": "number"}
    assert nested["required"] == ["x"]


# ── Appendix A サンプル（E2Eテスト）────────────────────────────────────────────

APPENDIX_A = {
    "kind": "fc_ir_v1",
    "tools": [
        {
            "id": "weather.get",
            "name": "weather_get",
            "title": "Get current weather",
            "doc": (
                "Retrieves current weather information for a specified city from an external API.\n"
                "Returns structured data including temperature, humidity, and weather summary."
            ),
            "effects": {"kind": "capabilities", "allow": ["NET:http_get"]},
            "input": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "units": {
                        "type": "optional",
                        "inner": {"type": "enum", "values": ["celsius", "fahrenheit"]},
                    },
                },
                "required": ["city"],
            },
            "output": {
                "type": "object",
                "properties": {
                    "temperature": {"type": "float"},
                    "humidity": {"type": "float"},
                    "description": {"type": "string"},
                },
                "required": ["temperature", "humidity", "description"],
            },
        }
    ],
    "meta": {"nail_version": "0.9.0", "created_at": "2026-02-25T10:00:00Z"},
}


def test_appendix_a_to_openai():
    converted = to_openai(APPENDIX_A)
    assert len(converted) == 1
    tool = converted[0]
    assert tool["type"] == "function"
    fn = tool["function"]
    assert fn["name"] == "weather_get"
    assert "Retrieves current weather" in fn["description"]
    params = fn["parameters"]
    assert params["type"] == "object"
    props = params["properties"]
    assert props["city"] == {"type": "string"}
    # units is optional → should map to enum, not in required
    assert props["units"] == {"type": "string", "enum": ["celsius", "fahrenheit"]}
    assert "city" in params.get("required", [])
    assert "units" not in params.get("required", [])


def test_appendix_a_to_anthropic():
    converted = to_anthropic(APPENDIX_A)
    assert len(converted) == 1
    tool = converted[0]
    assert tool["name"] == "weather_get"
    assert "Retrieves current weather" in tool["description"]
    schema = tool["input_schema"]
    assert schema["type"] == "object"
    assert "city" in schema["properties"]
    assert "units" in schema["properties"]
    assert "city" in schema.get("required", [])
    assert "units" not in schema.get("required", [])


def test_appendix_a_to_gemini():
    converted = to_gemini(APPENDIX_A)
    assert len(converted) == 1
    tool = converted[0]
    assert tool["name"] == "weather_get"
    assert "Retrieves current weather" in tool["description"]
    params = tool["parameters"]
    assert params["type"] == "object"
    assert "city" in params["properties"]


def test_appendix_a_canonicalize():
    canonical = canonicalize(APPENDIX_A)
    parsed = json.loads(canonical)

    # Verify root key order
    root_keys = list(parsed.keys())
    assert root_keys == ["kind", "tools", "meta"]

    # Verify tool key order
    tool_keys = list(parsed["tools"][0].keys())
    expected_tool_keys = ["id", "name", "title", "doc", "effects", "input", "output"]
    for k in expected_tool_keys:
        assert k in tool_keys
    # Verify ordering: id before name before title, etc.
    for i in range(len(expected_tool_keys) - 1):
        a = expected_tool_keys[i]
        b = expected_tool_keys[i + 1]
        assert tool_keys.index(a) < tool_keys.index(b), f"{a} should come before {b}"

    # Verify compact JSON (no pretty-printing indentation or newlines added by JSON encoder)
    # Re-encode with default settings; compact has no newlines from the encoder
    assert "\n " not in canonical   # no indented pretty-print lines
    # Verify round-trip is lossless
    assert json.loads(canonical) == json.loads(canonicalize(parsed))

    # Verify content
    assert parsed["kind"] == "fc_ir_v1"
    assert parsed["tools"][0]["id"] == "weather.get"
    assert parsed["meta"]["nail_version"] == "0.9.0"


def test_appendix_a_canonicalize_legacy_effects():
    """Legacy effects list should be normalized to capabilities format."""
    root = {
        "kind": "fc_ir_v1",
        "tools": [
            {
                "id": "fs.read",
                "doc": "Reads a file and returns its content as a UTF-8 string.",
                "effects": ["FS", "NET"],  # legacy format
                "input": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            }
        ],
        "meta": {},
    }
    canonical = canonicalize(root)
    parsed = json.loads(canonical)
    effects = parsed["tools"][0]["effects"]
    assert effects["kind"] == "capabilities"
    assert effects["allow"] == ["FS", "NET"]


def test_canonicalize_unknown_keys_sorted():
    """Unknown keys should appear after known keys, sorted alphabetically."""
    root = {
        "kind": "fc_ir_v1",
        "tools": [
            {
                "id": "test.tool",
                "doc": "A sufficiently long documentation string for testing purposes.",
                "effects": {"kind": "capabilities", "allow": []},
                "input": {
                    "type": "object",
                    "properties": {},
                },
                "zzz_unknown": "last",
                "aaa_unknown": "first",
            }
        ],
        "meta": {},
    }
    canonical = canonicalize(root)
    parsed = json.loads(canonical)
    tool_keys = list(parsed["tools"][0].keys())
    # aaa_unknown should come before zzz_unknown
    assert tool_keys.index("aaa_unknown") < tool_keys.index("zzz_unknown")
    # Both should come after known keys
    assert tool_keys.index("doc") < tool_keys.index("aaa_unknown")


def test_parse_valid_no_warn_with_output():
    """A complete valid tool should have no warnings beyond FC006."""
    tool = {
        "id": "math.add",
        "name": "math_add",
        "title": "Integer addition",
        "doc": "Adds two integers and returns the sum. No side effects.",
        "effects": {"kind": "capabilities", "allow": []},
        "input": {
            "type": "object",
            "properties": {
                "a": {"type": "int"},
                "b": {"type": "int"},
            },
            "required": ["a", "b"],
        },
        "output": {"type": "int"},
    }
    root = _make_root(tools=[tool])
    result = parse_fc_ir_v1(root)
    assert result.ok
    assert result.errors == []
    # No FC006 since output is present
    assert "FC006" not in _warn_codes(result)
