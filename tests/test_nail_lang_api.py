"""Tests for the nail_lang Python package API (Issue #60).

Covers:
- filter_by_effects: the primary LiteLLM/FC integration function
- get_tool_effects: introspect tool annotations
- annotate_tool_effects: add effects to a tool
- validate_effects: validation against NAIL vocabulary
- Package-level imports from nail_lang
"""

import pytest
from nail_lang import (
    filter_by_effects,
    get_tool_effects,
    annotate_tool_effects,
    validate_effects,
    VALID_EFFECTS,
    Checker,
    Runtime,
    CheckError,
)
from nail_lang._effects import _coerce_allowed


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _tool(name: str, effects=None) -> dict:
    """Build a minimal OpenAI-format tool dict."""
    fn: dict = {"name": name}
    if effects is not None:
        fn["effects"] = effects
    return {"type": "function", "function": fn}


FULL_TOOL_SET = [
    _tool("read_file",    ["FS"]),
    _tool("write_file",   ["FS"]),
    _tool("http_get",     ["NET"]),
    _tool("http_post",    ["NET", "IO"]),
    _tool("log",          ["IO"]),
    _tool("get_rand",     ["RAND"]),
    _tool("unknown_tool"),                  # no effects annotation
]


# ── filter_by_effects ─────────────────────────────────────────────────────────

class TestFilterByEffects:

    def test_empty_tools_returns_empty(self):
        assert filter_by_effects([], allowed=["IO"]) == []

    def test_empty_allowed_returns_nothing(self):
        result = filter_by_effects(FULL_TOOL_SET, allowed=[])
        # All tools require at least one effect; unannotated excluded by default
        assert result == []

    def test_io_only_allows_log(self):
        result = filter_by_effects(FULL_TOOL_SET, allowed=["IO"])
        names = {t["function"]["name"] for t in result}
        assert names == {"log"}

    def test_fs_io_allows_file_tools_and_log(self):
        result = filter_by_effects(FULL_TOOL_SET, allowed=["FS", "IO"])
        names = {t["function"]["name"] for t in result}
        assert names == {"read_file", "write_file", "log"}

    def test_net_io_allows_http_and_log(self):
        result = filter_by_effects(FULL_TOOL_SET, allowed=["NET", "IO"])
        names = {t["function"]["name"] for t in result}
        assert names == {"http_get", "http_post", "log"}

    def test_multi_effect_tool_excluded_if_any_disallowed(self):
        # http_post requires [NET, IO]; if NET is not allowed → excluded
        result = filter_by_effects(FULL_TOOL_SET, allowed=["IO"])
        names = {t["function"]["name"] for t in result}
        assert "http_post" not in names

    def test_unannotated_excluded_by_default(self):
        result = filter_by_effects(FULL_TOOL_SET, allowed=["IO", "FS", "NET", "RAND"])
        names = {t["function"]["name"] for t in result}
        assert "unknown_tool" not in names

    def test_unannotated_included_when_flag_set(self):
        result = filter_by_effects(FULL_TOOL_SET, allowed=["IO"], include_unannotated=True)
        names = {t["function"]["name"] for t in result}
        assert "unknown_tool" in names
        assert "log" in names
        assert "http_get" not in names

    def test_all_allowed_includes_all_annotated(self):
        all_effects = list(VALID_EFFECTS)
        result = filter_by_effects(FULL_TOOL_SET, allowed=all_effects)
        names = {t["function"]["name"] for t in result}
        annotated_expected = {
            "read_file", "write_file", "http_get", "http_post", "log", "get_rand"
        }
        assert names == annotated_expected  # unknown_tool excluded (unannotated)

    def test_returns_same_dict_objects(self):
        """filter_by_effects should return the same dicts (no copy)."""
        tools = [_tool("log", ["IO"])]
        result = filter_by_effects(tools, allowed=["IO"])
        assert result[0] is tools[0]

    def test_frozenset_allowed(self):
        result = filter_by_effects(FULL_TOOL_SET, allowed=frozenset(["IO"]))
        names = {t["function"]["name"] for t in result}
        assert names == {"log"}

    def test_set_allowed(self):
        result = filter_by_effects(FULL_TOOL_SET, allowed={"IO", "FS"})
        names = {t["function"]["name"] for t in result}
        assert names == {"read_file", "write_file", "log"}

    def test_non_list_tools_raises_type_error(self):
        with pytest.raises(TypeError):
            filter_by_effects("not a list", allowed=["IO"])

    def test_non_dict_tools_skipped(self):
        # Mixed list: non-dicts are silently skipped
        tools = [_tool("log", ["IO"]), "bad", 42, None]
        result = filter_by_effects(tools, allowed=["IO"])
        assert len(result) == 1
        assert result[0]["function"]["name"] == "log"

    def test_tool_without_function_key_skipped(self):
        bad_tool = {"type": "function"}  # missing "function" key
        tools = [bad_tool, _tool("log", ["IO"])]
        result = filter_by_effects(tools, allowed=["IO"])
        assert len(result) == 1

    def test_empty_effects_list_excluded_when_allowed_is_nonempty(self):
        # Tool with effects=[] has an empty effect set → subset of anything → included
        no_effect_tool = _tool("pure_fn", [])
        result = filter_by_effects([no_effect_tool], allowed=["IO"])
        assert len(result) == 1

    def test_empty_effects_list_and_empty_allowed(self):
        # effects=[] is a subset of [] → included
        no_effect_tool = _tool("pure_fn", [])
        result = filter_by_effects([no_effect_tool], allowed=[])
        assert len(result) == 1


# ── get_tool_effects ──────────────────────────────────────────────────────────

class TestGetToolEffects:

    def test_returns_frozenset(self):
        t = _tool("read_file", ["FS", "IO"])
        result = get_tool_effects(t)
        assert result == frozenset({"FS", "IO"})

    def test_returns_none_when_unannotated(self):
        t = _tool("unknown")
        assert get_tool_effects(t) is None

    def test_empty_effects_list(self):
        t = _tool("pure", [])
        assert get_tool_effects(t) == frozenset()

    def test_non_list_effects_returns_none(self):
        t = {"type": "function", "function": {"name": "bad", "effects": "IO"}}
        assert get_tool_effects(t) is None


# ── annotate_tool_effects ─────────────────────────────────────────────────────

class TestAnnotateToolEffects:

    def test_adds_effects_to_tool(self):
        t = _tool("my_tool")
        annotated = annotate_tool_effects(t, ["NET"])
        assert annotated["function"]["effects"] == ["NET"]

    def test_does_not_mutate_original(self):
        t = _tool("my_tool")
        _ = annotate_tool_effects(t, ["NET"])
        assert "effects" not in t["function"]

    def test_overwrites_existing_effects(self):
        t = _tool("my_tool", ["IO"])
        annotated = annotate_tool_effects(t, ["FS"])
        assert annotated["function"]["effects"] == ["FS"]


# ── validate_effects ──────────────────────────────────────────────────────────

class TestValidateEffects:

    def test_valid_effects_returns_list(self):
        result = validate_effects(["IO", "FS"])
        assert result == ["IO", "FS"]

    def test_unknown_effect_raises(self):
        with pytest.raises(ValueError) as exc_info:
            validate_effects(["IO", "MAGIC"])
        assert "MAGIC" in str(exc_info.value)

    def test_empty_list_valid(self):
        assert validate_effects([]) == []


# ── VALID_EFFECTS constant ────────────────────────────────────────────────────

class TestValidEffects:

    def test_contains_nail_effects(self):
        for e in ["IO", "FS", "NET", "TIME", "RAND", "MUT"]:
            assert e in VALID_EFFECTS

    def test_is_frozenset(self):
        assert isinstance(VALID_EFFECTS, frozenset)


# ── Package-level imports ─────────────────────────────────────────────────────

class TestPackageImports:

    def test_checker_importable(self):
        checker = Checker({
            "nail": "0.7.0",
            "kind": "fn",
            "id": "main",
            "effects": [],
            "params": [],
            "returns": {"type": "unit"},
            "body": [{"op": "return", "val": {"lit": None, "type": {"type": "unit"}}}],
        })
        checker.check()

    def test_runtime_importable(self):
        # Standalone fn: use run(args) directly
        spec = {
            "nail": "0.7.0",
            "kind": "fn",
            "id": "add",
            "effects": [],
            "params": [
                {"id": "a", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
                {"id": "b", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
            ],
            "returns": {"type": "int", "bits": 64, "overflow": "panic"},
            "body": [
                {"op": "return", "val": {"op": "+", "l": {"ref": "a"}, "r": {"ref": "b"}}}
            ],
        }
        runtime = Runtime(spec)
        result = runtime.run({"a": 3, "b": 4})
        assert result == 7

    def test_check_error_importable(self):
        with pytest.raises(CheckError):
            checker = Checker({
                "nail": "0.7.0",
                "kind": "fn",
                "id": "main",
                "effects": [],
                "params": [],
                "returns": {"type": "int", "bits": 64, "overflow": "panic"},
                "body": [],  # no return — should fail
            })
            checker.check()

    def test_version_string(self):
        from nail_lang import __version__
        assert __version__ == "0.9.0"


# ── Integration: filter then pass to LiteLLM-style call ──────────────────────

class TestEndToEndScenario:
    """Simulates the real-world LiteLLM pattern without actually calling LiteLLM."""

    def test_sandbox_scenario(self):
        """Restrict to read-only (FS + IO) — no network or process execution."""
        all_tools = [
            _tool("read_file",    ["FS"]),
            _tool("write_file",   ["FS"]),
            _tool("http_get",     ["NET"]),
            _tool("exec_script",  ["PROC"]),
            _tool("log",          ["IO"]),
        ]
        sandbox_tools = filter_by_effects(all_tools, allowed=["FS", "IO"])
        names = [t["function"]["name"] for t in sandbox_tools]
        assert names == ["read_file", "write_file", "log"]

    def test_privilege_delegation_scenario(self):
        """Agent A (FS+IO) delegates to Agent B — B's tools restricted to A's scope."""
        agent_a_scope = ["FS", "IO"]
        agent_b_tools = [
            _tool("read_file",   ["FS"]),
            _tool("http_post",   ["NET"]),
            _tool("exec",        ["PROC"]),
            _tool("log",         ["IO"]),
        ]
        agent_b_scoped = filter_by_effects(agent_b_tools, allowed=agent_a_scope)
        names = {t["function"]["name"] for t in agent_b_scoped}
        assert names == {"read_file", "log"}
        # http_post and exec are excluded — privilege escalation prevented
