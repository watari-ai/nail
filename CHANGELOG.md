# Changelog

All notable changes to NAIL are documented here.

## [v0.8.2] — 2026-02-25

### Fixed

- **`nail demo` broken in pip installs** (#81) — `demos/` was not included in the package distribution. Added `demos/__init__.py`, `demos/scenarios/__init__.py`, and `"demos*"` to setuptools package discovery. Added helpful error message when demo script is not found.
- **Version strings in scenario files** — all `.nail` scenario files updated from `"0.4"` to `"0.8"`.

## [v0.8.1] — 2026-02-25

### Fixed

- **Generic alias eager resolution in imports** (#71) — `_process_imports()` now skips eager resolution for generic aliases (`type_params`), matching main-module behavior. Prevents false arity errors at import time.
- **Checker context propagation to imported modules** (#72) — `_check_imported_module_body()` now passes `level` and `source_path` to sub-checkers, ensuring L3 termination proofs and nested path resolution work correctly.
- **Runtime generic alias args support** (#74) — `_resolve_type_spec` in runtime now handles `{"type":"alias","name":"X","args":[...]}`, matching checker semantics. Fixes typed-null and let-binding paths for generic aliases.
- **CLI option parsing hardened** (#73) — `--level` validates range 1–3, `--format` validates `human|json`, unknown flags produce clear error messages.

### Added

- **`nail demo` subcommand** — `nail demo rogue-agent`, `nail demo verifiability`, `nail demo termination`, `nail demo ai-review`, `nail demo mcp-firewall`, `nail demo trust-boundary`. Six interactive demos showcasing NAIL's effect system, verification, and tooling.
- **Scenario files** (`demos/scenarios/`) — 28 standalone `.nail` files for direct `nail check` verification.
- **CLI.md** — Comprehensive CLI command reference.

### Docs

- README, PHILOSOPHY.md, SPEC.md, ROADMAP.md, IDEAS.md all updated to reflect v0.8.0 positioning and FC Standard.
- GitHub repository: homepage set to `https://naillang.com`, topics added.

## [v0.7.2] — 2026-02-25

### Added

- **Generic Type Aliases** (`interpreter/checker.py`, closes #62)
  - Module-level `types:` dict entries can now have `type_params: ["T", "U", ...]`
  - Instantiation syntax: `{"type": "alias", "name": "Bag", "args": [<type>, ...]}`
  - `_substitute_params_in_spec`: dict-level type-param substitution (pre-resolution)
  - `_resolve_alias_spec`: handles generic vs non-generic paths + arity validation
  - Error code: `GENERIC_ALIAS_ARITY` (wrong number of args)
  - Generic aliases are resolved lazily (not cached, each instantiation is unique)
  - Non-generic aliases unaffected — backward compatible
  - 11 new tests in `tests/test_generic_aliases.py`

## [v0.7.1] — 2026-02-25

### Added

- **MCP Bridge** (`nail_lang/_mcp.py`, `integrations/mcp.md`, closes #61)
  - `from_mcp(mcp_tools)`: MCP tool format → OpenAI FC + NAIL effect annotations
  - `infer_effects(name, desc)`: heuristic effect inference (FS/NET/PROC/TIME/RAND/IO)
  - `to_mcp(openai_tools)`: OpenAI FC → MCP format (strips NAIL extension)
  - Full integration guide in `integrations/mcp.md`
  - 26 new tests in `tests/test_mcp_bridge.py`

## [v0.7.0] — 2026-02-25

### Added

- **Structured JSON Error Messages** (`interpreter/checker.py`, `interpreter/types.py`)
  - `CheckError`, `NailRuntimeError`, `NailTypeError`, `NailEffectError` all gain `to_json()` method
  - Machine-parseable error representation: `{error, code, message, location, ...extra}`
  - Error codes: `EFFECT_VIOLATION`, `UNKNOWN_OP`, `NOT_CANONICAL`, `RUNTIME_ERROR`, `TYPE_ERROR`
  - Backward compatible: `str(err)` and `err.args[0]` still return human-readable message
  - 22 new tests in `tests/test_structured_errors.py`
- **StrategyC FC Standard Proposal** (`docs/fc-standard-proposal.md`)
  - Formal proposal for adding `effects` field to OpenAI/Anthropic Function Calling schemas
  - LiteLLM integration guide (`integrations/litellm.md`)
- **`nail check --format json`** (`nail_cli.py`)
  - Machine-parseable check output: `{"ok": true, "checks": {"L0": "ok", "L1": "ok", ...}}`
  - On error: structured JSON on stderr (uses `CheckError.to_json()`)
  - Level 3 includes inline termination certificate
- **Generics / Parametric Types** (`interpreter/types.py`, `interpreter/checker.py`, SPEC.md §16)
  - `TypeParam` class: `{"type": "param", "name": "T"}` in type specs
  - Generic function declarations: `"type_params": ["T", "U"]` in fn spec
  - Type inference at call sites via unification (`unify_types`)
  - `substitute_type`: applies type substitution after inference
  - All container types support type params: `list<T>`, `option<T>`, `map<K,V>`, `result<T,E>`
  - Error codes: `GENERIC_TYPE_MISMATCH`, `TYPE_PARAM_CONFLICT`, `TYPE_PARAM_UNRESOLVED`
  - 35 new tests in `tests/test_generics.py`

### Fixed

- **Import `"from"` field** (`schema/nail-l0.json`, `interpreter/checker.py`, closes #40)
  - `"from"` is now optional in the L0 schema (removed from `required[]`)
  - Checker automatically loads modules from disk when `"from"` path is specified
  - Resolution order: absolute path → source-relative → CWD
  - Error codes: `MODULE_NOT_FOUND`, `MODULE_LOAD_ERROR`
  - `Checker.__init__` gains `source_path` param; CLI passes it automatically
  - 9 new tests in `tests/test_imports_from.py`

## [v0.6.0] — 2026-02-24

### Added

- **L3 Termination Proof** (`interpreter/checker.py`)
  - `Checker` now accepts `level` parameter (1, 2, or 3; default 2)
  - **Loop termination**: `loop` ops at L3 require `step` to be a literal non-zero integer; variable steps and zero steps raise `CheckError`
  - **Recursive termination**: direct/mutual recursion is permitted at L3 when every function in the cycle declares `"termination": {"measure": "<param>"}` annotation; measure parameter must exist
  - **Termination certificate**: `get_termination_certificate()` returns a JSON-serializable proof object with verdicts for every verified loop and recursion site
  - L2 and below: no behavior change — all existing tests continue to pass

- **CLI `--level` flag** (`nail_cli.py`)
  - `nail check <file> --level 3` — run L0+L1+L2+L3 checks and print termination summary
  - `nail run <file> --level 3` — verify through L3 before executing
  - Default remains `--level 2` for backward compatibility

- **Test suite** (`tests/test_l3_termination.py`)
  - 26 new tests covering: pass cases (literal step, variable bounds, recursive with annotation), fail cases (zero step, variable step, unannotated recursion, bad measure), and certificate content validation

### Changed

- SPEC.md: updated version line (`v0.6 implements L0–L3`), added Section 15 "L3 Termination Proof"
- ROADMAP.md: v0.6 marked ✅ COMPLETE

## [v0.5] — 2026-02-24

### Added

- **Enum / Algebraic Data Types** (Issue #52)
  - `enum_make` op: construct a variant with or without fields
  - `match_enum` op: exhaustive pattern matching — missing variant is a `CheckError`
  - Module-level `types` dict supports `"type": "enum"` with `variants` list
  - Each variant may have typed `fields`; field values are bound in match cases via `binds`
  - Example: `{"tag": "Circle", "fields": [{"name": "radius", "type": {...}}]}`

- **Core Standard Library** (Issue #54)
  - Math: `abs`, `min2`, `max2`, `clamp`
  - String: `str_len`, `str_concat`, `str_slice`, `str_contains`

- **Function Calling Effect Annotations** (Issue #55)
  - `integrations/function_calling.py`: annotate OpenAI/Anthropic tool schemas with NAIL effects
  - `filter_by_effects(tools, allow)`: restrict which tools a sandbox can call
  - Supports `from_openai()`, `from_anthropic()`, `to_nail_annotated()`, `validate_effects()`
  - See `docs/integrations.md` for usage examples

- **Python → NAIL IR Transpiler** (`transpiler/`)
  - Converts type-annotated Python functions to NAIL JSON IR
  - AST-based parsing; auto-detects IO/FS/NET effects from call patterns
  - `transpile_function()`, `transpile_to_json()`, `transpile_and_check()` public API
  - Supports: functions, basic types, return, if/else, for-range, augmented assign

### Improved

- **Return-path exhaustiveness** (Issue #43)
  - Documented and tested: `if` without `else` is always rejected (`CheckError`)
  - `match_enum` case missing `return` is caught by `_check_body` return tracking
  - 9 new tests in `tests/test_return_exhaustiveness.py`

- **Canonical form CI enforcement** (Issue #44)
  - `tools/check-canonical.py`: validates/auto-fixes non-canonical `.nail` files
  - CI step added: all examples must be in JCS canonical form

- **SPEC.md §3.1: Effect Model Static vs Runtime** (Issue #45)
  - Documents what the Checker (L2) guarantees vs Runtime (L2.5) enforces
  - Three-Tier Error Model: Recoverable (Result) / Unrecoverable (panic) / Runtime error

### Tests

- 395 tests total (v0.4: 204, transpiler: 37, function_calling: 44, stdlib/enum: 66, exhaustiveness: 9, other: 35)

---

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

- **Higher-Order Collection Operations** ([PR #51](https://github.com/watari-ai/nail/pull/51))
  - `list_map` — apply `fn(T) -> U` to every element; returns `list<U>`
  - `list_filter` — retain elements where `fn(T) -> bool` is true; returns `list<T>`
  - `list_fold` — reduce list with `fn(Acc, T) -> Acc` and an initial accumulator; returns `Acc`
  - `map_values` — apply `fn(V) -> W` to every map value; returns `map<K, W>`
  - `map_set` — mutate a map entry in place (`key`, `val`); returns `unit`
  - Function references validated at check time: parameter types, return types, and effect propagation enforced
  - Module-level constraint: `list_map`, `list_filter`, `list_fold`, `map_values` require the referenced `fn` to be defined in the same module
  - `FnType` introduced as an internal checker representation (not a first-class NAIL value type)
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
