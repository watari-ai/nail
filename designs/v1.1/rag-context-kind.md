# NAIL v1.1 Design: RAG Context Kind

## Status

Draft | Author: Watari | Date: 2026-03-06

---

## Summary

This document specifies `kind: context`, a new top-level kind for NAIL v1.1 that enables
NAIL files to carry RAG-retrieved knowledge as first-class, typed, provenance-annotated
chunks. It allows a RAG pipeline to emit structured NAIL context that AI agents can consume
with full awareness of retrieval quality, temporal validity, and cross-chunk relationships.

---

## Motivation

Current NAIL kinds (`skill`, `persona`, `effect`, etc.) describe *agent capability and
behavior*. There is no native way to represent *retrieved world knowledge* — the data an
agent needs at inference time but that does not belong to its skill definition.

Today, developers work around this by:

1. Injecting raw text into the system prompt (no structure, no confidence, no expiry)
2. Passing JSON blobs outside the NAIL contract (breaks tool-call type safety)
3. Embedding knowledge directly into `persona` or `skill` (wrong abstraction layer)

A dedicated `context` kind solves this by giving RAG-produced facts a proper home inside
the NAIL ecosystem. The pipeline becomes:

```
RAG database
  → NAIL context chunks (.nail, kind: context)
    → AI agent runtime (consumes structured, typed facts)
```

This unlocks native integrations with LlamaIndex, LangChain, and custom retrieval stacks
while keeping the NAIL contract as the single source of truth.

---

## Specification

### New `kind: context`

A `context` document is a self-contained knowledge chunk produced by a retrieval step.
It is designed to be generated programmatically and consumed at agent invocation time.

**Minimal example:**

```nail
kind: context
id: auth_flow_ctx_001
source:
  document_id: "docs/auth/oauth2-flow.md"
  chunk_index: 3
  retrieval_score: 0.91
valid_until: "2026-12-31"
facts:
  - key: "oauth2.pkce_required"
    value: true
    type: bool
    fact_confidence: 0.95
  - key: "oauth2.token_lifetime_seconds"
    value: 3600
    type: int
    fact_confidence: 0.99
relations:
  - target_id: "auth_flow_ctx_002"
    relation: "precedes"
```

**Full JSON Schema (informative):**

```json
{
  "$schema": "https://nail-lang.org/schemas/v1.1/context.json",
  "type": "object",
  "required": ["kind", "id", "source", "facts"],
  "properties": {
    "kind":        { "const": "context" },
    "id":          { "type": "string", "pattern": "^[a-z0-9_-]+$" },
    "source":      { "$ref": "#/$defs/source" },
    "valid_until": { "type": "string", "format": "date" },
    "facts":       { "type": "array", "items": { "$ref": "#/$defs/fact" }, "minItems": 1 },
    "relations":   { "type": "array", "items": { "$ref": "#/$defs/relation" } }
  },
  "$defs": {
    "source": {
      "type": "object",
      "required": ["document_id", "chunk_index", "retrieval_score"],
      "properties": {
        "document_id":     { "type": "string" },
        "chunk_index":     { "type": "integer", "minimum": 0 },
        "retrieval_score": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
      }
    },
    "fact": {
      "type": "object",
      "required": ["key", "value", "type"],
      "properties": {
        "key":             { "type": "string" },
        "value":           {},
        "type":            { "enum": ["string", "int", "float", "bool", "list", "object"] },
        "fact_confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
      }
    },
    "relation": {
      "type": "object",
      "required": ["target_id", "relation"],
      "properties": {
        "target_id": { "type": "string" },
        "relation":  { "enum": ["precedes", "follows", "supports", "contradicts", "elaborates"] }
      }
    }
  }
}
```

---

### Field: `source`

`source` carries the **retrieval provenance** — where the chunk came from and how
confidently it was retrieved.

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `document_id` | string | Yes | Stable identifier of the source document (path, URI, or DB key) |
| `chunk_index` | integer >= 0 | Yes | Zero-based index of this chunk within the source document |
| `retrieval_score` | float [0, 1] | Yes | Cosine similarity / BM25 score from the retrieval step |

`retrieval_score` answers: *"How relevant is this chunk to the query?"*
It is set by the retriever and should not be edited downstream.

---

### Field: `retrieval_score` and `fact_confidence`

The original issue (#111) proposed a single `confidence` field. After implementation
review, Watari proposed splitting it into two distinct scores with different semantics:

| Field | Scope | Set by | Answers |
|-------|-------|--------|---------|
| `source.retrieval_score` | Whole chunk | Retriever | "How relevant is this chunk to the query?" |
| `facts[].fact_confidence` | Individual fact | Knowledge curator / extraction model | "How reliable is this specific fact?" |

**Why the split matters:**

A chunk may be highly relevant to a query (`retrieval_score: 0.95`) yet contain one fact
that is hedged or inferred (`fact_confidence: 0.60`). Conflating these into a single
number would force the agent to treat the entire chunk uniformly.

With separate scores, an agent can apply threshold logic such as:

```
if fact.fact_confidence < 0.7:
    present as "uncertain" to the user
```

`fact_confidence` is **optional** (defaults to implicit 1.0 if omitted) to allow
lightweight, fully-automated pipelines that do not perform per-fact extraction.

---

### Field: `valid_until`

`valid_until` is an ISO 8601 date (`YYYY-MM-DD`) that marks the **temporal horizon**
beyond which the facts in this chunk should no longer be trusted.

- Optional. If absent, the facts are considered perpetually valid.
- The agent runtime **should** compare `valid_until` against the current wall-clock date
  and downgrade or discard stale contexts.
- The L0 checker (Phase B) will emit a `CONTEXT_EXPIRED` warning when a context file
  with a past `valid_until` is loaded.

Use cases:
- Regulatory rules that change on a known date
- API contract versions with a deprecation deadline
- Time-sensitive pricing or availability data

---

### Field: `facts`

`facts` is the **payload** of the context chunk — a list of typed key/value assertions.

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | string | Yes | Dot-notation identifier (e.g. `"oauth2.pkce_required"`) |
| `value` | any | Yes | The asserted value |
| `type` | enum | Yes | One of: `string`, `int`, `float`, `bool`, `list`, `object` |
| `fact_confidence` | float [0, 1] | No | Per-fact reliability score (optional, default 1.0) |

**Design notes:**

- `key` uses dot-notation by convention but is not parsed structurally by NAIL itself.
  Agents may interpret hierarchy as they see fit.
- `type` is required to allow downstream consumers to deserialize `value` without
  heuristics. NAIL validators will type-check `value` against `type` in Phase B.
- The array must contain **at least one** fact (empty context chunks are meaningless).

---

### Field: `relations`

`relations` enables **cross-chunk graph navigation** — a context chunk can declare
semantic relationships to other context chunks by their `id`.

| Sub-field | Type | Required | Description |
|-----------|------|----------|-------------|
| `target_id` | string | Yes | The `id` of the related context document |
| `relation` | enum | Yes | One of: `precedes`, `follows`, `supports`, `contradicts`, `elaborates` |

Relation semantics:

| Value | Meaning |
|-------|---------|
| `precedes` | This chunk describes an earlier step than the target |
| `follows` | This chunk describes a later step than the target |
| `supports` | This chunk provides evidence for the target's claims |
| `contradicts` | This chunk conflicts with the target (agent must reconcile) |
| `elaborates` | This chunk adds detail to the target without contradiction |

Relations are **unidirectional** by default. The Phase B cross-chunk loader may infer
inverses (`precedes` <-> `follows`) automatically.

`relations` is optional. Chunks with no relations are valid standalone units.

---

## Implementation Plan

### Phase A — Ship First

- [x] **Design spec** (this document)
- [ ] **JSON Schema extension** — add `context` to `schemas/v1.1/`
- [ ] **Example file** — `examples/rag/auth_flow_context.nail`

Phase A delivers enough for early adopters to write and validate `context` files
manually. No runtime changes are required.

### Phase B — After Community Feedback

- [ ] **L0 checker support** — validate `kind: context` documents, emit:
  - `CONTEXT_EXPIRED` if `valid_until` is in the past
  - `FACT_TYPE_MISMATCH` if `value` does not match `type`
  - `DANGLING_RELATION` if `target_id` is not found in the loaded context set
- [ ] **`transpiler_sketch.py`** — convert LlamaIndex `NodeWithScore` objects to NAIL context files
- [ ] **Cross-chunk relations loader** — build an in-memory graph from a directory of context files and resolve `relations`

---

## Compatibility

`kind: context` is a **purely additive** extension:

- No existing kinds (`skill`, `persona`, `effect`, `qualifier`, etc.) are modified.
- No existing validators, checkers, or runtimes require changes for Phase A.
- Files using `kind: context` are ignored by consumers that do not recognize the new kind,
  ensuring backward compatibility with v1.0 tooling.

The only breaking surface would be a future enforcement rule that *requires* context
chunks for certain effect kinds — but no such rule is proposed in this document.

---

## Examples

### Example 1: Authentication rules (`auth_flow_context.nail`)

See `examples/rag/auth_flow_context.nail`.

```nail
kind: context
id: auth_flow_ctx_001
source:
  document_id: "docs/auth/oauth2-flow.md"
  chunk_index: 3
  retrieval_score: 0.91
valid_until: "2026-12-31"
facts:
  - key: "oauth2.pkce_required"
    value: true
    type: bool
    fact_confidence: 0.95
  - key: "oauth2.token_lifetime_seconds"
    value: 3600
    type: int
    fact_confidence: 0.99
  - key: "oauth2.supported_grant_types"
    value: ["authorization_code", "client_credentials"]
    type: list
    fact_confidence: 1.0
relations:
  - target_id: "auth_flow_ctx_002"
    relation: "precedes"
```

### Example 2: API specification context

```nail
kind: context
id: payments_api_ctx_001
source:
  document_id: "specs/payments/v3-openapi.yaml"
  chunk_index: 12
  retrieval_score: 0.87
valid_until: "2026-06-30"
facts:
  - key: "payments.max_amount_jpy"
    value: 1000000
    type: int
    fact_confidence: 1.0
  - key: "payments.idempotency_key_required"
    value: true
    type: bool
    fact_confidence: 1.0
  - key: "payments.webhook_retry_policy"
    value: "exponential_backoff_3x"
    type: string
    fact_confidence: 0.88
  - key: "payments.deprecated_endpoint"
    value: "/v2/charge"
    type: string
    fact_confidence: 1.0
relations:
  - target_id: "payments_api_ctx_002"
    relation: "elaborates"
```

---

## Related Issues

- [#110](../../issues/110) Multi-layer LLM interface contracts
- [#111](../../issues/111) RAG Context Kind (parent issue)
