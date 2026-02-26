"""Nail-Lens inspector: convert NAIL spec to human-readable report."""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Type formatting
# ---------------------------------------------------------------------------

def format_type(t: Any) -> str:
    """Convert a NAIL type dict to a human-readable string."""
    if not isinstance(t, dict):
        return str(t)
    kind = t.get("type", "?")
    if kind == "int":
        return f"int{t.get('bits', 64)}"
    elif kind == "float":
        return f"float{t.get('bits', 64)}"
    elif kind == "bool":
        return "bool"
    elif kind == "string":
        return "str"
    elif kind == "unit":
        return "unit"
    elif kind == "option":
        inner = format_type(t.get("inner", {}))
        return f"option<{inner}>"
    elif kind == "result":
        ok = format_type(t.get("ok", {}))
        err = format_type(t.get("err", {}))
        return f"result<{ok}, {err}>"
    elif kind == "list":
        # NAIL uses "inner" for list element type
        elem = format_type(t.get("inner", t.get("elem", {})))
        return f"list<{elem}>"
    elif kind == "map":
        key = format_type(t.get("key", {}))
        val = format_type(t.get("value", t.get("val", {})))
        return f"map<{key}, {val}>"
    elif kind == "alias":
        return t.get("name", "?")
    elif kind == "enum":
        variants = [v.get("tag", "?") for v in t.get("variants", [])]
        return f"enum({', '.join(variants)})"
    else:
        return str(t)


# ---------------------------------------------------------------------------
# Call graph extraction
# ---------------------------------------------------------------------------

def _collect_calls_expr(expr: Any, calls: set[str]) -> None:
    """Recursively collect function call targets from an expression."""
    if not isinstance(expr, dict):
        return
    if expr.get("op") == "call":
        target = expr.get("fn")
        if target:
            calls.add(target)
    for key in ("l", "r", "v", "cond"):
        sub = expr.get(key)
        if isinstance(sub, dict):
            _collect_calls_expr(sub, calls)
    args = expr.get("args")
    if isinstance(args, list):
        for item in args:
            if isinstance(item, dict):
                _collect_calls_expr(item, calls)


def _collect_calls_body(body: list, calls: set[str]) -> None:
    """Recursively collect function call targets from a statement list."""
    for stmt in body:
        if not isinstance(stmt, dict):
            continue
        # Check the val expression
        val = stmt.get("val")
        if isinstance(val, dict):
            _collect_calls_expr(val, calls)
        # Recurse into nested statement lists
        for key in ("body", "then", "else"):
            nested = stmt.get(key)
            if isinstance(nested, list):
                _collect_calls_body(nested, calls)
        # match_enum cases: list of {tag, body}
        cases = stmt.get("cases")
        if isinstance(cases, list):
            for case in cases:
                if isinstance(case, dict):
                    case_body = case.get("body")
                    if isinstance(case_body, list):
                        _collect_calls_body(case_body, calls)


# ---------------------------------------------------------------------------
# Spec extraction helpers
# ---------------------------------------------------------------------------

def _get_functions(spec: dict) -> list[dict]:
    """Extract all function definitions from a spec."""
    if spec.get("kind") == "fn":
        return [spec]
    elif spec.get("kind") == "module":
        return [d for d in spec.get("defs", []) if d.get("kind") == "fn"]
    return []


def _get_types(spec: dict) -> dict:
    """Extract named type definitions from a spec."""
    return spec.get("types", {})


def _get_all_effects(spec: dict) -> set[str]:
    """Collect all effect tags used across all functions."""
    effects: set[str] = set()
    for fn in _get_functions(spec):
        for e in fn.get("effects", []):
            effects.add(e)
    return effects


# ---------------------------------------------------------------------------
# Main inspector
# ---------------------------------------------------------------------------

def inspect_spec(spec_dict: dict) -> str:
    """Convert a NAIL spec dict to a human-readable report string.

    Handles both single-function specs and module specs.

    Returns a multi-line string suitable for terminal output.
    """
    lines: list[str] = []
    sep = "─" * 60

    # --- HEADER ---
    kind = spec_dict.get("kind", "unknown")
    spec_id = spec_dict.get("id", "<unnamed>")
    nail_ver = spec_dict.get("nail", "?")
    meta = spec_dict.get("meta", {})
    spec_version = meta.get("spec_version", spec_dict.get("spec_version", "?"))

    lines.append(sep)
    lines.append("  NAIL Spec Inspector  (Nail-Lens v0.1.0)")
    lines.append(sep)
    lines.append(f"  Name         : {spec_id}")
    lines.append(f"  Kind         : {kind}")
    lines.append(f"  NAIL version : {nail_ver}")
    lines.append(f"  Spec version : {spec_version}")

    if kind == "module":
        exports = spec_dict.get("exports", [])
        lines.append(f"  Exports      : {', '.join(exports) if exports else '(none)'}")

    lines.append("")

    # --- FUNCTIONS ---
    functions = _get_functions(spec_dict)
    lines.append(sep)
    lines.append(f"  FUNCTIONS ({len(functions)})")
    lines.append(sep)

    call_graph: dict[str, set[str]] = {}

    for fn in functions:
        fn_id = fn.get("id", "?")
        params = fn.get("params", [])
        returns = fn.get("returns", {})
        effects = fn.get("effects", [])

        param_strs = [
            f"{p['id']}: {format_type(p.get('type', {}))}"
            for p in params
        ]
        param_str = ", ".join(param_strs) if param_strs else "()"
        ret_str = format_type(returns)
        effects_str = ", ".join(effects) if effects else "pure"

        lines.append(f"  fn {fn_id}({param_str}) -> {ret_str}")
        lines.append(f"      effects: [{effects_str}]")

        # Build call graph
        calls: set[str] = set()
        _collect_calls_body(fn.get("body", []), calls)
        call_graph[fn_id] = calls

        if calls:
            lines.append(f"      calls  : {', '.join(sorted(calls))}")

        lines.append("")

    # --- TYPES ---
    types = _get_types(spec_dict)
    if types:
        lines.append(sep)
        lines.append(f"  TYPES ({len(types)})")
        lines.append(sep)
        for type_name, type_def in types.items():
            type_kind = type_def.get("type", "?")
            if type_kind == "enum":
                variants = type_def.get("variants", [])
                lines.append(f"  type {type_name} = enum")
                for v in variants:
                    tag = v.get("tag", "?")
                    fields = v.get("fields", [])
                    if fields:
                        field_strs = [
                            f"{f['name']}: {format_type(f.get('type', {}))}"
                            for f in fields
                        ]
                        lines.append(f"      | {tag}({', '.join(field_strs)})")
                    else:
                        lines.append(f"      | {tag}")
            else:
                lines.append(f"  type {type_name} = {format_type(type_def)}")
        lines.append("")

    # --- CALL GRAPH ---
    has_calls = any(len(v) > 0 for v in call_graph.values())
    if has_calls:
        lines.append(sep)
        lines.append("  CALL GRAPH")
        lines.append(sep)
        for fn_id, calls in call_graph.items():
            if calls:
                lines.append(f"  {fn_id} → {', '.join(sorted(calls))}")
        lines.append("")

    # --- TERMINATION ---
    termination = spec_dict.get("termination")
    lines.append(sep)
    lines.append("  TERMINATION (L3)")
    lines.append(sep)
    if termination:
        measure = termination.get("measure", "?")
        lines.append("  Status  : ✓ Verified")
        lines.append(f"  Measure : {measure}")
    else:
        lines.append("  Status  : ✗ Not verified (no termination measure)")
    lines.append("")

    # --- SUMMARY ---
    all_effects = _get_all_effects(spec_dict)
    lines.append(sep)
    lines.append("  SUMMARY")
    lines.append(sep)
    lines.append(f"  Functions : {len(functions)}")
    lines.append(f"  Types     : {len(types)}")
    lines.append(
        f"  Effects   : {', '.join(sorted(all_effects)) if all_effects else 'none (pure)'}"
    )
    lines.append(f"  Termination verified : {'yes' if termination else 'no'}")
    lines.append(sep)

    return "\n".join(lines)
