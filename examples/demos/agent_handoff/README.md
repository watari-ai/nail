# NAIL Demo #105 — Agent Handoff

## Problem

Multi-agent pipelines typically hand raw tool lists between agents.
Without capability constraints, a *Planner* agent could accidentally call
`write_file`, and a *Reporter* agent could trigger network requests it has no
business making. The result is unpredictable behaviour and hard-to-audit
side-effects.

## Solution

NAIL effect annotations let you declare **what side-effects each tool can
produce** (`FS`, `NET`, `IO`, …). `nail.filter_by_effects()` then slices the
full tool list to only the tools a particular agent role is permitted to use —
no runtime monkey-patching, no duplicate specs.

```
all_tools ──┬─ filter(["FS"])         ──▶ Agent A (Planner)   : read_file
            ├─ filter(["FS", "NET"])  ──▶ Agent B (Executor)  : read_file, write_file, fetch_url
            └─ filter(["IO"])         ──▶ Agent C (Reporter)  : log_result
```

## Tool Inventory

| Tool | Effects | Purpose |
|------|---------|---------|
| `read_file` | `FS` | Read a file from the local filesystem |
| `write_file` | `FS` | Write / overwrite a file |
| `fetch_url` | `NET` | HTTP/HTTPS request |
| `log_result` | `IO` | Emit a structured log entry |

## How to Run

```bash
# From the repo root
cd examples/demos/agent_handoff
python3 demo.py
```

Expected output:

```
============================================================
  NAIL Demo #105 — Agent Handoff
  Effect annotations → role-based tool routing
============================================================

📦 Loaded 4 tool(s) from agent_tools.nail

🤖 Agent A (Planner) — read-only tools:
  ✓ read_file [FS]

🤖 Agent B (Executor) — full tools:
  ✓ read_file [FS]
  ✓ write_file [FS]
  ✓ fetch_url [NET]

🤖 Agent C (Reporter) — IO tools:
  ✓ log_result [IO]

------------------------------------------------------------
🔁 Handoff flow: Agent A → Agent B → Agent C

  A plans by reading state  (read_file)
  B executes: fetches data and writes results  (fetch_url, write_file, read_file)
  C reports outcomes via structured logs  (log_result)

💡 Each agent only sees what it's allowed to touch.
```

## Run Tests

```bash
cd /Users/w/nail
python -m pytest examples/demos/agent_handoff/tests/ -v
```
