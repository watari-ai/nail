# NAIL Conformance Test Suite

**Document version**: 0.1.0  
**Status**: Draft  
**Created**: 2026-02-26  
**Applies to**: NAIL v0.9.x and beyond  
**Audience**: Alternative implementers (Rust, Go, etc.), external contributors

---

## 1. Purpose

The NAIL Conformance Test Suite is a **portable, implementation-agnostic** set of test cases that verifies whether an alternative NAIL checker correctly implements the NAIL specification.

### Problem Statement

The reference implementation (`nail_lang`, Python) has **683 tests** (as of v0.9) covering interpreter behaviour, runtime execution, and internal APIs. However, these tests:

- Depend on Python internals and import paths
- Test runtime execution, not just checker semantics
- Include implementation details that are not part of the spec
- Cannot be run against a Rust or Go reimplementation without porting

### Goal

The Conformance Test Suite is a **minimal, self-contained** set of **JSON-driven test cases** that:

1. Tests only behaviours mandated by the NAIL specification
2. Can be driven from any language via a simple CLI contract
3. Provides a clear PASS/FAIL signal with machine-readable output
4. Serves as the acceptance criterion for declaring an implementation "conformant"

### What Conformance Means

> An implementation is **NAIL-conformant at level N** if it passes all Conformance Test Suite cases at levels 0 through N.

Partial conformance (e.g., L0+L1 but not L2) is explicitly supported and should be declared.

---

## 2. Test Categories

Tests are grouped into **levels** that correspond to layers of the NAIL checker, plus a separate **FC Standard** category for tool-calling IR.

### Level Overview

| Level | Name | Description | Mandatory |
|-------|------|-------------|-----------|
| **L0** | JSON Schema | Structural validity of NAIL documents | ✅ |
| **L1** | Type Check | Type system correctness | ✅ |
| **L2** | Effect Check | Effect propagation and violation detection | ✅ |
| **L3** | Termination | Loop/recursion termination proofs | Optional |
| **FC** | FC Standard | fc_ir_v1 format validation and provider conversion | ✅ |

### L0 — JSON Schema

Tests that the checker correctly accepts or rejects documents based on their **structural** validity, without evaluating semantics.

**Acceptance tests** (must not produce errors):
- Minimal valid module with one function
- Module with all optional fields present
- Function with no parameters
- Empty `types` object
- Function body with every valid `op` type

**Rejection tests** (must produce ERROR):
- Missing required top-level field (e.g., `nail` key absent)
- `kind` field with unknown value
- `params` is not an array
- `body` is not an array
- Type reference with unknown `type` string
- Nested type with missing required sub-field (e.g., `list` missing `inner`)

### L1 — Type Check

Tests that the checker detects **type errors** in function bodies and function signatures.

**Acceptance tests** (must not produce errors):
- Binary arithmetic on matching int types
- String concatenation
- `if` branches with matching return types
- `let` binding with correct type annotation
- `call` with argument types matching parameter types
- Optional unwrapping with correct fallback type
- Enum variant construction and match
- Generic function instantiation

**Rejection tests** (must produce `E_TYPE_*` or equivalent ERROR):
- Arithmetic between int and string
- `if` branches returning different types
- `let` annotation mismatching inferred type
- `call` with wrong argument count
- `call` with argument type mismatch
- Returning wrong type from function
- Accessing non-existent field on object type

### L2 — Effect Check

Tests that the checker correctly **propagates effects** and rejects functions that declare insufficient effects.

**Acceptance tests** (must not produce errors):
- PURE function with no IO ops
- Function declaring `IO` that calls `stdout`
- Function calling an IO function and also declaring `IO`
- Transitive effect propagation through a call chain

**Rejection tests** (must produce `E_EFFECT_*` or equivalent ERROR):
- Function calling `stdout` without declaring `IO`
- PURE function calling an IO function
- Function calling a `FS` function without declaring `FS`
- Effect category mismatch in fine-grained mode (e.g., `IO:stdout` vs `IO:stdin`)

### L3 — Termination (Optional)

Tests the **termination proof verifier** for loops and recursion. Implementations may skip this level and declare `L3: NOT IMPLEMENTED`.

**Acceptance tests** (must not produce errors):
- Loop with a decreasing integer measure
- Recursive function with decreasing measure passed to recursive call
- Tail-recursive function with valid measure

**Rejection tests** (must produce `E_TERMINATION_*` or equivalent ERROR):
- Loop missing a `measure` declaration
- Recursive call that does not decrement the measure
- Recursive call with `measure - k` where k ≤ 0
- Mutual recursion without measure propagation

### FC — FC Standard

Tests `nail fc check` behaviour for fc_ir_v1 documents.

**Acceptance tests** (must not produce errors):
- Minimal valid fc_ir_v1 with one PURE tool
- Tool with all optional fields present
- Tool with `optional` typed parameter
- Tool with `enum` type
- Tool with `annotations` containing arbitrary keys

**Rejection tests** (must produce ERROR):
- Duplicate `id` values → FC001
- Name collision between auto-generated names → FC002
- `input` not of type `object` → FC003
- PURE tool with non-empty `allow` → FC004
- Unknown field outside `annotations` in `--strict` mode → FC011

**WARN tests** (must produce WARN, not ERROR, in normal mode):
- Missing `output` field → FC006 WARN
- `doc` shorter than 20 characters → FC010 WARN
- Legacy string-array effects format → FC009 WARN
- Unknown field outside `annotations` (normal mode) → FC011 WARN

---

## 3. Test Format

Each test case is a **self-contained JSON object** stored in a single file inside `conformance/cases/`.

### Schema

```json
{
  "id": "L2-001",
  "category": "effect-check",
  "description": "IO effect propagation - caller missing effect declaration",
  "input": {
    "nail": "0.1.0",
    "kind": "module",
    "functions": [
      {
        "id": "log_message",
        "effects": [],
        "params": [{ "name": "msg", "type": { "type": "string" } }],
        "returns": { "type": "unit" },
        "body": [
          { "op": "stdout", "value": { "op": "var", "name": "msg" } }
        ]
      }
    ]
  },
  "expected": "CHECK_ERROR",
  "error_code": "E_EFFECT_MISSING",
  "level": 2
}
```

### Field Definitions

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `id` | ✅ | string | Unique stable identifier. Format: `{CATEGORY}-{NNN}` |
| `category` | ✅ | string | One of: `schema`, `type-check`, `effect-check`, `termination`, `fc-check` |
| `description` | ✅ | string | Human-readable explanation of what is being tested |
| `input` | ✅ | object | The NAIL document or fc_ir_v1 document to check |
| `expected` | ✅ | string | One of: `ACCEPT`, `CHECK_ERROR`, `CHECK_WARN` |
| `error_code` | ❌ | string | When `expected` is `CHECK_ERROR` or `CHECK_WARN`, the canonical error code expected |
| `level` | ✅ | integer | The conformance level this test belongs to (0–3 or 99 for FC) |
| `tags` | ❌ | array | Optional string tags for filtering (e.g., `["regression", "generics"]`) |
| `notes` | ❌ | string | Implementation notes or links to spec sections |

### `expected` Values

| Value | Meaning |
|-------|---------|
| `ACCEPT` | The checker must accept the input without any ERROR or WARN |
| `ACCEPT_WITH_WARN` | The checker must accept (exit 0) but at least one WARN must be present |
| `CHECK_ERROR` | The checker must produce at least one ERROR (exit code 1) |
| `CHECK_WARN` | The checker must produce at least one WARN (exit code 0 unless `--fail-on-warn`) |

### Error Code Conventions

Error codes are **canonical identifiers** defined by the NAIL spec. They are stable across patch versions.

| Prefix | Domain |
|--------|--------|
| `E_SCHEMA_*` | L0 structural errors |
| `E_TYPE_*` | L1 type errors |
| `E_EFFECT_*` | L2 effect errors |
| `E_TERMINATION_*` | L3 termination errors |
| `FC001`–`FC012` | FC Standard errors (see fc-ir-v1.md §8) |

### Complete Examples

**L0 acceptance test:**
```json
{
  "id": "L0-001",
  "category": "schema",
  "description": "Minimal valid module with one pure function",
  "input": {
    "nail": "0.1.0",
    "kind": "module",
    "functions": [
      {
        "id": "add",
        "effects": [],
        "params": [
          { "name": "a", "type": { "type": "int", "bits": 64, "overflow": "panic" } },
          { "name": "b", "type": { "type": "int", "bits": 64, "overflow": "panic" } }
        ],
        "returns": { "type": "int", "bits": 64, "overflow": "panic" },
        "body": [
          { "op": "return", "value": { "op": "add", "left": { "op": "var", "name": "a" }, "right": { "op": "var", "name": "b" } } }
        ]
      }
    ]
  },
  "expected": "ACCEPT",
  "level": 0
}
```

**L1 rejection test:**
```json
{
  "id": "L1-005",
  "category": "type-check",
  "description": "Type mismatch: adding int and string",
  "input": {
    "nail": "0.1.0",
    "kind": "module",
    "functions": [
      {
        "id": "bad_add",
        "effects": [],
        "params": [
          { "name": "n", "type": { "type": "int", "bits": 64, "overflow": "panic" } },
          { "name": "s", "type": { "type": "string" } }
        ],
        "returns": { "type": "int", "bits": 64, "overflow": "panic" },
        "body": [
          { "op": "return", "value": { "op": "add", "left": { "op": "var", "name": "n" }, "right": { "op": "var", "name": "s" } } }
        ]
      }
    ]
  },
  "expected": "CHECK_ERROR",
  "error_code": "E_TYPE_MISMATCH",
  "level": 1
}
```

**FC WARN test:**
```json
{
  "id": "FC-020",
  "category": "fc-check",
  "description": "Missing output field emits FC006 WARN",
  "input": {
    "kind": "fc_ir_v1",
    "tools": [
      {
        "id": "math.add",
        "doc": "Adds two integers and returns the result without side effects.",
        "effects": { "kind": "capabilities", "allow": [] },
        "input": {
          "type": "object",
          "properties": {
            "a": { "type": "int" },
            "b": { "type": "int" }
          },
          "required": ["a", "b"]
        }
      }
    ]
  },
  "expected": "ACCEPT_WITH_WARN",
  "error_code": "FC006",
  "level": 99,
  "notes": "output is recommended but not required. Absence should produce FC006 WARN, not ERROR."
}
```

---

## 4. Extraction Policy from Existing Tests

The reference implementation currently has **683 tests** across 23 test files. Not all of them belong in the conformance suite. Use the following criteria to determine inclusion.

### 4.1 Include in Conformance Suite

| Criterion | Rationale |
|-----------|-----------|
| Tests spec-mandated checker behaviour (ACCEPT/REJECT) | Core conformance |
| Tests a specific error code defined in the spec | Error codes are part of the public API |
| Tests canonicalization rules (field order, compact JSON) | Spec defines canonical form |
| Tests FC diagnostic codes (FC001–FC012) | Spec-defined diagnostics |
| Tests effect propagation rules | Core L2 behaviour |
| Tests type checking rules | Core L1 behaviour |

**Priority source files** (high yield for conformance extraction):

| File | Tests | Conformance relevance |
|------|-------|----------------------|
| `tests/test_interpreter.py` | 144 | L0–L2: many schema + type + effect tests |
| `tests/test_effects_fine_grained.py` | 35 | L2: direct effect check tests |
| `tests/test_fc_cli.py` | 26 | FC: fc_ir_v1 diagnostic codes |
| `tests/test_fc_standard.py` | 35 | FC: provider conversion |
| `tests/test_function_calling.py` | 44 | L1+FC: type system for tools |
| `tests/test_structured_errors.py` | 22 | L0–L2: error code format |
| `tests/test_l3_termination.py` | 26 | L3: termination proofs |
| `tests/test_l31_call_site_measure.py` | 28 | L3: call-site measure verification |

### 4.2 Exclude from Conformance Suite

| Criterion | Rationale |
|-----------|-----------|
| Tests Python runtime execution (numeric result of a computation) | Runtime behaviour is beyond spec scope for checkers |
| Tests internal APIs (`Checker` class methods, `Runtime` internals) | Implementation detail |
| Tests Python-to-NAIL transpiler (`test_transpiler.py`) | Tool-specific, not spec |
| Tests MCP Bridge protocol (`test_mcp_bridge.py`) | Protocol layer, not checker spec |
| Tests `nail_lang` Python SDK API (`test_nail_lang_api.py`) | Python binding, not spec |
| Tests that depend on file system layout or relative paths | Not portable |
| Tests for specific demo exit codes (`test_issue_82_demo_exit_code.py`) | Bug regression, not spec |

**Low-yield source files** (exclude or minimal extraction):

| File | Tests | Reason for exclusion |
|------|-------|----------------------|
| `tests/test_transpiler.py` | 37 | Transpiler is a tool, not part of the spec |
| `tests/test_mcp_bridge.py` | 26 | MCP protocol, not checker spec |
| `tests/test_nail_lang_api.py` | 35 | Python SDK API |
| `tests/test_runtime_generic_aliases.py` | 8 | Runtime execution, not checker |
| `tests/test_issue_82_demo_exit_code.py` | 12 | CLI demo regression |

### 4.3 Initial Extraction Target

Target: **~150 conformance cases** drawn from the existing test suite.

| Level | Target count | Primary source |
|-------|-------------|----------------|
| L0 | ~40 | `test_interpreter.py` (schema tests), `test_structured_errors.py` |
| L1 | ~50 | `test_interpreter.py` (type tests), `test_generics.py`, `test_type_aliases.py`, `test_enum.py` |
| L2 | ~40 | `test_effects_fine_grained.py`, `test_interpreter.py` (effect tests) |
| L3 | ~20 | `test_l3_termination.py`, `test_l31_call_site_measure.py` |
| FC | ~30 | `test_fc_cli.py`, `test_fc_standard.py` |
| **Total** | **~180** | |

---

## 5. Repository Structure

```
nail/
└── conformance/
    ├── README.md                  # How to run the suite and declare conformance
    ├── runner/
    │   ├── run.py                 # Reference runner (Python, uses nail_lang)
    │   └── cli_contract.md        # Contract for alternative runners (stdin/stdout protocol)
    ├── cases/
    │   ├── L0/                    # JSON Schema tests
    │   │   ├── L0-001.json
    │   │   ├── L0-002.json
    │   │   └── ...
    │   ├── L1/                    # Type Check tests
    │   │   ├── L1-001.json
    │   │   └── ...
    │   ├── L2/                    # Effect Check tests
    │   │   ├── L2-001.json
    │   │   └── ...
    │   ├── L3/                    # Termination tests (optional)
    │   │   ├── L3-001.json
    │   │   └── ...
    │   └── FC/                    # FC Standard tests
    │       ├── FC-001.json
    │       └── ...
    ├── index.json                 # Machine-readable index of all cases
    └── results/
        └── .gitkeep              # Local result files are gitignored
```

### `index.json` Format

```json
{
  "spec_version": "NAIL-0.9",
  "generated_at": "2026-02-26T00:00:00Z",
  "total": 180,
  "by_level": {
    "0": { "count": 40, "mandatory": true },
    "1": { "count": 50, "mandatory": true },
    "2": { "count": 40, "mandatory": true },
    "3": { "count": 20, "mandatory": false },
    "99": { "count": 30, "mandatory": true }
  },
  "cases": [
    { "id": "L0-001", "file": "cases/L0/L0-001.json", "level": 0, "expected": "ACCEPT" },
    { "id": "L1-005", "file": "cases/L1/L1-005.json", "level": 1, "expected": "CHECK_ERROR" }
  ]
}
```

---

## 6. CLI Contract for Alternative Runners

Alternative implementations must expose a command-line interface with the following contract to be driven by the conformance runner.

### Checker Interface

```bash
# Check a NAIL module document
your-checker check <input.json> [--strict] [--fail-on-warn]

# Check a fc_ir_v1 document
your-checker fc check <input.json> [--strict] [--fail-on-warn]
```

**Exit codes:**
- `0` — No errors (WARNs may be present)
- `1` — At least one ERROR present

**Output format** (stdout, one diagnostic per line):
```
[{CODE}] {SEVERITY}: {MESSAGE}
  at {location}
```

Where `SEVERITY` is `ERROR` or `WARN`.

### Result Reporting

The conformance runner collects results and emits a summary:

```
NAIL Conformance Test Suite — NAIL-0.9
Implementation: your-checker v1.0.0

L0 (schema):      40/40  PASS ✅
L1 (type-check):  50/50  PASS ✅
L2 (effect-check):38/40  FAIL ❌  (2 failures: L2-023, L2-037)
L3 (termination): SKIPPED (not implemented)
FC (fc-standard): 30/30  PASS ✅

Conformance level: NAIL-0.9 L0–L1–FC (L2 PARTIAL: 38/40)
```

Machine-readable output (`--json`):

```json
{
  "spec_version": "NAIL-0.9",
  "implementation": "your-checker",
  "impl_version": "1.0.0",
  "timestamp": "2026-02-26T00:05:00Z",
  "results": {
    "L0": { "passed": 40, "failed": 0, "total": 40 },
    "L1": { "passed": 50, "failed": 0, "total": 50 },
    "L2": { "passed": 38, "failed": 2, "total": 40, "failures": ["L2-023", "L2-037"] },
    "L3": { "skipped": true },
    "FC": { "passed": 30, "failed": 0, "total": 30 }
  },
  "conformance_level": "L0+L1+FC"
}
```

---

## 7. Declaring Conformance

Once your implementation passes the conformance suite, include the following badge and declaration in your README:

### Badge (text)

```
Conformance: NAIL-0.9 L0+L1+L2+FC (180/180)
```

### README Declaration Template

```markdown
## Conformance

This implementation is conformant with **NAIL-0.9** at levels L0, L1, L2, and FC.

| Level | Tests | Status |
|-------|-------|--------|
| L0 (schema)      | 40/40 | ✅ PASS |
| L1 (type-check)  | 50/50 | ✅ PASS |
| L2 (effect-check)| 40/40 | ✅ PASS |
| L3 (termination) | —     | ⚪ NOT IMPLEMENTED |
| FC (fc-standard) | 30/30 | ✅ PASS |

Run: `nail-conformance-runner --impl ./your-checker --spec NAIL-0.9`
```

---

## 8. Maintenance

### Adding New Tests

1. Create a new JSON file in the appropriate `cases/{LEVEL}/` directory
2. Assign the next sequential ID for that level
3. Add an entry to `index.json`
4. Run the reference runner against the new case to confirm expected behaviour
5. Submit as a PR with the title `conformance: add {ID} — {description}`

### Updating Tests for Spec Changes

When the spec changes and existing test expectations change:

- **Non-breaking spec change**: add new cases, do not modify existing ones
- **Breaking spec change (major bump)**: create `conformance/cases-v2/` with updated cases; the v1 cases remain as a historical record under `conformance/cases-v1/`

### Versioning the Suite

The conformance suite version tracks the spec version:

```
conformance/cases/   →  NAIL-0.9 cases
conformance/v1/      →  NAIL-1.0 cases (when created)
```

The `index.json` `spec_version` field must always match the NAIL spec version the cases were written against.
