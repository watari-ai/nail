"""MCP ↔ NAIL bridge: auto-annotate MCP tools with NAIL effects.

MCP (Model Context Protocol) defines tools in a different format than
OpenAI Function Calling. This module provides bidirectional conversion:

  from_mcp(mcp_tools)       → OpenAI-format + NAIL effect annotations
  to_mcp(openai_tools)      → MCP tool format (strips NAIL extensions)
  infer_effects(name, desc) → Heuristic: FS/NET/PROC/TIME/RAND/IO
"""

from __future__ import annotations

import re
from typing import Any


# ── Effect inference heuristics ──────────────────────────────────────────────

# Each rule: (pattern_list, effect)
# Evaluated in order; first match wins. Patterns are word-boundary regexes.
_EFFECT_RULES: list[tuple[list[str], str]] = [
    (["file", "read", "write", "path", "dir", "folder", "disk", "fs", "storage",
       "csv", "json_file", "yaml_file", "upload", "download_file"], "FS"),
    (["http", "request", "fetch", "url", "web", "curl", "api_call", "get_page",
       "download", "scrape", "browse", "net", "socket", "webhook"], "NET"),
    (["exec", "run", "shell", "command", "process", "spawn", "invoke", "script",
       "bash", "zsh", "terminal", "subprocess"], "PROC"),
    (["time", "date", "now", "timestamp", "sleep", "wait", "delay", "schedule",
       "clock", "calendar"], "TIME"),
    (["random", "rand", "uuid", "nonce", "shuffle", "sample", "entropy"], "RAND"),
    (["memory", "state", "mutable", "cache", "store", "set_", "update_", "mut"], "MUT"),
]


def infer_effects(name: str, description: str = "") -> list[str]:
    """Heuristically infer NAIL effect labels from a tool's name and description.

    Uses keyword matching against the tool name and description text.
    Returns the most specific matching effect, defaulting to ``["IO"]``.

    Args:
        name:        Tool name (e.g. ``"read_file"``).
        description: Optional tool description text.

    Returns:
        A list containing exactly one inferred effect label (or ``["IO"]``).

    Examples:
        >>> infer_effects("read_file", "Read a file from disk")
        ['FS']
        >>> infer_effects("http_get", "Fetch a URL")
        ['NET']
        >>> infer_effects("run_command", "Execute a shell command")
        ['PROC']
        >>> infer_effects("greet", "Say hello to the user")
        ['IO']
    """
    haystack = (name + " " + description).lower()

    for keywords, effect in _EFFECT_RULES:
        for kw in keywords:
            # Match keyword as substring (with optional word boundary)
            if re.search(r'\b' + re.escape(kw.lower()) + r'\b', haystack):
                return [effect]
            # Also check without word boundary (handles cases like "writefile")
            if kw.lower() in haystack:
                return [effect]

    return ["IO"]  # default: console / generic output


# ── MCP → OpenAI FC conversion ────────────────────────────────────────────────

def from_mcp(
    mcp_tools: list[dict[str, Any]],
    *,
    auto_annotate: bool = True,
    existing_effects: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Convert MCP tool definitions to OpenAI Function Calling format with NAIL effects.

    MCP tool format:
    ```json
    {
        "name": "read_file",
        "description": "Read a file from disk",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]
        }
    }
    ```

    Output (OpenAI FC + NAIL extension):
    ```json
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from disk",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            },
            "effects": ["FS"]
        }
    }
    ```

    Args:
        mcp_tools:        List of MCP tool dicts (with ``name``, ``description``,
                          ``inputSchema`` fields).
        auto_annotate:    When ``True`` (default), automatically infer NAIL effect
                          labels using :func:`infer_effects`.
        existing_effects: Optional mapping of ``{tool_name: [effects]}`` that takes
                          precedence over auto-annotation.

    Returns:
        List of OpenAI-format tool dicts with NAIL ``effects`` annotations.

    Example:
        >>> from nail_lang import from_mcp, filter_by_effects
        >>> annotated = from_mcp(my_mcp_tools)
        >>> safe = filter_by_effects(annotated, allowed=["FS", "IO"])
    """
    result = []
    overrides = existing_effects or {}

    for tool in mcp_tools:
        if not isinstance(tool, dict):
            continue

        name = tool.get("name", "")
        desc = tool.get("description", "")
        schema = tool.get("inputSchema") or tool.get("input_schema") or {}

        fn: dict[str, Any] = {
            "name": name,
            "description": desc,
            "parameters": schema,
        }

        # Effect annotation: explicit override > auto-inference > skip
        if name in overrides:
            fn["effects"] = list(overrides[name])
        elif auto_annotate:
            fn["effects"] = infer_effects(name, desc)

        result.append({"type": "function", "function": fn})

    return result


# ── OpenAI FC → MCP conversion ────────────────────────────────────────────────

def to_mcp(
    openai_tools: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert OpenAI Function Calling tool definitions to MCP format.

    Strips NAIL-specific ``effects`` annotations (MCP has no native concept
    of side-effect declarations).

    Args:
        openai_tools: List of OpenAI-format tool dicts (``type: function``).

    Returns:
        List of MCP tool dicts with ``name``, ``description``, ``inputSchema``.

    Example:
        >>> from nail_lang import filter_by_effects, to_mcp
        >>> safe_fc_tools = filter_by_effects(all_tools, allowed=["FS", "IO"])
        >>> mcp_tools = to_mcp(safe_fc_tools)  # feed back to an MCP server
    """
    result = []

    for tool in openai_tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function", {})
        if not isinstance(fn, dict):
            continue

        mcp_tool: dict[str, Any] = {
            "name": fn.get("name", ""),
            "description": fn.get("description", ""),
            "inputSchema": fn.get("parameters") or {},
        }
        result.append(mcp_tool)

    return result
