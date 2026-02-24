# NAIL Language Specification v0.4

> ⚠️ Draft. This specification evolves. Last updated: 2026-02-24 by Watari AI

---

## 1. Overview

A NAIL program is a **collection of JSON documents**. There is no text syntax. The act of a human "writing code" does not exist in NAIL. AI generates structured data, the verifier validates it, and the runtime executes it.

**The only representation form in NAIL: structured JSON data**

---

## 2. Type System

```json
{ "type": "int",    "bits": 64,  "overflow": "panic" }
{ "type": "float",  "bits": 64  }
{ "type": "bool" }
{ "type": "string", "encoding": "utf8" }
{ "type": "bytes" }
{ "type": "option", "inner": <type> }
{ "type": "list",   "inner": <type>, "len": "dynamic" }
{ "type": "list",   "inner": <type>, "len": <n> }
{ "type": "map",    "key": <type>, "value": <type> }
{ "type": "unit" }
{ "type": "alias",  "name": "<AliasName>" }
```

**Design principles:**
- `null` does not exist. Use `option` type instead.
- Integer overflow behavior must be declared.
- At the **type level**, only `"overflow": "panic"` is supported (type default).
- At the **expression level** (v0.3+), `"overflow": "wrap"` and `"overflow": "sat"` are supported per-operation. See [designs/v0.3/overflow-ops.md](designs/v0.3/overflow-ops.md).
- No implicit type conversions of any kind.

### Type Aliases (v0.4)

Type aliases are declared at module top-level and can be used from function signatures and type annotations.

```json
"types": {
  "UserId": { "type": "int", "bits": 64, "overflow": "panic" },
  "MaybeUserId": { "type": "option", "inner": { "type": "alias", "name": "UserId" } }
}
```

Alias usage:

```json
{ "type": "alias", "name": "UserId" }
```

Rules:
- Alias lookup scope is the containing module's `types`.
- Aliases may reference other aliases.
- Circular aliases are a compile error.

---

## 3. Effect System

All side effects must be declared in the function signature. Any undeclared side effect is a compile error.

```json
"effects": []          // Pure function (zero side effects)
"effects": ["IO"]      // Standard I/O
"effects": ["FS"]      // Filesystem
"effects": ["NET"]     // Network
"effects": ["TIME"]    // Current time access
"effects": ["RAND"]    // Random numbers
"effects": ["MUT"]     // Mutable global state
```

Multiple effects are listed as an array: `["IO", "NET"]`, etc.

Structured effect capabilities are also valid in `effects` (v0.4):

```json
"effects": [
  { "kind": "FS",  "allow": ["/tmp/", "./data/"], "ops": ["read"] },
  { "kind": "NET", "allow": ["api.example.com"] }
]
```

Rules:
- `effects` items may be string or object.
- String effects are fully supported (`"FS"`, `"IO"`, `"NET"`). The runtime normalises kind strings to uppercase, so `"Net"` is accepted but `"NET"` is the canonical form.
- Object effects must include `kind`.
- `kind: "FS"` may constrain filesystem access via `allow` and optional operation filter `ops`.
- `kind: "NET"` may constrain outbound domains via `allow` and optional operation filter `ops`.
- If any structured capability for a kind exists, operations of that kind are allowed only when one declared capability matches.

---

## 4. Function Definition

```json
{
  "nail": "0.1.0",
  "kind": "fn",
  "id": "add",
  "effects": [],
  "params": [
    { "id": "a", "type": { "type": "int", "bits": 64, "overflow": "panic" } },
    { "id": "b", "type": { "type": "int", "bits": 64, "overflow": "panic" } }
  ],
  "returns": { "type": "int", "bits": 64, "overflow": "panic" },
  "body": [
    { "op": "return", "val": { "op": "+", "l": { "ref": "a" }, "r": { "ref": "b" } } }
  ]
}
```

**Field specification:**
| Field | Required | Description |
|---|---|---|
| `nail` | ✅ | Spec version |
| `kind` | ✅ | `"fn"` |
| `id` | ✅ | Function identifier (alphanumeric and underscore only) |
| `effects` | ✅ | Effect list (empty array = pure function) |
| `params` | ✅ | Parameter list |
| `returns` | ✅ | Return type |
| `body` | ✅ | Statement list |

---

## 5. Operators

### Arithmetic
```json
{ "op": "+",   "l": <expr>, "r": <expr> }
{ "op": "-",   "l": <expr>, "r": <expr> }
{ "op": "*",   "l": <expr>, "r": <expr> }
{ "op": "/",   "l": <expr>, "r": <expr> }
{ "op": "%",   "l": <expr>, "r": <expr> }
```

### Comparison (type mismatch is a compile error)
```json
{ "op": "eq",  "l": <expr>, "r": <expr> }
{ "op": "neq", "l": <expr>, "r": <expr> }
{ "op": "lt",  "l": <expr>, "r": <expr> }
{ "op": "lte", "l": <expr>, "r": <expr> }
{ "op": "gt",  "l": <expr>, "r": <expr> }
{ "op": "gte", "l": <expr>, "r": <expr> }
```

### Logical
```json
{ "op": "and", "l": <expr>, "r": <expr> }
{ "op": "or",  "l": <expr>, "r": <expr> }
{ "op": "not", "v": <expr> }
```

### Function Call (v0.2)
```json
{ "op": "call", "fn": "add", "args": [ <expr>, <expr> ] }
```

`call` can be used as:
- an expression (return value is used)
- a statement in `body` (return value is discarded)

Rules:
- Calls are allowed only in `kind: "module"`.
- `kind: "fn"` cannot call functions.
- Forward references are allowed within a module.
- Effect propagation is required: `caller.effects ⊇ callee.effects`.
- Recursion is forbidden (direct and mutual). Any cycle in the call graph is a compile error.

---

## 6. Control Flow

### Conditional
```json
{
  "op": "if",
  "cond": <bool_expr>,
  "then": [ <statements> ],
  "else": [ <statements> ]
}
```

`else` is mandatory. All branches must return a value.

### Loop
```json
{
  "op": "loop",
  "bind": "i",
  "from": { "lit": 0 },
  "to":   { "lit": 10 },
  "step": { "lit": 1 },
  "body": [ <statements> ]
}
```

Infinite loops do not exist. Termination condition is required (for termination proof).

---

## 7. Literals

```json
{ "lit": 42 }
{ "lit": 3.14 }
{ "lit": true }
{ "lit": "hello" }
{ "lit": null, "type": { "type": "option", "inner": { "type": "int", "bits": 64, "overflow": "panic" } } }
```

---

## 8. Variables

```json
{ "op": "let", "id": "x", "type": <type>, "val": <expr> }
{ "op": "let", "id": "x", "type": <type>, "val": <expr>, "mut": true }
{ "op": "assign", "id": "x", "val": <expr> }
{ "ref": "x" }
```

`let` declares a variable. Variables are immutable by default.
Use `"mut": true` on `let` to declare a mutable variable.
Use `assign` to update a previously declared mutable variable.

---

## 9. Effectful Operations

```json
{ "op": "print", "val": <string_expr>, "effect": "IO" }
{ "op": "read_file", "path": <string_expr>, "effect": "FS" }
{ "op": "http_get", "url": <string_expr>, "effect": "NET" }
```

Effectful operations are a compile error if the corresponding effect is not declared in the function's `effects` list.
Each effectful operation must include an explicit `effect` field with the canonical value:
- `print` must declare `"effect": "IO"`
- `read_file` must declare `"effect": "FS"`
- `http_get` must declare `"effect": "NET"`
`print` expects a `String` argument.

Capability enforcement:
- `read_file` path must be inside an allowed FS path when FS capability objects are declared.
- `http_get` URL host must match an allowed domain when NET capability objects are declared.

---

## 10. Builtins

### String Operations
- `concat(String, String) -> String` — String concatenation
- `int_to_str(Int) -> String` — Convert integer to string
- `float_to_str(Float) -> String` — Convert float to string
- `bool_to_str(Bool) -> String` — Convert boolean to string

### Collection Operations (v0.4)
```json
{ "op": "list_get",  "list": <var>, "index": <expr> }
{ "op": "list_push", "list": <var>, "value": <expr> }
{ "op": "list_len",  "list": <var> }
{ "op": "map_get",   "map": <var>,  "key": <expr> }
```

Rules:
- `list_get`: `list` must be `list<T>`, `index` must be `int`; returns `T`.
  Out-of-bounds is a runtime error.
- `list_push`: `list` must be `list<T>`, `value` must be `T`; mutates in place; returns `unit`.
- `list_len`: `list` must be `list<T>`; returns `int`.
- `map_get`: `map` must be `map<K, V>`, `key` must be `K`; returns `V`.

### Overflow Policy (v0.3)
- **Type-level**: Only `"overflow": "panic"` is valid in type declarations. This is the default.
- **Expression-level** (v0.3): Per-operation `"overflow"` field overrides the type default:
  - `"wrap"`: Two's complement modular arithmetic
  - `"sat"`: Saturating arithmetic (clamp to min/max)
  - `"panic"`: Runtime panic on overflow (explicit, same as default)
- Expression-level override syntax: `{"op": "+", "overflow": "wrap", "l": ..., "r": ...}`
- See [designs/v0.3/overflow-ops.md](designs/v0.3/overflow-ops.md) for full specification.

---

## 11. Module Structure

```json
{
  "nail": "0.1.0",
  "kind": "module",
  "id": "math",
  "types": {
    "UserId": { "type": "int", "bits": 64, "overflow": "panic" }
  },
  "exports": ["add", "multiply"],
  "defs": [
    { ... },
    { ... }
  ]
}
```

`defs` are checked in 2 passes:
1. Collect all function signatures (for forward references)
2. Type/effect-check all bodies

Type aliases in `types` are resolved before function checking.

---

## 12. Project Structure (AI Project Standard)

NAIL defines, alongside the language spec, a **directory structure that lets AI understand a project with minimal context**.

```
project/
├── SPEC.md          Required: project specification (features, constraints, non-functional requirements)
├── AGENTS.md        Required: instructions for AI agents
├── ARCHITECTURE.md  Recommended: system diagram and dependency map
├── TODO.md          Recommended: current task list
├── src/             NAIL source files (*.nail)
├── tests/           Test cases (*.nail)
└── proofs/          Formal proof files (*.proof)
```

**Required fields in SPEC.md (YAML format):**
```yaml
name: <project_name>
version: <semver>
language: nail@<version>
entry: <module_id>
effects_allowed: [IO, FS, NET]
constraints:
  - <constraint in natural language>
```

The presence and format of these files is checked by the NAIL project verifier.

---

## 13. Verification Levels

| Level | Description |
|---|---|
| L0 | Syntactic correctness: JSON schema validation **+ JCS canonical form enforcement** |
| L1 | Type consistency (type inference and type checking) |
| L2 | Effect consistency (only declared effects may be used; effect propagation through `call` enforced) |
| L3 | Termination proof (all loops are proven to terminate) |
| L4 | Memory safety (buffer overflows proven impossible) |

**JCS Canonical Form (L0 requirement, v0.2+):** All NAIL source must be in [JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785) form: `json.dumps(sort_keys=True, separators=(',',':'))`. One program = one representation. Non-canonical input is rejected at L0. Use `nail canonicalize` to convert.

v0.4 implements L0–L2 (L3/L4 planned for future versions).

---

## 14. Implemented in v0.4

The following features were added in v0.4:

- **Result type** (`result`, `ok`, `err`, `match_result`) — error handling without exceptions. See [designs/v0.3/result-type.md](designs/v0.3/result-type.md)
- **Cross-module imports** — import and call functions from other NAIL modules. Circular import detection, effect propagation across boundaries. See [designs/v0.3/cross-module.md](designs/v0.3/cross-module.md)
- **Expression-level overflow** (`wrap`/`sat`/`panic` per operation). See [designs/v0.3/overflow-ops.md](designs/v0.3/overflow-ops.md)
- **Type aliases** (`module.types`, `{ "type": "alias", "name": ... }`) — reusable module-local type definitions.

## 15. Out of Scope (v0.4)

- Algebraic data types (Enum)
- Closures
- Async/await
- Generics
- Traits / Interfaces

These may be added in v0.5+ based on AI-generated proposals accepted into the spec.
