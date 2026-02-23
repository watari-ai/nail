# NAIL v0.3 Design Documents

Created: 2026-02-24 01:30 JST by ワタリ

These documents define the proposed design for NAIL v0.3 features.
Each links to its corresponding GitHub Issue.

## Features

| Feature | Design Doc | Issue | Priority |
|---------|-----------|-------|----------|
| Overflow ops (wrap/sat) | [overflow-ops.md](overflow-ops.md) | #2 | 🔴 High |
| Result type & error model | [result-type.md](result-type.md) | #3 | 🔴 High |
| Cross-module import | [cross-module.md](cross-module.md) | #4 | 🟡 Medium |

## Design Principles

All v0.3 features must follow NAIL's core guarantees:

1. **Zero ambiguity** — every feature must have exactly one canonical JSON representation
2. **Verifiable at L0-L2** — new constructs must be checkable without running the program
3. **Effect-transparent** — any new op that touches IO/FS/NET must declare it
4. **JCS canonical** — new fields must be sorted alphabetically in the canonical form

## Implementation Order

Suggested order for ジェバンニ (implementation agent):

1. **Overflow ops** — isolated change to `runtime.py` only; no new types needed
2. **Result type** — new type + new ops; medium complexity
3. **Cross-module** — requires CLI changes + multi-file resolution; highest complexity

Start with overflow ops. It is the smallest self-contained unit of work and generates immediate test coverage for the enhanced op system.

## Acceptance Gate

Each feature is complete when:
- All new example `.nail` files pass `nail check` and `nail run`
- All new tests pass
- CI green (all existing tests + new tests)
- ワタリ reviews and approves the PR
