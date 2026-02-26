# fc_ir_v1 — NAIL Tool-Calling IR Specification

**Spec version**: v0.9 (freeze candidate)  
**Status**: Draft — Pending final review (Issue #88)  
**Created**: 2026-02-25  
**Target NAIL version**: 0.9.x

---

## Freeze Declaration

This document is the reference specification for freezing **fc_ir_v1** in NAIL v0.9.

Once frozen, the following rules apply:

- The semantics of `kind: "fc_ir_v1"` must not change
- Deletion of existing fields or type changes are prohibited
- Additions that break backward compatibility are prohibited
- Future incompatible changes must be defined in a new version `fc_ir_v2`

The optional `annotations` field may be extended while preserving backward compatibility.

---

## Table of Contents

1. [Scope](#1-scope)
2. [Canonicalization](#2-canonicalization)
3. [ToolDef Schema](#3-tooldef-schema)
4. [Name Sanitization](#4-name-sanitization)
5. [Type Subset](#5-type-subset)
6. [Effects Representation](#6-effects-representation)
7. [Provider Mapping](#7-provider-mapping)
8. [Diagnostics](#8-diagnostics)

---

## 1. Scope

### What is fc_ir_v1?

`fc_ir_v1` is a **NAIL-native Tool Definition Intermediate Representation (IR)**. It defines tools in a provider-agnostic unified format — independent of any specific provider (OpenAI, Anthropic, Gemini, etc.) — and serves as a bridge layer for converting tool definitions into each provider's schema.

Primary design goals:

- **Provider-agnostic**: A single definition can generate schemas for multiple providers
- **Conversion transparency**: Explicitly indicates whether a provider conversion is lossy (information-lossy) or non-lossy
- **Integration with `nail check`**: Type checking and effects verification use the same type system as `nail check`
- **Machine-generated format**: Intended for generation and transformation by the NAIL compiler and toolchain

### Target use cases

- Storing and distributing tool definitions auto-generated from NAIL code
- Tool schema validation in CI/CD (`nail fc check`)
- Automated multi-provider deployment

### Non-goals

| Non-goal | Reason |
|----------|--------|
| General-purpose programming IR | This spec is specific to NAIL's Tool-Calling. It is not a general-purpose IR (e.g., LLVM IR) |
| Human-authored format | Designed for machine generation and transformation. Humans should refer to the NAIL source |
| Runtime execution spec | The tool invocation protocol and response handling are defined in a separate specification |
| Provider-specific extension management | Hints can be passed via the `annotations` field, but provider-specific semantics are out of scope |

---

## 2. Canonicalization

### What is canonical form?

`fc_ir_v1` has a unique canonical form defined for it, and the toolchain must always output in canonical form. Canonical form ensures that file comparison, hash verification, and diff display are unambiguous.

### Root key ordering

The keys of the root object must be output in the following order:

```
kind → tools → meta
```

### ToolDef key ordering

The keys of each element in the `tools` array (ToolDef) must be output in the following order:

```
id → name → title → doc → effects → input → output → examples → annotations
```

Absent keys are omitted. If unknown keys outside the spec are present, emit FC011 WARN and output them after the known keys (normal mode). Additional keys inside `annotations` are not treated as unknown spec keys.

### JSON formatting rules

- **No whitespace (compact JSON)**: Minimal representation with no spaces or newlines
- **`ensure_ascii=False`**: Non-ASCII characters (e.g., Japanese) are not escaped
- **Key sorting**: Follow the defined order above, not alphabetical order

### Canonicalization command

```bash
nail fc canonicalize <input.json> [-o <output.json>]
```

Options:
- `-o / --output`: Output file path (defaults to stdout if omitted)
- `--in-place`: Overwrite input file in place

### Canonical form check

```bash
nail fc check --strict <input.json>
```

With the `--strict` flag, canonical form violations are reported as **FC005 ERROR**. Recommended for CI environments.

### Handling unknown keys

If fields outside the spec (unknown keys) appear anywhere other than `annotations`, the toolchain behaves as follows:

<!-- Design rationale: It would be too harsh on developer experience to abort a normal canonicalize
     for unknown keys. The responsibility of canonicalize is "normalization," and preserving
     unknown information falls within that scope.
     Strict validation is delegated to check --strict. -->

**Normal mode:**
- **`nail fc check`**: Reports unknown keys as **FC011 WARN** (not an error)
- **`nail fc canonicalize`**: **Preserves unknown keys as-is** (no information destruction). Key reordering and value normalization still apply; unknown keys are placed after known keys (stable position). **Unknown keys are sorted lexicographically among themselves** (e.g., `{"z_unknown": ..., "m_unknown": ...}` → canonical output: `m_unknown`, then `z_unknown`). Outputs **FC011 WARN**

**Strict mode (`--strict`):**
- **`nail fc check --strict`**: Reports unknown keys as **FC011 ERROR**
- **`nail fc canonicalize --strict`**: Aborts conversion on unknown key detection and returns an error

Example WARN message:
```
FC011 WARN: Unknown key 'timeout' in ToolDef 'weather.get'. Consider moving to 'annotations'.
```

To move an unknown key to an allowed field, use `annotations`:
```json
{
  "id": "weather.get",
  "annotations": {
    "timeout": 30
  }
}
```

### Canonical form example

Canonical form (compact, ensure_ascii=False):
```json
{"kind":"fc_ir_v1","tools":[{"id":"weather.get","name":"weather_get","title":"Get current weather","doc":"Retrieves current weather information for a specified city. Returns temperature, humidity, and weather summary.","effects":{"kind":"capabilities","allow":["NET:http_get"]},"input":{"type":"object","properties":{"city":{"type":"string"},"units":{"type":"enum","values":["celsius","fahrenheit"]}},"required":["city"]},"output":{"type":"object","properties":{"temperature":{"type":"float"},"humidity":{"type":"float"},"description":{"type":"string"}},"required":["temperature","humidity","description"]}}],"meta":{"nail_version":"0.9.0","created_at":"2026-02-25T10:00:00Z","source_hash":"sha256:abc123","spec_rev":"abc1234"}}
```

---

## 3. ToolDef Schema

### Root structure

```json
{
  "kind": "fc_ir_v1",
  "tools": [
    { /* ToolDef */ },
    { /* ToolDef */ }
  ],
  "meta": {
    "nail_version": "0.9.0",
    "created_at": "2026-02-25T10:00:00Z",
    "source_hash": "sha256:...",
    "spec_rev": "abc1234"
  }
}
```

#### `meta` fields

| Field | Required | Description |
|-------|----------|-------------|
| `nail_version` | Recommended | NAIL version used for generation |
| `created_at` | Recommended | ISO 8601 UTC (Z) generation timestamp |
| `source_hash` | Optional | SHA-256 hash of the source file used for generation |
| `spec_rev` | Optional | Revision of this spec (e.g., git commit hash) |

> `created_at` must use **UTC ISO 8601 with Z suffix**. Example: `"2026-02-25T10:00:00Z"`. Timezone offsets (e.g., `+09:00`) are not allowed.

### ToolDef field specification

#### Required fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Stable identifier. Dot-separated allowed (e.g., `weather.get`). **Must not change once published.** |
| `doc` | string | Description for the LLM to understand the tool's purpose. 1–2 paragraphs. The core field for LLM guidance. |
| `effects` | object | Declaration of side effects the tool has. Capabilities format (see §6). |
| `input` | Type | Argument type definition. **Must be `type: "object"`** (FC003). If `input.required` is omitted or empty and `input.properties` has 2+ entries, emit **FC012 WARN**. |

#### Recommended fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Provider-safe tool name. Auto-generated as `sanitize(id)` if omitted (see §4). |
| `title` | string | Short display name for humans and LLMs. Used in UI display and LLM selection decisions. |
| `output` | Type | Return type definition. FC006 WARN is emitted if omitted. Reduces type verification coverage. |
| `examples` | array | Concrete input/output examples. Format: `[{ "input": {...}, "output": {...}, "description": "..." }]`. |

#### Optional fields

| Field | Type | Description |
|-------|------|-------------|
| `annotations` | object | Arbitrary key-value store for provider hints and future extensions. Backward compatibility guaranteed. Unknown keys are ignored by the toolchain. |

### Complete ToolDef example

```json
{
  "id": "weather.get",
  "name": "weather_get",
  "title": "Get current weather",
  "doc": "Retrieves current weather information for a specified city from an external API.\nReturns structured data including temperature, humidity, and weather summary. City name may be specified in English.",
  "effects": {
    "kind": "capabilities",
    "allow": ["NET:http_get"]
  },
  "input": {
    "type": "object",
    "properties": {
      "city": {
        "type": "string"
      },
      "units": {
        "type": "optional",
        "inner": {
          "type": "enum",
          "values": ["celsius", "fahrenheit"]
        }
      }
    },
    "required": ["city"]
  },
  "output": {
    "type": "object",
    "properties": {
      "temperature": { "type": "float" },
      "humidity": { "type": "float" },
      "description": { "type": "string" }
    },
    "required": ["temperature", "humidity", "description"]
  },
  "examples": [
    {
      "input": { "city": "Tokyo", "units": "celsius" },
      "output": { "temperature": 22.5, "humidity": 60.0, "description": "Clear" },
      "description": "Get Tokyo weather in Celsius"
    }
  ],
  "annotations": {
    "openai.strict": true,
    "cache_ttl_seconds": 300
  }
}
```

### Minimal ToolDef example (PURE tool)

```json
{
  "id": "math.add",
  "doc": "Adds two integers and returns the result. No side effects.",
  "effects": {
    "kind": "capabilities",
    "allow": []
  },
  "input": {
    "type": "object",
    "properties": {
      "a": { "type": "int" },
      "b": { "type": "int" }
    },
    "required": ["a", "b"]
  }
}
```

---

## 4. Name Sanitization

### Required format after sanitization

```
name = /^[a-z][a-z0-9_]*$/
```

Must begin with a lowercase letter (`[a-z]`), followed by any length of `[a-z0-9_]`. For example, `t_123abc` passes because it starts with `t` (a lowercase letter) — this is not special-casing `t_`, but simply satisfying the general rule that the first character must be a lowercase letter.

The final name must conform to `/^[a-z][a-z0-9_]*$/`. Failure to conform generates **FC002 ERROR** from `nail fc check`.

### Auto-generation rules

When the `name` field is omitted, it is auto-generated from `id` using the following rules:

1. Replace `.` and `-` with `_`
2. Replace all characters not in `[a-z0-9_]` with `_`
3. Collapse consecutive `_` into one
4. Normalize to lowercase
5. If the result starts with a digit, prepend `t_`
6. Trim trailing `_`
7. If the sanitized string is empty (e.g., `id="---"` or `id="🎉"` — no valid characters remain):
   - **FC002 ERROR**: `"Tool name cannot be empty after sanitization"`
   - Auto-generation is not performed (empty string is not used)

### Conversion examples

| `id` | Generated `name` |
|------|-----------------|
| `weather.get` | `weather_get` |
| `my-tool` | `my_tool` |
| `123abc` | `t_123abc` |
| `File/Reader` | `file_reader` |
| `my..double.dot` | `my_double_dot` |
| `hello world` | `hello_world` |
| `net.http.GET` | `net_http_get` |

### Collision detection

If two or more tools within the same `tools` list share the same `name` (whether explicit or auto-generated), it is an **FC002 ERROR**.

Collision example:
```json
{
  "tools": [
    { "id": "weather.get", /* name → weather_get */ ... },
    { "id": "weather_get", /* name → weather_get (collision!) */ ... }
  ]
}
```

Error message:
```
[FC002] ERROR: Name collision: tools 'weather.get' and 'weather_get' both generate name 'weather_get'. Specify 'name' explicitly.
```

Resolution:
```json
{
  "tools": [
    { "id": "weather.get",  "name": "weather_get_v1", ... },
    { "id": "weather_get",  "name": "weather_get_v2", ... }
  ]
}
```

---

## 5. Type Subset

The types usable in `input` / `output` of `fc_ir_v1` are a subset of the NAIL type system.

### Type list and provider mapping

| Type | fc_ir_v1 representation | OpenAI | Anthropic | Gemini |
|------|------------------------|--------|-----------|--------|
| bool | `{"type":"bool"}` | `boolean` | `boolean` | `boolean` |
| int (no precision) | `{"type":"int"}` | `integer` | `integer` | `integer` |
| int (with precision) | `{"type":"int","bits":64,"overflow":"panic"}` | `integer` + lossy | `integer` + lossy | `integer` + lossy |
| float | `{"type":"float"}` | `number` | `number` | `number` |
| string | `{"type":"string"}` | `string` | `string` | `string` |
| array | `{"type":"array","items":T}` | `array` | `array` | `array` |
| object | `{"type":"object","properties":{...},"required":[...]}` | `object` | `object` | `object` |
| optional | `{"type":"optional","inner":T}` | T (excluded from required) | T (excluded from required) | T (excluded from required) |
| enum | `{"type":"enum","values":["a","b"]}` | `string` + `enum` | `string` + `enum` | `string` + `enum` |

### Type representation details

#### bool

```json
{ "type": "bool" }
```

#### int (no precision)

```json
{ "type": "int" }
```

#### int (with precision)

```json
{
  "type": "int",
  "bits": 64,
  "overflow": "panic"
}
```

Valid `overflow` values: `"panic"` | `"wrap"` | `"saturate"`

#### float

```json
{ "type": "float" }
```

#### string

```json
{ "type": "string" }
```

#### array

```json
{
  "type": "array",
  "items": { "type": "string" }
}
```

#### object

```json
{
  "type": "object",
  "properties": {
    "name": { "type": "string" },
    "age":  { "type": "int" }
  },
  "required": ["name"]
}
```

If `required` is omitted, all fields are treated as optional.

#### optional

```json
{
  "type": "optional",
  "inner": { "type": "string" }
}
```

During provider conversion: use the `inner` type as-is, and exclude this field from the `required` array.

#### enum

```json
{
  "type": "enum",
  "values": ["celsius", "fahrenheit", "kelvin"]
}
```

During provider conversion: output as `type: "string"` + `enum: [...]`.

### Recording lossy type information

Precision information such as `int.bits` / `int.overflow` that cannot be represented in provider schemas is treated as **lossy**. Information lost during conversion is recorded in the `lossy` field of `tools.meta.json` (or equivalent metadata file):

```json
{
  "lossy": {
    "weather.get": {
      "name": "weather_get",
      "fields": ["int.bits", "int.overflow"]
    }
  }
}
```

`lossy` field specification:
- Keys are **`id`-based** (for stable reference; `name` is not used because renaming may change it)
- `name` field is the corresponding provider-safe name (trackable even after renaming)
- `fields` is a list of lost field paths

---

## 6. Effects Representation

### Standard format (capabilities)

```json
{
  "kind": "capabilities",
  "allow": ["FS:read_file", "NET:http_get", "IO:stdout"]
}
```

Each element of the `allow` array takes the form `{category}:{operation}`, or `{category}` alone.

### Category list

| Category | Description |
|----------|-------------|
| `PURE` | No side effects. Equivalent to an empty `allow` array. |
| `IO` | Access to standard I/O (stdin/stdout/stderr) |
| `FS` | Access to the filesystem |
| `NET` | Network communication |
| `SYS` | System calls (process creation, signals, etc.) |

### Declaring a PURE tool

When `allow` is an empty array, the tool is treated as having no side effects (PURE):

```json
{
  "kind": "capabilities",
  "allow": []
}
```

If a PURE tool includes `FS`/`NET`/`IO` categories in `allow`, it is an **FC004 ERROR**.

### Operation-level specification examples

```json
{
  "kind": "capabilities",
  "allow": [
    "FS:read_file",
    "FS:write_file",
    "NET:http_get",
    "NET:http_post",
    "IO:stdout"
  ]
}
```

Category-only specification (e.g., `"FS"`) is valid, but operation-level specification is recommended where possible.

### Legacy format (deprecated)

The following format is accepted for backward compatibility but emits **FC009 WARN**:

```json
["FS", "NET"]
```

Running `nail fc canonicalize` converts it to the standard capabilities format:

```json
{
  "kind": "capabilities",
  "allow": ["FS", "NET"]
}
```

### Effects verification by fc check

- `allow` is empty (PURE) but `FS`/`NET`/`IO` is present → **FC004 ERROR**
- Unknown category (other than `PURE` / `IO` / `FS` / `NET` / `SYS`) → **FC009 WARN** (FC009 is also used for legacy format; distinguish by context)
- Legacy string array format used → **FC009 WARN**

### Converting effects to providers

There is no standard way to pass structured effects information to provider schemas. `effects` is treated as a **lossy field**.

Optionally, `nail fc convert --provider openai --annotate-effects` appends effect annotations to OpenAI's `function.description` (default: OFF):

```json
{
  "function": {
    "name": "read_log_file",
    "description": "Reads a log file and returns its content.\n\n[effects: FS:read_file]"
  }
}
```

---

## 7. Provider Mapping

### Overview

`nail fc convert <tools.nail> --provider <name>` converts to each provider's schema format.

```bash
nail fc convert <tools.nail> --provider openai    -o openai-tools.json
nail fc convert <tools.nail> --provider anthropic -o anthropic-tools.json
nail fc convert <tools.nail> --provider gemini    -o gemini-tools.json
```

### OpenAI

Field mapping:

| fc_ir_v1 | OpenAI | Notes |
|----------|--------|-------|
| `name` | `function.name` | |
| `doc` | `function.description` | |
| `input` | `function.parameters` | JSON Schema format |
| `effects` | (lossy) | Appended to description with `--annotate-effects` |
| `output` | (lossy) | |
| `examples` | (lossy) | |
| `annotations.openai.*` | Corresponding fields | e.g., `strict` |

Conversion example:

```json
{
  "type": "function",
  "function": {
    "name": "weather_get",
    "description": "Retrieves current weather information for a specified city from an external API.\nReturns structured data including temperature, humidity, and weather summary.",
    "parameters": {
      "type": "object",
      "properties": {
        "city": { "type": "string" },
        "units": { "type": "string", "enum": ["celsius", "fahrenheit"] }
      },
      "required": ["city"]
    },
    "strict": true
  }
}
```

### Anthropic

Field mapping:

| fc_ir_v1 | Anthropic | Notes |
|----------|-----------|-------|
| `name` | `name` | |
| `doc` | `description` | |
| `input` | `input_schema` | JSON Schema format |
| `effects` | (lossy) | |
| `output` | (lossy) | |
| `examples` | (lossy) | |

Conversion example:

```json
{
  "name": "weather_get",
  "description": "Retrieves current weather information for a specified city from an external API.\nReturns structured data including temperature, humidity, and weather summary.",
  "input_schema": {
    "type": "object",
    "properties": {
      "city": { "type": "string" },
      "units": { "type": "string", "enum": ["celsius", "fahrenheit"] }
    },
    "required": ["city"]
  }
}
```

### Gemini

Field mapping:

| fc_ir_v1 | Gemini | Notes |
|----------|--------|-------|
| `name` | `name` | |
| `doc` | `description` | |
| `input` | `parameters` | JSON Schema format (Gemini uses OpenAPI Subset) |
| `effects` | (lossy) | |
| `output` | (lossy) | |
| `examples` | (lossy) | |

Conversion example:

```json
{
  "name": "weather_get",
  "description": "Retrieves current weather information for a specified city from an external API.\nReturns structured data including temperature, humidity, and weather summary.",
  "parameters": {
    "type": "object",
    "properties": {
      "city": { "type": "string" },
      "units": { "type": "string", "enum": ["celsius", "fahrenheit"] }
    },
    "required": ["city"]
  }
}
```

### Lossy field summary

The following fields cannot be represented in provider schemas and are lost during conversion (lossy):

| Field / Information | Reason |
|--------------------|--------|
| `int.bits` / `int.overflow` | Provider integer types do not carry precision information |
| `effects` structure | Provider tool schemas have no effects field |
| `examples` | Provider tool definitions have no example field |
| `output` type | Providers do not carry output type schemas in tool definitions |
| `annotations` | Non-provider-specific keys have no conversion target |

Lossy information can be emitted to a JSON file during conversion using `--lossy-report <file>` or `--emit-meta`.

`--emit-meta` output example (lossy keys unified by `id`):
```json
{
  "lossy": {
    "math.add": {
      "name": "math_add",
      "fields": ["int.bits", "int.overflow"]
    }
  }
}
```

---

## 8. Diagnostics

Complete list of all ERRORs and WARNs reported by `nail fc check`.

### Error code reference

| Code | Level | Condition | Message |
|------|-------|-----------|---------|
| **FC001** | ERROR | `id` is not unique | `Duplicate tool id: '{id}'` |
| **FC002** | ERROR | `name` collision (including auto-generated) | `Name collision: tools '{id1}' and '{id2}' both generate name '{name}'. Specify 'name' explicitly.` |
| **FC003** | ERROR | `input` is not an object | `Tool '{id}': 'input' must be of type object, got '{type}'` |
| **FC004** | ERROR | PURE tool declares effects | `Tool '{id}': pure tool declares effects {effects}` |
| **FC005** | ERROR | Canonical form violation in strict mode | `Input is not in canonical form. Run 'nail fc canonicalize' to fix.` |
| **FC006** | WARN | `output` not specified | `Tool '{id}': output type not declared — verification coverage is reduced` |
| **FC007** | WARN | Type not representable in provider (non-strict) | `Tool '{id}': type '{type}' is not representable in {provider} schema; will be degraded` |
| **FC008** | ERROR | Type not representable in provider (`--strict-provider`) | `Tool '{id}': type '{type}' cannot be represented in {provider} schema` |
| **FC009** | WARN | Legacy effects format in use | `Tool '{id}': effects uses legacy string array format; run 'nail fc canonicalize' to normalize` |
| **FC010** | WARN | `doc` is empty or too short (<20 chars) | `Tool '{id}': doc is too short (<20 chars); LLM guidance may be insufficient` |
| **FC011** | WARN (normal) / ERROR (`--strict`) | Unknown key outside `annotations` in ToolDef | `Unknown key '{key}' in ToolDef '{id}'. Consider moving to 'annotations'.` |
| **FC012** | WARN | `input.required` absent/empty with properties ≥ 2 | `Tool '{id}': 'input.required' is absent or empty but 'input.properties' has {n} fields — required args may be unintentionally optional` |

### Check modes

```bash
# Standard check (exit code 1 on ERROR only)
nail fc check input.json

# Strict check (canonical violations also become ERRORs)
nail fc check --strict input.json

# Provider strict check (types not representable in provider become ERRORs)
nail fc check --strict-provider openai input.json
nail fc check --strict-provider anthropic input.json
nail fc check --strict-provider gemini input.json

# Treat WARNs as exit code 1 (recommended for CI)
nail fc check --strict --fail-on-warn input.json
```

### Output format

```
[FC001] ERROR: Duplicate tool id: 'weather.get'
  at tools[3].id

[FC006] WARN: Tool 'math.add': output type not declared — verification coverage is reduced
  at tools[1]

[FC010] WARN: Tool 'fs.read': doc is too short (<20 chars); LLM guidance may be insufficient
  at tools[2].doc
```

### Recommended CI configuration

```yaml
# .github/workflows/nail-check.yml
- name: nail fc check
  run: |
    nail fc check --strict --fail-on-warn tools.fc.json
```

---

## Appendix A: Complete fc_ir_v1 file example

```json
{
  "kind": "fc_ir_v1",
  "tools": [
    {
      "id": "weather.get",
      "name": "weather_get",
      "title": "Get current weather",
      "doc": "Retrieves current weather information for a specified city from an external API.\nReturns structured data including temperature, humidity, and weather summary.",
      "effects": {
        "kind": "capabilities",
        "allow": ["NET:http_get"]
      },
      "input": {
        "type": "object",
        "properties": {
          "city": { "type": "string" },
          "units": {
            "type": "optional",
            "inner": { "type": "enum", "values": ["celsius", "fahrenheit"] }
          }
        },
        "required": ["city"]
      },
      "output": {
        "type": "object",
        "properties": {
          "temperature": { "type": "float" },
          "humidity": { "type": "float" },
          "description": { "type": "string" }
        },
        "required": ["temperature", "humidity", "description"]
      },
      "examples": [
        {
          "input": { "city": "Tokyo", "units": "celsius" },
          "output": { "temperature": 22.5, "humidity": 60.0, "description": "Clear" },
          "description": "Get Tokyo weather in Celsius"
        }
      ],
      "annotations": {
        "openai.strict": true,
        "cache_ttl_seconds": 300
      }
    },
    {
      "id": "math.add",
      "name": "math_add",
      "title": "Integer addition",
      "doc": "Adds two integers and returns the result. No side effects. Panics on overflow.",
      "effects": {
        "kind": "capabilities",
        "allow": []
      },
      "input": {
        "type": "object",
        "properties": {
          "a": { "type": "int", "bits": 64, "overflow": "panic" },
          "b": { "type": "int", "bits": 64, "overflow": "panic" }
        },
        "required": ["a", "b"]
      },
      "output": {
        "type": "int",
        "bits": 64,
        "overflow": "panic"
      }
    },
    {
      "id": "fs.read_file",
      "name": "fs_read_file",
      "title": "Read file",
      "doc": "Reads the file at the specified path and returns its content as a string.\nReturns an error if the file does not exist. Assumes UTF-8 encoding.",
      "effects": {
        "kind": "capabilities",
        "allow": ["FS:read_file"]
      },
      "input": {
        "type": "object",
        "properties": {
          "path": { "type": "string" },
          "encoding": {
            "type": "optional",
            "inner": { "type": "string" }
          }
        },
        "required": ["path"]
      },
      "output": {
        "type": "string"
      }
    }
  ],
  "meta": {
    "nail_version": "0.9.0",
    "created_at": "2026-02-25T10:00:00Z",
    "source_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "spec_rev": "abc1234"
  }
}
```

---

## Appendix B: Auto-generation flow from NAIL source

```
NAIL source (.nail)
       │
       ▼
  nail compile
       │
       ▼
 fc_ir_v1 JSON        ← Format defined by this specification
       │
       ├─► nail fc check         (type, effects, canonical verification)
       │
       ├─► nail fc convert <tools.nail> --provider openai      → OpenAI tools JSON
       ├─► nail fc convert <tools.nail> --provider anthropic   → Anthropic tools JSON
       └─► nail fc convert <tools.nail> --provider gemini      → Gemini tools JSON
```

---

## Appendix C: Change history

| Version | Date | Changes |
|---------|------|---------|
| v0.9-draft | 2026-02-25 | Initial draft (Issue #88) |
| v0.9-draft | 2026-02-25 | FC011: canonicalize preserves unknown keys with WARN (no abort). Escalates to ERROR in --strict mode only |

---

*This document is the freeze-candidate draft for fc_ir_v1 in NAIL v0.9. It will be finalized as v0.9 following review.*
