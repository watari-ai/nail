# NAIL v0.3 Design: Cross-Module Import (Issue #4)

## Status: Proposed — not yet implemented

## Motivation

NAIL v0.2 supports modules (multiple fns in one file), but all calls are intra-module.
Real programs need to compose across files — a math library, a string utils library, etc.
Cross-module imports must carry effect information through module boundaries.

## Current State

`math_module.nail` demonstrates intra-module calls:
```json
{"kind": "module", "defs": [{"kind": "fn", "id": "add", ...}, {"kind": "fn", "id": "double", ...}]}
```

The call op `{"op": "call", "fn": "double", "args": [...]}` resolves locally.

## Proposed: Import Declaration

Add a top-level `"imports"` field to module specs:

```json
{
  "nail": "0.3",
  "kind": "module",
  "imports": [
    {"module": "math_utils", "fns": ["add", "multiply"]},
    {"module": "string_ops", "fns": ["concat"]}
  ],
  "defs": [...]
}
```

## Proposed: Cross-Module Call Op

```json
{"op": "call", "module": "math_utils", "fn": "add", "args": [{"ref": "x"}, {"ref": "y"}]}
```

When `"module"` is present, resolve `fn` from the imported module rather than locally.

## Effect Propagation Across Modules

If `math_utils.add` declares `"effects": []` (pure), calling it from a pure function is allowed.
If `io_utils.print_line` declares `"effects": ["IO"]`, calling it requires the caller to declare `IO`.

The checker must resolve the callee's effect signature from the imported module file.

## Example: math_utils.nail (library)

```json
{
  "nail": "0.3",
  "kind": "module",
  "id": "math_utils",
  "imports": [],
  "defs": [
    {
      "nail": "0.3",
      "kind": "fn",
      "id": "add",
      "effects": [],
      "params": [
        {"id": "a", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
        {"id": "b", "type": {"type": "int", "bits": 64, "overflow": "panic"}}
      ],
      "returns": {"type": "int", "bits": 64, "overflow": "panic"},
      "body": [
        {"op": "return", "val": {"op": "+", "l": {"ref": "a"}, "r": {"ref": "b"}}}
      ]
    },
    {
      "nail": "0.3",
      "kind": "fn",
      "id": "square",
      "effects": [],
      "params": [
        {"id": "x", "type": {"type": "int", "bits": 64, "overflow": "panic"}}
      ],
      "returns": {"type": "int", "bits": 64, "overflow": "panic"},
      "body": [
        {"op": "return", "val": {"op": "*", "l": {"ref": "x"}, "r": {"ref": "x"}}}
      ]
    }
  ]
}
```

## Example: main.nail (consumer)

```json
{
  "nail": "0.3",
  "kind": "module",
  "id": "main",
  "imports": [
    {"module": "math_utils", "fns": ["add", "square"]}
  ],
  "defs": [
    {
      "nail": "0.3",
      "kind": "fn",
      "id": "sum_of_squares",
      "effects": [],
      "params": [
        {"id": "a", "type": {"type": "int", "bits": 64, "overflow": "panic"}},
        {"id": "b", "type": {"type": "int", "bits": 64, "overflow": "panic"}}
      ],
      "returns": {"type": "int", "bits": 64, "overflow": "panic"},
      "body": [
        {
          "id": "sq_a", "mut": false, "op": "let",
          "type": {"type": "int", "bits": 64, "overflow": "panic"},
          "val": {"op": "call", "module": "math_utils", "fn": "square", "args": [{"ref": "a"}]}
        },
        {
          "id": "sq_b", "mut": false, "op": "let",
          "type": {"type": "int", "bits": 64, "overflow": "panic"},
          "val": {"op": "call", "module": "math_utils", "fn": "square", "args": [{"ref": "b"}]}
        },
        {
          "op": "return",
          "val": {"op": "call", "module": "math_utils", "fn": "add", "args": [{"ref": "sq_a"}, {"ref": "sq_b"}]}
        }
      ]
    }
  ]
}
```

## CLI Usage

```
nail run main.nail --modules math_utils.nail
nail check main.nail --modules math_utils.nail
```

Or via a manifest:
```json
{"entrypoint": "main.nail", "modules": ["math_utils.nail", "string_ops.nail"]}
```

## Checker Rules

1. Validate that all `imports[].module` have a corresponding file loaded
2. Validate that all `imports[].fns` exist in the target module
3. Cross-module `call` ops: resolve callee from imports, check arg types and effect propagation
4. Circular imports: detect and raise CheckError
5. Module `"id"` field must match filename (e.g., `math_utils.nail` → `"id": "math_utils"`)

## Acceptance Criteria

- [ ] `checker.py`: accept `--modules` list; resolve cross-module calls
- [ ] `runtime.py`: load and execute imported modules
- [ ] `nail_cli.py`: add `--modules` flag to `run` and `check`
- [ ] Examples: `examples/cross_module/math_utils.nail` + `examples/cross_module/main.nail`
- [ ] Tests: cross-module call, effect propagation through import, missing module (CheckError), circular import (CheckError)
- [ ] CI: passes all existing tests plus 6+ new ones
