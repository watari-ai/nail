# NAIL Conformance Test Suite

**Suite version**: 0.1.0  
**Spec version**: NAIL-0.8  
**Status**: Active  
**Created**: 2026-02-26  

---

## Purpose

The NAIL Conformance Test Suite is a **portable, implementation-agnostic** set of test cases that verifies whether a NAIL checker (reference or alternative) correctly implements the NAIL specification.

All test cases are self-contained JSON files. No Python interpreter, no internal imports, no runtime execution — just structured inputs and expected outcomes.

### What Conformance Means

> An implementation is **NAIL-conformant at level N** if it passes all Conformance Test Suite cases at levels 0 through N.

Partial conformance (e.g., L0+L1 but not L2) is explicitly supported and should be declared.

---

## Test Levels

| Level | Name         | Count | Mandatory | Description |
|-------|--------------|-------|-----------|-------------|
| **L0** | Schema Validity  | 10 | ✅ | Structural validity of NAIL documents (required fields, valid kinds, type syntax) |
| **L1** | Type System      | 10 | ✅ | Type checking: return types, arithmetic operand types, let bindings |
| **L2** | Effect System    | 10 | ✅ | Effect propagation and violation detection (IO, FS, NET) |
| **L3** | Termination      | 7  | Optional | Loop and recursive function termination proofs |
| **FC** | FC Standard      | 8  | ✅ | NAIL function-calling tool format validation |

**Total: 45 test cases**

---

## Directory Structure

```
conformance/
├── README.md           ← This file
├── index.json          ← Machine-readable test index
├── L0/                 ← Schema validity tests (L0-001 … L0-010)
├── L1/                 ← Type system tests (L1-001 … L1-010)
├── L2/                 ← Effect system tests (L2-001 … L2-010)
├── L3/                 ← Termination tests (L3-001 … L3-007)
└── FC/                 ← FC Standard tests (FC-001 … FC-008)
```

---

## Test File Format

Each test case is a single JSON file:

**Acceptance test:**
```json
{
  "id": "L0-001",
  "category": "schema",
  "description": "Minimal valid fn-kind document",
  "level": 0,
  "spec_version": "0.8",
  "input": { ... },
  "expected": "ACCEPT",
  "tags": ["minimal", "fn"]
}
```

**Rejection test:**
```json
{
  "id": "L2-003",
  "category": "effect-check",
  "description": "print used without declaring IO effect",
  "level": 2,
  "spec_version": "0.8",
  "input": { ... },
  "expected": "CHECK_ERROR",
  "error_code": "EFFECT_ERROR",
  "tags": ["io", "print", "missing-effect"]
}
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `id` | ✅ | Unique stable identifier (e.g., `L2-003`) |
| `category` | ✅ | One of: `schema`, `type-check`, `effect-check`, `termination`, `fc-check` |
| `description` | ✅ | Human-readable explanation of the test |
| `level` | ✅ | Checker level required (0–3, or 99 for FC) |
| `spec_version` | ✅ | NAIL spec version this test targets |
| `input` | ✅ | The NAIL document (or FC tool array) to check |
| `expected` | ✅ | `ACCEPT`, `CHECK_ERROR`, or `ACCEPT_WITH_WARN` |
| `error_code` | ❌ | Expected error code when `expected` is `CHECK_ERROR` |
| `tags` | ❌ | String tags for filtering |
| `notes` | ❌ | Implementation notes, spec section references |

### `expected` Values

| Value | Meaning |
|-------|---------|
| `ACCEPT` | Checker must accept input without any error |
| `CHECK_ERROR` | Checker must report at least one error |
| `ACCEPT_WITH_WARN` | Checker must accept (exit 0) but emit at least one warning |

---

## Error Codes

| Code | Domain | Description |
|------|--------|-------------|
| `CHECK_ERROR` | L0–L3 | Generic check error (structural issues, schema violations) |
| `EFFECT_ERROR` | L2 | Direct effect violation (using IO/FS/NET without declaration) |
| `EFFECT_VIOLATION` | L2 | Cross-function effect propagation failure |
| `MEASURE_NOT_DECREASING` | L3 | Loop measure is zero or not provably decreasing |

---

## Running Against the Reference Implementation

### Prerequisites

```bash
cd /Users/w/nail
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### Manual test (single case)

```bash
# L0–L3 tests (NAIL module/fn format)
python -c "
import json
from interpreter import Checker, CheckError
with open('conformance/L0/L0-001.json') as f:
    t = json.load(f)
try:
    Checker(t['input'], level=t['level']).check()
    print('ACCEPT')
except Exception as e:
    print(f'ERROR: {e}')
"

# FC tests (tool array format)
python -c "
import json
from nail_lang.fc_cli import fc_check
import tempfile, os
with open('conformance/FC/FC-001.json') as f:
    t = json.load(f)
tmp = tempfile.mktemp(suffix='.json')
with open(tmp, 'w') as f:
    json.dump(t['input'], f)
rc = fc_check(tmp, 'openai', False, 'human', False)
os.unlink(tmp)
print('ACCEPT' if rc == 0 else 'ERROR')
"
```

### Run all L0–L3 tests (reference runner)

```bash
python conformance/runner.py --level 0 1 2 3
```

---

## Alternative Implementer Guide

### Contract

An alternative NAIL checker must expose:

```bash
# Check a NAIL module/fn document at a given level
your-checker check <input.json> --level <N>

# Check a FC tool array
your-checker fc check <input.json>
```

**Exit codes:**
- `0` — No errors (check passed)
- `1` — At least one error present

### Level Mapping

| `level` field | Checker invocation |
|---------------|-------------------|
| `0` | `check --level 0` (schema only) |
| `1` | `check --level 1` (schema + type) |
| `2` | `check --level 2` (schema + type + effect) — default |
| `3` | `check --level 3` (schema + type + effect + termination) |
| `99` | `fc check` (FC tool array validation) |

---

## Declaring Conformance

Once your implementation passes the suite, include this table in your README:

```markdown
## Conformance

| Level | Tests | Status |
|-------|-------|--------|
| L0 (schema)       | 10/10 | ✅ PASS |
| L1 (type-check)   | 10/10 | ✅ PASS |
| L2 (effect-check) | 10/10 | ✅ PASS |
| L3 (termination)  | —     | ⚪ NOT IMPLEMENTED |
| FC (fc-standard)  |  8/8  | ✅ PASS |

Conformance: NAIL-0.8 L0+L1+L2+FC (38/38 mandatory)
```

**Badge (text):**
```
Conformance: NAIL-0.8 L0+L1+L2+FC (38/38)
```

---

## Maintenance

### Adding new tests

1. Create `{LEVEL}/{LEVEL}-{NNN}.json` with the next sequential ID
2. Add an entry to `index.json` (update `total` and level counts)
3. Run the reference implementation to confirm the expected outcome
4. Submit as a PR titled `conformance: add {ID} — {description}`

### Versioning

- `suite_version` in `index.json` follows semver
- `spec_version` must match the NAIL spec version tested
- Breaking spec changes create a new `v2/` directory; existing cases are preserved as historical record

---

*See also: `designs/v0.9/conformance-test-suite.md` for design rationale and extraction policy.*
