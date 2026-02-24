"""Tests for nail_lang MCP ↔ OpenAI FC bridge (Issue #61).

Covers:
- infer_effects: heuristic effect inference from tool name/description
- from_mcp: MCP → OpenAI FC + NAIL effects
- to_mcp: OpenAI FC → MCP (strips effects)
- Round-trip: from_mcp → filter_by_effects → to_mcp
"""

import pytest
from nail_lang import from_mcp, to_mcp, infer_effects, filter_by_effects


# ── infer_effects ─────────────────────────────────────────────────────────────

class TestInferEffects:

    def test_file_operations_infer_fs(self):
        assert infer_effects("read_file") == ["FS"]
        assert infer_effects("write_file") == ["FS"]
        assert infer_effects("list_directory") == ["FS"]

    def test_path_in_name_infers_fs(self):
        assert infer_effects("get_path_info") == ["FS"]

    def test_http_operations_infer_net(self):
        assert infer_effects("http_get") == ["NET"]
        assert infer_effects("fetch_url") == ["NET"]

    def test_description_hints_net(self):
        assert infer_effects("query", "Fetch data from a web URL") == ["NET"]

    def test_exec_infers_proc(self):
        assert infer_effects("exec_command") == ["PROC"]
        assert infer_effects("run_shell_script") == ["PROC"]
        assert infer_effects("bash_eval") == ["PROC"]

    def test_time_operations_infer_time(self):
        assert infer_effects("get_current_time") == ["TIME"]
        assert infer_effects("sleep_ms") == ["TIME"]

    def test_random_operations_infer_rand(self):
        assert infer_effects("generate_uuid") == ["RAND"]
        assert infer_effects("random_sample") == ["RAND"]

    def test_default_io_for_unknown(self):
        assert infer_effects("greet") == ["IO"]
        assert infer_effects("format_output") == ["IO"]
        assert infer_effects("print_result") == ["IO"]

    def test_description_takes_precedence_when_name_is_generic(self):
        # name is generic, description reveals the effect
        result = infer_effects("process_input", "Execute a shell command")
        assert result == ["PROC"]

    def test_download_word_infers_net(self):
        assert infer_effects("download_resource") == ["NET"]


# ── from_mcp ──────────────────────────────────────────────────────────────────

def _mcp_tool(name: str, desc: str = "", schema: dict = None) -> dict:
    return {
        "name": name,
        "description": desc,
        "inputSchema": schema or {"type": "object", "properties": {}},
    }


class TestFromMcp:

    def test_converts_basic_structure(self):
        mcp = [_mcp_tool("log", "Log a message")]
        result = from_mcp(mcp)
        assert len(result) == 1
        tool = result[0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "log"
        assert tool["function"]["description"] == "Log a message"

    def test_auto_annotates_effects_by_default(self):
        mcp = [_mcp_tool("read_file", "Read a file")]
        result = from_mcp(mcp)
        assert result[0]["function"]["effects"] == ["FS"]

    def test_io_default_for_generic_tool(self):
        mcp = [_mcp_tool("greet", "Say hello")]
        result = from_mcp(mcp)
        assert result[0]["function"]["effects"] == ["IO"]

    def test_auto_annotate_false_skips_effects(self):
        mcp = [_mcp_tool("read_file", "Read a file")]
        result = from_mcp(mcp, auto_annotate=False)
        assert "effects" not in result[0]["function"]

    def test_existing_effects_override_auto(self):
        mcp = [_mcp_tool("read_file", "Read a file")]
        result = from_mcp(mcp, existing_effects={"read_file": ["FS", "IO"]})
        assert result[0]["function"]["effects"] == ["FS", "IO"]

    def test_existing_effects_only_override_matching(self):
        mcp = [
            _mcp_tool("read_file", "Read a file"),
            _mcp_tool("log", "Log a message"),
        ]
        result = from_mcp(mcp, existing_effects={"read_file": ["MUT"]})
        names = {t["function"]["name"]: t["function"]["effects"] for t in result}
        assert names["read_file"] == ["MUT"]
        assert names["log"] == ["IO"]  # auto-annotated

    def test_parameters_preserved(self):
        schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
        mcp = [_mcp_tool("read_file", schema=schema)]
        result = from_mcp(mcp)
        assert result[0]["function"]["parameters"] == schema

    def test_empty_input_returns_empty(self):
        assert from_mcp([]) == []

    def test_non_dict_items_skipped(self):
        result = from_mcp(["bad", 42, None, _mcp_tool("log")])
        assert len(result) == 1
        assert result[0]["function"]["name"] == "log"

    def test_inputschema_alias(self):
        mcp = [{"name": "t", "description": "", "input_schema": {"type": "object"}}]
        result = from_mcp(mcp)
        assert result[0]["function"]["parameters"] == {"type": "object"}


# ── to_mcp ────────────────────────────────────────────────────────────────────

def _fc_tool(name: str, desc: str = "", effects=None) -> dict:
    fn = {"name": name, "description": desc, "parameters": {"type": "object"}}
    if effects is not None:
        fn["effects"] = effects
    return {"type": "function", "function": fn}


class TestToMcp:

    def test_converts_basic_structure(self):
        fc = [_fc_tool("log", "Log a message", ["IO"])]
        result = to_mcp(fc)
        assert len(result) == 1
        mcp = result[0]
        assert mcp["name"] == "log"
        assert mcp["description"] == "Log a message"
        assert "effects" not in mcp

    def test_strips_effects(self):
        fc = [_fc_tool("read_file", effects=["FS"])]
        result = to_mcp(fc)
        assert "effects" not in result[0]

    def test_inputschema_contains_parameters(self):
        schema = {"type": "object", "properties": {"n": {"type": "integer"}}}
        fc = [{"type": "function", "function": {"name": "t", "description": "", "parameters": schema}}]
        result = to_mcp(fc)
        assert result[0]["inputSchema"] == schema

    def test_empty_input(self):
        assert to_mcp([]) == []

    def test_non_dict_items_skipped(self):
        result = to_mcp(["bad", _fc_tool("log")])
        assert len(result) == 1


# ── Round-trip ────────────────────────────────────────────────────────────────

class TestRoundTrip:
    """MCP → annotate → filter → back to MCP."""

    def test_full_pipeline(self):
        mcp_tools = [
            _mcp_tool("read_file",    "Read a file from disk"),
            _mcp_tool("http_get",     "Fetch a URL over the network"),
            _mcp_tool("run_command",  "Execute a shell command"),
            _mcp_tool("log",          "Log a message to console"),
        ]

        # Convert + auto-annotate
        fc_tools = from_mcp(mcp_tools)
        names_effects = {t["function"]["name"]: t["function"]["effects"] for t in fc_tools}
        assert names_effects["read_file"] == ["FS"]
        assert names_effects["http_get"]  == ["NET"]
        assert names_effects["run_command"] == ["PROC"]
        assert names_effects["log"] == ["IO"]

        # Sandbox: FS + IO only
        sandboxed = filter_by_effects(fc_tools, allowed=["FS", "IO"])
        sandboxed_names = {t["function"]["name"] for t in sandboxed}
        assert sandboxed_names == {"read_file", "log"}
        # NET and PROC excluded ✓

        # Convert back to MCP
        restored = to_mcp(sandboxed)
        assert len(restored) == 2
        assert all("effects" not in t for t in restored)
        restored_names = {t["name"] for t in restored}
        assert restored_names == {"read_file", "log"}
