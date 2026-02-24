# Changelog

All notable changes to NAIL are documented here.

## [v0.4] — 2026-02-24

### Added

- **Type Aliases** ([PR #49](https://github.com/watari-ai/nail/pull/49))
  - Module-level `types` dict for user-defined type aliases
  - Alias resolution in checker and runtime with circular reference detection → `CheckError`
  - Aliases can be used in function signatures, `let` bindings, and nested type expressions
  - Example: `"types": {"UserId": {"type": "int", "bits": 64, "overflow": "panic"}}`

- **Fine-grained Effect Capabilities** ([PR #50](https://github.com/watari-ai/nail/pull/50))
  - Structured effect declarations with path/URL allow-lists and operation constraints
  - Example: `{"kind": "FS", "allow": ["/tmp/"], "ops": ["read"]}` — read-only access to `/tmp/`
  - Backward compatible: legacy string-style `"FS"` / `"NET"` / `"IO"` still accepted
  - Checker validates constraints at check time; runtime enforces resource boundaries at execution time
  - `read_file` (FS) and `http_get` (NET) fully implemented — no longer deferred
  - 106 tests passing

- **Collection Type Operations** ([PR #51](https://github.com/watari-ai/nail/pull/51) — 予定)
  - Type-checked operations: `list_get`, `list_push`, `list_len`, `map_get`
  - Element type and key type validated at check time
  - Out-of-bounds → `NailRuntimeError`; type mismatch → `NailTypeError`
  - 114 tests passing

### Changed

- `read_file` and `http_get` promoted from "checker validates; runtime not yet executed" to fully implemented
- Effect declarations can now be structured objects in addition to plain strings

---

## [v0.3] — 2026-02-24

- **Overflow ops** — `wrap` / `sat` / `panic` at expression level
- **Result type** — `ok` / `err` / `match_result` ops
- **Cross-module import** — `modules` param, circular import detection, effect propagation
- **CI matrix** — Python 3.11 + 3.12, jsonschema L0 validation, example schema checks
- **Verifiability demo** — negative examples showing what NAIL catches at check time
- 94 tests passing

---

## [v0.2] — 2026-02-23

- **Checker fixes** — unknown op → `CheckError`; immutable variable enforcement
- **JCS canonical form** — `nail canonicalize` normalizes any NAIL program; `nail check --strict` rejects non-canonical input
- **`call` op + effect propagation check** — calling IO function from pure context is a compile-time error
- **Tone shift** — Effect System, Zero Ambiguity, and Verification Layers as 3 core guarantees; token efficiency is a side effect
- 73 tests passing

---

## [v0.1] — 2026-02-22

- Initial language spec (`SPEC.md`) and Python reference interpreter
- L0 JSON Schema, L1 Type Checker, L2 Effect Checker
- Types: `int` / `float` / `bool` / `string` / `option` / `list` / `map` / `unit`
- Effect system: `IO` / `FS` / `NET` / `TIME` / `RAND` / `MUT`
- `kind: fn` + `kind: module` + function calls
- Mutable variables (`let mut` + `assign`), bounded loops, if/else, recursion
- Return-path exhaustiveness check
- CLI: `nail run / check` (supports `--call`, `--arg`)
- 50 tests passing
