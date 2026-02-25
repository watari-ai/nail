#!/usr/bin/env python3
"""
NAIL MCP Firewall Demo
========================
"Sandbox AI agent tool access by effect."

Uses the nail_lang Python API (from_mcp, infer_effects, filter_by_effects)
to show how NAIL enforces least-privilege on MCP tool sets.

Run: python demos/mcp_firewall_demo.py
"""

import sys, textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nail_lang._mcp import from_mcp, infer_effects
from nail_lang._effects import filter_by_effects


def section(title: str):
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print(f"{'═' * 64}")


# ── Step 1: Define MCP tools ─────────────────────────────────────────

section("Step 1: MCP Tool Definitions")

mcp_tools = [
    {
        "name": "read_file",
        "description": "Read a file from disk",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "http_get",
        "description": "Fetch a URL via HTTP GET",
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "run_command",
        "description": "Execute a shell command",
        "inputSchema": {
            "type": "object",
            "properties": {"cmd": {"type": "string"}},
            "required": ["cmd"],
        },
    },
    {
        "name": "log_message",
        "description": "Print a log message to console",
        "inputSchema": {
            "type": "object",
            "properties": {"msg": {"type": "string"}},
            "required": ["msg"],
        },
    },
]

for tool in mcp_tools:
    print(f"  • {tool['name']:15s} — {tool['description']}")


# ── Step 2: Auto-annotate with NAIL effects ──────────────────────────

section("Step 2: Effect Inference (from_mcp)")

annotated = from_mcp(mcp_tools)

print("  from_mcp() auto-annotates each tool:\n")
for tool in annotated:
    fn = tool["function"]
    effects = fn.get("effects", [])
    print(f"  {fn['name']:15s} → effects: {effects}")


# ── Step 3: Policy — Read-Only Researcher (FS + IO) ─────────────────

section("Step 3: Policy — Read-Only Researcher (FS + IO)")

print(textwrap.dedent("""\
  This agent can read files and log, but NOT access the network
  or run shell commands.
"""))

researcher_tools = filter_by_effects(annotated, allowed=["FS", "IO"])
allowed_names = {t["function"]["name"] for t in researcher_tools}

for tool in annotated:
    name = tool["function"]["name"]
    status = "✅ allowed" if name in allowed_names else "❌ blocked"
    print(f"  {name:15s} {status}")


# ── Step 4: Policy — Network Analyst (NET + IO) ─────────────────────

section("Step 4: Policy — Network Analyst (NET + IO)")

print(textwrap.dedent("""\
  This agent can fetch URLs and log, but NOT read local files
  or run shell commands.
"""))

analyst_tools = filter_by_effects(annotated, allowed=["NET", "IO"])
allowed_names = {t["function"]["name"] for t in analyst_tools}

for tool in annotated:
    name = tool["function"]["name"]
    status = "✅ allowed" if name in allowed_names else "❌ blocked"
    print(f"  {name:15s} {status}")


# ── Step 5: Policy — Air-Gapped (IO only) ───────────────────────────

section("Step 5: Policy — Air-Gapped (IO only)")

print(textwrap.dedent("""\
  Maximum isolation: the agent can only print log messages.
  No filesystem, no network, no process execution.
"""))

airgapped_tools = filter_by_effects(annotated, allowed=["IO"])
allowed_names = {t["function"]["name"] for t in airgapped_tools}

for tool in annotated:
    name = tool["function"]["name"]
    status = "✅ allowed" if name in allowed_names else "❌ blocked"
    print(f"  {name:15s} {status}")


# ── Summary matrix ───────────────────────────────────────────────────

section("Summary: Policy × Tool Matrix")

# Compute sets for the matrix
policies = [
    ("Researcher (FS+IO)",  ["FS", "IO"]),
    ("Analyst (NET+IO)",    ["NET", "IO"]),
    ("Air-Gapped (IO)",     ["IO"]),
]

tool_names = [t["function"]["name"] for t in annotated]

print()
# Header
hdr = f"  {'Policy':<25s}"
for name in tool_names:
    hdr += f" {name:>12s}"
print(hdr)
print(f"  {'─' * 25}" + "─" * (13 * len(tool_names)))

for policy_label, allowed_effects in policies:
    filtered = filter_by_effects(annotated, allowed=allowed_effects)
    allowed_set = {t["function"]["name"] for t in filtered}
    row = f"  {policy_label:<25s}"
    for name in tool_names:
        row += f" {'✅':>11s}" if name in allowed_set else f" {'❌':>11s}"
    print(row)

print()
print(textwrap.dedent("""\
  "Effect-based filtering: no code changes needed.
   Just declare the policy — NAIL enforces it."
"""))
