# NAIL v1.1: Routing Hints as Declarative Qualifiers

> **Status**: Draft — pending Boss review (2026-03-05)
> **Issue**: #112
> **Priority**: P2 (v1.1, can slip to v1.2)
> **Author**: watari-ai

---

## Overview

In multi-agent systems, tasks are often dispatched to different LLM tiers — local lightweight
models vs. cloud-hosted heavy models — based on task characteristics such as complexity,
required persona context, or memory access depth. Currently NAIL has no mechanism to
**declare** these characteristics or to **verify** that runtime routing decisions are
consistent with them.

This design adds **routing hint qualifiers** to NAIL task definitions. These are declarative
annotations that express why a task belongs in one tier versus another. The NAIL FC checker
can then flag inconsistencies between declared hints and observed runtime behavior, extending
the existing effect verification model to cover routing decisions.

**Current state**: No routing hint syntax exists. Task routing is entirely opaque to NAIL.
**Delta**: Three new qualifier fields (`complexity_tier`, `persona_required`, `memory_depth`)
are added to task definitions; `nail fc check` gains a new routing consistency check pass.

---

## Proposed Syntax

### Basic usage — light task

```nail
task search_query {
  effects: [NET]
  complexity_tier: "light"
  persona_required: false
  memory_depth: "shallow"
}
```

### Heavy task requiring persona context

```nail
task draft_reply {
  effects: [NET, STATE]
  complexity_tier: "heavy"
  persona_required: true
  memory_depth: "deep"
}
```

### Combined with delegation qualifier (builds on #111)

```nail
task summarize_thread {
  effects: [NET]
  complexity_tier: "light"
  persona_required: false
  memory_depth: "shallow"
  can_delegate: {
    max_delegation_depth: 1
  }
}
```

### Minimal — only complexity hint

Unspecified fields are treated as `unspecified` (no verification emitted for those fields).

```nail
task classify_intent {
  effects: []
  complexity_tier: "light"
}
```

### Error case — inconsistent hints at call site

If a runtime routes `search_query` (declared `complexity_tier: "light"`) to a cloud-tier
agent, `nail fc check` emits:

```
W112: task 'search_query' declares complexity_tier=light
      but runtime trace shows delegation to cloud-tier agent 'gpt-4o'
      → routing decision may be inconsistent with declared hint

W112: task 'classify_intent' declares persona_required=false
      but runtime passed persona context at call site
      → unnecessary context propagation detected
```

---

## Semantics

### Type checker impact

Routing hints are **metadata qualifiers only** — they do not affect the type of the task
nor restrict which other tasks can call it. The type system remains unchanged.

The FC checker gains a new optional pass `--routing-hints` (off by default in v1.1,
opt-in via config flag `nail_fc_routing_hints: true`). This pass:

1. Reads declared hints from the task AST
2. Consumes a runtime trace log (JSONL format, TBD in NATP v1.0 / #114)
3. Emits `W112` warnings (not errors) when routing behavior contradicts hints

Warnings, not errors, because:
- Routing decisions are made by the runtime, not NAIL
- NAIL is declarative; it cannot enforce routing
- A runtime may legitimately override a hint for valid operational reasons

### Relationship to FC (Function Contract)

FC checks already verify that declared `effects` match observed effects at runtime.
Routing hints follow the same pattern:

| Feature            | Declared in NAIL              | Verified by FC checker          |
|--------------------|-------------------------------|---------------------------------|
| Effects            | `effects: [NET]`              | `nail fc check`                 |
| Delegation depth   | `max_delegation_depth: N`     | `nail fc check`                 |
| **Routing hints**  | `complexity_tier: "light"`    | `nail fc check --routing-hints` |

This means routing hints are **first-class FC citizens**: same verification infrastructure,
same warning/error pipeline, same JSONL trace format.

### Qualifier value domains

| Field              | Type        | Values                            |
|--------------------|-------------|-----------------------------------|
| `complexity_tier`  | string enum | `"light"` \| `"heavy"`           |
| `persona_required` | bool        | `true` \| `false`                |
| `memory_depth`     | string enum | `"shallow"` \| `"deep"`          |

All fields are optional. Unspecified = no verification for that field.

---

## Implementation Plan

### Affected files

| File | Change |
|---|---|
| `nail/parser/grammar.lark` | Add routing hint fields to qualifier grammar |
| `nail/parser/ast_nodes.py` | New `RoutingHintQualifier` dataclass |
| `nail/checker/fc_ir_v2.py` | Add `RoutingHints` struct to task IR |
| `nail/checker/fc_checker.py` | New `check_routing_hints()` pass (opt-in) |
| `nail/checker/trace_reader.py` | Parse routing metadata from JSONL trace |
| `nail/cli/check.py` | `--routing-hints` CLI flag |
| `designs/v1.0/spec-freeze.md` | Amendment C: routing hint qualifiers |
| `CHANGELOG.md` | v1.1 entry |

### Estimated test count

- Parser: 8 tests (valid variants, missing fields, unknown enum values)
- AST: 3 tests (dataclass construction, round-trip serialization)
- FC checker routing pass: 15 tests (consistent, inconsistent, opt-in flag off/on)
- CLI integration: 4 tests
- **Total: ~30 new tests**

### Dependency on other issues

| Issue | Relationship |
|---|---|
| #108 | Conceptual precursor — draft design where routing hints first emerged |
| #109 / PR #109 | Phase 1 `can_delegate` — parsing infrastructure to reuse |
| #110 | v1.1 umbrella — routing hints in scope |
| #111 | `max_delegation_depth` — syntax and checker pattern to follow |
| #114 | NATP v1.0 — defines runtime trace JSONL format consumed by `--routing-hints`; if #114 slips, verification pass cannot land |

**Critical path**: #114 (NATP) must define trace format before routing hint verification
can be fully implemented. The qualifier syntax and parser can land independently.

Suggested phasing:
- **v1.1 P2a**: qualifier syntax + parser + AST (no trace dependency)
- **v1.1 P2b**: FC checker routing pass (depends on #114 trace format)

---

## Open Questions

1. **Enum extensibility**: Should `complexity_tier` and `memory_depth` be closed enums
   (`"light"` / `"heavy"`, `"shallow"` / `"deep"`) or open strings? Closed enums enable
   exhaustive checker coverage but may be too rigid for diverse runtimes. Open strings are
   flexible but make verification harder — what does `complexity_tier: "medium"` mean
   to the checker?

2. **Warning vs. error escalation**: Currently proposed as warnings (`W112`) to avoid
   blocking valid runtime overrides. Should there be a per-task `routing_hints_strict: true`
   flag to escalate to errors? If so, how does this interact with the global
   `--routing-hints` opt-in? Risk of combinatorial complexity.

3. **Trace format ownership**: Routing hint verification requires reading a runtime trace
   that records which agent tier handled each task invocation. This format will be defined
   in NATP (#114). If #114 slips to v1.2, should we define a minimal interim trace schema
   in #112 itself, or defer the entire verification pass? Deferring is cleaner but means
   P2a (syntax-only) ships with no observable validation benefit.
