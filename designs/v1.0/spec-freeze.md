# NAIL v1.0 Spec Freeze Declaration

**Status**: Draft — Ready for Review  
**Created**: 2026-02-28  
**Authors**: NAIL Core Team  
**Applies to**: NAIL v1.0.0 and all future v1.x implementations

---

## 1. What "Frozen" Means

The NAIL v1.0 spec freeze declares that all elements listed in §2 are **immutable** going forward:

- No field removals, renames, or type changes without a `NAIL-2.0` major bump.
- Any document valid under NAIL-1.0 is **guaranteed to remain valid** in all NAIL-1.x implementations.
- Optional fields may be added (minor bump) but may never be made required without a major bump.

Deprecation follows the policy defined in `designs/v0.9/spec-versioning-policy.md §3`:

> A deprecated feature must remain **fully functional** for a minimum of **2 minor versions** after the deprecation notice before removal (which requires a major bump).

Example: a feature deprecated in NAIL-1.1 cannot be removed before NAIL-2.0.

---

## 2. Frozen Elements (v1.0)

### 2.1 JSON Root Structure

The `kind` discriminator field and all associated required fields are frozen:

| `kind` value | Required fields |
|---|---|
| `"fn"` | `nail`, `kind`, `id`, `effects`, `params`, `returns`, `body` |
| `"module"` | `nail`, `kind`, `id`, `exports`, `defs` |
| `"tool_spec"` | `nail`, `kind`, `id`, `doc`, `input`, `effects` |

The `nail` version field and `meta.spec_version` semantics (required from v1.0 stable onward) are frozen.

### 2.2 Core Opcodes

The following opcodes and their field contracts are frozen:

| Category | Opcodes |
|---|---|
| Control flow | `return`, `if`/`else`, `loop` |
| Variables | `let`, `assign` |
| Arithmetic | `+`, `-`, `*`, `/`, `%` (with `overflow` policy) |
| Comparison | `eq`, `neq`, `lt`, `lte`, `gt`, `gte` |
| Logical | `and`, `or`, `not` |
| Function call | `call` |
| Effectful ops | `print`, `read_file`, `http_get`, `exec_cmd` |
| Collections | `list_get`, `list_push`, `list_len`, `list_map`, `list_filter`, `list_fold`, `list_slice`, `list_contains`, `map_get`, `map_set`, `map_has`, `map_keys`, `map_values` |
| ADT | `enum_make`, `match_enum` |
| Result | `match_result`, `unwrap_ok`, `unwrap_err` |

### 2.3 Type System

All primitive and composite types are frozen:

`int` · `float` · `bool` · `string` · `bytes` · `unit` · `option<T>` · `list<T>` · `map<K,V>` · `result<T,E>` · `enum` (ADT) · type aliases · generic type aliases (`type_params`)

Overflow modes `panic` / `wrap` / `sat` (expression-level) are frozen.  
`null` non-existence is a language invariant — use `option` instead.

### 2.4 Effect Annotations

The effect system is frozen in both forms:
- **String form**: `"FS"`, `"NET"`, `"IO"`, `"TIME"`, `"RAND"`, `"MUT"`, `"REPO"` — declarative, no runtime value restriction
- **Structured capability form**: `{"kind": "FS"|"NET", "allow": [...], "ops": [...]}` — runtime-enforced allowlist (only `"FS"` and `"NET"` support structured form; other kinds are a compile error)

Effect propagation rules (callee effects ⊆ caller effects) are frozen. MCP Bridge ops (`from_mcp`, `to_mcp`, `infer_effects`) are **not frozen** (see §3).

### 2.5 FC Standard Format

The `nail_lang.fc_standard` API and the `tool_spec` JSON format with an `effects` array are frozen. The round-trip guarantee (NAIL ↔ OpenAI ↔ Anthropic ↔ Gemini) is a stability commitment.

### 2.6 Checker Levels

| Level | Description | Status |
|---|---|---|
| L0 | JSON schema + canonical form | Frozen |
| L1 | Type checking | Frozen |
| L2 | Effect checking (static + runtime) | Frozen |
| L3 | Termination proof (minimum guarantee only; `measure` annotation semantics frozen; L3.1 extended requirements TBD for v1.1) | Partially frozen |

Canonical form (JCS-inspired, `sort_keys=True`, compact separators) is frozen.

### 2.7 `meta.spec_version` Semantics

From v1.0 stable, `meta.spec_version` is a **required field**. The value must be a string matching `"NAIL-{major}.{minor}"`. Checkers emit `UNSUPPORTED_SPEC_VERSION` on unrecognised values. This contract is frozen.

---

## 3. Not Frozen — Reserved for Post-1.0

The following are explicitly **out of scope** for v1.0 and may change freely:

- **LSP support** — Language Server Protocol integration (Nail-Lens)
- **WASM compilation** — NAIL → WebAssembly target
- **Async / Concurrency model** — full design pending (cancellation, timeout, join/await)
- **NATP** — NAIL-format AI Agent Protocol for inter-agent task delegation
- **Dialect extensions** — `nail-finance`, `nail-embedded`, `nail-web`, and other domain-specific layers
- **L4: Memory safety** — buffer overflow proofs (deferred)
- **L3.1 extended requirements** — extended termination proof requirements beyond `measure` annotations (TBD for v1.1)
- **Effect Security Audit Log** — formal FS/NET permission boundary spec (deferred)
- **MCP Bridge ops** — `from_mcp`, `to_mcp`, `infer_effects` (dependent on external MCP spec; may evolve independently)

---

## 4. Breaking Change Examples

### Would require NAIL-2.0

- Renaming `effects` to `capabilities` in function definitions
- Adding a required field to `kind: "fn"` root structure
- Changing `"overflow": "panic"` semantics
- Tightening L0 validation to reject documents valid under NAIL-1.0
- Promoting any existing WARN error code to ERROR
- Removing any frozen opcode

### Safely addable as NAIL-1.1

- New optional field in `tool_spec` (e.g., `"tags": [...]`)
- New optional effect string (e.g., `"DB"`)
- New stdlib builtin function
- New CLI flag (e.g., `--annotate-effects`)
- New WARN error code
- Relaxed validation rule (e.g., `doc` minimum length reduced)

---

## 5. Conformance Reference

Alternative NAIL implementations must pass the conformance test suite located at `conformance/` (45 tests as of v0.9.0, covering L0 / L1 / L2 / L3 / FC). Passing all tests is the **minimum bar** for claiming NAIL-1.0 conformance.

Conformance declaration format (for implementation READMEs):

```
Conformance: NAIL-1.0 (L0–L3 + FC)
Test suite: PASS 45/45
```

Partial conformance (e.g., L0–L2 without L3) is valid and must be declared explicitly:

```
Conformance: NAIL-1.0 (L0–L2)
Test suite: PASS 38/45 (L3 not implemented)
```

See `designs/v0.9/spec-versioning-policy.md §5` for the full implementer checklist.

---

## 6. Effective Date

**To be set when this PR is merged and approved.**

Once the effective date is stamped:

1. `SPEC.md` version line is updated to `v1.0`.
2. `meta.spec_version` becomes a required field (checkers emit `FC013 ERROR` if absent).
3. This document moves from Draft to **Ratified**.
4. A `NAIL-1.0.0` git tag is created.
