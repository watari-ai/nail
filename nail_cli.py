#!/usr/bin/env python3
"""
nail_cli — NAIL Language Interpreter CLI module

Provides the `main()` entry point for the `nail` command installed via pip.

Usage:
  nail run <file.nail>                                    # Run a fn-kind NAIL program
  nail run <file.nail> --call <fn_id> [--arg name=value] # Run a function in a module
  nail check <file.nail>                                  # Check without running (L0-L2)
  nail --version                                          # Show interpreter version
  nail version                                            # Show interpreter version (alias)
"""

import sys
import json
from pathlib import Path

# Ensure the package root is on sys.path when running as installed module
_pkg_root = Path(__file__).parent
if str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from interpreter import Checker, Runtime, CheckError, NailTypeError, NailEffectError, NailRuntimeError
from interpreter.runtime import UNIT


def load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"✗ File not found: {path}", file=sys.stderr)
        sys.exit(1)
    if p.suffix != ".nail":
        print(f"✗ Not a .nail file: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        with open(p) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)


def parse_arg(s: str) -> tuple[str, object]:
    """Parse 'name=value' into (name, typed_value)."""
    if "=" not in s:
        print(f"✗ --arg must be name=value, got: {s!r}", file=sys.stderr)
        sys.exit(1)
    name, _, raw = s.partition("=")
    name = name.strip()
    raw = raw.strip()
    # Type inference: bool → int → float → string
    if raw == "true":
        return name, True
    if raw == "false":
        return name, False
    try:
        return name, int(raw)
    except ValueError:
        pass
    try:
        return name, float(raw)
    except ValueError:
        pass
    return name, raw


def cmd_check(path: str):
    spec = load(path)
    try:
        checker = Checker(spec)
        checker.check()
        kind = spec.get("kind", "?")
        prog_id = spec.get("id", "?")
        fn_count = len(spec.get("defs", [])) if kind == "module" else 1
        print(f"✓ {path}  [{kind}:{prog_id}]  {fn_count} fn(s)")
        print(f"  L0: JSON schema  — OK")
        print(f"  L1: Type check   — OK")
        print(f"  L2: Effect check — OK")
    except CheckError as e:
        print(f"✗ Schema error: {e}", file=sys.stderr)
        sys.exit(1)
    except NailTypeError as e:
        print(f"✗ Type error: {e}", file=sys.stderr)
        sys.exit(1)
    except NailEffectError as e:
        print(f"✗ Effect error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_run(path: str, call_fn: str | None, raw_args: list[str]):
    spec = load(path)

    # Parse arguments
    args = dict(parse_arg(a) for a in raw_args)

    # Check first
    try:
        checker = Checker(spec)
        checker.check()
    except (CheckError, NailTypeError, NailEffectError) as e:
        print(f"✗ Verification failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Run
    try:
        runtime = Runtime(spec)
        kind = spec.get("kind")

        if kind == "module":
            if not call_fn:
                # Try 'main' by default
                call_fn = "main"
            result = runtime.run_fn(call_fn, args)
        else:
            result = runtime.run(args if args else None)

        # Print return value (non-unit results)
        if result is not UNIT and result is not None:
            print(f"→ {result}")

    except NailRuntimeError as e:
        print(f"✗ Runtime error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd in ("version", "--version"):
        from interpreter import __version__
        print(f"NAIL interpreter v{__version__}")
        sys.exit(0)

    elif cmd == "check":
        if len(args) < 2:
            print("Usage: nail check <file.nail>", file=sys.stderr)
            sys.exit(1)
        cmd_check(args[1])

    elif cmd == "run":
        if len(args) < 2:
            print("Usage: nail run <file.nail> [--call fn] [--arg name=value]", file=sys.stderr)
            sys.exit(1)

        file_path = args[1]
        call_fn = None
        raw_args = []

        i = 2
        while i < len(args):
            if args[i] == "--call" and i + 1 < len(args):
                call_fn = args[i + 1]
                i += 2
            elif args[i] == "--arg" and i + 1 < len(args):
                raw_args.append(args[i + 1])
                i += 2
            else:
                print(f"Unknown option: {args[i]}", file=sys.stderr)
                sys.exit(1)

        cmd_run(file_path, call_fn, raw_args)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
