#!/usr/bin/env python3
"""
Check that all .nail files in examples/ are in canonical (JCS) form.
A NAIL file is canonical if: json.dumps(json.loads(content), sort_keys=True, separators=(',', ':'))
equals the file content (after stripping trailing whitespace/newline).

Usage:
    python tools/check-canonical.py           # check examples/
    python tools/check-canonical.py path/...  # check specific files or dirs
    python tools/check-canonical.py --fix     # auto-fix non-canonical files

Exit code: 0 if all files are canonical, 1 if any are not.
"""
import json
import sys
from pathlib import Path


def is_canonical(path: Path) -> tuple[bool, str | None]:
    """Return (True, None) if canonical, (False, canonical_form) otherwise."""
    content = path.read_text(encoding="utf-8").strip()
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    if content == canonical:
        return True, None
    return False, canonical


def find_nail_files(paths: list[Path]) -> list[Path]:
    result = []
    for p in paths:
        if p.is_dir():
            result.extend(sorted(p.rglob("*.nail")))
        elif p.suffix == ".nail":
            result.append(p)
    return result


def main():
    args = sys.argv[1:]
    fix_mode = "--fix" in args
    args = [a for a in args if a != "--fix"]

    if args:
        search_paths = [Path(a) for a in args]
    else:
        # Default: check examples/
        search_paths = [Path(__file__).parent.parent / "examples"]

    files = find_nail_files(search_paths)
    if not files:
        print("No .nail files found.")
        sys.exit(0)

    failures = []
    for f in files:
        ok, canonical = is_canonical(f)
        if not ok:
            if isinstance(canonical, str) and canonical.startswith("Invalid JSON"):
                print(f"ERROR  {f}: {canonical}")
                failures.append(f)
            else:
                if fix_mode:
                    f.write_text(canonical + "\n", encoding="utf-8")
                    print(f"FIXED  {f}")
                else:
                    print(f"FAIL   {f}  (not in canonical JCS form)")
                    failures.append(f)

    if failures and not fix_mode:
        print(f"\n{len(failures)} file(s) not in canonical form.")
        print("Run with --fix to auto-correct, or: python -c \"import json; p=open('FILE'); d=json.load(p); open('FILE','w').write(json.dumps(d,sort_keys=True,separators=(',',':')))\"")
        sys.exit(1)
    elif not failures:
        print(f"✓ All {len(files)} .nail file(s) are in canonical form.")
    sys.exit(0)


if __name__ == "__main__":
    main()
