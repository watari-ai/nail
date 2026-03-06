# NAIL v1.1 Design: Delegation Depth Tracking

## Status

Draft | Author: Watari | Date: 2026-03-06

---

## Summary

This document specifies **delegation depth tracking** for NAIL v1.1 — a runtime
enforcement mechanism that bounds how many re-delegation hops a task may traverse.
The mechanism is realised as a `max_delegation_depth` field inside the existing
`can_delegate` qualifier block, backed by a per-invocation `delegation_depth` counter
maintained by the NAIL runtime.

---

## Motivation

NAIL v1.0 introduced `can_delegate` as a boolean qualifier: a task either permits
further delegation or it does not. This binary model is insufficient for real-world
agent hierarchies, where the concern is not delegation itself but **unbounded**
delegation.

Consider a three-agent chain: Orchestrator → Specialist → SubAgent. The Orchestrator
explicitly intends to delegate to the Specialist, but never intends for the Specialist
to further delegate to an arbitrary SubAgent. Under v1.0, once `can_delegate: true` is
set, there is no in-spec way to express this boundary.

Without depth bounds:
- Sensitive effects (e.g. `FS_WRITE`, `STATE`) can propagate arbitrarily deep.
- Irreversible actions (e.g. file deletion, data mutation) can reach agents that were
  never audited for those responsibilities.
- Authority provenance becomes opaque: the origin task that held the effect grant is
  obscured by intermediaries.

`max_delegation_depth` closes this gap by allowing authors to declare, **in the
specification language itself**, the maximum number of additional hops a task may
undergo after it is first invoked.

---

## Design Decision: Dynamic vs Static Enforcement

Two enforcement strategies were evaluated:

### Why Not Static Analysis

Static call-graph analysis was the initial candidate. In principle, a linter could walk
the delegation chain at `nail fc check` time and verify that no path exceeds the declared
depth.

This approach was **rejected** for the following reasons:

1. **Open-world assumption**: NAIL agents operate in environments where not all agents
   are known at lint time. An orchestrator may delegate to an agent whose NAIL file is
   loaded from a remote registry, a plugin, or a dynamically composed manifest.
   Static analysis cannot inspect what it cannot see.

2. **Dynamic dispatch**: Tool and task names are frequently resolved at runtime from
   variables, user input, or routing tables. A static checker cannot follow a call of
   the form `invoke(selected_tool, payload)` where `selected_tool` is determined at
   runtime.

3. **False confidence**: A static checker that passes under closed-world assumptions
   would silently fail to catch violations that only appear at runtime — the worst
   possible failure mode for a safety property.

Static analysis may still be provided as an **optional informational pass** (Phase B)
for closed, fully-specified agent graphs, but it is not the primary enforcement
mechanism.

### Why Dynamic Runtime Enforcement

Runtime enforcement was adopted as the primary mechanism because:

1. **Completeness**: A runtime counter catches every delegation, regardless of how the
   call was resolved — static, dynamic, or cross-module.

2. **Simplicity**: A single integer field (`delegation_depth`) on the runtime context
   is the entire implementation surface. No graph traversal, no module loading.

3. **Predictability**: The runtime counter is deterministic and inspectable. It can be
   logged, traced, and asserted in tests without mocking a static analysis pass.

4. **Testability**: Depth enforcement, chain propagation, and reset behaviour can all be
   covered by straightforward unit tests (target: ≥ 30 new tests, see #111).

5. **Composability**: The counter composes naturally with other runtime state (grants,
   effect budgets, audit logs) without requiring a separate analysis phase.

**Decision**: Adopt dynamic runtime enforcement as the sole mandatory mechanism.
Static analysis is deferred to Phase B as an opt-in informational feature.

---

## Specification

### `can_delegate` block

The `can_delegate` qualifier block is extended with two new optional fields:

```nail
task write_sensitive {
  effects: [FS]
  can_delegate: {
    max_delegation_depth: 1
    reversible: false
  }
}
```

**Full field reference for `can_delegate`:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `max_delegation_depth` | integer >= 0 | No | unlimited | Maximum number of re-delegation hops permitted after the initial invocation |
| `reversible` | bool | No | `true` | Whether the task's effects can be undone. When `false`, applies additional delegation constraints (see `reversible: false` interaction) |

**Semantics of `max_delegation_depth`:**

- `0` — the task may not delegate to any further task.
- `1` — the task may delegate once; the delegated task may not delegate further.
- `N` — exactly N additional hops are permitted beyond the initial invocation.
- Absent — no depth constraint is applied (equivalent to v1.0 behaviour when `can_delegate` is truthy).

**Validation:**

- `max_delegation_depth` must be a non-negative integer. Negative values are a schema
  error (`INVALID_DEPTH_VALUE`).
- If `can_delegate` is absent or falsy, `max_delegation_depth` is meaningless and
  should not be specified (checker emits `DEPTH_WITHOUT_DELEGATE` warning).

---

### Runtime Context: `delegation_depth`

Each NAIL runtime invocation context carries a `delegation_depth` field:

```
RuntimeContext {
  task_id:          string
  effect_grants:    Set<EffectLabel>
  delegation_depth: int      // default: 0
  origin_id:        string?  // stretch: authority gradient (see Examples)
}
```

**Lifecycle rules:**

1. **Initialisation**: When a new top-level invocation begins (i.e. the call originates
   from outside any active NAIL context), `delegation_depth` is set to `0`.

2. **Propagation**: When task A delegates to task B, the runtime passes B a context
   where `delegation_depth = A.context.delegation_depth + 1`.

3. **Enforcement**: Before executing task B, the runtime checks:
   ```
   if A.max_delegation_depth is set:
       if B.context.delegation_depth > A.max_delegation_depth:
           raise DelegationDepthError(
               task=B.id,
               depth=B.context.delegation_depth,
               max=A.max_delegation_depth
           )
   ```

4. **Reset**: When a new top-level invocation begins, `delegation_depth` is reset to `0`.
   Concurrent invocations each maintain their own independent counter.

5. **Isolation**: Each invocation context is isolated. A deeply nested chain in one
   concurrent execution does not affect the counter of another.

---

### `DelegationDepthError`

Raised when a delegation attempt would exceed the declared `max_delegation_depth`.

**Error structure:**

```
DelegationDepthError {
  code:       "DELEGATION_DEPTH_EXCEEDED"
  task_id:    string    // ID of the task that attempted the delegation
  target_id:  string    // ID of the task that would have been delegated to
  depth:      int       // current depth at the point of the attempted delegation
  max_depth:  int       // declared max_delegation_depth on the source task
  message:    string    // human-readable description
}
```

**Example error message:**
```
DelegationDepthError: task 'write_sensitive' attempted to delegate to 'archive_records'
at depth 2, but max_delegation_depth is 1.
```

**Propagation:**

`DelegationDepthError` is a hard error. It is not catchable within the NAIL task that
caused it. It propagates to the caller of the originating top-level invocation, which
is responsible for handling or logging it.

**Checker rule (Phase A — static warning only):**

| Rule ID | Trigger | Severity |
|---------|---------|----------|
| `INVALID_DEPTH_VALUE` | `max_delegation_depth` is negative | Error |
| `DEPTH_WITHOUT_DELEGATE` | `max_delegation_depth` set without `can_delegate` | Warning |
| `DEPTH_ALWAYS_ZERO` | `max_delegation_depth: 0` with `can_delegate: true` | Warning (contradictory) |

---

### `reversible: false` interaction

When `reversible: false` is set on a task's `can_delegate` block, the following
additional rule applies (Issue #112):

> **If `reversible: false` and `max_delegation_depth` is not explicitly specified,
> the runtime treats `max_delegation_depth` as `0`.**

This means an irreversible task that permits delegation at all will, by default, allow
**no further re-delegation** from its delegatee.

An explicit override is always permitted:

```nail
task delete_user {
  effects: [STATE, NET]
  can_delegate: {
    reversible: false
    max_delegation_depth: 1   # explicit: one hop allowed despite irreversibility
  }
}
```

**Rationale**: Irreversible actions carry the highest risk of uncorrectable errors.
Defaulting to depth-0 for irreversible tasks adds a safety margin without removing
flexibility — a deliberate choice is always one field away.

**Checker enforcement (Phase A):**

The checker emits an informational note when `reversible: false` is combined with an
explicit `max_delegation_depth > 0`, reminding authors that the override is intentional:

```
NOTE: task 'delete_user' sets reversible: false with max_delegation_depth: 1.
Irreversible tasks default to depth 0; this explicit override is intentional.
```

---

## Implementation Plan

### Phase A — Specification + Schema + Runtime Core

Deliverables:

- [x] **Design spec** (this document)
- [ ] **JSON Schema extension** — add `max_delegation_depth` (integer, >= 0) and
  `reversible` (bool) to `schemas/v1.1/can_delegate.json`
- [ ] **`fc_ir_v2.py`** — add `max_delegation_depth: Optional[int]` field to
  `EffectQualifier` dataclass
- [ ] **Runtime context** — add `delegation_depth: int = 0` to `RuntimeContext`
- [ ] **`check_call`** — enforce depth limit; raise `DelegationDepthError`
- [ ] **`reversible: false` default** — apply depth-0 default in checker/runtime when
  `reversible: false` and depth unspecified
- [ ] **Static checker rules** — `INVALID_DEPTH_VALUE`, `DEPTH_WITHOUT_DELEGATE`,
  `DEPTH_ALWAYS_ZERO`
- [ ] **Tests** — depth enforcement, chain propagation, reset behaviour, `reversible`
  interaction (≥ 30 new tests)
- [ ] **CHANGELOG entry**

### Phase B — Advanced Enforcement + Authority Gradient

Deliverables:

- [ ] **`origin_id` tracking** — propagate the root task's identity through the
  delegation chain (authority gradient; see Example 3)
- [ ] **`grants` scoped to origin** — allow `grants` blocks to reference `origin_id`
  as a constraint (e.g. "only accept this grant if the origin is task X")
- [ ] **Static informational pass** — optional closed-world graph walk for fully
  specified agent graphs (emits `DEPTH_MAY_EXCEED_STATIC` info note; not a hard error)
- [ ] **Structured logging** — emit `delegation_depth` to the NAIL audit log on every
  delegation event
- [ ] **AUDIT effect integration** — tasks that record delegation events should declare
  `effects: [AUDIT]` (#113); Phase B formalises this interaction
- [ ] **Documentation: migration guide** — upgrading from unqualified `can_delegate`
  to depth-bounded delegation

---

## Compatibility

Delegation depth tracking is **purely additive**:

- Tasks that do not specify `max_delegation_depth` behave identically to v1.0.
- The `delegation_depth` runtime counter is internal; it does not appear in any
  existing NAIL output format.
- `nail fc check` static rules are new; they do not change the result of any
  currently passing check.
- Runtimes that do not implement `delegation_depth` will ignore the field and treat
  delegation as unbounded (v1.0 behaviour). A future strict-mode flag may make the
  counter mandatory.
- `reversible: false` defaulting to depth-0 applies **only** when `can_delegate` is
  also present. Legacy tasks with `reversible: false` but no `can_delegate` are
  unaffected.

---

## Examples

### Example 1: Single hop allowed

An orchestrator task delegates to a worker, but prevents the worker from delegating
further.

```nail
# orchestrator.nail
task orchestrate_write {
  effects: [FS, NET]
  can_delegate: {
    max_delegation_depth: 1
  }
}

# worker.nail
task write_chunk {
  effects: [FS]
  can_delegate: {
    max_delegation_depth: 0   # explicit; cannot delegate further
  }
}
```

**Runtime trace:**

```
top-level call → orchestrate_write   (depth: 0)
  delegates to → write_chunk         (depth: 1)  ← depth == max; OK
    delegates to → any_task          (depth: 2)  ← depth > max on write_chunk (0); DelegationDepthError
```

`DelegationDepthError` is raised at the second delegation attempt. `orchestrate_write`
itself could still attempt another delegation at depth 1 (within its own max of 1).

---

### Example 2: No delegation (depth 0)

A sensitive deletion task is permitted to have `can_delegate` declared (so the
qualifier block can carry metadata), but is prohibited from re-delegating.

```nail
task delete_records {
  effects: [STATE, FS]
  can_delegate: {
    max_delegation_depth: 0
    reversible: false
  }
}
```

Any attempt to delegate from `delete_records` immediately raises `DelegationDepthError`
at depth 1 > 0.

**With `reversible: false` and no explicit depth:**

```nail
task delete_records_v2 {
  effects: [STATE, FS]
  can_delegate: {
    reversible: false
    # max_delegation_depth not set → defaults to 0 per #112 rule
  }
}
```

Both declarations are semantically equivalent.

---

### Example 3: Authority gradient (stretch)

*(Phase B target)* Track the root authority through a multi-hop chain so that
downstream tasks can verify they are executing on behalf of a trusted origin.

```nail
# Chain: A → B → C
task task_a {
  effects: [NET, STATE]
  can_delegate: {
    max_delegation_depth: 2
  }
}

task task_b {
  effects: [NET]
  can_delegate: {
    max_delegation_depth: 1
    grants: [{ to: "task_c", scoped_to_origin: "task_a" }]
  }
}

task task_c {
  effects: [NET]
  # leaf; no further delegation
}
```

**Runtime context at each hop (Phase B):**

```
task_a invoked   → depth: 0, origin_id: "task_a"
  → task_b       → depth: 1, origin_id: "task_a"  (propagated)
    → task_c     → depth: 2, origin_id: "task_a"  (propagated)
```

`task_c` can verify that the invocation originates from `task_a` and reject calls
from any other root. This enables **origin-scoped grants**: a permission that is only
valid when the ultimate authority is the declared origin.

---

## Related Issues

- [#107](../../issues/107) Effect Qualifiers Phase 1 (prerequisite — introduces `can_delegate`)
- [#108](../../issues/108) Delegation Depth Tracking (this issue)
- [#110](../../issues/110) Multi-layer LLM interface contracts (architectural complement)
- [#111](../../issues/111) Delegation Phase 2: `max_delegation_depth` (implementation issue)
- [#112](../../issues/112) `reversible: false` implies `max_delegation_depth: 0` default
- [#113](../../issues/113) Effect System: AUDIT and DELEG label additions (DELEG interacts with delegation qualifier)
