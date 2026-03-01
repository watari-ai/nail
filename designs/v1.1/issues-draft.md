# NAIL v1.1 — Draft GitHub Issues

> **Status**: Draft. Pending Boss review before creation.  
> **Context**: v1.0 RC targets after PR #109 merge. These issues define v1.1 scope.  
> **Rule**: All issues in English per Boss instruction (2/28).

---

## Issue #110 (Umbrella): [meta] NAIL v1.1 planning

**Title**: `[meta] NAIL v1.1 planning`

**Body**:
```
This tracking issue covers the v1.1 milestone, which begins after v1.0 RC ships.

## Design principle
"Extend the periphery, not the frozen core."

L0–L3 / FC Standard / Effect System core are frozen in v1.0 and will not change in v1.1.
v1.1 adds depth within existing extension points (qualifier syntax, effect label namespace).

## Issues in scope for v1.1
- [ ] #111 Delegation Phase 2: `max_delegation_depth` constraint
- [ ] #112 `reversible: false` → type-checked delegation depth limit
- [ ] #113 Effect System: AUDIT and DELEG label additions
- [ ] #114 NATP v1.0 specification (NAIL Agent Transfer Protocol)

## Out of scope for v1.1 (deferred to later)
- WASM compilation target
- Async / Concurrency model
- L4 Memory safety layer

## Timeline
- v1.0 RC: after #107 (PR #109) merges
- v1.1 design sprint: begins after v1.0 RC ships
- v1.1 RC: TBD based on community feedback
```

**Labels**: `meta`, `v1.1`

---

## Issue #111: Delegation Phase 2: `max_delegation_depth`

**Title**: `feat: Delegation Phase 2 — max_delegation_depth qualifier`

**Body**:
```
## Background

Phase 1 (PR #109 / Issue #107) introduced `can_delegate` as a qualifier field.
Phase 2 adds `max_delegation_depth` to bound how many re-delegation hops are allowed.

## Design decision: dynamic over static

After analysis (see #108 comment), we adopt **dynamic runtime enforcement** rather than static analysis.

Rationale:
- Static call-graph analysis fails under open-world assumption (external agents unknown at lint time)
- Dynamic dispatch (tool names in variables) cannot be statically resolved
- Runtime hop counter is simple, predictable, and easy to test

Rejected alternative: static corollary graph walk (too fragile across module boundaries).

## Proposed syntax

```nail
task write_sensitive {
  effects: [FS]
  can_delegate: {
    max_delegation_depth: 1   # only one re-delegation hop allowed
    reversible: false
  }
}
```

## Runtime semantics

- Each NAIL runtime context carries a `delegation_depth: int` field (default: 0)
- When task A delegates to task B, depth increments by 1
- If `depth > max_delegation_depth` → raise `DelegationDepthError`
- Depth resets when a new top-level invocation begins

## Authority gradient (stretch goal for Phase 2)

Track `origin_id` through the chain: A → B → C → D preserves A's identity
as the root authority. Allows `grants` to be scoped to origin, not just caller.

## Acceptance criteria
- [ ] `fc_ir_v2.py`: `max_delegation_depth` field on `EffectQualifier`
- [ ] Runtime context: `delegation_depth` counter
- [ ] `check_call`: enforce depth limit, raise `DelegationDepthError`
- [ ] Tests: depth enforcement, chain propagation, reset behavior (≥ 30 new tests)
- [ ] Spec: update `designs/v1.0/spec-freeze.md` Amendment B
- [ ] CHANGELOG entry

Related: #107 (Phase 1), #108 (Draft design)
```

**Labels**: `enhancement`, `v1.1`, `delegation`

---

## Issue #112: `reversible: false` → typed constraint on delegation depth

**Title**: `feat: reversible: false implies max_delegation_depth: 0 default`

**Body**:
```
## Background

In Phase 1 (PR #109), `reversible: false` is metadata-only — it doesn't affect type rules.

Phase 2 should give `reversible: false` a semantic consequence:
**an irreversible task may not be delegated further unless `max_delegation_depth` is explicitly set.**

## Proposed rule

```
if task.reversible == false and task.can_delegate is set:
    if max_delegation_depth is not explicitly specified:
        default max_delegation_depth = 0  # no re-delegation
```

Explicit override is allowed:
```nail
task delete_user {
  effects: [STATE, NET]
  can_delegate: {
    reversible: false
    max_delegation_depth: 1   # explicit: allows exactly 1 hop
  }
}
```

## Rationale

Irreversible actions carry the highest risk of uncorrectable errors.
Constraining their delegation depth by default adds a safety margin
without removing flexibility (explicit override is always available).

## Acceptance criteria
- [ ] Checker: apply default depth=0 when `reversible: false` and depth unspecified
- [ ] Tests: default enforcement, explicit override, interaction with Phase 2 depth checker
- [ ] Spec: Amendment B updated to include this rule

Depends on: #111
```

**Labels**: `enhancement`, `v1.1`, `delegation`, `safety`

---

## Issue #113: Effect System — AUDIT and DELEG label additions

**Title**: `feat: new effect labels AUDIT and DELEG`

**Body**:
```
## Background

v1.0 freezes five effect labels: FS, NET, EXEC, UI, STATE.
Two additional labels were identified during Phase 2 design as natural extensions.

## Proposed additions

### AUDIT
Signals that the task writes to an audit log or observability sink.

```nail
task log_access {
  effects: [AUDIT]
}
```

Semantic intent: AUDIT is write-only, append-only. 
A task with only AUDIT effect cannot read existing state or affect control flow.
This allows runtime systems to safely permit AUDIT in otherwise restricted contexts.

### DELEG
Signals that the task performs agent-to-agent delegation.

```nail
task orchestrate {
  effects: [DELEG]
  can_delegate: { max_delegation_depth: 2 }
}
```

Semantic intent: any task that spawns sub-agents or calls external agent APIs
should declare DELEG. This makes delegation visible at the effect level,
not just at the qualifier level.

## Implementation notes
- Add AUDIT and DELEG to the effect label enum in `fc_ir_v2.py`
- Update `check_program` to validate AUDIT (no read-state operations)
- Update spec: extend effect label table
- Add to naillang.com playground dropdown

## Acceptance criteria
- [ ] `fc_ir_v2.py`: AUDIT and DELEG labels
- [ ] AUDIT semantic check (write-only)
- [ ] Tests: AUDIT allowed/disallowed contexts, DELEG with delegation qualifier (≥ 20 tests)
- [ ] Spec updated
- [ ] Playground updated

Related: #107 (Phase 1 effects), #111 (DELEG + max_delegation_depth interaction)
```

**Labels**: `enhancement`, `v1.1`, `effects`

---

## Issue #114: NATP v1.0 Specification (NAIL Agent Transfer Protocol)

**Title**: `spec: NATP v1.0 — NAIL Agent Transfer Protocol`

**Body**:
```
## Background

`zyom45/nail-a2a` (v0.1.0) demonstrated NAIL as an adapter layer over Google A2A protocol.
NATP v1.0 generalizes this: NAIL as a **protocol-agnostic envelope** for agent-to-agent communication.

## Concept

Instead of inventing a new wire protocol, NATP uses NAIL spec files as the message format:

```
Agent A ──[NAIL spec]──► Agent B
         tasks: [...]
         effects: [...]
         grants: [...]
```

Any transport can carry a NAIL spec. The spec is the contract.

## NATP v1.0 requirements

1. **Envelope format**: NAIL task+effect+grants section as the standard message
2. **Discovery**: how agents advertise their NAIL-compatible surface (minimal; URI-based)
3. **Error model**: how `DelegationError` and effect violations are communicated back
4. **Versioning**: `spec_version` field (already in NAIL spec) as the compatibility signal

## nail-a2a v0.2 as PoC

- Implement NATP draft in `zyom45/nail-a2a` v0.2
- Collect feedback from implementation
- Reflect in NATP v1.0 final spec
- Include NATP v1.0 in NAIL v1.1 spec (or as companion document)

## Acceptance criteria
- [ ] `designs/natp/v1.0-draft.md`: envelope format, discovery, error model, versioning
- [ ] nail-a2a v0.2 PoC implementing the draft
- [ ] At least one end-to-end example (two NAIL agents communicating over NATP)
- [ ] NAIL v1.1 spec references NATP v1.0

Related: zyom45/nail-a2a
```

**Labels**: `spec`, `v1.1`, `natp`

---

## Next steps (after Boss review)

1. Merge PR #109 (Issue #107 — Phase 1)
2. Create issues #110–#114 on watari-ai/nail
3. Begin v1.1 design sprint with #111 (Phase 2) as first implementation target
4. nail-a2a v0.2 can proceed in parallel with #114

> Note: issues #104, #105, #106 (demos) can be closed after PR #109 merges.
