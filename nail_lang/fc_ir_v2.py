"""fc_ir_v2: Delegation-aware Effect Qualifiers for NAIL (Phase 1).

Implements the Zone of Indifference concept from DeepMind's "Intelligent AI
Delegation" paper as a first-class feature of NAIL's type system.

Reference: Issue #107 — Delegation-aware Effect Qualifiers (Phase 1)

Effect qualifier format
-----------------------
The ``effects.allow`` array inside a function definition accepts two forms:

    # Backward-compatible string form (delegation defaults to "implicit")
    { "allow": ["FS:write_file"] }

    # Extended object form
    { "allow": [{ "op": "FS:write_file", "reversible": false, "delegation": "explicit" }] }

``delegation`` values
~~~~~~~~~~~~~~~~~~~~~
* ``"implicit"`` (default): ordinary delegation — propagates to callees without
  extra friction.
* ``"explicit"``: the caller must list the op in its own ``grants`` field, or
  FC-E010 is raised.

``grants`` field
----------------
An optional list of op strings on a function definition:

    { "op": "def", "name": "save_report",
      "effects": { "allow": [{ "op": "FS:write_file", "delegation": "explicit" }] },
      "grants": ["FS:write_file"],
      "body": [ ... ] }

Type rules (Phase 1)
--------------------
* ``allow`` is the pre-condition (the capability declaration).
* ``grants`` is the additional friction gate.  **Both are required** for a
  function to legally invoke an ``explicit``-delegation op.
* Matching is exact string equality only (wildcards / prefixes are out-of-scope
  for Phase 1).
* ``reversible`` is metadata — it is stored and preserved, but does **not**
  affect type rules in Phase 1.
* Only ``delegation: "explicit"`` triggers type-rule enforcement; ``"implicit"``
  is always propagation-safe.

Error codes
-----------
``FC-E010`` — ``ExplicitDelegationViolation``
    Raised when a callee declares ``delegation: "explicit"`` for an op, but the
    caller does not list that op in its ``grants`` field.

Usage example
-------------
>>> callee_def = {
...     "op": "def", "name": "save_report",
...     "effects": {"allow": [{"op": "FS:write_file", "delegation": "explicit"}]},
...     "grants": ["FS:write_file"],
...     "body": [],
... }
>>> caller_def = {
...     "op": "def", "name": "run_pipeline",
...     "effects": {"allow": ["NET:fetch"]},
...     "grants": [],  # missing FS:write_file → FC-E010
...     "body": [{"op": "call", "fn": "save_report"}],
... }
>>> errors = check_call(caller_def, callee_def)
>>> errors[0].code
'FC-E010'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    # Data types
    "EffectQualifier",
    "FcDef",
    "DelegationError",
    # Parsing
    "parse_effect_qualifier",
    "parse_effects",
    "parse_def",
    # Checking
    "check_call",
    "check_program",
]

# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class DelegationError(Exception):
    """Structured error from fc_ir_v2 delegation checking.

    Attributes:
        message:  Human-readable description.
        code:     Machine-readable error code (e.g. ``"FC-E010"``).
        callee:   Name of the callee function, when applicable.
        op:       The effect op that triggered the error, when applicable.
    """

    def __init__(
        self,
        message: str,
        code: str = "FC_ERROR",
        callee: str | None = None,
        op: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.callee = callee
        self.op = op
        self._extra = kwargs

    def __repr__(self) -> str:  # pragma: no cover
        return f"DelegationError(code={self.code!r}, message={self.message!r})"

    def to_dict(self) -> dict[str, Any]:
        """Return a serialisable representation."""
        result: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.callee is not None:
            result["callee"] = self.callee
        if self.op is not None:
            result["op"] = self.op
        result.update(self._extra)
        return result


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class EffectQualifier:
    """A parsed element from an ``effects.allow`` list.

    Attributes:
        op:           The effect operation identifier (e.g. ``"FS:write_file"``).
        reversible:   Metadata flag — does not affect Phase 1 type rules.
        delegation:   ``"implicit"`` (default) or ``"explicit"``.
    """

    op: str
    reversible: bool = True
    delegation: str = "implicit"  # "implicit" | "explicit"

    def is_explicit(self) -> bool:
        """Return True when this qualifier requires explicit caller grants."""
        return self.delegation == "explicit"


@dataclass
class FcDef:
    """A parsed function definition in the ``op: "def"`` IR format.

    Attributes:
        name:       Function name.
        qualifiers: Parsed effect qualifiers from ``effects.allow``.
        grants:     Ops this function explicitly grants to itself (the friction gate).
        body:       Raw body statements (not interpreted by fc_ir_v2).
    """

    name: str
    qualifiers: list[EffectQualifier] = field(default_factory=list)
    grants: list[str] = field(default_factory=list)
    body: list[Any] = field(default_factory=list)

    # Computed
    def explicit_ops(self) -> set[str]:
        """Return the set of ops that require explicit delegation."""
        return {q.op for q in self.qualifiers if q.is_explicit()}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_effect_qualifier(item: Any) -> EffectQualifier:
    """Parse one element from an ``effects.allow`` list.

    Accepts both the legacy string form and the new object form.

    Args:
        item: A string op identifier, or a dict with ``op``, ``reversible``,
              and ``delegation`` keys.

    Returns:
        ``EffectQualifier`` with parsed fields.

    Raises:
        DelegationError: If ``item`` has an unexpected type or invalid fields.
    """
    if isinstance(item, str):
        if not item:
            raise DelegationError(
                "Effect qualifier string must not be empty",
                code="FC_PARSE_ERROR",
            )
        return EffectQualifier(op=item)

    if isinstance(item, dict):
        op = item.get("op")
        if not isinstance(op, str) or not op:
            raise DelegationError(
                "Effect qualifier object must have a non-empty string field 'op'",
                code="FC_PARSE_ERROR",
            )
        reversible_raw = item.get("reversible", True)
        if not isinstance(reversible_raw, bool):
            raise DelegationError(
                f"Effect qualifier 'reversible' must be a boolean, got {type(reversible_raw).__name__}",
                code="FC_PARSE_ERROR",
                op=op,
            )
        delegation = item.get("delegation", "implicit")
        if delegation not in ("implicit", "explicit"):
            raise DelegationError(
                f"Effect qualifier 'delegation' must be 'implicit' or 'explicit', "
                f"got {delegation!r}",
                code="FC_PARSE_ERROR",
                op=op,
            )
        return EffectQualifier(op=op, reversible=reversible_raw, delegation=delegation)

    raise DelegationError(
        f"Effect qualifier must be a string or object, got {type(item).__name__}",
        code="FC_PARSE_ERROR",
    )


def parse_effects(effects_obj: Any) -> list[EffectQualifier]:
    """Parse the ``effects`` field of a function definition.

    Args:
        effects_obj: Either an object ``{ "allow": [...] }`` or ``None`` / missing.

    Returns:
        List of parsed ``EffectQualifier`` objects (empty list when no effects).

    Raises:
        DelegationError: If the structure is invalid.
    """
    if effects_obj is None:
        return []

    if not isinstance(effects_obj, dict):
        raise DelegationError(
            f"'effects' must be an object with an 'allow' field, got {type(effects_obj).__name__}",
            code="FC_PARSE_ERROR",
        )

    allow = effects_obj.get("allow", [])
    if not isinstance(allow, list):
        raise DelegationError(
            "'effects.allow' must be a list",
            code="FC_PARSE_ERROR",
        )

    return [parse_effect_qualifier(item) for item in allow]


def parse_def(def_obj: Any) -> FcDef:
    """Parse a function definition in the ``op: "def"`` IR format.

    Args:
        def_obj: A dict with at minimum ``{ "op": "def", "name": "..." }``.

    Returns:
        Parsed ``FcDef``.

    Raises:
        DelegationError: If the definition is malformed.
    """
    if not isinstance(def_obj, dict):
        raise DelegationError(
            f"Function definition must be an object, got {type(def_obj).__name__}",
            code="FC_PARSE_ERROR",
        )

    op = def_obj.get("op")
    if op != "def":
        raise DelegationError(
            f"Expected op='def', got {op!r}",
            code="FC_PARSE_ERROR",
        )

    name = def_obj.get("name")
    if not isinstance(name, str) or not name:
        raise DelegationError(
            "Function definition requires a non-empty string field 'name'",
            code="FC_PARSE_ERROR",
        )

    qualifiers = parse_effects(def_obj.get("effects"))

    grants = def_obj.get("grants", [])
    if not isinstance(grants, list):
        raise DelegationError(
            f"[{name}] 'grants' must be a list, got {type(grants).__name__}",
            code="FC_PARSE_ERROR",
        )
    for g in grants:
        if not isinstance(g, str):
            raise DelegationError(
                f"[{name}] All 'grants' items must be strings, got {type(g).__name__}",
                code="FC_PARSE_ERROR",
            )

    body = def_obj.get("body", [])
    if not isinstance(body, list):
        raise DelegationError(
            f"[{name}] 'body' must be a list",
            code="FC_PARSE_ERROR",
        )

    return FcDef(name=name, qualifiers=qualifiers, grants=grants, body=body)


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------


def check_call(
    caller_def: Any,
    callee_def: Any,
) -> list[DelegationError]:
    """Check whether a caller is allowed to invoke a callee.

    Phase 1 rule: for every op in the callee's ``effects.allow`` whose
    ``delegation`` is ``"explicit"``, the caller must list that op in its
    own ``grants`` field.  If any op is missing, FC-E010 is raised.

    Args:
        caller_def: The calling function definition (raw dict or ``FcDef``).
        callee_def: The called function definition (raw dict or ``FcDef``).

    Returns:
        A (possibly empty) list of ``DelegationError`` objects with
        ``code="FC-E010"`` for each violation.
    """
    # Accept both raw dicts and pre-parsed FcDef objects
    if isinstance(caller_def, dict):
        caller = parse_def(caller_def)
    elif isinstance(caller_def, FcDef):
        caller = caller_def
    else:
        raise DelegationError(
            f"caller_def must be a dict or FcDef, got {type(caller_def).__name__}",
            code="FC_PARSE_ERROR",
        )

    if isinstance(callee_def, dict):
        callee = parse_def(callee_def)
    elif isinstance(callee_def, FcDef):
        callee = callee_def
    else:
        raise DelegationError(
            f"callee_def must be a dict or FcDef, got {type(callee_def).__name__}",
            code="FC_PARSE_ERROR",
        )

    caller_grants: set[str] = set(caller.grants)
    explicit_ops = callee.explicit_ops()

    errors: list[DelegationError] = []
    for op in sorted(explicit_ops):
        if op not in caller_grants:
            errors.append(
                DelegationError(
                    f"FC-E010: ExplicitDelegationViolation — "
                    f"callee '{callee.name}' requires explicit delegation for op '{op}', "
                    f"but caller '{caller.name}' does not declare it in 'grants'",
                    code="FC-E010",
                    callee=callee.name,
                    caller=caller.name,
                    op=op,
                )
            )

    return errors


def check_program(defs: list[Any]) -> list[DelegationError]:
    """Check a list of function definitions for delegation violations.

    Scans each function's ``body`` for ``op: "call"`` statements and verifies
    that the caller's ``grants`` cover all ``explicit``-delegation ops of the
    callee.

    Call statement shape (minimal)::

        { "op": "call", "fn": "<callee_name>", ... }

    Args:
        defs: List of raw function definition dicts (``op: "def"`` format).

    Returns:
        A (possibly empty) list of ``DelegationError`` objects.

    Raises:
        DelegationError: If parsing fails (malformed definition).
    """
    # Parse all definitions first
    parsed: dict[str, FcDef] = {}
    parse_errors: list[DelegationError] = []

    for raw_def in defs:
        try:
            fc_def = parse_def(raw_def)
            parsed[fc_def.name] = fc_def
        except DelegationError as exc:
            parse_errors.append(exc)

    if parse_errors:
        return parse_errors

    # Walk each caller's body and check calls against callee signatures
    errors: list[DelegationError] = []
    for caller_name, caller_fc in parsed.items():
        for stmt in caller_fc.body:
            if not isinstance(stmt, dict):
                continue
            if stmt.get("op") != "call":
                continue
            callee_name = stmt.get("fn")
            if not isinstance(callee_name, str) or callee_name not in parsed:
                continue  # unknown callee — not in scope for this check
            callee_fc = parsed[callee_name]
            errors.extend(check_call(caller_fc, callee_fc))

    return errors
