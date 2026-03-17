# NAIL v1.1 Design: Multi-Layer LLM Interface Contracts

## Status

Draft | Author: Watari | Date: 2026-03-06

---

## Summary

This document specifies **multi-layer LLM interface contracts** for NAIL v1.1 — a
mechanism that allows developers to declare, in the NAIL file itself, the interface
boundaries between hierarchically-coordinated LLM layers (e.g. L1: Claude, L2: GPT-4,
L3: local model). Each layer declares what inputs it accepts, what outputs it may return,
and what effects it is permitted to produce. Upper layers may delegate tasks to lower
layers only within the bounds of the declared contract.

---

## Motivation

Modern AI systems increasingly chain multiple LLM backends in hierarchical arrangements:
a capable frontier model orchestrates mid-tier models, which in turn delegate narrow
subtasks to efficient local models. Today, the boundaries between these layers are
enforced only by convention — nothing in the system's specification language prevents an
L1 from delegating a privileged action to an L3 that was never designed to handle it.

NAIL v1.0 introduced effect qualifiers and delegation depth (`#107`, `#108`), but these
operate at the function level. There is no native way to describe **architectural-layer
contracts** — the guaranteed interface that every agent at a given layer must honour.

Multi-layer contracts close this gap:

- Developers declare each layer's identity, locality, allowed inputs, allowed outputs, and
  permitted effects in a single NAIL document.
- The `nail fc check` linter enforces that delegation chains never escalate privileges
  from a lower layer to a higher one, and never leak retained fields across layers.
- Combined with routing hints (`#112`), the runtime can verify not just *what* is
  delegated, but *where* it will execute.

The goal is the same as for all NAIL design: push correctness into the **specification
language**, not the runtime.

---

## Specification

### Layer Declaration (`layer` qualifier)

A `layer` block is a top-level key added to any NAIL file that participates in a
multi-layer contract. It declares the layer's identity and its position in the hierarchy.

```nail
layer:
  id: "l1_orchestrator"
  level: 1
  locality: "cloud"         # "local" | "cloud" | "hybrid"
  model_hint: "claude-3-5"  # informative, not enforced
  delegates_to:
    - "l2_specialist"
    - "l2_reviewer"
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier for this layer within the contract set |
| `level` | integer >= 1 | Yes | Hierarchy depth. Level 1 is the topmost orchestrator |
| `locality` | enum | Yes | Execution context: `"local"`, `"cloud"`, or `"hybrid"` |
| `model_hint` | string | No | Informative model identifier (not validated) |
| `delegates_to` | list<string> | No | Layer IDs this layer is permitted to delegate to |

**Design notes:**

- `level` is a logical declaration, not a runtime counter. It allows the checker to detect
  inversion anomalies (e.g. an L3 delegating to an L1).
- `delegates_to` is an allowlist. If absent, the layer may not delegate to any other
  layer. An empty list is equivalent to absent.
- A layer NAIL file that omits the `layer` block is treated as a single-layer contract
  (backward compatible with v1.0).

---

### Interface Contract per Layer

Each layer declares the typed boundary of its interface using three sub-blocks:
`accepts`, `returns`, and `effects`.

```nail
layer:
  id: "l2_specialist"
  level: 2
  locality: "cloud"
  delegates_to:
    - "l3_local_embed"

  accepts:
    - name: "task_description"
      type: string
      required: true
    - name: "context_chunks"
      type: list
      required: false
    - name: "retain:user_id"   # deprecated style; use visibility: retain as canonical
      type: string
      required: true
      visibility: retain    # never passed to sub-layers

  returns:
    - name: "result_text"
      type: string
    - name: "confidence"
      type: float

  effects:
    allow:
      - NET
      - KNOWLEDGE
    deny:
      - FS_WRITE
      - EXEC
```

**`accepts` fields:**

| Sub-field | Type | Description |
|-----------|------|-------------|
| `name` | string | Field name. `retain:` prefix is legacy and deprecated; use `visibility` instead |
| `type` | enum | One of: `string`, `int`, `float`, `bool`, `list`, `object` |
| `required` | bool | Whether this field must be present in the invocation |
| `visibility` | enum | `"pass"` (default) or `"retain"` — controls delegation behaviour |

`retain:prefix` is retained for backward compatibility only. Canonical form in v1.1 is:
use plain `name` + explicit `visibility: retain`.

**`visibility: retain` semantics:**

A field marked `retain` is consumed by this layer only. It MUST NOT appear in any
payload passed to a sub-layer during delegation. The checker emits `DELEGATION_LEAK` if a
`retain` field is observed in a downstream delegation call.

**`effects` block:**

`allow` lists effect types this layer may produce. `deny` lists effect types explicitly
forbidden, regardless of what the invoked function might request. If `deny` is absent,
only the `allow` list applies. If both are absent, no effect restrictions are imposed (not
recommended).

If the same effect appears in both `effects.allow` and `effects.deny`, `deny` takes
precedence.

---

### Delegation Rules (what L1 can delegate to L2)

Delegation from an upper layer to a lower layer is governed by three rules:

**Rule 1: Allowlist-only delegation**

A layer may only delegate to layers explicitly listed in its `delegates_to`. Any
delegation attempt to an unlisted layer causes the checker to emit `DELEGATION_UNLISTED`.

**Rule 2: Effect monotonicity (no privilege escalation)**

A lower-level layer's `effects.allow` set must be a subset of (or equal to) the
delegating layer's `effects.allow` set. A delegation that would grant the sub-layer an
effect type the parent does not hold causes `EFFECT_ESCALATION`.

```
L1.effects.allow = {NET, KNOWLEDGE}
L2.effects.allow = {NET, KNOWLEDGE, FS_WRITE}   <- EFFECT_ESCALATION
```

**Rule 3: Retain field isolation**

No `retain`-marked field from the parent layer may appear in the invocation payload sent
to the sub-layer. Violations cause `DELEGATION_LEAK`.

**Summary of checker rules:**

| Rule ID | Trigger | Severity |
|---------|---------|----------|
| `DELEGATION_UNLISTED` | Delegation to a layer not in `delegates_to` | Error |
| `EFFECT_ESCALATION` | Sub-layer `effects.allow` is a superset of parent's | Error |
| `DELEGATION_LEAK` | `retain` field appears in sub-layer invocation payload | Error |
| `LAYER_LEVEL_INVERSION` | Higher `level` number delegating to a lower number | Warning |
| `DELEGATION_CYCLE` | Delegation graph contains a cycle | Error |
| `LOCALITY_VIOLATION` | `locality: "local"` layer receives a cloud-routed delegation | Warning (Phase B: Error in strict mode) |

---

### Cross-Layer Effect Propagation

When an effect is triggered deep in the delegation chain, it propagates upward through
the layer stack. The runtime records which layer originally permitted the effect; the
checker may verify propagation paths in Phase B.

**Propagation rules:**

1. An effect produced by L3 is attributed to L3's `effects.allow`.
2. If L2 delegated to L3, L2 implicitly "owns" the side-effect budget for that call.
3. If L3 produces an effect not in L2's `effects.allow`, the runtime should raise
   `EFFECT_PROPAGATION_VIOLATION` (Phase B).

In Phase A, propagation is declared only; runtime enforcement is deferred.

```nail
# Phase A: declarative annotation only
layer:
  id: "l2_specialist"
  propagates_effects: true    # opt-in flag; default false
```

When `propagates_effects: true`, the checker will verify (in Phase B) that any effect
produced by sub-layers is also present in this layer's `effects.allow`.

---

### Interaction with Routing Hints (#112)

Routing hints (`complexity_tier`, `privacy_tier`, `persona_required`) operate at the
**effect level**. Layer contracts operate at the **architectural level**. Together, they
provide two complementary validation surfaces:

| Concern | Governed by |
|---------|-------------|
| Which model tier to use for this call | `complexity_tier` (routing hint) |
| Whether personal data may leave the host | `privacy_tier` (routing hint) |
| Which layers this layer may delegate to | `delegates_to` (layer contract) |
| Which effects a layer may produce | `effects.allow` / `effects.deny` (layer contract) |
| Where the layer physically executes | `locality` (layer contract) |

**Joint validation example:**

```nail
layer:
  id: "l1_orchestrator"
  level: 1
  locality: "cloud"
  delegates_to: ["l2_local"]

kind: effect
id: classify_intent
complexity_tier: "light"
privacy_tier: "confidential"
routing: "strict"
```

The checker will emit:

- `ROUTING_PRIVACY_MISSING` if `privacy_tier` is absent on a NET effect (routing hint rule)
- `DELEGATION_UNLISTED` if L1 tries to delegate to a layer not in `delegates_to` (layer contract rule)
- `LOCALITY_PRIVACY_CONFLICT` if a `privacy_tier: "confidential"` effect is delegated to a
  `locality: "cloud"` sub-layer (joint rule, Phase B)

**Joint rule `LOCALITY_PRIVACY_CONFLICT`:**

| Trigger | Severity |
|---------|----------|
| `privacy_tier: "confidential"` effect delegated to a `locality: "cloud"` sub-layer | Error (Phase B) |

---

### Interaction with RAG Context Kind (#111)

RAG context chunks (`kind: context`) may be attached to a layer invocation as part of the
`accepts` payload. Layer contracts govern which layers may receive context chunks and
whether those chunks may be forwarded downstream.

```nail
layer:
  id: "l1_orchestrator"
  level: 1
  locality: "cloud"
  delegates_to: ["l2_specialist"]

  accepts:
    - name: "rag_context"
      type: list           # list of kind:context documents
      required: false
      visibility: pass     # allowed to forward to L2
```

**Rules for context forwarding:**

1. A `retain`-visibility context field must not be forwarded (same `DELEGATION_LEAK` rule).
2. If a context chunk has `valid_until` in the past, the checker emits `CONTEXT_EXPIRED`
   before the chunk enters the delegation chain (Phase B).
3. `retrieval_score` thresholds are not enforced at the layer contract level; they are the
   responsibility of the RAG pipeline that produced the chunks.

This ensures that stale or sensitive RAG knowledge does not inadvertently propagate into
lower-trust layers.

---

## Implementation Plan (Phase A / B)

### Phase A — Specification + Syntax + Static Checks

Deliverables:

- [x] **Design spec** (this document)
- [ ] **JSON Schema extension** — add `layer` block schema to `schemas/v1.1/layer.json`
- [ ] **`nail fc check` extension** — implement:
  - `DELEGATION_UNLISTED`
  - `EFFECT_ESCALATION`
  - `DELEGATION_LEAK`
  - `LAYER_LEVEL_INVERSION`
  - `DELEGATION_CYCLE`
  - `LOCALITY_VIOLATION` (warning only)
- [ ] **Example files** — `examples/multi-layer/` (see Examples section)
- [ ] **Docs update** — add layer contracts to the v1.1 qualifier reference

Phase A ships zero runtime changes. All checks are static.

### Phase B — Runtime Enforcement + Joint Rules

Deliverables:

- [ ] **Runtime effect propagation tracking** — attribute effects to originating layers
- [ ] **`EFFECT_PROPAGATION_VIOLATION`** — runtime check when sub-layer produces
  an effect not in the parent's `effects.allow`
- [ ] **`LOCALITY_PRIVACY_CONFLICT`** — joint checker rule (layer contract + routing hint)
- [ ] **`propagates_effects` enforcement** — validate propagation paths in checker
- [ ] **`CONTEXT_EXPIRED` in delegation chain** — gate stale context at layer boundary
- [ ] **Documentation: migration guide** — moving from untyped delegation to layer contracts

---

## Compatibility

Layer contracts are **purely additive**:

- No existing kinds, effects, or qualifiers are modified.
- Files without a `layer` block behave identically to v1.0.
- `nail fc check` only emits new rules; it does not break existing passing checks.
- Runtimes that do not recognise the `layer` block will ignore it safely.
- The `delegates_to` allowlist defaults to empty (deny-all) only when `layer` is
  explicitly declared; legacy files without `layer` are unaffected.

---

## Examples

### Example 1: Two-Layer Code Review

**L1 — Cloud Orchestrator** (`examples/multi-layer/code-review-l1.nail`)

```nail
layer:
  id: "cr_orchestrator"
  level: 1
  locality: "cloud"
  model_hint: "claude-3-5"
  delegates_to:
    - "cr_reviewer"

  accepts:
    - name: "pull_request_diff"
      type: string
      required: true
    - name: "retain:author_token"
      type: string
      required: true
      visibility: retain     # auth token stays in L1

  returns:
    - name: "review_summary"
      type: string
    - name: "approved"
      type: bool

  effects:
    allow:
      - NET
      - KNOWLEDGE
    deny:
      - FS_WRITE
      - EXEC

kind: effect
id: orchestrate_review
complexity_tier: "heavy"
privacy_tier: "internal"
persona_required: false
```

**L2 — Cloud Reviewer** (`examples/multi-layer/code-review-l2.nail`)

```nail
layer:
  id: "cr_reviewer"
  level: 2
  locality: "cloud"
  model_hint: "gpt-4o"
  delegates_to: []           # leaf layer; no further delegation

  accepts:
    - name: "pull_request_diff"
      type: string
      required: true
    # author_token is NOT here — retained by L1

  returns:
    - name: "review_comments"
      type: list
    - name: "score"
      type: float

  effects:
    allow:
      - KNOWLEDGE
    deny:
      - NET
      - FS_WRITE
      - EXEC

kind: effect
id: review_diff
complexity_tier: "heavy"
privacy_tier: "internal"
persona_required: false
```

**Checker output (valid contract):** No errors. `author_token` is correctly retained in
L1 and absent from L2's `accepts`. L2's `effects.allow` is a subset of L1's. ✓

---

### Example 2: Three-Layer Agent Hierarchy

```
L1 (Claude, cloud) → orchestrates tasks
  └── L2 (GPT-4, cloud) → specialist reasoning
        └── L3 (local LLM, Ollama) → embedding + classification
```

**L1** (`examples/multi-layer/hierarchy-l1.nail`)

```nail
layer:
  id: "h_orchestrator"
  level: 1
  locality: "cloud"
  delegates_to:
    - "h_specialist"

  accepts:
    - name: "user_query"
      type: string
      required: true
    - name: "retain:session_token"
      type: string
      required: true
      visibility: retain

  returns:
    - name: "final_answer"
      type: string

  effects:
    allow:
      - NET
      - KNOWLEDGE
      - PERSONA
```

**L2** (`examples/multi-layer/hierarchy-l2.nail`)

```nail
layer:
  id: "h_specialist"
  level: 2
  locality: "cloud"
  delegates_to:
    - "h_local_embed"
  propagates_effects: true

  accepts:
    - name: "user_query"
      type: string
      required: true
    # session_token intentionally absent

  returns:
    - name: "structured_answer"
      type: object

  effects:
    allow:
      - KNOWLEDGE
      - NET
    deny:
      - PERSONA
      - FS_WRITE
```

**L3** (`examples/multi-layer/hierarchy-l3.nail`)

```nail
layer:
  id: "h_local_embed"
  level: 3
  locality: "local"
  delegates_to: []

  accepts:
    - name: "text"
      type: string
      required: true

  returns:
    - name: "embedding"
      type: list
    - name: "label"
      type: string

  effects:
    allow:
      - KNOWLEDGE
    deny:
      - NET
      - PERSONA
      - FS_WRITE
      - EXEC

kind: effect
id: embed_and_classify
complexity_tier: "light"
privacy_tier: "confidential"   # stays local
routing: "strict"
```

**Checker output:**

- L3 `effects.allow` ⊆ L2 `effects.allow` ⊆ L1 `effects.allow` ✓
- `session_token` absent from L2 and L3 `accepts` ✓
- `privacy_tier: "confidential"` on L3 + `locality: "local"` — no `LOCALITY_PRIVACY_CONFLICT` ✓
- `routing: "strict"` on L3 → `UNIMPLEMENTED_STRICT_ROUTING` info note (Phase A)

---

## Related Issues

- [#107](../../issues/107) Effect Qualifiers Phase 1 (prerequisite)
- [#108](../../issues/108) Delegation Depth Tracking (complementary)
- [#110](../../issues/110) Multi-layer LLM interface contracts (parent issue)
- [#111](../../issues/111) RAG Context Kind (interacts with context forwarding)
- [#112](../../issues/112) Routing Hints as Declarative Qualifiers (interacts with locality + privacy)
