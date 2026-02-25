"""
Type stubs for the ``nail_lang`` public API.

These stubs enable IDE auto-complete and mypy / pyright type-checking for
code that imports from ``nail_lang``.

Public API re-exports (mirrors ``nail_lang/__init__.py``):

Core
----
Checker, CheckError, Runtime

Type system
-----------
NailType, NailTypeError, NailEffectError, NailRuntimeError
parse_type, substitute_type, unify_types, TypeParam
IntType, FloatType, BoolType, StringType, UnitType
OptionType, ListType, MapType, ResultType, EnumType

Effect filtering (LiteLLM / OpenAI FC integration)
---------------------------------------------------
filter_by_effects, get_tool_effects, annotate_tool_effects
validate_effects, VALID_EFFECTS

MCP bridge
----------
from_mcp, to_mcp, infer_effects

FC Standard (multi-provider conversions)
-----------------------------------------
to_openai_tool, to_anthropic_tool, to_gemini_tool
from_openai_tool, from_anthropic_tool, from_gemini_tool
convert_tools
"""

from __future__ import annotations

from typing import Any, Literal, Union, overload

# ---------------------------------------------------------------------------
# Re-exported version
# ---------------------------------------------------------------------------

__version__: str

# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class NailTypeError(Exception):
    """Raised when a type error is detected during L1 checking."""
    def to_json(self) -> dict[str, Any]: ...

class NailEffectError(Exception):
    """Raised when an effect violation is detected during L2 checking."""
    def to_json(self) -> dict[str, Any]: ...

class NailRuntimeError(Exception):
    """Raised when a runtime error occurs during NAIL program execution."""
    ...

class CheckError(Exception):
    """Structured check-time error with JSON representation.

    Attributes:
        message: Human-readable error description.
        code: Machine-readable error code (e.g. ``"EFFECT_VIOLATION"``).
        location: Dict with location context (e.g. ``{"fn": "main"}``).
    """
    message: str
    code: str
    location: dict[str, Any]

    def __init__(
        self,
        message: str,
        code: str = ...,
        location: dict[str, Any] | None = ...,
        **extra: Any,
    ) -> None: ...

    def to_json(self) -> dict[str, Any]:
        """Return a machine-parseable representation of this error."""
        ...

# ---------------------------------------------------------------------------
# Type system
# ---------------------------------------------------------------------------

class NailType:
    """Abstract base for all NAIL types."""
    ...

class IntType(NailType):
    bits: int
    overflow: Literal["panic", "wrap", "sat"]
    def __init__(self, bits: int = ..., overflow: str = ...) -> None: ...

class FloatType(NailType):
    bits: int
    def __init__(self, bits: int = ...) -> None: ...

class BoolType(NailType): ...
class StringType(NailType): ...
class UnitType(NailType): ...

class OptionType(NailType):
    inner: NailType
    def __init__(self, inner: NailType) -> None: ...

class ListType(NailType):
    inner: NailType
    length: str
    def __init__(self, inner: NailType, length: str = ...) -> None: ...

class MapType(NailType):
    key: NailType
    value: NailType
    def __init__(self, key: NailType, value: NailType) -> None: ...

class ResultType(NailType):
    ok: NailType
    err: NailType
    def __init__(self, ok: NailType, err: NailType) -> None: ...

class EnumType(NailType):
    name: str
    variants: list[Any]
    def __init__(self, name: str, variants: list[Any]) -> None: ...

class TypeParam(NailType):
    name: str
    def __init__(self, name: str) -> None: ...

def parse_type(
    spec: dict[str, Any],
    type_params: frozenset[str] | None = ...,
) -> NailType:
    """Parse a NAIL type spec dict into a ``NailType`` object.

    Args:
        spec: A type descriptor dict, e.g. ``{"type": "int", "bits": 64, "overflow": "panic"}``.
        type_params: Optional set of in-scope generic type parameter names.

    Returns:
        The corresponding ``NailType`` instance.

    Raises:
        NailTypeError: If the spec is not a recognised type.
    """
    ...

def substitute_type(t: NailType, subst: dict[str, NailType]) -> NailType:
    """Apply a type substitution to *t*, replacing ``TypeParam`` nodes.

    Args:
        t: A ``NailType`` that may contain ``TypeParam`` nodes.
        subst: Mapping from type-parameter names to concrete types.

    Returns:
        A new ``NailType`` with all ``TypeParam`` nodes replaced.
    """
    ...

def unify_types(
    pattern: NailType,
    concrete: NailType,
    subst: dict[str, NailType],
) -> None:
    """Unify *pattern* against *concrete*, building a type substitution.

    Modifies *subst* in-place.  Used for generic function instantiation.

    Raises:
        NailTypeError: If the types cannot be unified.
    """
    ...

# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------

class Checker:
    """NAIL program verifier.

    Runs L0 (schema), L1 (type), L2 (effect) and optionally L3
    (termination) checks on a NAIL program spec.

    Args:
        spec: A parsed NAIL program dict (``json.load(...)``).
        raw_text: Original file content, used by ``--strict`` canonical check.
        strict: If ``True``, reject non-canonical JSON form.
        modules: Dict of ``{module_id: module_spec}`` for cross-module imports.
        level: Verification level — 1 (schema), 2 (type+effect), 3 (termination).
        source_path: Path to the source file; used to resolve relative ``"from"``
            import paths.

    Example::

        from nail_lang import Checker, CheckError

        spec = json.loads(open("my_program.nail").read())
        checker = Checker(spec, level=3)
        try:
            checker.check()
        except CheckError as e:
            print(e.to_json())
    """

    def __init__(
        self,
        spec: dict[str, Any],
        raw_text: str | None = ...,
        strict: bool = ...,
        modules: dict[str, dict[str, Any]] | None = ...,
        level: int = ...,
        source_path: str | None = ...,
    ) -> None: ...

    def check(self) -> None:
        """Run all verification checks up to ``self.level``.

        Raises:
            CheckError: On L0 schema violations.
            NailTypeError: On L1 type errors.
            NailEffectError: On L2 effect violations.
        """
        ...

    def get_termination_certificate(self) -> dict[str, Any]:
        """Return the L3 termination proof certificate.

        Must be called after a successful ``check()`` with ``level=3``.

        Returns:
            A dict with keys:

            * ``level`` (int): Always 3.
            * ``verdict`` (str): ``"all_loops_terminate"``.
            * ``functions_verified`` (int): Number of functions with proofs.
            * ``proofs`` (dict): Per-function termination proof details.
        """
        ...

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------

class Runtime:
    """NAIL program executor.

    Runs a verified NAIL program spec.

    Args:
        spec: A parsed NAIL program dict (already verified via ``Checker``).
        modules: Dict of ``{module_id: module_spec}`` for cross-module calls.

    Example::

        from nail_lang import Checker, Runtime

        spec = json.loads(open("fibonacci.nail").read())
        Checker(spec).check()
        rt = Runtime(spec)
        result = rt.run_fn("fib", {"n": 10})
        print(result)  # → 55
    """

    def __init__(
        self,
        spec: dict[str, Any],
        modules: dict[str, dict[str, Any]] | None = ...,
    ) -> None: ...

    def run(self, args: dict[str, Any] | None = ...) -> Any:
        """Run a ``kind: "fn"`` program.

        Args:
            args: Parameter name → value dict, or ``None`` for zero-arg functions.

        Returns:
            The function's return value, or ``None`` / ``UNIT`` for unit-returning functions.

        Raises:
            NailRuntimeError: On runtime errors (type mismatch, missing param, etc.).
        """
        ...

    def run_fn(self, fn_id: str, args: dict[str, Any]) -> Any:
        """Call a named function within a ``kind: "module"`` program.

        Args:
            fn_id: The ``"id"`` of the function to call.
            args: Parameter name → value dict.

        Returns:
            The function's return value.

        Raises:
            NailRuntimeError: If the function is not found or a runtime error occurs.
        """
        ...

# ---------------------------------------------------------------------------
# Effect filtering
# ---------------------------------------------------------------------------

VALID_EFFECTS: frozenset[str]
"""The set of recognised NAIL effect kind labels.

Current values: ``IO``, ``FS``, ``NET``, ``TIME``, ``RAND``, ``MUT``, ``PROC``.
"""

def filter_by_effects(
    tools: list[dict[str, Any]],
    allowed: list[str] | set[str] | frozenset[str],
    *,
    include_unannotated: bool = ...,
) -> list[dict[str, Any]]:
    """Filter OpenAI-format tool definitions to only those within an effect scope.

    Args:
        tools: List of OpenAI-format tool objects with NAIL ``"effects"`` annotations.
        allowed: Permitted effect kind labels for the current execution context.
        include_unannotated: If ``True``, include tools with no ``"effects"`` annotation.

    Returns:
        Filtered list of tools whose declared effects are a subset of *allowed*.
    """
    ...

def get_tool_effects(tool: dict[str, Any]) -> frozenset[str] | None:
    """Extract declared effects from a tool definition.

    Returns:
        A frozenset of effect kind strings, or ``None`` if unannotated.
    """
    ...

def annotate_tool_effects(
    tool: dict[str, Any],
    effects: list[str] | set[str],
) -> dict[str, Any]:
    """Return a copy of *tool* with an ``"effects"`` annotation applied.

    Args:
        tool: An OpenAI-format tool dict.
        effects: Effect labels to annotate.

    Returns:
        A new (deep-copied) tool dict with ``tool["function"]["effects"]`` set.
    """
    ...

def validate_effects(effects: list[str]) -> list[str]:
    """Validate a list of effect kind strings.

    Raises:
        ValueError: If any label is not in ``VALID_EFFECTS``.
    """
    ...

# ---------------------------------------------------------------------------
# MCP bridge
# ---------------------------------------------------------------------------

def from_mcp(
    tool: dict[str, Any],
    *,
    effects: list[str] | None = ...,
    infer: bool = ...,
) -> dict[str, Any]:
    """Convert an MCP tool definition to NAIL FC-Standard format.

    Args:
        tool: An MCP tool dict with ``name``, ``description``, and ``inputSchema``.
        effects: Explicit effect list to annotate; overrides inference.
        infer: If ``True`` (default), infer effects from name/description heuristics.

    Returns:
        An OpenAI-format FC-Standard tool dict with NAIL ``"effects"`` annotation.
    """
    ...

def to_mcp(tool: dict[str, Any]) -> dict[str, Any]:
    """Convert a NAIL FC-Standard tool to MCP tool definition format.

    Args:
        tool: An OpenAI-format FC-Standard tool dict.

    Returns:
        An MCP-compatible tool dict.
    """
    ...

def infer_effects(name: str, description: str = ...) -> list[str]:
    """Heuristically infer NAIL effects from a tool's name and description.

    Uses keyword matching.  For production use, prefer explicit effect annotation
    via ``annotate_tool_effects``.

    Args:
        name: Tool function name.
        description: Tool description text.

    Returns:
        List of inferred effect kind strings.
    """
    ...

# ---------------------------------------------------------------------------
# FC Standard — multi-provider conversions
# ---------------------------------------------------------------------------

def to_openai_tool(openai_fc_tool: dict[str, Any]) -> dict[str, Any]:
    """Identity conversion — returns the tool unchanged (OpenAI is the canonical format).

    Args:
        openai_fc_tool: An OpenAI-format FC-Standard tool dict.

    Returns:
        The same dict (no copy is made).
    """
    ...

def to_anthropic_tool(openai_fc_tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI-format FC-Standard tool to Anthropic tool format.

    Args:
        openai_fc_tool: An OpenAI-format FC-Standard tool dict.

    Returns:
        An Anthropic-compatible tool dict.
    """
    ...

def to_gemini_tool(openai_fc_tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI-format FC-Standard tool to Gemini function declaration.

    Args:
        openai_fc_tool: An OpenAI-format FC-Standard tool dict.

    Returns:
        A Gemini-compatible function declaration dict.
    """
    ...

def from_openai_tool(
    openai_tool: dict[str, Any],
    *,
    effects: list[str] | None = ...,
) -> dict[str, Any]:
    """Annotate an OpenAI tool with NAIL effects (returns a copy).

    Args:
        openai_tool: An OpenAI-format tool dict.
        effects: NAIL effect labels to attach.  ``None`` → no annotation.

    Returns:
        A new tool dict with ``"effects"`` annotated.
    """
    ...

def from_anthropic_tool(
    anthropic_tool: dict[str, Any],
    *,
    effects: list[str] | None = ...,
) -> dict[str, Any]:
    """Convert an Anthropic tool definition to OpenAI FC-Standard format.

    Args:
        anthropic_tool: An Anthropic ``tool_use`` tool dict.
        effects: NAIL effect labels to annotate.

    Returns:
        An OpenAI-format FC-Standard tool dict.
    """
    ...

def from_gemini_tool(
    gemini_tool: dict[str, Any],
    *,
    effects: list[str] | None = ...,
) -> dict[str, Any]:
    """Convert a Gemini function declaration to OpenAI FC-Standard format.

    Args:
        gemini_tool: A Gemini ``function_declarations`` item dict.
        effects: NAIL effect labels to annotate.

    Returns:
        An OpenAI-format FC-Standard tool dict.
    """
    ...

def convert_tools(
    tools: list[dict[str, Any]],
    *,
    to: Literal["openai", "anthropic", "gemini"],
    from_: Literal["openai", "anthropic", "gemini"] = ...,
) -> list[dict[str, Any]]:
    """Batch-convert a list of tool definitions between providers.

    Args:
        tools: List of tool dicts in *from_* format.
        to: Target provider format (``"openai"``, ``"anthropic"``, or ``"gemini"``).
        from_: Source provider format.  Default: ``"openai"``.

    Returns:
        List of tool dicts in *to* format.
    """
    ...
