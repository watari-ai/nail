"""FC Standard: Convert between NAIL's OpenAI FC format and provider-specific formats.

This module provides bidirectional conversion between:
  - NAIL internal representation (OpenAI FC format + ``effects`` annotations)
  - Standard OpenAI Function Calling format (no effects)
  - Anthropic tool format  (``input_schema`` instead of ``parameters``)
  - Gemini tool format     (flat ``name``/``description``/``parameters``)

Usage:
    from nail_lang import to_openai_tool, to_anthropic_tool, to_gemini_tool
    from nail_lang import from_openai_tool, from_anthropic_tool, from_gemini_tool
    from nail_lang import convert_tools

    # NAIL → OpenAI (strip effects)
    openai_tool = to_openai_tool(nail_annotated_tool)

    # NAIL → Anthropic
    anthropic_tool = to_anthropic_tool(nail_annotated_tool)

    # NAIL → Gemini
    gemini_tool = to_gemini_tool(nail_annotated_tool)

    # Reverse: provider format → NAIL (auto-infer effects)
    nail_tool = from_openai_tool(openai_tool)
    nail_tool = from_anthropic_tool(anthropic_tool)
    nail_tool = from_gemini_tool(gemini_tool)

    # Batch conversion
    anthropic_tools = convert_tools(nail_tools, target="anthropic", source="nail")
"""

from __future__ import annotations

import copy
from typing import Any

from nail_lang._mcp import infer_effects


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_fn(openai_fc_tool: dict[str, Any]) -> dict[str, Any]:
    """Extract the inner ``function`` dict from an OpenAI FC tool.

    Accepts both full ``{"type": "function", "function": {...}}`` format and
    bare function dicts (for convenience).
    """
    if "function" in openai_fc_tool:
        return openai_fc_tool["function"]
    # Bare format — treat the whole dict as the function descriptor
    return openai_fc_tool


def _strip_effects(fn: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy of *fn* without the ``effects`` key."""
    result = dict(fn)
    result.pop("effects", None)
    return result


# ── to_* functions (NAIL → provider) ─────────────────────────────────────────

def to_openai_tool(openai_fc_tool: dict[str, Any]) -> dict[str, Any]:
    """Convert a NAIL-annotated OpenAI FC tool to standard OpenAI format.

    Removes the NAIL-specific ``effects`` field so the result can be sent
    directly to the OpenAI API without causing validation errors.

    Args:
        openai_fc_tool: NAIL internal OpenAI FC tool dict, optionally containing
                        an ``effects`` field inside ``function``.

    Returns:
        Standard OpenAI tool dict (``{"type": "function", "function": {...}}``),
        with ``effects`` removed.

    Example:
        >>> nail_tool = {
        ...     "type": "function",
        ...     "function": {
        ...         "name": "read_file",
        ...         "description": "Read a file",
        ...         "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        ...         "effects": ["FS"],
        ...     },
        ... }
        >>> to_openai_tool(nail_tool)
        {'type': 'function', 'function': {'name': 'read_file', 'description': 'Read a file', 'parameters': {...}}}
    """
    fn = _extract_fn(openai_fc_tool)
    return {
        "type": "function",
        "function": _strip_effects(fn),
    }


def to_anthropic_tool(openai_fc_tool: dict[str, Any]) -> dict[str, Any]:
    """Convert a NAIL-annotated OpenAI FC tool to Anthropic tool format.

    Anthropic tools use ``input_schema`` instead of ``parameters``, and the
    entire tool is a flat dict without a ``type`` wrapper.

    Args:
        openai_fc_tool: NAIL internal OpenAI FC tool dict.

    Returns:
        Anthropic tool dict::

            {
                "name": "...",
                "description": "...",
                "input_schema": {"type": "object", "properties": {...}, "required": [...]}
            }

    Example:
        >>> to_anthropic_tool(nail_tool)
        {'name': 'read_file', 'description': '...', 'input_schema': {...}}
    """
    fn = _extract_fn(openai_fc_tool)
    result: dict[str, Any] = {
        "name": fn.get("name", ""),
        "description": fn.get("description", ""),
        "input_schema": copy.deepcopy(fn.get("parameters") or {}),
    }
    return result


def to_gemini_tool(openai_fc_tool: dict[str, Any]) -> dict[str, Any]:
    """Convert a NAIL-annotated OpenAI FC tool to Gemini tool format.

    Gemini uses a flat dict with ``name``, ``description``, and ``parameters``
    (same JSON Schema as OpenAI), but without the outer ``type: function`` wrapper.

    Args:
        openai_fc_tool: NAIL internal OpenAI FC tool dict.

    Returns:
        Gemini tool dict::

            {
                "name": "...",
                "description": "...",
                "parameters": {"type": "object", "properties": {...}, "required": [...]}
            }

    Example:
        >>> to_gemini_tool(nail_tool)
        {'name': 'read_file', 'description': '...', 'parameters': {...}}
    """
    fn = _extract_fn(openai_fc_tool)
    result: dict[str, Any] = {
        "name": fn.get("name", ""),
        "description": fn.get("description", ""),
        "parameters": copy.deepcopy(fn.get("parameters") or {}),
    }
    return result


# ── from_* functions (provider → NAIL) ───────────────────────────────────────

def from_openai_tool(
    openai_tool: dict[str, Any],
    *,
    auto_annotate: bool = True,
) -> dict[str, Any]:
    """Convert a standard OpenAI tool to NAIL-annotated OpenAI FC format.

    Adds NAIL ``effects`` annotation by calling :func:`~nail_lang.infer_effects`
    on the tool name and description.

    Args:
        openai_tool:    Standard OpenAI tool dict (``{"type": "function", "function": {...}}``).
        auto_annotate:  When ``True`` (default), infer and attach ``effects``.

    Returns:
        NAIL-annotated OpenAI FC tool dict with ``effects`` in ``function``.

    Example:
        >>> from_openai_tool({"type": "function", "function": {"name": "read_file", ...}})
        {'type': 'function', 'function': {'name': 'read_file', ..., 'effects': ['FS']}}
    """
    if "function" in openai_tool:
        fn = copy.deepcopy(openai_tool["function"])
    else:
        fn = copy.deepcopy(openai_tool)

    if auto_annotate and "effects" not in fn:
        fn["effects"] = infer_effects(fn.get("name", ""), fn.get("description", ""))

    return {"type": "function", "function": fn}


def from_anthropic_tool(
    anthropic_tool: dict[str, Any],
    *,
    auto_annotate: bool = True,
) -> dict[str, Any]:
    """Convert an Anthropic tool definition to NAIL-annotated OpenAI FC format.

    Anthropic uses ``input_schema``; this converts it back to ``parameters``
    and wraps it in the standard OpenAI ``{"type": "function", "function": {...}}``
    envelope.

    Args:
        anthropic_tool: Anthropic tool dict (``{"name": ..., "input_schema": ...}``).
        auto_annotate:  When ``True`` (default), infer and attach ``effects``.

    Returns:
        NAIL-annotated OpenAI FC tool dict.

    Example:
        >>> from_anthropic_tool({"name": "read_file", "description": "...", "input_schema": {...}})
        {'type': 'function', 'function': {'name': 'read_file', ..., 'effects': ['FS']}}
    """
    name = anthropic_tool.get("name", "")
    desc = anthropic_tool.get("description", "")
    schema = copy.deepcopy(anthropic_tool.get("input_schema") or {})

    fn: dict[str, Any] = {
        "name": name,
        "description": desc,
        "parameters": schema,
    }

    if auto_annotate:
        fn["effects"] = infer_effects(name, desc)

    return {"type": "function", "function": fn}


def from_gemini_tool(
    gemini_tool: dict[str, Any],
    *,
    auto_annotate: bool = True,
) -> dict[str, Any]:
    """Convert a Gemini tool definition to NAIL-annotated OpenAI FC format.

    Gemini uses a flat dict with ``parameters`` (JSON Schema); this wraps it
    in the OpenAI ``{"type": "function", "function": {...}}`` envelope.

    Args:
        gemini_tool:   Gemini tool dict (``{"name": ..., "parameters": ...}``).
        auto_annotate: When ``True`` (default), infer and attach ``effects``.

    Returns:
        NAIL-annotated OpenAI FC tool dict.

    Example:
        >>> from_gemini_tool({"name": "read_file", "description": "...", "parameters": {...}})
        {'type': 'function', 'function': {'name': 'read_file', ..., 'effects': ['FS']}}
    """
    name = gemini_tool.get("name", "")
    desc = gemini_tool.get("description", "")
    schema = copy.deepcopy(gemini_tool.get("parameters") or {})

    fn: dict[str, Any] = {
        "name": name,
        "description": desc,
        "parameters": schema,
    }

    if auto_annotate:
        fn["effects"] = infer_effects(name, desc)

    return {"type": "function", "function": fn}


# ── Batch conversion utility ──────────────────────────────────────────────────

_SOURCE_FROM: dict[str, Any] = {
    "nail": from_openai_tool,     # nail → nail-annotated (no-op, normalise only)
    "openai": from_openai_tool,
    "anthropic": from_anthropic_tool,
    "gemini": from_gemini_tool,
}

_TARGET_TO: dict[str, Any] = {
    "nail": None,          # keep NAIL format (no stripping)
    "openai": to_openai_tool,
    "anthropic": to_anthropic_tool,
    "gemini": to_gemini_tool,
}


def convert_tools(
    tools: list[dict[str, Any]],
    *,
    target: str = "openai",
    source: str = "nail",
    auto_annotate: bool = True,
) -> list[dict[str, Any]]:
    """Batch-convert a list of tool definitions between provider formats.

    Supports ``source``/``target`` values: ``"nail"``, ``"openai"``,
    ``"anthropic"``, ``"gemini"``.

    When ``source == "nail"`` (the default), tools are assumed to already be in
    NAIL's internal OpenAI FC format (with or without ``effects``).

    When ``target == "nail"``, output retains NAIL annotations (useful for
    enriching tools from an external provider and storing them internally).

    Args:
        tools:         List of tool dicts in ``source`` format.
        target:        Desired output format.  One of ``"nail"``, ``"openai"``,
                       ``"anthropic"``, ``"gemini"``.
        source:        Input format.  One of ``"nail"``, ``"openai"``,
                       ``"anthropic"``, ``"gemini"``.
        auto_annotate: Passed to the ``from_*`` function; controls whether
                       effect labels are inferred.

    Returns:
        List of converted tool dicts.

    Raises:
        ValueError: If ``source`` or ``target`` is not a recognised format.

    Example:
        >>> nail_tools = [{"type": "function", "function": {"name": "read_file", ...}}]
        >>> convert_tools(nail_tools, target="anthropic")
        [{'name': 'read_file', 'description': '...', 'input_schema': {...}}]

        >>> anthropic_tools = [{"name": "search", "description": "...", "input_schema": {...}}]
        >>> convert_tools(anthropic_tools, source="anthropic", target="gemini")
        [{'name': 'search', 'description': '...', 'parameters': {...}}]
    """
    target_key = target.lower()
    source_key = source.lower()

    if source_key not in _SOURCE_FROM:
        raise ValueError(
            f"Unknown source format {source!r}. "
            f"Valid options: {sorted(_SOURCE_FROM)}"
        )
    if target_key not in _TARGET_TO:
        raise ValueError(
            f"Unknown target format {target!r}. "
            f"Valid options: {sorted(_TARGET_TO)}"
        )

    from_fn = _SOURCE_FROM[source_key]
    to_fn = _TARGET_TO[target_key]

    result = []
    for tool in tools:
        # Step 1: normalise to NAIL internal format
        nail_tool = from_fn(tool, auto_annotate=auto_annotate)

        # Step 2: convert to target format
        if to_fn is None:
            # target == "nail": keep internal representation
            result.append(nail_tool)
        else:
            result.append(to_fn(nail_tool))

    return result
