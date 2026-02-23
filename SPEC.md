# NAIL Language Specification v0.1

> ⚠️ Draft. This specification evolves. Last updated by: Watari AI

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
```

**Design principles:**
- `null` does not exist. Use `option` type instead.
- Integer overflow behavior must be declared.
- In v0.1, only `"overflow": "panic"` is supported.
- `"overflow": "wrap"` and `"overflow": "sat"` are reserved for v0.2+.
- No implicit type conversions of any kind.

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
`print` expects a `String` argument.

---

## 10. Builtins

### String Operations
- `concat(String, String) -> String` — String concatenation
- `int_to_str(Int) -> String` — Convert integer to string
- `float_to_str(Float) -> String` — Convert float to string
- `bool_to_str(Bool) -> String` — Convert boolean to string

### Overflow Policy (v0.1)
- v0.1 supports only `"overflow": "panic"`.
- `"overflow": "wrap"` and `"overflow": "sat"` are reserved for v0.2+.
- `wrap` and `sat` behavior is out-of-scope in v0.1.

---

## 11. Module Structure

```json
{
  "nail": "0.1.0",
  "kind": "module",
  "id": "math",
  "exports": ["add", "multiply"],
  "defs": [
    { ... },
    { ... }
  ]
}
```

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
| L0 | Syntactic correctness (JSON schema validation) |
| L1 | Type consistency (type inference and type checking) |
| L2 | Effect consistency (only declared effects may be used) |
| L3 | Termination proof (all loops are proven to terminate) |
| L4 | Memory safety (buffer overflows proven impossible) |

v0.1 implements L0–L2.

---

## 13. Out of Scope for v0.1

- Algebraic data types (Enum)
- Closures
- Async/await
- Error handling (Result type)
- Generics
- Traits / Interfaces

These will be added in v0.2+ based on AI-generated proposals that are accepted into the spec.
