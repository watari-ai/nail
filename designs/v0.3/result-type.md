# NAIL v0.3 Design: Result Type (Issue #3)

## Status: Proposed — not yet implemented

## Motivation

NAIL v0.2 has no explicit error model. Functions either:
1. Panic on overflow/bad input (via `"overflow": "panic"`)
2. Return a value assuming no error

This means callers cannot distinguish "function succeeded" from "function panicked."
An explicit `Result` type makes error handling a first-class, spec-verifiable property.

## Proposed Type Syntax

```json
{"type": "result", "ok": <TypeSpec>, "err": <TypeSpec>}
```

Examples:
```json
{"type": "result", "ok": {"type": "int", "bits": 64, "overflow": "panic"}, "err": {"type": "string"}}
{"type": "result", "ok": {"type": "bool"}, "err": {"type": "unit"}}
```

## Proposed Statement Ops

### Construct Ok / Err

```json
{"op": "return", "val": {"op": "ok",  "val": <expr>}}
{"op": "return", "val": {"op": "err", "val": <expr>}}
```

### Match / unwrap

```json
{
  "op": "match_result",
  "val": <expr>,
  "ok_bind": "x",
  "ok_body": [...],
  "err_bind": "e",
  "err_body": [...]
}
```

## Example: Safe Division

```json
{
  "nail": "0.3",
  "kind": "fn",
  "id": "safe_div",
  "effects": [],
  "params": [
    {"id": "a", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
    {"id": "b", "type": {"type": "int", "bits": 64, "overflow": "panic"}}
  ],
  "returns": {
    "type": "result",
    "ok": {"type": "int", "bits": 64, "overflow": "panic"},
    "err": {"type": "string"}
  },
  "body": [
    {
      "op": "if",
      "cond": {"op": "==", "l": {"ref": "b"}, "r": {"lit": 0}},
      "then": [
        {"op": "return", "val": {"op": "err", "val": {"lit": "division by zero"}}}
      ],
      "else": [
        {
          "op": "return",
          "val": {
            "op": "ok",
            "val": {"op": "/", "l": {"ref": "a"}, "r": {"ref": "b"}}
          }
        }
      ]
    }
  ]
}
```

## Example: Caller using match_result

```json
{
  "nail": "0.3",
  "kind": "fn",
  "id": "compute",
  "effects": [],
  "params": [
    {"id": "x", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
    {"id": "y", "type": {"type": "int", "bits": 64, "overflow": "panic"}}
  ],
  "returns": {"type": "int", "bits": 64, "overflow": "panic"},
  "body": [
    {"id": "r", "mut": false, "op": "let",
     "type": {"type": "result", "ok": {"type": "int", "bits": 64, "overflow": "panic"}, "err": {"type": "string"}},
     "val": {"op": "call", "fn": "safe_div", "args": [{"ref": "x"}, {"ref": "y"}]}
    },
    {
      "op": "match_result",
      "val": {"ref": "r"},
      "ok_bind": "quotient",
      "ok_body": [
        {"op": "return", "val": {"ref": "quotient"}}
      ],
      "err_bind": "_msg",
      "err_body": [
        {"op": "return", "val": {"lit": -1}}
      ]
    }
  ]
}
```

## Checker Rules

1. `"type": "result"` requires both `"ok"` and `"err"` sub-type specs
2. `{"op": "ok", "val": expr}` — `expr` must match the result's `ok` type
3. `{"op": "err", "val": expr}` — `expr` must match the result's `err` type
4. `match_result` — bind types are inferred from the result type; both branches must be checked
5. A function returning `result<T, E>` must not return a bare `T` — must wrap in `ok`/`err`

## Acceptance Criteria

- [ ] `types.py`: add `ResultType(ok: NailType, err: NailType)`
- [ ] `checker.py`: validate ok/err construction and match_result branches
- [ ] `runtime.py`: represent as `{"_tag": "ok"/"err", "_val": value}`
- [ ] Example: `examples/safe_div.nail` (function + caller)
- [ ] Tests: ok path, err path, mismatched type (should CheckError), nested result
- [ ] CI: passes all existing tests plus 8+ new ones
