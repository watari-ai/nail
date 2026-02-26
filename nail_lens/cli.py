"""Nail-Lens CLI — Human-readable NAIL spec inspector."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .inspector import (
    format_type,
    inspect_spec,
    _get_functions,
    _get_all_effects,
    _get_types,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_spec(path_str: str) -> dict:
    """Load and parse a NAIL spec JSON file."""
    path = Path(path_str)
    if not path.exists():
        print(f"Error: file not found: {path_str}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {path_str}: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_inspect(args: argparse.Namespace) -> None:
    """Inspect a NAIL spec and print a human-readable report."""
    spec = load_spec(args.file)
    print(inspect_spec(spec))


def cmd_diff(args: argparse.Namespace) -> None:
    """Compare two NAIL specs and report added/removed/changed functions."""
    spec1 = load_spec(args.file1)
    spec2 = load_spec(args.file2)

    fns1 = {f["id"]: f for f in _get_functions(spec1)}
    fns2 = {f["id"]: f for f in _get_functions(spec2)}

    added = sorted(set(fns2.keys()) - set(fns1.keys()))
    removed = sorted(set(fns1.keys()) - set(fns2.keys()))
    common = set(fns1.keys()) & set(fns2.keys())

    changed: list[tuple[str, list[str]]] = []
    for fn_id in sorted(common):
        f1 = fns1[fn_id]
        f2 = fns2[fn_id]
        diffs: list[str] = []

        # Compare params
        p1 = [
            (p["id"], format_type(p.get("type", {})))
            for p in f1.get("params", [])
        ]
        p2 = [
            (p["id"], format_type(p.get("type", {})))
            for p in f2.get("params", [])
        ]
        if p1 != p2:
            diffs.append(f"params changed: {p1} → {p2}")

        # Compare return type
        r1 = format_type(f1.get("returns", {}))
        r2 = format_type(f2.get("returns", {}))
        if r1 != r2:
            diffs.append(f"return type changed: {r1} → {r2}")

        # Compare effects
        e1 = sorted(f1.get("effects", []))
        e2 = sorted(f2.get("effects", []))
        if e1 != e2:
            diffs.append(f"effects changed: {e1} → {e2}")

        if diffs:
            changed.append((fn_id, diffs))

    if not added and not removed and not changed:
        print("No differences found.")
        return

    for fn_id in added:
        fn = fns2[fn_id]
        params = ", ".join(
            f"{p['id']}: {format_type(p.get('type', {}))}"
            for p in fn.get("params", [])
        )
        ret = format_type(fn.get("returns", {}))
        print(f"+ fn {fn_id}({params}) -> {ret}")

    for fn_id in removed:
        fn = fns1[fn_id]
        params = ", ".join(
            f"{p['id']}: {format_type(p.get('type', {}))}"
            for p in fn.get("params", [])
        )
        ret = format_type(fn.get("returns", {}))
        print(f"- fn {fn_id}({params}) -> {ret}")

    for fn_id, diffs in changed:
        print(f"~ fn {fn_id}:")
        for d in diffs:
            print(f"    {d}")


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate a NAIL spec at the specified level."""
    spec = load_spec(args.file)
    level_str = args.level.upper()

    level_map = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L3.1": 3}
    level_strict = level_str == "L3.1"

    if level_str not in level_map:
        print(
            f"Error: invalid level {args.level}. Use L0, L1, L2, L3, or L3.1",
            file=sys.stderr,
        )
        sys.exit(1)

    level = level_map[level_str]

    try:
        from interpreter.checker import Checker, CheckError  # noqa: F401

        checker = Checker(spec, level=level, strict=level_strict)
        checker.check()
        print(f"✓ Validation passed (level {args.level})")
    except Exception as e:
        try:
            from interpreter.checker import CheckError as _CE

            if isinstance(e, _CE):
                print(f"✗ Validation failed: {e.message}")
            else:
                print(f"✗ Validation failed: {e}")
        except ImportError:
            print(f"✗ Validation failed: {e}")
        sys.exit(1)


def cmd_effects(args: argparse.Namespace) -> None:
    """List all effects used in a NAIL spec."""
    spec = load_spec(args.file)
    functions = _get_functions(spec)

    all_effects: set[str] = set()
    fn_with_effects: list[tuple[str, list[str]]] = []

    for fn in functions:
        effects = fn.get("effects", [])
        if effects:
            fn_with_effects.append((fn["id"], effects))
            all_effects.update(effects)

    if not all_effects:
        print("No effects used (pure spec).")
        return

    spec_id = spec.get("id", "<unnamed>")
    print(f"Effects summary for: {spec_id}")
    print("─" * 40)
    print(f"All effects: {', '.join(sorted(all_effects))}")

    if fn_with_effects:
        print()
        print("Per-function effects:")
        for fn_id, effects in fn_with_effects:
            print(f"  {fn_id}: {', '.join(effects)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nail-lens",
        description="Nail-Lens: Human-readable NAIL spec inspector",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect a NAIL spec file")
    p_inspect.add_argument("file", help="Path to .nail file")
    p_inspect.set_defaults(func=cmd_inspect)

    # diff
    p_diff = subparsers.add_parser("diff", help="Compare two NAIL spec files")
    p_diff.add_argument("file1", help="First .nail file")
    p_diff.add_argument("file2", help="Second .nail file")
    p_diff.set_defaults(func=cmd_diff)

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate a NAIL spec file")
    p_validate.add_argument(
        "--level",
        default="L2",
        choices=["L0", "L1", "L2", "L3", "L3.1"],
        help="Validation level (default: L2)",
    )
    p_validate.add_argument("file", help="Path to .nail file")
    p_validate.set_defaults(func=cmd_validate)

    # effects
    p_effects = subparsers.add_parser(
        "effects", help="List all effects used in a NAIL spec file"
    )
    p_effects.add_argument("file", help="Path to .nail file")
    p_effects.set_defaults(func=cmd_effects)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
