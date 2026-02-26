"""fc_ir_v1 — NAIL Tool-Calling IR Implementation.

Implements the fc_ir_v1 specification as defined in docs/fc-ir-v1.md:
  - Type definitions (TypedDict)
  - Name sanitization (§4)
  - Parser / validator (§3, §8)
  - Canonicalization (§2)
  - NAIL type → JSON Schema conversion (§5)
  - Provider conversions: to_openai, to_anthropic, to_gemini (§7)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

# ── Type definitions ──────────────────────────────────────────────────────────

# These are plain dicts at runtime; TypedDict is for documentation / type checkers.
try:
    from typing import TypedDict

    class EffectsCapabilities(TypedDict, total=False):
        kind: str   # "capabilities"
        allow: list  # list of capability strings

    class ToolDef(TypedDict, total=False):
        id: str
        name: str
        title: str
        doc: str
        effects: Any   # EffectsCapabilities or legacy list
        input: dict
        output: dict
        examples: list
        annotations: dict

    class FcIrV1Root(TypedDict, total=False):
        kind: str    # "fc_ir_v1"
        tools: list  # list of ToolDef
        meta: dict

except ImportError:
    pass  # Python < 3.8 fallback


@dataclass
class Diagnostic:
    """A single diagnostic message from parse/validate."""
    code: str       # e.g. "FC001"
    level: str      # "ERROR" or "WARN"
    message: str
    path: str = ""  # JSON path, e.g. "tools[0].id"


@dataclass
class ParseResult:
    """Result of parse_fc_ir_v1()."""
    ok: bool                          # True if no ERRORs
    root: Optional[dict]              # Parsed root (None if fatal error)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.level == "ERROR"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.level == "WARN"]


# ── Name Sanitization (§4) ────────────────────────────────────────────────────

def sanitize_name(tool_id: str) -> tuple[str, Optional[Diagnostic]]:
    """Sanitize a tool id into a provider-safe name per §4.

    Returns:
        (sanitized_name, diagnostic_or_None)
        If the result is empty, diagnostic is an FC002 ERROR and name is "".
    """
    s = tool_id

    # Step 1: Replace . and - with _
    s = s.replace(".", "_").replace("-", "_")

    # Step 2: Replace characters not in [a-z0-9_] with _
    s = re.sub(r"[^a-z0-9_]", "_", s, flags=re.IGNORECASE)

    # Step 3: Collapse consecutive _ into one
    s = re.sub(r"_+", "_", s)

    # Step 4: Lowercase
    s = s.lower()

    # Step 5: If starts with digit, prepend t_
    if s and s[0].isdigit():
        s = "t_" + s

    # Step 6: Trim trailing _
    s = s.rstrip("_")

    # Step 7: Empty check → FC002 ERROR
    if not s:
        diag = Diagnostic(
            code="FC002",
            level="ERROR",
            message=f"Tool name cannot be empty after sanitization (id={tool_id!r})",
            path="",
        )
        return "", diag

    return s, None


# ── Parser / Validator (§3, §8) ───────────────────────────────────────────────

_KNOWN_TOOL_KEYS = {
    "id", "name", "title", "doc", "effects", "input", "output", "examples", "annotations"
}

_DOC_MIN_LEN = 20  # FC010 threshold


def parse_fc_ir_v1(data: dict) -> ParseResult:
    """Parse and validate an fc_ir_v1 document.

    Returns a ParseResult with diagnostics. ok=True if no ERRORs are present.
    """
    diags: list[Diagnostic] = []

    # ── Root kind check ───────────────────────────────────────────────────────
    if not isinstance(data, dict):
        diags.append(Diagnostic(
            code="FC001",
            level="ERROR",
            message="Root must be a JSON object",
            path="",
        ))
        return ParseResult(ok=False, root=None, diagnostics=diags)

    kind = data.get("kind")
    if kind != "fc_ir_v1":
        diags.append(Diagnostic(
            code="FC001",
            level="ERROR",
            message=f"Expected kind 'fc_ir_v1', got {kind!r}",
            path="kind",
        ))
        return ParseResult(ok=False, root=None, diagnostics=diags)

    tools = data.get("tools", [])
    if not isinstance(tools, list):
        diags.append(Diagnostic(
            code="FC001",
            level="ERROR",
            message="'tools' must be an array",
            path="tools",
        ))
        return ParseResult(ok=False, root=None, diagnostics=diags)

    # ── Per-tool validation ───────────────────────────────────────────────────
    seen_ids: dict[str, int] = {}        # id → first index
    seen_names: dict[str, str] = {}      # name → first tool id

    for i, tool in enumerate(tools):
        base_path = f"tools[{i}]"

        if not isinstance(tool, dict):
            diags.append(Diagnostic(
                code="FC001",
                level="ERROR",
                message=f"Tool at index {i} is not an object",
                path=base_path,
            ))
            continue

        # ── Required fields ────────────────────────────────────────────────
        tool_id = tool.get("id")
        if not tool_id:
            diags.append(Diagnostic(
                code="FC001",
                level="ERROR",
                message=f"Tool at index {i}: missing required field 'id'",
                path=f"{base_path}.id",
            ))
            tool_id = f"<unknown[{i}]>"  # placeholder for further checks

        for req_field in ("doc", "effects", "input"):
            if req_field not in tool:
                diags.append(Diagnostic(
                    code="FC001",
                    level="ERROR",
                    message=f"Tool '{tool_id}': missing required field '{req_field}'",
                    path=f"{base_path}.{req_field}",
                ))

        # ── id duplicate check (FC001) ─────────────────────────────────────
        if tool_id and not tool_id.startswith("<unknown"):
            if tool_id in seen_ids:
                diags.append(Diagnostic(
                    code="FC001",
                    level="ERROR",
                    message=f"Duplicate tool id: '{tool_id}'",
                    path=f"{base_path}.id",
                ))
            else:
                seen_ids[tool_id] = i

        # ── Name sanitization / collision check (FC002) ───────────────────
        explicit_name = tool.get("name")
        if explicit_name:
            resolved_name = explicit_name
        else:
            resolved_name, san_diag = sanitize_name(tool_id or "")
            if san_diag:
                san_diag.path = f"{base_path}.id"
                diags.append(san_diag)
                resolved_name = ""

        if resolved_name:
            if resolved_name in seen_names:
                first_id = seen_names[resolved_name]
                diags.append(Diagnostic(
                    code="FC002",
                    level="ERROR",
                    message=(
                        f"Name collision: tools '{first_id}' and '{tool_id}' "
                        f"both generate name '{resolved_name}'. "
                        f"Specify 'name' explicitly."
                    ),
                    path=f"{base_path}.name",
                ))
            else:
                seen_names[resolved_name] = tool_id

        # ── input.type must be object (FC003) ─────────────────────────────
        inp = tool.get("input")
        if inp is not None:
            if not isinstance(inp, dict) or inp.get("type") != "object":
                diags.append(Diagnostic(
                    code="FC003",
                    level="ERROR",
                    message=(
                        f"Tool '{tool_id}': 'input' must be of type object, "
                        f"got '{inp.get('type') if isinstance(inp, dict) else type(inp).__name__}'"
                    ),
                    path=f"{base_path}.input",
                ))

        # ── output missing (FC006 WARN) ────────────────────────────────────
        if "output" not in tool:
            diags.append(Diagnostic(
                code="FC006",
                level="WARN",
                message=f"Tool '{tool_id}': output type not declared — verification coverage is reduced",
                path=base_path,
            ))

        # ── effects: legacy format (FC009 WARN) ───────────────────────────
        effects = tool.get("effects")
        if effects is not None and isinstance(effects, list):
            diags.append(Diagnostic(
                code="FC009",
                level="WARN",
                message=(
                    f"Tool '{tool_id}': effects uses legacy string array format; "
                    f"run 'nail fc canonicalize' to normalize"
                ),
                path=f"{base_path}.effects",
            ))

        # ── doc too short (FC010 WARN) ─────────────────────────────────────
        doc = tool.get("doc", "")
        if isinstance(doc, str) and len(doc) < _DOC_MIN_LEN:
            diags.append(Diagnostic(
                code="FC010",
                level="WARN",
                message=f"Tool '{tool_id}': doc is too short (<{_DOC_MIN_LEN} chars); LLM guidance may be insufficient",
                path=f"{base_path}.doc",
            ))

        # ── Unknown keys (FC011 WARN) ──────────────────────────────────────
        unknown_keys = set(tool.keys()) - _KNOWN_TOOL_KEYS
        for uk in sorted(unknown_keys):
            diags.append(Diagnostic(
                code="FC011",
                level="WARN",
                message=f"Unknown key '{uk}' in ToolDef '{tool_id}'. Consider moving to 'annotations'.",
                path=f"{base_path}.{uk}",
            ))

    has_errors = any(d.level == "ERROR" for d in diags)
    return ParseResult(ok=not has_errors, root=data if not has_errors else None, diagnostics=diags)


# ── Canonicalization (§2) ─────────────────────────────────────────────────────

_ROOT_KEY_ORDER = ["kind", "tools", "meta"]
_TOOL_KEY_ORDER = ["id", "name", "title", "doc", "effects", "input", "output", "examples", "annotations"]


def _normalize_effects(effects: Any) -> Any:
    """Convert legacy effects list to capabilities format."""
    if isinstance(effects, list):
        return {"kind": "capabilities", "allow": effects}
    return effects


def _ordered_tool(tool: dict) -> dict:
    """Return a new dict with keys in canonical ToolDef order."""
    result: dict = {}

    # Known keys in order
    for k in _TOOL_KEY_ORDER:
        if k in tool:
            if k == "effects":
                result[k] = _normalize_effects(tool[k])
            else:
                result[k] = tool[k]

    # Unknown keys: append alphabetically
    unknown_keys = sorted(set(tool.keys()) - set(_TOOL_KEY_ORDER))
    for k in unknown_keys:
        result[k] = tool[k]

    return result


def _ordered_root(data: dict) -> dict:
    """Return a new dict with keys in canonical root order."""
    result: dict = {}

    for k in _ROOT_KEY_ORDER:
        if k in data:
            if k == "tools":
                result[k] = [_ordered_tool(t) for t in data[k]]
            else:
                result[k] = data[k]

    # Unknown root keys: append alphabetically
    unknown_keys = sorted(set(data.keys()) - set(_ROOT_KEY_ORDER))
    for k in unknown_keys:
        result[k] = data[k]

    return result


def canonicalize(data: dict) -> str:
    """Return the canonical compact JSON string for an fc_ir_v1 document.

    - Root key order: kind → tools → meta
    - ToolDef key order: id → name → title → doc → effects → input → output → examples → annotations
    - Legacy effects converted to capabilities format
    - Compact JSON (no spaces), ensure_ascii=False
    - Unknown keys placed after known keys, sorted alphabetically
    """
    ordered = _ordered_root(data)
    return json.dumps(ordered, separators=(",", ":"), ensure_ascii=False)


# ── Type Conversion: NAIL → JSON Schema (§5) ──────────────────────────────────

def _nail_type_to_schema(nail_type: dict) -> tuple[dict, list[str]]:
    """Convert a NAIL type definition to JSON Schema.

    Returns:
        (json_schema, lossy_fields)
    """
    if not isinstance(nail_type, dict):
        return {}, []

    t = nail_type.get("type", "")
    lossy: list[str] = []

    if t == "bool":
        return {"type": "boolean"}, lossy

    elif t == "int":
        schema: dict = {"type": "integer"}
        if "bits" in nail_type:
            lossy.append("int.bits")
        if "overflow" in nail_type:
            lossy.append("int.overflow")
        return schema, lossy

    elif t == "float":
        return {"type": "number"}, lossy

    elif t == "string":
        return {"type": "string"}, lossy

    elif t == "enum":
        values = nail_type.get("values", [])
        return {"type": "string", "enum": values}, lossy

    elif t == "array":
        items_type = nail_type.get("items", {})
        items_schema, items_lossy = _nail_type_to_schema(items_type)
        lossy.extend(items_lossy)
        return {"type": "array", "items": items_schema}, lossy

    elif t == "optional":
        inner = nail_type.get("inner", {})
        inner_schema, inner_lossy = _nail_type_to_schema(inner)
        lossy.extend(inner_lossy)
        # optional means: use inner schema, but exclude from required
        # We attach a sentinel so callers can handle required exclusion
        inner_schema["__optional__"] = True
        return inner_schema, lossy

    elif t == "object":
        properties = nail_type.get("properties", {})
        required_list = nail_type.get("required", [])

        converted_props: dict = {}
        final_required: list[str] = []

        for prop_name, prop_type in properties.items():
            prop_schema, prop_lossy = _nail_type_to_schema(prop_type)
            lossy.extend(prop_lossy)

            is_optional = prop_schema.pop("__optional__", False)

            converted_props[prop_name] = prop_schema

            # A field is required if it was in the original required list
            # AND it is not optional
            if prop_name in required_list and not is_optional:
                final_required.append(prop_name)

        result: dict = {"type": "object", "properties": converted_props}
        if final_required:
            result["required"] = final_required
        return result, lossy

    else:
        # Unknown type — pass through as-is
        return dict(nail_type), lossy


def _convert_input_to_schema(nail_input: dict) -> tuple[dict, list[str]]:
    """Convert a NAIL input (must be type=object) to JSON Schema for providers."""
    schema, lossy = _nail_type_to_schema(nail_input)
    # Clean up any stray __optional__ sentinel at top level
    schema.pop("__optional__", None)
    return schema, lossy


def _get_tool_name(tool: dict) -> str:
    """Get the resolved provider-safe name for a tool."""
    if "name" in tool:
        return tool["name"]
    tool_id = tool.get("id", "")
    name, _ = sanitize_name(tool_id)
    return name


# ── Provider Conversions (§7) ─────────────────────────────────────────────────

def to_openai(root: dict) -> list[dict]:
    """Convert an fc_ir_v1 root to OpenAI FC array.

    Output format:
        {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    result = []
    for tool in root.get("tools", []):
        name = _get_tool_name(tool)
        doc = tool.get("doc", "")
        nail_input = tool.get("input", {})
        params, _ = _convert_input_to_schema(nail_input)

        fn: dict = {
            "name": name,
            "description": doc,
            "parameters": params,
        }

        # Handle annotations.openai.* — e.g. strict
        annotations = tool.get("annotations", {})
        for k, v in annotations.items():
            if k.startswith("openai."):
                fn[k[len("openai."):]] = v

        result.append({"type": "function", "function": fn})

    return result


def to_anthropic(root: dict) -> list[dict]:
    """Convert an fc_ir_v1 root to Anthropic tools array.

    Output format:
        {"name": ..., "description": ..., "input_schema": {...}}
    """
    result = []
    for tool in root.get("tools", []):
        name = _get_tool_name(tool)
        doc = tool.get("doc", "")
        nail_input = tool.get("input", {})
        params, _ = _convert_input_to_schema(nail_input)

        result.append({
            "name": name,
            "description": doc,
            "input_schema": params,
        })

    return result


def to_gemini(root: dict) -> list[dict]:
    """Convert an fc_ir_v1 root to Gemini tools array.

    Output format:
        {"name": ..., "description": ..., "parameters": {...}}
    """
    result = []
    for tool in root.get("tools", []):
        name = _get_tool_name(tool)
        doc = tool.get("doc", "")
        nail_input = tool.get("input", {})
        params, _ = _convert_input_to_schema(nail_input)

        result.append({
            "name": name,
            "description": doc,
            "parameters": params,
        })

    return result
