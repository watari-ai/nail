# NAIL v0.3 Design: Overflow Ops (Issue #2)

## Status: Proposed — not yet implemented

## Motivation

NAIL v0.2 allows `"overflow"` only at the type-declaration level:
```json
{"type": "int", "bits": 64, "overflow": "panic"}
```

This forces all operations on a value to use the same overflow behavior.
Real programs often need per-operation control — e.g., wrap for hash functions, sat for audio.

## Proposed Syntax

Add `"overflow"` at the **expression** level, overriding the type's default:

```json
{"op": "+", "overflow": "wrap", "l": {"ref": "x"}, "r": {"ref": "y"}}
{"op": "+", "overflow": "sat",  "l": {"ref": "x"}, "r": {"ref": "y"}}
{"op": "+", "overflow": "panic","l": {"ref": "x"}, "r": {"ref": "y"}}
```

When `"overflow"` is omitted on the expression, inherit from the type declaration.

## Example: Saturating Counter

```json
{
  "nail": "0.3",
  "kind": "fn",
  "id": "saturating_increment",
  "effects": [],
  "params": [
    {"id": "n", "type": {"type": "int", "bits": 8, "overflow": "panic"}}
  ],
  "returns": {"type": "int", "bits": 8, "overflow": "panic"},
  "body": [
    {
      "op": "return",
      "val": {
        "op": "+",
        "overflow": "sat",
        "l": {"ref": "n"},
        "r": {"lit": 1}
      }
    }
  ]
}
```

Calling `saturating_increment(255)` → 255 (saturates at max)
Calling `saturating_increment(100)` → 101

## Example: Wrapping Hash

```json
{
  "nail": "0.3",
  "kind": "fn",
  "id": "hash_mix",
  "effects": [],
  "params": [
    {"id": "a", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
    {"id": "b", "type": {"type": "int", "bits": 64, "overflow": "panic"}}
  ],
  "returns": {"type": "int", "bits": 64, "overflow": "panic"},
  "body": [
    {
      "op": "return",
      "val": {
        "op": "+",
        "overflow": "wrap",
        "l": {"op": "*", "overflow": "wrap", "l": {"ref": "a"}, "r": {"lit": 2654435761}},
        "r": {"ref": "b"}
      }
    }
  ]
}
```

## Checker Rules

1. If `"overflow"` is present on an expression, validate it is one of: `"panic"`, `"wrap"`, `"sat"`
2. If `"overflow"` is absent on an expression, no change in behavior (type-level default applies)
3. `"wrap"` and `"sat"` are only valid for `"type": "int"` expressions — not float, bool, string

## Runtime Behavior

- `"wrap"`: use Python `% (2**bits)` (two's complement wrapping)
- `"sat"`: clamp to `[-(2**(bits-1)), 2**(bits-1)-1]` for signed, `[0, 2**bits-1]` for unsigned
- `"panic"`: raise `NailOverflowError` on overflow (current behavior)

## Acceptance Criteria

- [ ] `checker.py`: validate `"overflow"` field on binary ops
- [ ] `runtime.py`: implement wrap and sat semantics
- [ ] New test fixtures: `examples/saturating_counter.nail`, `examples/hash_mix.nail`
- [ ] `tests/`: at least 5 new tests covering wrap, sat, and negative inputs
- [ ] CI: passes all existing tests (73+) plus new ones
