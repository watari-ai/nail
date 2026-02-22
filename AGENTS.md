# AGENTS.md — NAIL Project

This repository is the home of NAIL, an experimental programming language that is proactively developed and evolved by AI.

## What Makes This Repository Unique

NAIL is "a programming language for AI authorship," and even its specification is designed and improved by AI.
AI agents working in this repository are not just implementers, but also **language designers**.

## What Is Expected of You

### How to Approach Implementation Tasks
1. **Always read `SPEC.md` first** — it defines NAIL's type system, effects, and syntax rules.
2. **Read `PHILOSOPHY.md`** — it explains the reasons behind the design.
3. Before implementation, verify whether the spec has contradictions or missing parts.
4. If you find a problem, leave a proposed fix as a comment before implementing.

### Proposing Spec Improvements
- If you discover an improvement idea during implementation, you may add a Markdown proposal under `proposals/`.
- Format: `proposals/YYYY-MM-DD-<topic>.md`
- AI improving the specification is a core idea of NAIL.

### Prohibitions
- Do not change the NAIL spec without authorization (follow the flow: proposal → approval → change).
- Do not add human-oriented syntax (NAIL has no text syntax).
- Do not introduce any design that deviates from JSON format.

## Directory Structure

```
nail/
├── SPEC.md          Language specification (read before touching code)
├── PHILOSOPHY.md    Design philosophy (critical reasoning for decisions)
├── ROADMAP.md       Development phases
├── AGENTS.md        This file
├── examples/        Sample programs (*.nail)
├── interpreter/     Python reference interpreter (built in Phase 1)
├── experiments/     LLM comparison experiment data (built in Phase 2)
└── proposals/       AI spec-improvement proposals (free to add)
```

## Current Top Priority Task

Check Phase 1 in `ROADMAP.md`.

---

*This file conforms to the NAIL spec's project structure standard.*
