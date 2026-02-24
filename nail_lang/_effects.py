"""Effect filtering utilities for NAIL × Function Calling integration.

This module implements the effect-safe tool routing primitives described in:
  docs/fc-standard-proposal.md
  integrations/litellm.md

The key concept: every tool in an AI agent system should declare which
side effects it may invoke (FS, NET, IO, …). Before passing tools to an
LLM, filter them to only those whose effect set is contained within the
caller's authorized effect scope.
"""

from __future__ import annotations

from typing import Any


# Valid NAIL effect labels (matches interpreter/types.py VALID_EFFECTS + PROC)
VALID_EFFECTS: frozenset[str] = frozenset({"IO", "FS", "NET", "TIME", "RAND", "MUT", "PROC"})


def filter_by_effects(
    tools: list[dict[str, Any]],
    allowed: list[str] | set[str] | frozenset[str],
    *,
    include_unannotated: bool = False,
) -> list[dict[str, Any]]:
    """Filter OpenAI-format tool definitions to only those within an effect scope.

    Args:
        tools:
            List of OpenAI-format tool objects. Each tool dict should look like::

                {
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "description": "...",
                        "parameters": {...},
                        "effects": ["FS"]   ← NAIL extension
                    }
                }

            The ``"effects"`` key in ``function`` is the NAIL extension.
            It lists which NAIL effect kinds the tool may invoke.

        allowed:
            The set of permitted effect kinds for the current execution
            context.  Any tool that requires an effect outside this set
            is excluded.  Example: ``["FS", "IO"]`` permits filesystem
            access and console output but blocks network and process
            execution.

        include_unannotated:
            When ``False`` (default, **recommended for production**): tools
            without an ``"effects"`` annotation are treated as having
            *unrestricted* effects and are **excluded**.

            When ``True``: unannotated tools are treated as having *no*
            side effects (pure) and are **included**. Only appropriate in
            development / permissive environments.

    Returns:
        A new list containing only the tools whose declared effect set is
        a subset of ``allowed``.  The original tool dicts are not copied
        (the same dict objects are returned).

    Raises:
        TypeError: If ``tools`` is not a list or ``allowed`` is not iterable.
        ValueError: If any value in ``allowed`` is not a string.

    Examples:
        >>> tools = [
        ...     {"type": "function", "function": {"name": "read_file",  "effects": ["FS"]}},
        ...     {"type": "function", "function": {"name": "http_get",   "effects": ["NET"]}},
        ...     {"type": "function", "function": {"name": "log",        "effects": ["IO"]}},
        ...     {"type": "function", "function": {"name": "no_effects"               }},
        ... ]
        >>> filter_by_effects(tools, allowed=["FS", "IO"])
        [read_file_tool, log_tool]
        # http_get excluded (NET not in allowed)
        # no_effects excluded (unannotated → unrestricted by default)

        >>> filter_by_effects(tools, allowed=["FS", "IO"], include_unannotated=True)
        [read_file_tool, log_tool, no_effects_tool]
        # no_effects included when include_unannotated=True
    """
    if not isinstance(tools, list):
        raise TypeError(f"tools must be a list, got {type(tools).__name__}")

    allowed_set: frozenset[str] = _coerce_allowed(allowed)
    result: list[dict[str, Any]] = []

    for tool in tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function", {})
        if not isinstance(fn, dict):
            continue

        effects_raw = fn.get("effects")

        if effects_raw is None:
            # No effects annotation
            if include_unannotated:
                result.append(tool)
            # else: excluded (unrestricted / unknown)
            continue

        if not isinstance(effects_raw, list):
            # Malformed annotation — exclude conservatively
            continue

        tool_effects = frozenset(str(e) for e in effects_raw)

        # Include only if all of the tool's effects are permitted
        if tool_effects.issubset(allowed_set):
            result.append(tool)

    return result


def get_tool_effects(tool: dict[str, Any]) -> frozenset[str] | None:
    """Extract the declared effects from a single tool definition.

    Returns ``None`` if the tool has no ``"effects"`` annotation.

    Args:
        tool: An OpenAI-format tool dict.

    Returns:
        A frozenset of effect kind strings, or ``None`` if unannotated.

    Example:
        >>> get_tool_effects({"type": "function", "function": {"name": "r", "effects": ["FS", "IO"]}})
        frozenset({'FS', 'IO'})
        >>> get_tool_effects({"type": "function", "function": {"name": "no_ann"}})
        None
    """
    fn = tool.get("function", {})
    if not isinstance(fn, dict):
        return None
    raw = fn.get("effects")
    if raw is None:
        return None
    if not isinstance(raw, list):
        return None
    return frozenset(str(e) for e in raw)


def annotate_tool_effects(
    tool: dict[str, Any],
    effects: list[str] | set[str],
) -> dict[str, Any]:
    """Return a copy of *tool* with an ``"effects"`` annotation applied.

    Does not mutate the original dict.

    Args:
        tool: An OpenAI-format tool dict.
        effects: The effect labels to annotate (e.g. ``["FS", "IO"]``).

    Returns:
        A new dict with ``tool["function"]["effects"]`` set.

    Example:
        >>> annotated = annotate_tool_effects(my_tool, ["NET"])
        >>> annotated["function"]["effects"]
        ['NET']
    """
    import copy
    result = copy.deepcopy(tool)
    result.setdefault("function", {})["effects"] = list(effects)
    return result


def validate_effects(effects: list[str]) -> list[str]:
    """Validate a list of effect kind strings against the NAIL effect vocabulary.

    Args:
        effects: List of effect label strings to validate.

    Returns:
        The same list if all labels are valid.

    Raises:
        ValueError: If any label is not a recognised NAIL effect kind.

    Example:
        >>> validate_effects(["IO", "FS"])
        ['IO', 'FS']
        >>> validate_effects(["IO", "MAGIC"])
        ValueError: Unknown effect 'MAGIC'. Valid effects: {'FS', 'IO', ...}
    """
    for e in effects:
        if e not in VALID_EFFECTS:
            raise ValueError(
                f"Unknown effect '{e}'. Valid effects: {sorted(VALID_EFFECTS)}"
            )
    return effects


def _coerce_allowed(allowed: Any) -> frozenset[str]:
    """Internal: normalise the *allowed* parameter to frozenset[str]."""
    if isinstance(allowed, frozenset):
        return allowed
    try:
        result = frozenset(allowed)
    except TypeError:
        raise TypeError(f"allowed must be iterable, got {type(allowed).__name__}")
    for item in result:
        if not isinstance(item, str):
            raise ValueError(f"Each allowed effect must be a string, got {type(item).__name__}: {item!r}")
    return result
