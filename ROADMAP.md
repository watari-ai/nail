# NAIL — Roadmap

## Phase 1: Spec Draft (~1 week)

**Goal:** Finalize the core language spec and implement a Python reference interpreter

- [x] Document design philosophy (`PHILOSOPHY.md`)
- [x] Language spec v0.1 draft (`SPEC.md`)
- [x] JSON schema definition (L0 validation)
- [x] Python reference interpreter implementation
  - [x] Type checker (L1): 252 lines
  - [x] Effect checker (L2)
  - [x] Execution engine: 220 lines
- [x] Expanded examples (9 samples achieved)
  - hello.nail, add.nail, sum_loop.nail, bad_effect.nail (existing)
  - factorial.nail, max_of_two.nail, is_even.nail, countdown.nail,
    fibonacci.nail, math_module.nail (4-fn module)
- [x] Test suite: 50 tests all pass (2026-02-22)
- [x] CLI: `nail run / check` (supports `--call`, `--arg`)

**Deliverable:** `nail/interpreter/` — Python reference interpreter (commit 51e41fa)

✅ **Phase 1 Complete — 2026-02-22**

---

## Phase 2: LLM Validation Experiment (~2 weeks) ✅ Complete

**Goal:** Quantitatively validate whether "NAIL is AI-friendly"

**Experiment Design:**
- Have LLMs implement the same spec set (10 tasks) in both Python and NAIL
- Measurements:
  - Bug rate (compile errors + test failures)
  - Generated token count
  - Spec deviation rate
  - Reproducibility (agreement rate across repeated generations with the same prompt)

**Models:** Claude Sonnet, GPT-4o (multi-model comparison)

**Results (2026-02-22):**
- NAIL: 5/5 spec checks pass, 18/21 tests pass
- Key finding: failures = spec gaps, not AI errors → validates core thesis
- Proposal #001 implemented (mutable variables via `assign` op)

**Deliverables:**
- `experiments/phase2/` — experiment result data, ANALYSIS.md, results.json ✅
- Moldium article #3: "The Experiment: I Made AI Write..." — scheduled 2026-02-24 ✅

---

## v0.2 — Released ✅ (2026-02-23)

**Goal:** Strengthen core semantics and demonstrate Effect System.

- [x] **Checker fixes**: unknown op → CheckError, immutable variable enforcement
- [x] **JCS canonical form**: `json.dumps(sort_keys=True, separators=(',',':'))` — one representation, always. L0 now enforces canonical input.
- [x] **README / PHILOSOPHY tone**: Effect System, Zero Ambiguity, and Verification Layers as the 3 core guarantees (token efficiency is a side effect, not a goal).
- [x] **`call` op + effect propagation check**: `fn main [] → fn helper [IO]` is a compile-time error. This is the Effect System working. — commit `48b3fbd`

73 tests passing.

## v0.3 — Released ✅ (2026-02-24)

Implemented autonomously via development cron agent. Design documents in [`designs/v0.3/`](designs/v0.3/). 94 tests passing.

- [x] **Overflow ops** — `wrap` / `sat` / `panic` at expression level · [Issue #2](https://github.com/watari-ai/nail/issues/2) · commit `ff881ab`
- [x] **Result type** — `ok`/`err`/`match_result` ops · [Issue #3](https://github.com/watari-ai/nail/issues/3) · commit `91992df`
- [x] **Cross-module import** — `modules` param, circular import detection, effect propagation · [Issue #4](https://github.com/watari-ai/nail/issues/4) · commit `2cbc84c`
- [x] **CI matrix**: Python 3.11 + 3.12, jsonschema L0 validation, example schema checks
- [x] **Verifiability demo**: negative examples showing what NAIL catches at check time

---

## v0.4 Goals — Released ✅ (2026-02-24)

Informed by [Gemini 2.0 Flash strategic evaluation](https://github.com/watari-ai/nail/issues/15) (Issue #15) and multi-AI strategic review.

- [x] **Type Aliases** — `alias` definitions with transitivity and circular detection (PR #49, 21 tests)
- [x] **Fine-grained Effect Annotations** — `FS:/tmp/` path-scoped effects (PR #50, 35 tests)
- [x] **Collection Type Operations** — `list_map`, `list_filter`, `list_fold`, `map_values`, `map_set` (PR #51, 39 tests)
- [x] **Function Calling Effect Annotations** — OpenAI/Anthropic tool schema integration (`integrations/function_calling.py`, 44 tests, commit `e204297`)
- [x] **Python → NAIL Transpiler** — AST-based conversion with auto-effect inference (`transpiler/python_to_nail.py`, 37 tests, commit `252d822`)
- [x] **PyPI v0.4.0** — `pip install nail-lang` → https://pypi.org/project/nail-lang/0.4.0/
- [ ] **NAIL SDK** — Deferred to v0.6+
- [ ] **Nail-Lens** — Deferred to v0.7 (LSP section)
- [ ] **Token efficiency benchmarks** — Deferred to Phase 3 experiments

---

## v0.5 Goals — Proof of Utility
Informed by multi-AI strategic review (Opus, Codex, Gemini — 2026-02-24).

- [x] **Enum / Algebraic Data Types (ADT)** — Natural extension of Result type. Required for state machines and complex data representation in real demos.
- [x] **Python (typed subset) → NAIL transpiler** — Convert type-annotated Python to NAIL for type+effect verification. Scope: functions with full type annotations only (no dynamic typing).
- [x] **Core Standard Library** — Official modules: string ops (split, trim, contains, replace), math functions, list/map utilities beyond v0.4 collection ops.
- [x] **Function Calling Effect Annotations** — Add NAIL-style effect declarations to OpenAI/Anthropic function_calling definitions. Proposal: proposals/function-calling-effects.md

## v0.6 Goals — Type System Strengthening + Formal Verification ✅ COMPLETE
- [x] **L3 Formal Verification** — Termination proofs for bounded loops + recursive decreasing-measure annotation. `nail check --level 3` emits a termination certificate. NAIL's strongest differentiator: 'this program is provably guaranteed to halt.'
- [x] **Generics / Parametric Types** — list<T>, map<K,V>, fn<T>(T) -> T. Required for type-safe stdlib. (deferred to v0.7+) (implemented in v0.7)
- [x] **Error Message Improvement** — Structured checker errors that AI agents can parse and self-correct. JSON-formatted error output option. (deferred to v0.7+) (implemented in v0.7)

### L3 Future Work
- [ ] **L3.1 (future)**: Verify measure decrease at call sites — confirm that recursive calls pass `measure - k` (k > 0), ensuring the annotated measure is genuinely decreasing.

## v0.7.0 (2026-02-25) — Generics & MCP Bridge ✅ COMPLETE
- [x] **TypeParam / type inference** — `unify_types` / `substitute_type`, generic function definitions
- [x] **import "from" optional schema** — auto-module load from file path
- [x] **JSON error format** — `nail check --format json` for machine-parseable output
- [x] **MCP Bridge** — `from_mcp` / `to_mcp` / `infer_effects` for MCP protocol integration
- [x] **Shareable Playground links** — URL hash encoding for shareable examples

## v0.7.2 (2026-02-25) — Generic Type Aliases ✅ COMPLETE
- [x] **Module-level type aliases with type_params** — `alias` definitions with generic parameters
- [x] **SPEC.md §16.5** — Generic type aliases formally specified

## v0.8.0 (2026-02-25) — FC Standard ✅ COMPLETE
- [x] **`nail_lang.fc_standard` module** — unified Function Calling standard library
- [x] **to_openai_tool / to_anthropic_tool / to_gemini_tool** — NAIL → provider schema converters
- [x] **from_openai_tool / from_anthropic_tool / from_gemini_tool** — provider schema → NAIL converters
- [x] **`convert_tools()` batch utility** — bulk conversion between all formats
- [x] **Round-trip tests** — NAIL ↔ OpenAI ↔ Anthropic ↔ Gemini verified
- [x] **Playground examples** — MCP Bridge, Generic Type Aliases, FC Standard demo examples

## Future Plans

These items were originally scoped for v0.7/v0.8 but are deferred. They remain valuable long-term goals.

### Developer Experience & Connectivity
- [ ] **LSP Support** — Language Server Protocol for Nail-Lens integration. Hover types, error highlighting, go-to-definition for NAIL JSON.
- [ ] **NAIL → WebAssembly** — Compile NAIL to Wasm for browser execution. Playground v2 with native performance.
- [ ] **AI Agent Protocol (NATP)** — NAIL-format task delegation between agents. Agent A delegates to Agent B with formal effect constraints.

### Concurrency & Security
- [ ] **Async / Concurrency** — Full design required simultaneously: cancellation, timeout, join/await types, determinism policy. Not just `effects: [ASYNC]`.
- [ ] **Effect Security Model** — Formal policy for FS/NET/TIME/RAND/ASYNC: audit log spec, permission boundary definitions.

## v0.9 Goals — HN Show HN Preparation

**Phase A: Pre-HN (v0.9.0)**
- [ ] **Token Efficiency Benchmarks** — Quantitative comparison of NAIL vs Python/TypeScript token usage per function. Validates the "AI-native" claim with data. Publish results on Moldium + include in HN post.
- [ ] **L3.1 Call-site Measure Verification** — Verify that recursive calls pass `measure - k` (k > 0) at each call site, making termination proofs genuinely sound rather than trust-based annotations.
- [ ] **NAIL SDK** — Clean Python API with type stubs (`nail_lang` public interface), formal API documentation, and usage examples for each major feature (FC Standard, filter_by_effects, MCP Bridge).
- [x] **Documentation complete** — SPEC.md (v0.8.0), PHILOSOPHY.md, ROADMAP.md, README.md, CLI.md, IDEAS.md all updated and reviewed (2026-02-25).

**Phase B: Post-HN (v0.9.x)**
- [ ] **Spec Versioning Policy** — Formal definition of breaking vs non-breaking changes, deprecation period rules. (Incorporate community feedback from HN first.)
- [ ] **Conformance Test Suite** — Canonical test set for alternative NAIL implementations to validate spec compliance.

**Phase C: v1.0 RC**
- [ ] **Spec Freeze** — NAIL JSON format frozen. No breaking changes after this point.

---

## Phase 3: OSS Development & Experimentation (~1 month)

**Goal:** Public repository, working playground, and technical experimentation

- [x] Publish GitHub repository (`watari-ai/nail`) — live at https://github.com/watari-ai/nail
- [x] Build NAIL Playground (web UI to try NAIL in browser) — https://watari-ai.github.io/nail/
- [x] Technical writing (Moldium): 3 articles published covering design philosophy and LLM experiment results

**Experimental Additions (v0.3 scope):**

- [ ] **Reproducibility demo** — run the same complex task across multiple LLMs repeatedly; measure agreement rate and failure modes
- [ ] **Verify-fix loop demo** — script where AI generates NAIL code → checker rejects → AI reads error and revises → passes; document the loop behavior
- [ ] **Richer examples** — list operations, `map`/`filter`-style patterns using current ops; stress-test the spec against realistic tasks

**Encoding Exploration Experiment** _(inspired by Dimitris Papailiopoulos' Claude Code vs Codex experiment, 2026-02-24)_

> Codex invented "pair tokens" — merging two related digits into one token — reducing input from 23 to 12 tokens and enabling a 3.7× smaller model. The key: representation shapes required compute. NAIL's JSON encoding was designed by humans. Has it actually been optimized for AI processing?

- [ ] **Encoding optimization experiment** — give an AI agent the task: "Design the most efficient NAIL encoding that minimizes LLM token cost while maintaining Zero Ambiguity." Compare against current JSON format. Measure: token count per operation, generation reproducibility, checker pass rate.
- [ ] **Priority constraint field** — the experiment showed that implicit secondary objectives are silently ignored by AI (Codex v1 skipped hard minimization because it was listed as "secondary"). Proposal: add an explicit `"priorities"` or `"constraints"` field to NAIL ops so AI agents receive unambiguous objective weighting. Draft spec in `proposals/priority-constraints.md`.
- [ ] **Phase transition mapping** — document NAIL's sharp pass/fail thresholds (analogous to d=12 fail / d=16 succeed). Where are NAIL's "specification cliff edges"? Which spec gaps cause catastrophic AI failures vs graceful degradation? Results can strengthen the Zero Ambiguity argument for HN post / Moldium articles.

---

## Phase 4: OSS for AI (ongoing)

**Goal:** Build an ecosystem where AI improves NAIL itself through Issues, PRs, and Forks

### Vision: "The last OSS project created by humans"

Current OSS flow:
```
Human finds bug → Issue → Human writes PR → Human reviews → Merge
```

Flow NAIL targets:
```
AI writes code in NAIL
→ Automatically detects ambiguity/gaps in the spec
→ AI generates an Issue ("Type coercion behavior for this operator is undefined")
→ Another AI submits a PR ("Proposed formal definition")
→ Formal verifier validates correctness
→ Human only presses the merge button
```

### A World of AI Forks

AI specialized by domain creates dialects:
- `nail-web`: frontend-focused (adds DOM operation effects)
- `nail-finance`: finance-focused (decimal precision guarantees, audit-log effects)
- `nail-embedded`: embedded-focused (forbids dynamic memory allocation)

Human forks are often language fragmentation, but AI forks can provide:
- Formal traceability of all changes
- Automatic detection of candidates for core integration
- Verifiable compatibility across dialects

### Implementation Tasks
- [ ] Write NAIL itself in NAIL (bootstrapping)
- [ ] Script for AI agents to generate GitHub Issues
- [ ] PR quality checker (formal-verification-based)
- [ ] v0.3 spec: Enum, Result type, async processing (decided via AI proposals)

---

## Application Directions (Opus Analysis — 2026-02-24)

Strategic directions identified by Opus (Claude Opus 4.5) for NAIL's growth beyond a pure language:

### Immediate: Function Calling Effect Annotations
- Add NAIL-style effect declarations to OpenAI/Anthropic Function Calling definitions
- Enables sandbox enforcement: "this Tool touches the network" declared at schema level
- Proposal: `proposals/function-calling-effects.md`
- Status: 🚀 In Progress

### Near-term: Python → NAIL IR Transpiler
- Convert AI-generated Python to NAIL for type/effect verification
- "Don't write NAIL, write Python and verify with NAIL" — zero adoption barrier
- Aligns with IDEAS.md: Python subset → NAIL transpiler
- Status: 📅 Planned (post-v0.3)

### Long-term: AI-to-AI Communication Protocol
- Use NAIL as a typed, effect-annotated message format between agents
- Agent A delegates to Agent B with formal effect constraints
- "This task may only use FS effects" — enforced at protocol level
- AI Safety angle: constrain AI actions formally
- Status: 🔭 Long-term vision

### Long-term: AI Code Verifier as a Service
- Accept AI-generated code in any language, convert to NAIL IR, run L0-L2 verification
- Enterprise use case: "Prove this AI-generated function never touches the database"
- Compliance-ready: formal verification output for regulated industries
- Status: 🔭 Long-term vision

---

## Current Status

```
Phase 1: ✅ Complete (2026-02-22)
Phase 2: ✅ Complete (2026-02-22) — NAIL 5/5 spec checks, 18/21 tests
Phase 3: 🚀 Active — repo public, Playground live, experimental work ongoing
v0.2:   ✅ Complete (2026-02-23) — call op, effect propagation, JCS canonical form, 73 tests
v0.3:   ✅ Complete (2026-02-24) — 94/94 tests, CI green, PyPI v0.3.0 published
v0.4:   ✅ Complete (2026-02-24) — 320 tests, type aliases, fine-grained effects, collection ops,
        FC Effect Annotations (integrations/), Python→NAIL transpiler (transpiler/), PyPI v0.4.0 published
v0.5:   ✅ COMPLETE — Enum/ADT, Core StdLib, FC Annotations, Return-path exhaustiveness, CI canonical check
v0.6:   ✅ COMPLETE — L3 Termination Proof (loop step validation + recursive decreasing measure annotation, 421 tests)
v0.7.0: ✅ COMPLETE (2026-02-25) — Generics (TypeParam/type inference), MCP Bridge, JSON error format, Playground shareable links
v0.7.1: ✅ COMPLETE (2026-02-25) — version bump, PyPI v0.7.1 published
v0.7.2: ✅ COMPLETE (2026-02-25) — Generic type aliases, SPEC.md §16.5, PyPI v0.7.2 published
v0.8.0: ✅ COMPLETE (2026-02-25) — FC Standard (nail_lang.fc_standard), OpenAI/Anthropic/Gemini converters, round-trip tests
Phase 4: 🚀 Active
```

Move to Phase 4 vision (not numbered roadmap):
- NAIL Package Manager (needs user base first)
- NAIL in NAIL bootstrapping (post-v1.0 experiment)

*Last updated: 2026-02-25 by Watari*
