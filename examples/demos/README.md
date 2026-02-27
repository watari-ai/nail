# NAIL — Example Demos

Three self-contained demos showing how NAIL's effect system solves real AI engineering problems.
No API keys required; all demos run offline.

---

## Demos

### [#104 — API Routing](./api_routing/)

> *One spec, three providers.*

Convert a single NAIL tool spec into OpenAI, Anthropic, and Gemini function-calling formats
without duplication or drift.

**Key API:** `nail.convert_tools(tools, source="nail", target="openai|anthropic|gemini")`

```bash
cd api_routing && python3 demo.py
```

---

### [#105 — Agent Handoff](./agent_handoff/)

> *Each agent only sees what it's allowed to touch.*

Use `filter_by_effects()` to slice a shared tool registry into per-agent subsets:
Planner gets read-only tools, Executor gets full access, Reporter gets IO-only.

**Key API:** `nail.filter_by_effects(tools, allowed=["FS", "NET", "IO"])`

```bash
cd agent_handoff && python3 demo.py
```

---

### [#106 — Verify-Fix Loop](./verify_fix_loop/)

> *NAIL Checker catches errors before they reach production.*

Simulate an LLM generate → validate → error-feedback → fix → validate loop.
Shows how machine-readable NAIL errors enable automated self-correction.

**Key API:** `Checker(spec).check()` raises `CheckError` with structured messages.

```bash
cd verify_fix_loop && python3 demo.py
```

---

## Running All Tests

From the repo root:

```bash
python3 -m pytest examples/demos/ -v
```

Expected: **23 tests, all pass.**

---

## Effect Tags Reference

| Tag | Meaning |
|-----|---------|
| `FS` | Filesystem read/write |
| `NET` | Network access |
| `IO` | Logging / stdout / stdin |
| `REPO` | Repository / version control |
| `DB` | Database access |

Effects are declared in the NAIL spec and enforced at validation time —
giving every AI agent a machine-auditable capability boundary.
