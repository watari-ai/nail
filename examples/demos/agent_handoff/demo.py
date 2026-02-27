"""NAIL Demo #105 — Agent Handoff

Demonstrates how NAIL effect annotations enable safe, role-based tool handoff
between agents.  A single tool spec is loaded and then filtered per-agent with
nail.filter_by_effects() so that each agent only receives the tools it is
allowed to call.

Pipeline:
    Agent A (Planner)   → read-only   → allowed: ["FS"] (read, no write)
    Agent B (Executor)  → full access → allowed: ["FS", "NET"]
    Agent C (Reporter)  → output only → allowed: ["IO"]

Run:
    cd examples/demos/agent_handoff
    python3 demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from anywhere in the repo without an editable install
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import nail_lang as nail

SPEC_PATH = Path(__file__).parent / "agent_tools.nail"


def load_tools(path: Path) -> list[dict]:
    """Load agent_tools.nail and return the tool list."""
    with path.open() as f:
        spec = json.load(f)
    tools: list[dict] = spec.get("tools", [])
    if not tools:
        raise ValueError(f"No tools found in {path}")
    return tools


def tool_label(tool: dict) -> str:
    """Return a short display label for a tool dict."""
    fn = tool.get("function", {})
    name = fn.get("name", "?")
    effects = fn.get("effects", [])
    effect_str = ", ".join(effects) if effects else "—"
    return f"{name} [{effect_str}]"


def show_agent(title: str, tools: list[dict]) -> None:
    """Print the tool list for an agent."""
    print(f"🤖 {title}")
    if tools:
        for t in tools:
            print(f"  ✓ {tool_label(t)}")
    else:
        print("  (no tools)")
    print()


def main() -> None:
    print("=" * 60)
    print("  NAIL Demo #105 — Agent Handoff")
    print("  Effect annotations → role-based tool routing")
    print("=" * 60)
    print()

    # 1. Load all tools from the shared spec
    all_tools = load_tools(SPEC_PATH)
    print(f"📦 Loaded {len(all_tools)} tool(s) from {SPEC_PATH.name}")
    print()

    # ------------------------------------------------------------------ #
    # Agent A — Planner                                                    #
    # Reads files to understand the current state; no writes, no network. #
    # write_file is FS but we deliberately exclude it by keeping only the #
    # read_file tool.  We achieve this by noting that write_file also has  #
    # "FS" — so we post-filter by name to keep only readers.              #
    # ------------------------------------------------------------------ #
    planner_tools = [
        t for t in nail.filter_by_effects(all_tools, allowed=["FS"])
        if t["function"]["name"] == "read_file"
    ]
    show_agent("Agent A (Planner) — read-only tools:", planner_tools)

    # ------------------------------------------------------------------ #
    # Agent B — Executor                                                   #
    # Can read/write files and make network calls; no logging output.     #
    # ------------------------------------------------------------------ #
    executor_tools = nail.filter_by_effects(all_tools, allowed=["FS", "NET"])
    show_agent("Agent B (Executor) — full tools:", executor_tools)

    # ------------------------------------------------------------------ #
    # Agent C — Reporter                                                   #
    # Only allowed to emit structured log output.                         #
    # ------------------------------------------------------------------ #
    reporter_tools = nail.filter_by_effects(all_tools, allowed=["IO"])
    show_agent("Agent C (Reporter) — IO tools:", reporter_tools)

    # Handoff summary
    print("-" * 60)
    print("🔁 Handoff flow: Agent A → Agent B → Agent C")
    print()
    print("  A plans by reading state  (read_file)")
    print("  B executes: fetches data and writes results  (fetch_url, write_file, read_file)")
    print("  C reports outcomes via structured logs  (log_result)")
    print()
    print("💡 Each agent only sees what it's allowed to touch.")


if __name__ == "__main__":
    main()
