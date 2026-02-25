# NAIL Language Specification v0.8

> ⚠️ Draft. This specification evolves. Last updated: 2026-02-25 by Watari AI (v0.8.0 FC Standard + MCP Bridge + Generics specified)

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
{ "type": "enum",   "variants": [ { "tag": "<Tag>" }, { "tag": "<Tag>", "fields": [ { "name": "<field>", "type": <type> } ] } ] }
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
- Aliases may reference other aliases (transitivity: chains of arbitrary depth are resolved).
- Aliases may be used anywhere a type is valid: parameter types, return types, `let` binding type annotations, and nested within `option`, `list`, `map`, and `result` types.
- Circular aliases (direct, indirect, or via nested types) are a compile error.
- Referencing an undefined alias name is a compile error.

### Enum / ADT (v0.5)

Enum definitions are declared under module-level `types` (same namespace as type aliases).

```json
"types": {
  "Color": {
    "type": "enum",
    "variants": [
      { "tag": "Red" },
      { "tag": "Green" },
      { "tag": "Blue" }
    ]
  },
  "Shape": {
    "type": "enum",
    "variants": [
      { "tag": "Circle", "fields": [ { "name": "radius", "type": { "type": "float", "bits": 64 } } ] },
      { "tag": "Rectangle", "fields": [
        { "name": "w", "type": { "type": "float", "bits": 64 } },
        { "name": "h", "type": { "type": "float", "bits": 64 } }
      ] }
    ]
  }
}
```

Rules:
- Each variant tag must be unique within the enum.
- Variant field names must be unique within the variant.
- Enum field types follow the normal type system and alias resolution rules.
- `result<Ok, Err>` remains supported and can be seen as a specialized two-variant ADT.

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
- Object effects must include `kind`. `kind` must be one of `"FS"`, `"NET"` (other values are a compile error).
- Object effects must include `allow`. A missing or empty `allow` list is a compile error. All items in `allow` must be strings (non-string items are a compile error).
- `kind: "FS"` constrains filesystem access via `allow` (list of allowed directory roots) and optional operation filter `ops`.
  - A file path is allowed if it starts with any entry in `allow` (i.e. files inside subdirectories of an allowed root are permitted).
  - Sibling directories outside the allowed roots are denied.
- `kind: "NET"` constrains outbound domains via `allow` (list of exact hostnames) and optional operation filter `ops`.
  - Domain matching is case-insensitive (RFC 4343): `"API.EXAMPLE.COM"` matches `"api.example.com"`.
  - Matching is **exact hostname** — subdomains do **not** match the parent: `"sub.api.example.com"` does not match `"api.example.com"`.
- `ops`, when present, must be a list of strings (not a plain string). If `ops` is absent, all operations of that kind are permitted.
- If any structured capability for a kind exists, operations of that kind are allowed only when one declared capability matches.
- Both check-time (L2) and runtime enforcement are required (defence-in-depth).

### 3.1 Effect Model: Static vs Runtime (v0.5)

NAIL's effect system has two complementary enforcement layers. Understanding their respective roles is essential for building correct AI agent sandboxes.

#### What the Checker (L2) Guarantees

The checker performs **static analysis** at load time (before execution):

- Every function with a side-effect operation (`print`, `read_file`, `http_get`, etc.) must declare the corresponding effect in its signature.
- Functions calling other functions cannot "hide" effects: if `helper` declares `[IO]`, then `main` must also declare `[IO]` (or be rejected by the checker).
- For structured capabilities (`{"kind":"FS","allow":["/tmp/"]}"`), the checker verifies that the declared paths/hosts are syntactically valid. It **cannot** verify at compile time that the actual values passed at runtime fall within bounds — that is the runtime's job.

**Checker guarantee:** _If a function declares `effects: []`, it contains no calls to effectful operations. This is a structural guarantee enforced by the verifier, not a promise._

#### What the Runtime (L2.5) Enforces

The runtime performs **dynamic enforcement** at execution time:

- Structured FS capabilities: each `read_file`/`write_file` call is checked against the `allow` paths. A path outside the declared roots raises `RuntimeError`.
- Structured NET capabilities: each `http_get` call is checked against the `allow` hostnames. An unexpected host raises `RuntimeError`. URL schemes are also validated — only `http://` and `https://` are permitted.
- Unstructured effects (`"FS"`, `"NET"` without `allow`): no path/host restriction at runtime; the declaration is purely informational at this level.

**Runtime guarantee:** _For structured capabilities, the actual runtime values are constrained to the declared allowlist. This is defence-in-depth against checker escape vectors._

#### User Responsibility

- The user (or AI agent) is responsible for declaring effects accurately. The checker catches undeclared effects, but cannot validate that effect declarations are _complete_ (e.g. you could declare `["FS"]` but only use NET — the checker does not warn).
- For sandboxing AI-generated code, prefer structured capabilities (`{"kind":"NET","allow":["..."]}`). Bare effect strings (`"NET"`) declare intent but do not constrain values.

#### Three-Tier Error Model

| Tier | Type | Example | Recovery |
|------|------|---------|----------|
| Recoverable | `Result` type (`ok`/`err`) | File not found, parse error | Handled in code via `unwrap_ok`/`unwrap_err` |
| Unrecoverable | `panic` overflow policy | Integer overflow | Program terminates |
| Runtime error | `RuntimeError` | FS path outside `allow` | Sandbox catches and logs |

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

### Enum Construction / Matching (v0.5)

Construct an enum value:

```json
{
  "op": "enum_make",
  "tag": "Circle",
  "fields": { "radius": { "lit": 3.14, "type": { "type": "float", "bits": 64 } } },
  "into": "my_shape"
}
```

Pattern match:

```json
{
  "op": "match_enum",
  "val": { "ref": "my_shape" },
  "cases": [
    { "tag": "Circle", "binds": { "radius": "r" }, "body": [ <statements> ] },
    { "tag": "Rectangle", "binds": { "w": "width", "h": "height" }, "body": [ <statements> ] }
  ],
  "default": [ <statements> ]
}
```

Rules:
- `enum_make.tag` must exist on the target enum.
- `enum_make.fields` must exactly match the selected variant fields (names and types).
- `match_enum` requires either:
  - exhaustive coverage of all variant tags, or
  - a `default` branch.
- `binds` introduces typed variables in each case body.

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
- `str_len(String) -> Int`
- `str_split(String, String) -> list<String>`
- `str_trim(String) -> String`
- `str_upper(String) -> String`
- `str_lower(String) -> String`
- `str_contains(String, String) -> Bool`
- `str_starts_with(String, String) -> Bool`
- `str_replace(String, String, String) -> String`

### Math Operations (v0.5)
- `abs(Number) -> Number`
- `min2(Number, Number) -> Number`
- `max2(Number, Number) -> Number`

### Collection Operations (v0.4)
```json
{ "op": "list_get",  "list": <var>, "index": <expr> }
{ "op": "list_push", "list": <var>, "value": <expr> }
{ "op": "list_len",  "list": <var> }
{ "op": "map_get",   "map": <var>,  "key": <expr> }
{ "op": "list_slice", "list": <list_expr>, "from": <int_expr>, "to": <int_expr> }
{ "op": "list_contains", "list": <list_expr>, "val": <expr> }
{ "op": "map_has",   "map": <map_expr>, "key": <expr> }
{ "op": "map_keys",  "map": <map_expr> }
```

Rules:
- `list_get`: `list` must be `list<T>`, `index` must be `int`; returns `T`.
  Out-of-bounds is a runtime error.
- `list_push`: `list` must be `list<T>`, `value` must be `T`; mutates in place; returns `unit`.
- `list_len`: `list` must be `list<T>`; returns `int`.
- `list_slice`: `list` must be `list<T>`, `from` and `to` must be `int`; returns `list<T>`.
- `list_contains`: `list` must be `list<T>`, `val` must be `T`; returns `bool`.
- `map_get`: `map` must be `map<K, V>`, `key` must be `K`; returns `V`.
- `map_has`: `map` must be `map<K, V>`, `key` must be `K`; returns `bool`.
- `map_keys`: `map` must be `map<K, V>`; returns `list<K>`.

### Higher-Order Collection Operations (v0.4)

These operations accept a **function reference** (`"fn"` field: a string ID of a module-level `kind:fn` definition).
They are available **only at module level (`kind:module`)** and cannot be used inside a plain `kind:fn` body that is not part of a module.

```json
{ "op": "list_map",    "list": <list_expr>, "fn": "<fn_id>" }
{ "op": "list_filter", "list": <list_expr>, "fn": "<fn_id>" }
{ "op": "list_fold",   "list": <list_expr>, "fn": "<fn_id>", "init": <expr> }
{ "op": "map_values",  "map":  <map_expr>,  "fn": "<fn_id>" }
{ "op": "map_set",     "map":  <map_expr>,  "key": <expr>,   "val": <expr> }
```

#### Signatures & Return Types

| Op | fn signature required | Returns |
|---|---|---|
| `list_map` | `fn(T) -> U` | `list<U>` (same length as input) |
| `list_filter` | `fn(T) -> bool` | `list<T>` (subset, dynamic length) |
| `list_fold` | `fn(Acc, T) -> Acc` | `Acc` (type of `init`) |
| `map_values` | `fn(V) -> W` | `map<K, W>` |
| `map_set` | *(no fn field)* | `unit` — mutates map in place |

#### Argument Types

- **`list_map`**: `list` must be `list<T>`; referenced `fn` must accept exactly one parameter of type `T` and return any type `U`. Returns `list<U>`.
- **`list_filter`**: `list` must be `list<T>`; referenced `fn` must accept exactly one parameter of type `T` and return `bool`. Returns `list<T>`.
- **`list_fold`**: `list` must be `list<T>`; `init` must be of type `Acc`; referenced `fn` must accept `(Acc, T)` and return `Acc`. Returns `Acc`.
- **`map_values`**: `map` must be `map<K, V>`; referenced `fn` must accept exactly one parameter of type `V` and return any type `W`. Returns `map<K, W>`.
- **`map_set`**: `map` must be `map<K, V>`, `key` must be `K`, `val` must be `V`; mutates the map in place. Returns `unit`. *(No `fn` field.)*

#### Effect Propagation

The effect set of a `list_map` / `list_filter` / `list_fold` / `map_values` operation is the **union** of:
- effects declared on the *enclosing* function, and
- effects declared on the referenced `fn`.

If the referenced `fn` declares an effect not declared on the caller, the checker raises a `CheckError`.  
In other words: **a pure caller cannot reference an effectful fn in a higher-order op.**

#### `kind:module` Constraint

`list_map`, `list_filter`, `list_fold`, and `map_values` require that the referenced `fn` is defined in the **same module** (i.e., appears in the `defs` array of the enclosing `kind:module` document). Cross-module function references in higher-order ops are not supported in v0.4.

`map_set` has no `fn` field and is usable inside any function body without restriction.

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
| L0 | Syntactic correctness: JSON schema validation **+ canonical form enforcement** |
| L1 | Type consistency (type inference and type checking) |
| L2 | Effect consistency (only declared effects may be used; effect propagation through `call` enforced) |
| L3 | Termination proof (all loops are proven to terminate) |
| L4 | Memory safety (buffer overflows proven impossible) |

**Canonical Form (L0 requirement, v0.2+):** All NAIL source must be in canonical form: `json.dumps(sort_keys=True, separators=(',',':'))`. NAIL uses an RFC 8785-inspired canonical subset (sorted keys + compact separators; does not claim full RFC 8785 compliance). One program = one representation. Non-canonical input is rejected at L0 when `--strict` is used. Use `nail canonicalize` to convert.

**`--strict` mode:** Input must be *exactly* equal to the canonical form — no leading or trailing whitespace or newlines are permitted.

v0.6 implements L0–L3 (L4 planned for future versions).

---

## 14. Version Changelog

### v0.3 (cumulative from v0.2)
- Result type (`result`, `ok`, `err`, `match_result`) — see [designs/v0.3/result-type.md](designs/v0.3/result-type.md)
- Cross-module imports — see [designs/v0.3/cross-module.md](designs/v0.3/cross-module.md)
- Expression-level overflow (`wrap`/`sat`/`panic` per operation) — see [designs/v0.3/overflow-ops.md](designs/v0.3/overflow-ops.md)

### v0.4 additions
- **Type aliases** (`module.types`, `{ "type": "alias", "name": ... }`) — reusable module-local type definitions.
- **Collection operations** — `list_get`, `list_push`, `list_len`, `map_get`, `map_set`, `map_has`, `list_make`, `map_make`.
- **Higher-order collection operations** — `list_map`, `list_filter`, `list_fold`, `map_values`; accept a `fn` reference string; module-level only; effect propagation enforced at check time.
- **Granular effect capabilities** — structured `effects` objects with `kind`, `allow`, and `ops` for fine-grained access control.
- **Effectful op contract** — `read_file` and `http_get` require an explicit `"effect"` field; bare declaration is a check-time error.
- **URL scheme restriction** — `http_get` accepts only `http://` and `https://` schemes.
- **PyPI** — `pip install nail-lang` published.

### v0.5 additions
- **Enum / ADT** (`enum_make` / `match_enum`) — see §2.
- **Core StdLib** (`str_split`, `str_trim`, `str_upper`, `str_lower`, `str_contains`, `str_starts_with`, `str_replace`, `abs`, `min2`, `max2`).
- **FC effect annotations** — tool sandbox metadata for AI agent tool lists.
- **Return-path exhaustiveness check** — checker verifies all branches return.

### v0.6 additions
- **L3 Termination Proof** — `nail check --level 3` emits a termination certificate. See §15.

### v0.7 additions
- **Generics / Parametric Types** (`type_params`, `{"type": "param", "name": "T"}`) — see §16.
- **MCP Bridge** (`from_mcp` / `to_mcp` / `infer_effects`) — see §18.
- **JSON error format** — `nail check --format json` for machine-parseable output.
- **`import "from"` file resolution** — auto-module load from file path.
- **Shareable Playground links** — URL hash encoding.

### v0.7.2 additions
- **Generic Type Aliases** — `type_params` on module-level aliases. See §16.5.

### v0.8.0 additions
- **FC Standard** (`nail_lang.fc_standard`) — unified Function Calling standard library. See §19.
- **Provider converters** — `to_openai_tool`, `to_anthropic_tool`, `to_gemini_tool`, and their inverses.
- **Batch conversion** — `convert_tools()` utility.
- **Round-trip guarantee** — NAIL ↔ OpenAI ↔ Anthropic ↔ Gemini verified.

## 15. L3 Termination Proof (v0.6)

L3 verification proves that every loop and every recursive call will terminate. Enable with `nail check --level 3` or `nail run --level 3`.

### Loop Termination

A `loop` op (fields: `bind`, `from`, `to`, `step`, `body`) is proven terminating when:

1. **`step` is a literal integer** — e.g. `{"lit": 1}` or `{"lit": -3}`. Variable expressions are rejected.
2. **`step` is non-zero** — `{"lit": 0}` is rejected as it would loop forever.

If both `from` and `to` are also literals, the checker additionally notes any trivially-empty loops (positive step with `from > to`, or negative step with `from < to`). These still pass — they terminate trivially by never executing.

```json
{
  "op": "loop",
  "bind": "i",
  "from": {"lit": 0},
  "to":   {"lit": 100},
  "step": {"lit": 1},
  "body": []
}
```

### Recursive Function Termination

Direct or mutual recursion is permitted at L3 if every function in the cycle declares a `termination` annotation with a `measure` field naming a decreasing parameter:

```json
{
  "nail": "0.1.0",
  "kind": "module",
  "id": "factorial",
  "exports": ["fact"],
  "defs": [
    {
      "id": "fact",
      "effects": [],
      "params": [{"id": "n", "type": {"type": "int", "bits": 64, "overflow": "panic"}}],
      "returns": {"type": "int", "bits": 64, "overflow": "panic"},
      "termination": {"measure": "n"},
      "body": [
        {
          "op": "if",
          "cond": {"op": "eq", "l": {"ref": "n"}, "r": {"lit": 0}},
          "then": [{"op": "return", "val": {"lit": 1}}],
          "else": [
            {"op": "return", "val": {"op": "*", "l": {"ref": "n"},
              "r": {"op": "call", "fn": "fact", "args": [{"op": "-", "l": {"ref": "n"}, "r": {"lit": 1}}]}}}
          ]
        }
      ]
    }
  ]
}
```

The `termination.measure` must reference an existing parameter name. The checker records this as a "decreasing measure annotation" proof.

> ⚠️ **v0.6 limitation**: Termination proofs are trust-based annotation checks. The checker verifies that `measure` names a valid parameter, but does not verify that the measure strictly decreases at each recursive call site. Actual decrease verification is planned for a future version (see ROADMAP).

### Termination Certificate

After a successful L3 check, call `get_termination_certificate()` to retrieve a proof object:

```json
{
  "level": 3,
  "verdict": "all_loops_terminate",
  "functions_verified": 1,
  "proofs": {
    "fact": [
      {
        "kind": "recursion",
        "measure": "n",
        "verdict": "terminates",
        "proof": "decreasing_measure_annotation"
      }
    ]
  }
}
```

Loop proofs include `kind: "loop"`, `step`, `step_literal: true`, `verdict: "terminates"`, `proof: "step_nonzero_literal"`, and an optional `note` for trivially-empty loops.

---

## 16. Generics / Parametric Types (v0.7)

NAIL supports generic function declarations via `type_params`. Type variables are resolved at call sites through type inference (unification).

### 16.1 Syntax

```json
{
  "nail": "0.7.0",
  "kind": "fn",
  "id": "identity",
  "type_params": ["T"],
  "effects": [],
  "params": [
    {"id": "x", "type": {"type": "param", "name": "T"}}
  ],
  "returns": {"type": "param", "name": "T"},
  "body": [
    {"op": "return", "val": {"ref": "x"}}
  ]
}
```

- `"type_params"`: Array of type variable names (strings). E.g. `["T"]`, `["T", "E"]`.
- `{"type": "param", "name": "T"}`: A type variable reference. Valid only inside a function that declares `"T"` in its `type_params`.
- Type params may appear anywhere a concrete type may appear: in parameter types, return types, and nested inside `list`, `option`, `map`, `result` type specs.

### 16.2 Type Inference at Call Sites

When calling a generic function, the checker infers the type substitution automatically:

```json
{"op": "call", "fn": "identity", "args": [{"lit": 42}]}
```
→ arg type is `int64(panic)` → checker infers `T ← int64(panic)` → return type is `int64(panic)`.

Multi-param inference:
```json
{
  "nail": "0.7.0",
  "kind": "fn",
  "id": "pair",
  "type_params": ["T", "U"],
  "params": [
    {"id": "a", "type": {"type": "param", "name": "T"}},
    {"id": "b", "type": {"type": "param", "name": "U"}}
  ],
  "returns": {"type": "param", "name": "T"},
  ...
}
```
Calling `pair(7, true)` → `T ← int64`, `U ← bool` → return type `int64`.

### 16.3 Checker Rules

1. **Scope**: A `{"type": "param", "name": "T"}` is valid only inside a function that declares `"T"` in `type_params`.
2. **Consistency**: If `T` is inferred as `int64` at arg position 0, it must also be `int64` at arg position 1 (if it appears there too). Conflicts raise a `GENERIC_TYPE_MISMATCH` error.
3. **Completeness**: All declared type params must be inferrable from the argument types. A type param that appears only in the return type (not in any param) raises `TYPE_PARAM_UNRESOLVED`.
4. **Effect inference**: Effect checking for generic calls is identical to monomorphic calls — callee effects must be a subset of the caller's declared effects.

### 16.4 Supported Generic Containers

All container types support generic element types:

| Type spec | Example |
|-----------|---------|
| `list<T>` | `{"type": "list", "inner": {"type": "param", "name": "T"}}` |
| `option<T>` | `{"type": "option", "inner": {"type": "param", "name": "T"}}` |
| `map<K, V>` | `{"type": "map", "key": {"type": "param", "name": "K"}, "value": {"type": "param", "name": "V"}}` |
| `result<T, E>` | `{"type": "result", "ok": {"type": "param", "name": "T"}, "err": {"type": "param", "name": "E"}}` |

---

## 16.5 Generic Type Aliases (v0.7.2)

Module-level type aliases in the `types:` dict may be parameterized with `type_params`.

### Definition

```json
{
  "nail": "0.7.2",
  "kind": "module",
  "id": "collections",
  "types": {
    "Bag": {
      "type_params": ["T"],
      "type": "list",
      "inner": {"type": "param", "name": "T"}
    },
    "Pair": {
      "type_params": ["A", "B"],
      "type": "map",
      "key":   {"type": "param", "name": "A"},
      "value": {"type": "param", "name": "B"}
    }
  }
}
```

### Instantiation

Use `"args": [...]` when referencing a generic alias:

```json
{"type": "alias", "name": "Bag", "args": [{"type": "int", "bits": 64, "overflow": "panic"}]}
```

This resolves to `{"type": "list", "inner": {"type": "int", "bits": 64, "overflow": "panic"}}`.

### Rules

- `"type_params"` must be a non-empty array of distinct string names.
- The number of `"args"` must exactly match the number of `"type_params"`.
- `{"type": "param", "name": "T"}` inside the alias body is replaced by the corresponding arg.
- Generic aliases are resolved lazily (at each instantiation site). They are **not** cached — each instantiation is independent.
- Non-generic aliases (no `"type_params"`) are unchanged; they resolve eagerly and are cached.

### Error codes

| Code | Meaning |
|------|---------|
| `GENERIC_ALIAS_ARITY` | Wrong number of type arguments (too few or too many) |

### Non-generic aliases with spurious `args`

If a non-generic alias (no `type_params`) is referenced with `"args": [...]`, the args are silently ignored. The alias resolves as a non-generic alias.

## 17. Out of Scope (v0.8)

- Closures
- Async/await
- Higher-kinded types (HKT)
- Traits / Interfaces / Type classes
- L4: Memory safety (buffer overflow proofs)
- Higher-rank polymorphism

These may be added in future versions based on AI-generated proposals accepted into the spec.

---

## 18. MCP Bridge (v0.7)

NAIL integrates with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) via three operations:

### `from_mcp`

Convert an MCP tool definition to a NAIL function definition:

```json
{
  "op": "from_mcp",
  "tool": {
    "name": "read_file",
    "description": "Read a file from the filesystem",
    "inputSchema": {
      "type": "object",
      "properties": {
        "path": { "type": "string" }
      },
      "required": ["path"]
    }
  }
}
```

### `to_mcp`

Convert a NAIL function definition to MCP tool format:

```json
{
  "op": "to_mcp",
  "fn": "read_file"
}
```

### `infer_effects`

Infer NAIL effects from an MCP tool definition (heuristic analysis of name, description, and schema):

```json
{
  "op": "infer_effects",
  "tool": { "name": "http_fetch", "description": "Fetch from URL" }
}
```

Returns an array of inferred effect strings (e.g., `["NET"]`).

### Effect Inference Rules

| Pattern | Inferred Effect |
|---------|----------------|
| name/description contains `file`, `read`, `write`, `fs` | `FS` |
| name/description contains `http`, `url`, `fetch`, `request`, `net` | `NET` |
| name/description contains `print`, `log`, `output` | `IO` |
| otherwise | `[]` (pure) |

---

## 19. FC Standard (v0.8.0)

`nail_lang.fc_standard` provides a unified Function Calling standard library for converting between NAIL function definitions and provider-specific schemas.

### Converters

```python
from nail_lang.fc_standard import (
    to_openai_tool,
    to_anthropic_tool,
    to_gemini_tool,
    from_openai_tool,
    from_anthropic_tool,
    from_gemini_tool,
    convert_tools,
)
```

### `to_openai_tool(nail_fn) -> dict`

Converts a NAIL function definition to OpenAI `tools` format:

```json
{
  "type": "function",
  "function": {
    "name": "search_web",
    "description": "Search the web and return results",
    "parameters": {
      "type": "object",
      "properties": {
        "query": { "type": "string" }
      },
      "required": ["query"]
    }
  }
}
```

### `to_anthropic_tool(nail_fn) -> dict`

Converts to Anthropic `tools` format:

```json
{
  "name": "search_web",
  "description": "Search the web and return results",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": { "type": "string" }
    },
    "required": ["query"]
  }
}
```

### `to_gemini_tool(nail_fn) -> dict`

Converts to Gemini `functionDeclarations` format:

```json
{
  "name": "search_web",
  "description": "Search the web and return results",
  "parameters": {
    "type": "OBJECT",
    "properties": {
      "query": { "type": "STRING" }
    },
    "required": ["query"]
  }
}
```

### `convert_tools(nail_fns, target) -> list`

Batch conversion from a list of NAIL function definitions to the specified target format.

```python
openai_tools = convert_tools(nail_fns, target="openai")
anthropic_tools = convert_tools(nail_fns, target="anthropic")
gemini_tools = convert_tools(nail_fns, target="gemini")
```

### Round-Trip Guarantee

NAIL → provider → NAIL round-trips preserve:
- Function name and description
- Parameter names and types (within the expressiveness of each provider's schema format)
- Required parameter list

Effect annotations are preserved as NAIL-side metadata and survive round-trips.

### Type Mapping

| NAIL type | OpenAI/Anthropic/Gemini JSON Schema |
|-----------|-------------------------------------|
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| `string` | `"string"` |
| `list<T>` | `{"type": "array", "items": ...}` |
| `map<K,V>` | `{"type": "object"}` |
| `option<T>` | T + not required |
