# NAIL v1.1 Design: Routing Hints as Declarative Qualifiers

## Status

Draft | Author: Watari | Date: 2026-03-06

---

## Summary

This document specifies a set of new **routing hint qualifiers** for NAIL v1.1 that allow
developers to declare, at the NAIL file level, how an effect should be routed between
local and cloud LLMs, how sensitive the data is, and whether user-specific context is
required. These qualifiers are consumed by the NAIL runtime and the `nail fc check`
checker.

---

## Motivation

As NAIL-powered systems grow to coordinate multiple LLM backends — local models (e.g.
Ollama, mlx-lm) alongside cloud APIs (e.g. OpenAI, Anthropic) — the decision of *where*
to route an inference call is currently made entirely outside the NAIL contract, in
ad-hoc application code.

This creates a gap:

- Developers cannot express routing intent in the skill/effect definition itself.
- The checker has no surface to validate routing mismatches.
- Privacy constraints (data residency, PII) are enforced by convention rather than
  contract.
- Load planning is impossible without knowing the expected token budget at declaration
  time.

Routing hint qualifiers close this gap by making routing intent a first-class NAIL
declaration, auditable by `nail fc check` and readable by orchestration runtimes.

---

## Specification

### New Qualifiers

The following qualifiers are added to the `qualifier` vocabulary for NAIL v1.1.
They may appear on any `kind: effect` document.

---

#### `complexity_tier`

```nail
complexity_tier: "light" | "heavy"
```

| Value | Meaning |
|-------|---------|
| `"light"` | Suitable for a local or small model (e.g. summarization, classification, short-form generation). Route to local LLM by preference. |
| `"heavy"` | Requires a capable cloud model (e.g. multi-step reasoning, code generation, long-context synthesis). Route to cloud LLM by preference. |

`complexity_tier` is a **soft hint** by default (see [Soft Hints vs Hard Constraints](#soft-hints-vs-hard-constraints)).
The runtime may override it based on current load or availability, unless `routing: "strict"` is set.

---

#### `persona_required`

```nail
persona_required: true | false
```

When `true`, the effect requires access to user-specific context (memory, preferences,
history, or identity data). The runtime must ensure that a persona layer with the
appropriate user context is loaded before invoking this effect.

When `false` (default), the effect is stateless with respect to the user and can be
served without any personal data.

This qualifier interacts with privacy enforcement: setting `persona_required: true`
while `privacy_tier` is absent triggers a linting warning (see [Linting Rules](#linting-rules)).

---

#### `privacy_tier`

```nail
privacy_tier: "public" | "internal" | "confidential"
```

| Value | Meaning |
|-------|---------|
| `"public"` | Data handled by this effect is non-sensitive and may transit any backend. |
| `"internal"` | Data is internal to the organization. Cloud LLMs may be used, but data must not be logged or retained by the provider. |
| `"confidential"` | Data is PII or otherwise highly sensitive. Must be processed by a local model only; must not leave the host. |

The runtime **should** enforce `privacy_tier: "confidential"` by refusing to route to
external APIs. `nail fc check` will emit a `ROUTING_PRIVACY_VIOLATION` error if a
`"confidential"` effect is observed routing to a cloud endpoint (Phase B, strict mode).

---

#### `estimated_tokens` *(optional)*

```nail
estimated_tokens: <int>
```

An optional hint indicating the expected total token budget (prompt + completion) for a
typical invocation of this effect. Used by orchestration runtimes for load planning,
queue prioritization, and cost estimation.

This field does not affect routing decisions by default. It may be used by strict-mode
schedulers in Phase B to reject invocations that would exceed a configured budget.

There is no validation of the declared value against actual usage in Phase A.

---

### Soft Hints vs Hard Constraints

By default, all routing qualifiers are **soft hints**. The runtime is free to deviate
from the declared intent based on operational conditions (model unavailability, queue
depth, fallback policies).

To upgrade hints to **hard constraints**, set:

```nail
routing: "strict"
```

When `routing: "strict"` is present:

- `complexity_tier: "heavy"` → runtime **must** use a cloud model; local fallback is forbidden.
- `complexity_tier: "light"` → runtime **must** use a local model; cloud escalation is forbidden.
- `privacy_tier: "confidential"` → runtime **must** refuse any cloud routing; will raise
  a runtime error rather than silently fall back.

`routing: "strict"` is a Phase B feature. In Phase A, the field is parsed and stored but
has no runtime enforcement. `nail fc check` will emit an `UNIMPLEMENTED_STRICT_ROUTING`
informational note when it encounters `routing: "strict"` during Phase A.

---

### Interaction with Effect Qualifiers

Routing hint qualifiers are composable with existing effect qualifiers defined in v1.0
(e.g. `locality`, `max_delegation_depth`).

Key interactions:

| Combination | Behavior |
|-------------|----------|
| `privacy_tier: "confidential"` + `locality: pass` | Checker emits `ROUTING_PRIVACY_LEAK` warning — confidential data should not be passed across layers to a potentially remote model. |
| `complexity_tier: "heavy"` + `max_delegation_depth: 0` | Contradictory: heavy effects typically need delegation. Checker emits `ROUTING_DEPTH_CONFLICT` informational note. |
| `persona_required: true` + `privacy_tier: "public"` | Allowed but suspicious — personal context is being used for a public-tier effect. Checker emits `ROUTING_PERSONA_PUBLIC` advisory. |

---

### Linting Rules

The following rules are enforced by `nail fc check` in Phase A (warnings) and Phase B
(errors in strict mode).

| Rule ID | Trigger | Severity | Message |
|---------|---------|----------|---------|
| `ROUTING_PRIVACY_MISSING` | Effect has a `NET` effect type AND `privacy_tier` is not set | Warning | `privacy_tier not set on NET effect; data residency is unspecified` |
| `ROUTING_PERSONA_NO_PRIVACY` | `persona_required: true` AND `privacy_tier` is absent | Warning | `persona_required is true but privacy_tier is not declared` |
| `ROUTING_PRIVACY_LEAK` | `privacy_tier: "confidential"` AND `locality: pass` | Warning | `confidential data may transit a remote layer via locality:pass` |
| `ROUTING_DEPTH_CONFLICT` | `complexity_tier: "heavy"` AND `max_delegation_depth: 0` | Info | `heavy complexity tier with zero delegation depth may be unintentional` |
| `ROUTING_PERSONA_PUBLIC` | `persona_required: true` AND `privacy_tier: "public"` | Advisory | `persona context used in a public-tier effect` |
| `UNIMPLEMENTED_STRICT_ROUTING` | `routing: "strict"` present in Phase A | Info | `strict routing is declared but not enforced until Phase B` |
| `ROUTING_PRIVACY_VIOLATION` | `privacy_tier: "confidential"` observed routing to cloud endpoint *(Phase B, strict)* | Error | `confidential effect routed to external API` |

**`NET` effect note:** Any effect that performs network I/O (classified as `NET` in the
effect type system) without a declared `privacy_tier` is a data residency risk. Phase A
surfaces this as a warning to encourage adoption; Phase B may promote it to an error for
`routing: "strict"` files.

---

## Implementation Plan (Phase A / B)

### Phase A — Specification + Syntax + Checker Warnings

Deliverables:

- [x] **Design spec** (this document)
- [ ] **JSON Schema extension** — add `complexity_tier`, `persona_required`,
  `privacy_tier`, `estimated_tokens`, `routing` to `schemas/v1.1/qualifiers.json`
- [ ] **`nail fc check` extension** — implement linting rules:
  `ROUTING_PRIVACY_MISSING`, `ROUTING_PERSONA_NO_PRIVACY`, `ROUTING_PRIVACY_LEAK`,
  `ROUTING_DEPTH_CONFLICT`, `ROUTING_PERSONA_PUBLIC`, `UNIMPLEMENTED_STRICT_ROUTING`
- [ ] **Example files** — `examples/routing/` (see [Examples](#examples))
- [ ] **Docs update** — add routing hints to the v1.1 qualifier reference

Phase A ships zero runtime changes. Routing decisions remain in application code;
NAIL only lints the declarations.

### Phase B — Strict Mode + `estimated_tokens` Enforcement

Deliverables:

- [ ] **Runtime enforcement of `routing: "strict"`** — route resolver respects hard
  constraints; raises `RoutingConstraintError` on violation
- [ ] **`ROUTING_PRIVACY_VIOLATION` checker rule** — requires runtime telemetry integration
- [ ] **`estimated_tokens` budget enforcement** — scheduler rejects invocations exceeding
  configured per-effect budget (opt-in via `nail.config` flag `routing.enforce_token_budget`)
- [ ] **Documentation: migration guide** — upgrading soft-hint deployments to strict mode

---

## Compatibility

Routing hint qualifiers are **purely additive**:

- No existing kinds, effects, or qualifiers are modified.
- Files without routing qualifiers behave identically to v1.0.
- `nail fc check` only emits new warnings; it does not break existing passing checks.
- Runtimes that do not recognize routing qualifiers will ignore them safely.

The `routing: "strict"` field is parsed in Phase A but has no effect until Phase B,
ensuring that files authored during Phase A remain valid when Phase B ships.

---

## Examples

### Example 1: Light local effect, no personal data

```nail
kind: effect
id: summarize_article
complexity_tier: "light"
persona_required: false
privacy_tier: "public"
estimated_tokens: 800
```

Interpretation: Route to local LLM, no user context needed, data is public.
`nail fc check` passes with no warnings.

---

### Example 2: Heavy cloud effect with user context

```nail
kind: effect
id: generate_personalized_report
complexity_tier: "heavy"
persona_required: true
privacy_tier: "internal"
estimated_tokens: 4000
```

Interpretation: Route to cloud LLM, load user persona first, data must not be retained
by the provider. `nail fc check` passes; runtime should enforce provider data retention
policy for `internal` tier.

---

### Example 3: Confidential local-only effect (strict)

```nail
kind: effect
id: analyze_medical_record
complexity_tier: "heavy"
persona_required: true
privacy_tier: "confidential"
routing: "strict"
estimated_tokens: 2000
```

Interpretation: Must use local model; cloud routing is forbidden. `nail fc check`
emits `UNIMPLEMENTED_STRICT_ROUTING` (Phase A info note). Phase B runtime will enforce
and raise `RoutingConstraintError` if a cloud endpoint is attempted.

---

### Example 4: NET effect missing privacy_tier → linting warning

```nail
kind: effect
id: fetch_and_summarize
effect_type: NET
complexity_tier: "light"
persona_required: false
# privacy_tier intentionally omitted to demonstrate linting
```

`nail fc check` output:

```
WARNING ROUTING_PRIVACY_MISSING: fetch_and_summarize — privacy_tier not set on NET effect; data residency is unspecified
```

---

### Example 5: persona_required without privacy_tier → linting warning

```nail
kind: effect
id: user_greeting
persona_required: true
complexity_tier: "light"
# privacy_tier omitted
```

`nail fc check` output:

```
WARNING ROUTING_PERSONA_NO_PRIVACY: user_greeting — persona_required is true but privacy_tier is not declared
```

---

## Related Issues

- [#108](../../issues/108) Delegation depth tracking (Phase 2)
- [#110](../../issues/110) Multi-layer LLM interface contracts
- [#111](../../issues/111) RAG Context Kind
- [#112](../../issues/112) Routing hints as declarative qualifiers (parent issue)
