#!/usr/bin/env python3
"""
nail_cli — NAIL Language Interpreter CLI module

Provides the `main()` entry point for the `nail` command installed via pip.

Usage:
  nail run <file.nail>                                    # Run a fn-kind NAIL program
  nail run <file.nail> --call <fn_id> [--arg name=value] # Run a function in a module
  nail check <file.nail> [--strict]                       # Check without running (L0-L2)
  nail canonicalize <file.nail>                           # Output canonical form JSON
  nail canonicalize -                                     # Read from stdin
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


def cmd_canonicalize(path: str | None):
    """Output the canonical JSON form of a .nail file (or stdin)."""
    if path is None or path == "-":
        try:
            spec = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(f"✗ Invalid JSON from stdin: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        spec = load(path)
    # JCS-subset canonical form: sorted keys, no spaces, ensure_ascii=False
    print(json.dumps(spec, sort_keys=True, ensure_ascii=False, separators=(',', ':')))


def load_modules(module_paths: list[str]) -> dict:
    """Load module specs from file paths → {module_id: spec}."""
    modules = {}
    for mp in module_paths:
        mod_spec = load(mp)
        mod_id = mod_spec.get("id")
        if not mod_id:
            mod_id = Path(mp).stem  # fall back to filename without extension
        modules[mod_id] = mod_spec
    return modules


def cmd_check(path: str, strict: bool = False, module_paths: list[str] | None = None,
               level: int = 2, fmt: str = "human"):
    """Check a NAIL program. fmt='human' (default) or 'json' for machine-parseable output."""
    spec = load(path)
    raw_text = None
    if strict:
        with open(path) as f:
            raw_text = f.read()
    modules = load_modules(module_paths or [])
    try:
        checker = Checker(spec, raw_text=raw_text, strict=strict, modules=modules, level=level, source_path=path)
        checker.check()
        if fmt == "json":
            result: dict = {
                "ok": True,
                "file": path,
                "kind": spec.get("kind", "?"),
                "id": spec.get("id", "?"),
                "level": level,
                "checks": {
                    "L0": "ok",
                    "L1": "ok",
                    "L2": "ok",
                },
            }
            if level >= 3:
                cert = checker.get_termination_certificate()
                result["checks"]["L3"] = "ok"
                result["termination"] = cert
            print(json.dumps(result, indent=2))
        else:
            kind = spec.get("kind", "?")
            prog_id = spec.get("id", "?")
            fn_count = len(spec.get("defs", [])) if kind == "module" else 1
            strict_label = " [strict]" if strict else ""
            print(f"✓ {path}  [{kind}:{prog_id}]  {fn_count} fn(s){strict_label}")
            print(f"  L0: JSON schema  — OK" + (" (canonical form verified)" if strict else ""))
            print(f"  L1: Type check   — OK")
            print(f"  L2: Effect check — OK")
            if level >= 3:
                cert = checker.get_termination_certificate()
                fns_verified = cert["functions_verified"]
                print(f"  L3: Termination  — OK ({fns_verified} function(s) verified)")
    except CheckError as e:
        if fmt == "json":
            print(json.dumps(e.to_json()), file=sys.stderr)
        else:
            print(f"✗ Schema error: {e}", file=sys.stderr)
        sys.exit(1)
    except NailTypeError as e:
        if fmt == "json":
            print(json.dumps(e.to_json()), file=sys.stderr)
        else:
            print(f"✗ Type error: {e}", file=sys.stderr)
        sys.exit(1)
    except NailEffectError as e:
        if fmt == "json":
            print(json.dumps(e.to_json()), file=sys.stderr)
        else:
            print(f"✗ Effect error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_run(path: str, call_fn: str | None, raw_args: list[str], module_paths: list[str] | None = None, level: int = 2):
    spec = load(path)
    modules = load_modules(module_paths or [])

    # Parse arguments
    args = dict(parse_arg(a) for a in raw_args)

    # Check first
    try:
        checker = Checker(spec, modules=modules, level=level, source_path=path)
        checker.check()
    except (CheckError, NailTypeError, NailEffectError) as e:
        print(f"✗ Verification failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Run
    try:
        runtime = Runtime(spec, modules=modules)
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
            print("Usage: nail check <file.nail> [--strict] [--level N] [--format human|json]", file=sys.stderr)
            sys.exit(1)
        file_path = args[1]
        strict = "--strict" in args[2:]
        module_paths = [args[i+1] for i in range(2, len(args)-1) if args[i] == "--modules"]
        level = 2
        fmt = "human"
        for i in range(2, len(args) - 1):
            if args[i] == "--level":
                try:
                    level = int(args[i + 1])
                except (ValueError, IndexError):
                    print("✗ --level requires an integer (1, 2, or 3)", file=sys.stderr)
                    sys.exit(1)
            elif args[i] == "--format":
                fmt = args[i + 1] if i + 1 < len(args) else "human"
                if fmt not in ("human", "json"):
                    print(f"✗ --format must be 'human' or 'json', got: {fmt!r}", file=sys.stderr)
                    sys.exit(1)
        cmd_check(file_path, strict=strict, module_paths=module_paths, level=level, fmt=fmt)

    elif cmd == "canonicalize":
        file_path = args[1] if len(args) > 1 else None
        cmd_canonicalize(file_path)

    elif cmd == "run":
        if len(args) < 2:
            print("Usage: nail run <file.nail> [--call fn] [--arg name=value]", file=sys.stderr)
            sys.exit(1)

        file_path = args[1]
        call_fn = None
        raw_args = []
        run_level = 2

        module_paths = []
        i = 2
        while i < len(args):
            if args[i] == "--call" and i + 1 < len(args):
                call_fn = args[i + 1]
                i += 2
            elif args[i] == "--arg" and i + 1 < len(args):
                raw_args.append(args[i + 1])
                i += 2
            elif args[i] == "--modules" and i + 1 < len(args):
                module_paths.append(args[i + 1])
                i += 2
            elif args[i] == "--level" and i + 1 < len(args):
                try:
                    run_level = int(args[i + 1])
                except ValueError:
                    print("✗ --level requires an integer (1, 2, or 3)", file=sys.stderr)
                    sys.exit(1)
                i += 2
            else:
                print(f"Unknown option: {args[i]}", file=sys.stderr)
                sys.exit(1)

        cmd_run(file_path, call_fn, raw_args, module_paths=module_paths, level=run_level)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
