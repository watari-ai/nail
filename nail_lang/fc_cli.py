"""FC CLI: Logic for `nail fc` subcommands.

Provides convert, check, roundtrip, and import operations on NAIL's OpenAI FC format.

Input format:
    A JSON array of tools in NAIL's internal OpenAI FC format, e.g.::

        [
          {
            "type": "function",
            "function": {
              "name": "read_file",
              "description": "Read a file",
              "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
              "effects": ["FS"]
            }
          }
        ]

Exit codes:
    0 — success
    1 — system error (file not found, JSON parse error, etc.)
    2 — check failure (user needs to fix their tool definitions)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from nail_lang._fc_standard import (
    convert_tools,
    from_openai_tool,
    from_anthropic_tool,
    from_gemini_tool,
)

# Allowed primitive types for all providers
_UNIVERSAL_TYPES = {"object", "array", "string", "number", "integer", "boolean"}

# Effects that indicate side effects (non-PURE)
_SIDE_EFFECT_LABELS = {"IO", "NET", "FS"}

# All recognised effect kind labels (used for validation)
VALID_EFFECTS = {"FS", "NET", "PROC", "TIME", "RAND", "IO", "PURE"}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _load_tools(input_path: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Load tools from *input_path*. Returns (tools, error_message)."""
    p = Path(input_path)
    if not p.exists():
        return None, f"File not found: {input_path}"
    try:
        with open(p) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return None, f"JSON parse error in {input_path}: {e}"
    if not isinstance(data, list):
        return None, f"Expected a JSON array of tools, got {type(data).__name__}"
    return data, None


def _collect_schema_types(schema: dict[str, Any], found: set[str] | None = None) -> set[str]:
    """Recursively collect all 'type' values from a JSON Schema."""
    if found is None:
        found = set()
    if not isinstance(schema, dict):
        return found
    t = schema.get("type")
    if isinstance(t, str):
        found.add(t)
    elif isinstance(t, list):
        found.update(t)
    for key in ("properties", "items", "additionalProperties"):
        val = schema.get(key)
        if isinstance(val, dict):
            for v in val.values():
                if isinstance(v, dict):
                    _collect_schema_types(v, found)
    for key in ("allOf", "anyOf", "oneOf"):
        for sub in schema.get(key) or []:
            _collect_schema_types(sub, found)
    return found


# ── Public functions ──────────────────────────────────────────────────────────


def fc_convert(input_path: str, provider: str, out: str | None, fmt: str) -> int:
    """Convert NAIL tools to provider format.

    Args:
        input_path: Path to the input .nail (JSON) file.
        provider:   Target provider: "openai", "anthropic", or "gemini".
        out:        Output file path, or None to print to stdout.
        fmt:        Output format: "human" or "json".

    Returns:
        0 on success, 1 on system error.
    """
    tools, err = _load_tools(input_path)
    if err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    try:
        converted = convert_tools(tools, target=provider, source="nail")
    except ValueError as e:
        print(f"✗ Conversion error: {e}", file=sys.stderr)
        return 1

    output = json.dumps(converted, indent=2, ensure_ascii=False)

    if out:
        try:
            Path(out).write_text(output + "\n", encoding="utf-8")
            if fmt == "human":
                print(f"✓ Converted {len(converted)} tool(s) → {provider}  →  {out}")
        except OSError as e:
            print(f"✗ Cannot write output file: {e}", file=sys.stderr)
            return 1
    else:
        print(output)

    return 0


def fc_check(
    input_path: str,
    provider: str,
    strict_provider: bool,
    fmt: str,
    strict: bool,
) -> int:
    """Check NAIL tools for validity and provider compatibility.

    Checks performed (MVP):
    - Tool name uniqueness (duplicate names → error)
    - Input schema type compatibility with the target provider
      (non-universal types → warning; with ``--strict-provider`` → error)
    - Effects consistency: a PURE tool (no effects / empty list) must not
      declare side-effect labels (IO/NET/FS) → error
    - With ``--strict``: canonical JSON check (keys must be sorted)

    Args:
        input_path:      Path to the input .nail (JSON) file.
        provider:        Target provider: "openai", "anthropic", or "gemini".
        strict_provider: Treat non-universal types as errors instead of warnings.
        fmt:             Output format: "human" or "json".
        strict:          Enable strict/canonical checks.

    Returns:
        0 on success, 1 on system error, 2 on check failure.
    """
    p = Path(input_path)
    if not p.exists():
        msg = f"File not found: {input_path}"
        if fmt == "json":
            print(json.dumps({"ok": False, "errors": [msg], "warnings": []}))
        else:
            print(f"✗ {msg}", file=sys.stderr)
        return 1

    try:
        raw_text = p.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        msg = f"JSON parse error: {e}"
        if fmt == "json":
            print(json.dumps({"ok": False, "errors": [msg], "warnings": []}))
        else:
            print(f"✗ {msg}", file=sys.stderr)
        return 1

    if not isinstance(data, list):
        msg = f"Expected a JSON array of tools, got {type(data).__name__}"
        if fmt == "json":
            print(json.dumps({"ok": False, "errors": [msg], "warnings": []}))
        else:
            print(f"✗ {msg}", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []

    # --- Check 1: Tool name uniqueness ---
    seen_names: dict[str, int] = {}  # name → first occurrence index
    for i, tool in enumerate(data):
        fn = tool.get("function", tool)
        name = fn.get("name", "")
        if not name:
            errors.append(f"Tool[{i}]: missing 'name' field")
            continue
        if name in seen_names:
            errors.append(
                f"Tool[{i}]: duplicate tool name '{name}' "
                f"(also at index {seen_names[name]})"
            )
        else:
            seen_names[name] = i

    # --- Check 2: Schema type compatibility ---
    for i, tool in enumerate(data):
        fn = tool.get("function", tool)
        name = fn.get("name", f"[{i}]")
        params = fn.get("parameters", {})
        if not isinstance(params, dict):
            continue
        found_types = _collect_schema_types(params)
        unknown_types = found_types - _UNIVERSAL_TYPES
        for t in sorted(unknown_types):
            msg = (
                f"Tool '{name}': schema type '{t}' may not be supported by "
                f"provider '{provider}'"
            )
            if strict_provider:
                errors.append(msg)
            else:
                warnings.append(msg)

    # --- Check 3: Effects consistency ---
    for i, tool in enumerate(data):
        fn = tool.get("function", tool)
        name = fn.get("name", f"[{i}]")
        effects = fn.get("effects")
        if effects is None:
            # No effects annotation — PURE by default, nothing to check
            continue
        if not isinstance(effects, list):
            errors.append(f"Tool '{name}': 'effects' must be a list, got {type(effects).__name__}")
            continue
        if len(effects) == 0:
            # Explicitly PURE — safe
            continue
        # Non-empty effects: check for side-effect labels
        side_effects = [e for e in effects if e in _SIDE_EFFECT_LABELS]
        # If there are side effects, this is OK (it's not PURE). But let's also
        # check the inverse: if ALL effects are empty ([]) it's PURE.
        # The spec says: PURE (effects=[]) with IO/NET/FS in effects is an error.
        # Since we just confirmed effects is non-empty, we only error if someone
        # marks a tool as PURE but includes side effects — which can't happen
        # with an empty list. But if someone puts PURE-sentinel + side effects
        # together (e.g. ["PURE", "FS"]), flag that.
        pure_labels = {e for e in effects if e in ("PURE",)}
        if pure_labels and side_effects:
            errors.append(
                f"Tool '{name}': declared as PURE but has side-effect labels: "
                f"{side_effects}"
            )
        # Validate each effect label against VALID_EFFECTS
        for e in effects:
            if e not in VALID_EFFECTS:
                errors.append(
                    f"Tool '{name}': unknown effect label '{e}'. "
                    f"Valid effects: {sorted(VALID_EFFECTS - {'PURE'})}"
                )

    # --- Check 4 (strict): Canonical form ---
    if strict:
        try:
            canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            reparsed = json.loads(canonical)
            canonical_pretty = json.dumps(reparsed, sort_keys=True, indent=2, ensure_ascii=False)
            actual_pretty = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False)
            if canonical_pretty != actual_pretty:
                warnings.append(
                    "File is not in canonical form (keys not sorted). "
                    "Run 'nail canonicalize' to fix."
                )
        except Exception as e:
            warnings.append(f"Canonical check failed: {e}")

    # --- Output ---
    ok = len(errors) == 0
    exit_code = 0 if ok else 2

    if fmt == "json":
        print(json.dumps({"ok": ok, "errors": errors, "warnings": warnings}, indent=2))
    else:
        total = len(data)
        if ok:
            print(f"✓ {input_path}  [{total} tool(s)]  provider={provider}")
        else:
            print(f"✗ {input_path}  [{total} tool(s)]  provider={provider}")
        for e in errors:
            print(f"  ERROR:   {e}")
        for w in warnings:
            print(f"  WARNING: {w}")
        if ok and not warnings:
            print(f"  All checks passed.")
        elif ok and warnings:
            print(f"  Passed with {len(warnings)} warning(s).")

    return exit_code


def fc_roundtrip(input_path: str, provider: str, fmt: str) -> int:
    """Convert NAIL → provider → NAIL and show any information loss.

    Args:
        input_path: Path to the input .nail (JSON) file.
        provider:   Intermediate provider: "openai", "anthropic", or "gemini".
        fmt:        Output format: "human" or "json".

    Returns:
        0 if roundtrip is lossless, 1 on system error, 2 if information was lost.
    """
    tools, err = _load_tools(input_path)
    if err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    try:
        # Step 1: NAIL → provider
        provider_tools = convert_tools(tools, target=provider, source="nail")
        # Step 2: provider → NAIL
        roundtripped = convert_tools(provider_tools, target="nail", source=provider)
    except ValueError as e:
        print(f"✗ Conversion error: {e}", file=sys.stderr)
        return 1

    # Compare original and roundtripped (normalise originals first)
    original_normalised = convert_tools(tools, target="nail", source="nail")

    diffs: list[dict[str, Any]] = []
    for i, (orig, rt) in enumerate(zip(original_normalised, roundtripped)):
        orig_fn = orig.get("function", orig)
        rt_fn = rt.get("function", rt)
        name = orig_fn.get("name", f"[{i}]")

        orig_json = json.dumps(orig_fn, sort_keys=True, ensure_ascii=False)
        rt_json = json.dumps(rt_fn, sort_keys=True, ensure_ascii=False)

        if orig_json != rt_json:
            # Compute field-level diff
            field_diffs = []
            all_keys = set(orig_fn) | set(rt_fn)
            for k in sorted(all_keys):
                ov = orig_fn.get(k)
                rv = rt_fn.get(k)
                if ov != rv:
                    field_diffs.append({"field": k, "original": ov, "roundtripped": rv})
            diffs.append({"tool": name, "diffs": field_diffs})

    has_loss = len(diffs) > 0
    exit_code = 2 if has_loss else 0

    if fmt == "json":
        print(
            json.dumps(
                {
                    "ok": not has_loss,
                    "provider": provider,
                    "total": len(tools),
                    "lossless": len(tools) - len(diffs),
                    "loss_detected": len(diffs),
                    "diffs": diffs,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        total = len(tools)
        if not has_loss:
            print(
                f"✓ Roundtrip lossless  [{total} tool(s)]  "
                f"NAIL → {provider} → NAIL"
            )
        else:
            print(
                f"✗ Roundtrip detected {len(diffs)} difference(s) in "
                f"{total} tool(s)  NAIL → {provider} → NAIL"
            )
            for diff in diffs:
                print(f"\n  Tool: {diff['tool']}")
                for fd in diff["diffs"]:
                    print(f"    {fd['field']}:")
                    print(f"      original:     {json.dumps(fd['original'], ensure_ascii=False)}")
                    print(f"      roundtripped: {json.dumps(fd['roundtripped'], ensure_ascii=False)}")

    return exit_code


def fc_import(input_path: str, source: str, out: str | None, fmt: str) -> int:
    """Import provider tool schemas into NAIL format.

    Reads a JSON file containing tool schemas in a provider-specific format
    (OpenAI, Anthropic, or Gemini) and converts them to NAIL's internal
    OpenAI FC format with effect annotations.

    Args:
        input_path: Path to the input JSON file containing provider tool schemas.
        source:     Source provider format: "openai", "anthropic", or "gemini".
        out:        Output .nail file path, or None to print to stdout.
        fmt:        Output format: "human" (default) or "json".

    Returns:
        0 on success, 1 on error.

    Example::

        $ nail fc import openai_tools.json --from openai
        $ nail fc import anthropic_tools.json --from anthropic --out my_tools.nail
    """
    p = Path(input_path)
    if not p.exists():
        print(f"✗ File not found: {input_path}", file=sys.stderr)
        return 1

    try:
        with open(p) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ JSON parse error in {input_path}: {e}", file=sys.stderr)
        return 1

    # Accept both a single tool dict and a list of tools
    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        print(f"✗ Expected a JSON array of tools, got {type(data).__name__}", file=sys.stderr)
        return 1

    _from_fn = {
        "openai": from_openai_tool,
        "anthropic": from_anthropic_tool,
        "gemini": from_gemini_tool,
    }
    converter = _from_fn[source]

    nail_tools: list[dict[str, Any]] = []
    errors: list[str] = []

    for i, tool in enumerate(data):
        try:
            nail_tools.append(converter(tool))
        except (KeyError, ValueError, TypeError) as e:
            errors.append(f"Tool[{i}]: {e}")

    if errors:
        for err in errors:
            print(f"✗ {err}", file=sys.stderr)
        return 1

    output = json.dumps(nail_tools, indent=2, ensure_ascii=False)

    if out:
        try:
            out_path = Path(out)
            if out_path.suffix == "":
                out_path = out_path.with_suffix(".nail")
            out_path.write_text(output + "\n", encoding="utf-8")
            if fmt == "human":
                print(f"✓ Imported {len(nail_tools)} tool(s) from {source} → {out_path}")
        except OSError as e:
            print(f"✗ Cannot write output file: {e}", file=sys.stderr)
            return 1
    else:
        print(output)
        if fmt == "human":
            print(
                f"\n# Imported {len(nail_tools)} tool(s) from {source} format.",
                file=sys.stderr,
            )

    return 0
