"""
NAIL Function Calling Effect Annotations
=========================================

Extends OpenAI / Anthropic Function Calling schemas with NAIL-style effect
declarations.  The ``effects`` field answers the question every sandbox runtime
needs answered: *what does this tool actually do to the world?*

NAIL effect vocabulary (from SPEC.md §3):

    []        — Pure function, zero side effects
    ["IO"]    — Standard I/O (stdin / stdout)
    ["FS"]    — Filesystem access (read or write)
    ["NET"]   — Network access (HTTP, DNS, sockets)
    ["TIME"]  — Current time access
    ["RAND"]  — Random number generation
    ["MUT"]   — Mutable global state

Multiple effects compose freely: ["NET", "IO"], ["FS", "MUT"], etc.

Main API:
    from_openai(schema)            — Parse an OpenAI function schema dict
    from_anthropic(tool)           — Parse an Anthropic tool definition dict
    to_nail_annotated(fn, effects) — Attach NAIL effects to a parsed function
    filter_by_effects(fns, allow)  — Return only functions whose effects are
                                     all within the allowed set
    validate_effects(effects)      — Raise ValueError for unknown effect kinds

See docs/integrations.md for usage examples and rationale.
"""

from __future__ import annotations

from typing import Any, Sequence
from copy import deepcopy

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_EFFECTS: frozenset[str] = frozenset(
    {"IO", "FS", "NET", "TIME", "RAND", "MUT"}
)

# Sentinel for "effects unknown / unrestricted" — tools without an ``effects``
# field are treated as UNKNOWN so policy engines can apply a conservative
# default (e.g. deny, or require explicit annotation).
UNKNOWN = "*"


# ---------------------------------------------------------------------------
# Core data structure
# ---------------------------------------------------------------------------

class NAILFunction:
    """An LLM function / tool definition augmented with NAIL effect metadata.

    Attributes:
        name        Function identifier.
        description Human-readable description string.
        parameters  Parameter schema dict (OpenAI style) or None.
        input_schema  Anthropic-style parameter schema or None.
        effects     List of declared NAIL effect kinds, e.g. ["FS", "NET"].
                    An empty list ``[]`` means *pure* (no side effects).
                    The sentinel ``["*"]`` means *unknown / unrestricted*.
        source      Original schema dict (for round-trip access).
        fmt         Original schema format: "openai" | "anthropic" | "nail".
    """

    def __init__(
        self,
        *,
        name: str,
        description: str = "",
        parameters: dict | None = None,
        input_schema: dict | None = None,
        effects: list[str] | None = None,
        source: dict | None = None,
        fmt: str = "nail",
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.input_schema = input_schema
        # None means "not declared" — distinguishable from [] (pure)
        self.effects: list[str] | None = effects
        self.source = source
        self.fmt = fmt

    # ------------------------------------------------------------------
    # Convenience predicates
    # ------------------------------------------------------------------

    def is_pure(self) -> bool:
        """Return True iff effects are declared as empty (explicitly pure)."""
        return self.effects is not None and len(self.effects) == 0

    def is_unknown(self) -> bool:
        """Return True iff no effects declaration is present."""
        return self.effects is None

    def has_effect(self, kind: str) -> bool:
        """Return True iff *kind* is among the declared effects."""
        if self.effects is None:
            return True  # unknown — conservatively assume yes
        return kind in self.effects

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        eff = self.effects if self.effects is not None else [UNKNOWN]
        return f"NAILFunction(name={self.name!r}, effects={eff!r})"

    def to_dict(self) -> dict[str, Any]:
        """Serialise back to a NAIL-annotated dict (OpenAI schema shape)."""
        out: dict[str, Any] = {"name": self.name}
        if self.description:
            out["description"] = self.description
        out["effects"] = self.effects if self.effects is not None else [UNKNOWN]
        if self.parameters is not None:
            out["parameters"] = deepcopy(self.parameters)
        if self.input_schema is not None:
            out["input_schema"] = deepcopy(self.input_schema)
        return out


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def from_openai(schema: dict[str, Any]) -> NAILFunction:
    """Parse an OpenAI function-calling schema dict into a :class:`NAILFunction`.

    Accepts both the bare function object and the wrapper::

        {"type": "function", "function": {...}}

    If the schema already contains an ``effects`` field it is preserved;
    otherwise ``effects`` is left as ``None`` (unknown).

    Args:
        schema: OpenAI function calling schema.

    Returns:
        A :class:`NAILFunction` instance.

    Raises:
        ValueError: If ``name`` is missing.
    """
    # Unwrap {"type": "function", "function": {...}} envelope
    if schema.get("type") == "function" and "function" in schema:
        schema = schema["function"]

    name = schema.get("name")
    if not name:
        raise ValueError("OpenAI function schema must have a 'name' field")

    raw_effects = schema.get("effects")
    if raw_effects is not None:
        validate_effects(raw_effects)

    return NAILFunction(
        name=name,
        description=schema.get("description", ""),
        parameters=deepcopy(schema.get("parameters")),
        effects=list(raw_effects) if raw_effects is not None else None,
        source=schema,
        fmt="openai",
    )


def from_anthropic(tool: dict[str, Any]) -> NAILFunction:
    """Parse an Anthropic tool definition dict into a :class:`NAILFunction`.

    Anthropic uses ``input_schema`` instead of ``parameters``::

        {
            "name": "read_file",
            "description": "...",
            "input_schema": {"type": "object", "properties": {...}}
        }

    Args:
        tool: Anthropic tool definition dict.

    Returns:
        A :class:`NAILFunction` instance.

    Raises:
        ValueError: If ``name`` is missing.
    """
    name = tool.get("name")
    if not name:
        raise ValueError("Anthropic tool definition must have a 'name' field")

    raw_effects = tool.get("effects")
    if raw_effects is not None:
        validate_effects(raw_effects)

    return NAILFunction(
        name=name,
        description=tool.get("description", ""),
        input_schema=deepcopy(tool.get("input_schema")),
        effects=list(raw_effects) if raw_effects is not None else None,
        source=tool,
        fmt="anthropic",
    )


# ---------------------------------------------------------------------------
# Annotation helpers
# ---------------------------------------------------------------------------

def to_nail_annotated(fn: NAILFunction, effects: list[str]) -> NAILFunction:
    """Return a copy of *fn* with NAIL effect annotations applied.

    Args:
        fn:      The source :class:`NAILFunction` (not mutated).
        effects: List of NAIL effect kinds to declare.
                 Pass ``[]`` to declare the function as *pure*.

    Returns:
        A new :class:`NAILFunction` with the ``effects`` field set.

    Raises:
        ValueError: If any element of *effects* is not a valid NAIL effect.

    Example::

        fn = from_openai({"name": "read_file", "parameters": {...}})
        annotated = to_nail_annotated(fn, ["FS"])
        print(annotated.to_dict())
        # {"name": "read_file", "effects": ["FS"], "parameters": {...}}
    """
    validate_effects(effects)
    return NAILFunction(
        name=fn.name,
        description=fn.description,
        parameters=deepcopy(fn.parameters),
        input_schema=deepcopy(fn.input_schema),
        effects=list(effects),
        source=fn.source,
        fmt=fn.fmt,
    )


# ---------------------------------------------------------------------------
# Policy helpers
# ---------------------------------------------------------------------------

def filter_by_effects(
    functions: Sequence[NAILFunction],
    allowed: Sequence[str],
) -> list[NAILFunction]:
    """Return only functions whose declared effects are all within *allowed*.

    Functions with unknown effects (``effects=None``) are **excluded** by
    default — unknown is treated as potentially unrestricted.

    Args:
        functions: Iterable of :class:`NAILFunction` objects.
        allowed:   Allowed effect kinds, e.g. ``["FS", "IO"]``.

    Returns:
        Filtered list in original order.

    Example::

        tools = [read_file, send_email, pure_calc]
        safe  = filter_by_effects(tools, allowed=["FS"])
        # → [read_file, pure_calc]  (send_email has NET which is not in allowed)
    """
    validate_effects(list(allowed))
    allowed_set = frozenset(allowed)
    result = []
    for fn in functions:
        if fn.effects is None:
            continue  # unknown effects → exclude (conservative)
        if frozenset(fn.effects).issubset(allowed_set):
            result.append(fn)
    return result


def requires_any(fn: NAILFunction, effects: Sequence[str]) -> bool:
    """Return True iff *fn* declares at least one of the given *effects*.

    Useful for quickly checking whether a tool needs a particular capability::

        if requires_any(tool, ["NET"]):
            raise RuntimeError("Network not permitted in sandbox")

    Args:
        fn:      Function to inspect.
        effects: Effect kinds to check for.

    Returns:
        True if any of *effects* appear in ``fn.effects``; False if none do.
        Returns True (conservative) if ``fn.effects`` is None (unknown).
    """
    if fn.effects is None:
        return True  # unknown → conservative: assume yes
    return bool(frozenset(fn.effects) & frozenset(effects))


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_effects(effects: list[str]) -> None:
    """Raise :class:`ValueError` if any entry is not a valid NAIL effect kind.

    Valid kinds: IO, FS, NET, TIME, RAND, MUT

    Args:
        effects: List to validate.

    Raises:
        ValueError: On first invalid effect kind found.
    """
    for e in effects:
        if e not in VALID_EFFECTS:
            raise ValueError(
                f"Unknown NAIL effect kind: {e!r}. "
                f"Valid kinds are: {sorted(VALID_EFFECTS)}"
            )


# ---------------------------------------------------------------------------
# Batch conversion utilities
# ---------------------------------------------------------------------------

def annotate_openai_schema(
    schema: dict[str, Any],
    effects: list[str],
) -> dict[str, Any]:
    """One-shot helper: parse an OpenAI schema and return an annotated dict.

    Equivalent to::

        to_nail_annotated(from_openai(schema), effects).to_dict()

    Args:
        schema:  OpenAI function schema.
        effects: NAIL effects to declare.

    Returns:
        A new dict with the ``effects`` field injected.
    """
    fn = from_openai(schema)
    annotated = to_nail_annotated(fn, effects)
    return annotated.to_dict()


def annotate_openai_tool_list(
    tools: list[dict[str, Any]],
    effect_map: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Annotate a list of OpenAI tool dicts using an *effect_map*.

    Args:
        tools:       List of OpenAI tool schema dicts.
        effect_map:  Mapping from function name to declared effects.
                     Functions not in the map are left with ``effects: ["*"]``.

    Returns:
        New list of annotated dicts (originals not modified).

    Example::

        annotated = annotate_openai_tool_list(tools, {
            "send_email": ["NET", "IO"],
            "read_file":  ["FS"],
            "pure_calc":  [],
        })
    """
    result = []
    for tool in tools:
        fn = from_openai(tool)
        declared = effect_map.get(fn.name)
        if declared is not None:
            fn = to_nail_annotated(fn, declared)
        result.append(fn.to_dict())
    return result
