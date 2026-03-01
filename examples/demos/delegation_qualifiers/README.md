# NAIL Demo — Delegation Qualifiers

## Problem

As AI agent pipelines grow longer (A → B → C → D), irreversible capabilities
can silently propagate through the chain without any explicit re-authorization.
This is the **Zone of Indifference**: by the time `FS:write_file` reaches Agent
D, no intermediate agent has consciously chosen to grant it.

```
Reporter (A) → Analyzer (B) → Processor (C) → Writer (D)
                                                  └─ owns FS:write_file (irreversible)
```

Without enforcement, Processor (C) could invoke Writer (D) and inherit
filesystem write access by accident, simply by calling a function it doesn't
fully understand.

## Solution

NAIL's `fc_ir_v2` module introduces **delegation qualifiers** — a first-class
type-system feature inspired by DeepMind's *Intelligent AI Delegation* paper.

Any capability marked `delegation: "explicit"` requires every caller in the
chain to consciously re-authorize it via a `grants` field:

```json
{
  "op": "def",
  "name": "write_output",
  "effects": {
    "allow": [
      { "op": "FS:write_file", "reversible": false, "delegation": "explicit" }
    ]
  },
  "grants": ["FS:write_file"],
  "body": []
}
```

If any agent in the chain omits `grants`, `check_program()` raises **FC-E010**
at type-check time — before any code runs.

## Valid Chain vs. Broken Chain

### ✅ `agent_chain.nail` — all agents declare grants

Every agent (Reporter → Analyzer → Processor → Writer) includes:
```json
"grants": ["FS:write_file"]
```

`check_program()` returns zero errors.

### ❌ `agent_chain_broken.nail` — Processor (C) missing grants

Processor (`run_pipeline`) forgot the `grants` field:
```json
{
  "op": "def",
  "name": "run_pipeline",
  "effects": {
    "allow": [{ "op": "FS:write_file", "reversible": false, "delegation": "explicit" }]
  },
  "body": [{ "op": "call", "fn": "write_output" }]
}
```

Expected output from `nail fc check agent_chain_broken.nail`:

```
FC-E010: ExplicitDelegationViolation — callee 'write_output' requires
explicit delegation for op 'FS:write_file', but caller 'run_pipeline'
does not declare it in 'grants'
```

## How to Run

```bash
cd examples/demos/delegation_qualifiers
python3 demo.py
```

Expected output:

```
============================================================
  NAIL Demo — Delegation Qualifiers
  Zone of Indifference detection via fc_ir_v2
============================================================

============================================================
  Demo: Valid delegation chain (FC-E010 free)
============================================================

📄 Loaded 4 function def(s) from agent_chain.nail

Chain: write_summary → generate_report → run_pipeline → write_output
Each agent declares  grants: ['FS:write_file']  ✓

✅ check_program() → 0 errors (chain is safe)

============================================================
  Demo: Broken delegation chain (FC-E010 expected)
============================================================

📄 Loaded 4 function def(s) from agent_chain_broken.nail

Chain: write_summary → generate_report → run_pipeline → write_output
Processor (run_pipeline) has NO grants field  ✗

🚨 check_program() → 1 error(s) detected:

   Code    : FC-E010
   Callee  : write_output
   Op      : FS:write_file
   Message : FC-E010: ExplicitDelegationViolation — callee 'write_output'
             requires explicit delegation for op 'FS:write_file', but
             caller 'run_pipeline' does not declare it in 'grants'

💡 Zone of Indifference prevented — NAIL blocked the chain at type-check time.
```

## Run Tests

```bash
cd /Users/w/nail
python -m pytest examples/demos/delegation_qualifiers/tests/ -v
```

## Files

| File | Purpose |
|------|---------|
| `agent_chain.nail` | Valid 4-agent delegation chain (all grants present) |
| `agent_chain_broken.nail` | Broken chain — Processor (C) missing `grants` |
| `demo.py` | Loads both specs, calls `fc_ir_v2.check_program()`, prints results |
| `tests/test_demo_delegation_qualifiers.py` | 8+ pytest tests |

## References

- [DeepMind — Intelligent AI Delegation](https://deepmind.google/research/publications/intelligent-ai-delegation/)
- NAIL Issue #107 — Delegation-aware Effect Qualifiers (Phase 1)
- NAIL PR #109 — `fc_ir_v2` implementation
