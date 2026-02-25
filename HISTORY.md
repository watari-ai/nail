# NAIL — Version History

This file preserves the full historical detail of early phases and versions.
For current status and future plans, see [ROADMAP.md](ROADMAP.md).

---

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
- [x] **Canonical form**: `json.dumps(sort_keys=True, separators=(',',':'))` — one representation, always. L0 now enforces canonical input.
- [x] **README / PHILOSOPHY tone**: Effect System, Zero Ambiguity, and Verification Layers as the 3 core guarantees (token efficiency is a side effect, not a goal).
- [x] **`call` op + effect propagation check**: `fn main [] → fn helper [IO]` is a compile-time error. This is the Effect System working. — commit `48b3fbd`

73 tests passing.

---

## v0.3 — Released ✅ (2026-02-24)

Implemented autonomously via development cron agent. Design documents in [`designs/v0.3/`](designs/v0.3/). 94 tests passing.

- [x] **Overflow ops** — `wrap` / `sat` / `panic` at expression level · [Issue #2](https://github.com/watari-ai/nail/issues/2) · commit `ff881ab`
- [x] **Result type** — `ok`/`err`/`match_result` ops · [Issue #3](https://github.com/watari-ai/nail/issues/3) · commit `91992df`
- [x] **Cross-module import** — `modules` param, circular import detection, effect propagation · [Issue #4](https://github.com/watari-ai/nail/issues/4) · commit `2cbc84c`
- [x] **CI matrix**: Python 3.11 + 3.12, jsonschema L0 validation, example schema checks
- [x] **Verifiability demo**: negative examples showing what NAIL catches at check time

---

## v0.4 — Released ✅ (2026-02-24)

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

## Application Directions (Opus Analysis — 2026-02-24)

Strategic directions identified by Opus (Claude Opus 4.5) for NAIL's growth beyond a pure language:

### Immediate: Function Calling Effect Annotations
- Add NAIL-style effect declarations to OpenAI/Anthropic Function Calling definitions
- Enables sandbox enforcement: "this Tool touches the network" declared at schema level
- Proposal: `proposals/function-calling-effects.md`
- Status: ✅ Implemented (v0.4)

### Near-term: Python → NAIL IR Transpiler
- Convert AI-generated Python to NAIL for type/effect verification
- "Don't write NAIL, write Python and verify with NAIL" — zero adoption barrier
- Aligns with IDEAS.md: Python subset → NAIL transpiler
- Status: ✅ Implemented (v0.4)

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

## v0.9.0 — Spec & Conformance (2026-02-26)

### New Features
- **Conformance Test Suite** (`conformance/`): 45 canonical tests across L0/L1/L2/L3/FC — reference test set for alternative NAIL implementations. Run with `python -m pytest conformance/` (validation script TBD).
- **Spec Versioning Policy** (`designs/v0.9/spec-versioning-policy.md`): Formal definition of breaking vs non-breaking changes, deprecation period rules, FC IR v1.0 compatibility guarantee.
- **HN Show HN Preparation**: Token efficiency benchmarks, E2E agent demo GIF (`demos/nail_killer_demo.gif`), FC CLI (`nail fc convert/check/roundtrip`).

### Improvements
- FC IR v1.0 spec finalized (freeze candidate): `docs/fc-ir-v1.md`
- Type stubs complete (`nail_lang/__init__.pyi`)
- NAIL SDK quickstart documentation

### Tests
- 617 → 617 tests (conformance suite is separate, not counted in unit tests)

---

## Phase 4 Vision: "A World of AI Forks"

### The last OSS project created by humans

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

### AI-specialized Dialects

AI specialized by domain creates dialects:
- `nail-web`: frontend-focused (adds DOM operation effects)
- `nail-finance`: finance-focused (decimal precision guarantees, audit-log effects)
- `nail-embedded`: embedded-focused (forbids dynamic memory allocation)

Human forks are often language fragmentation, but AI forks can provide:
- Formal traceability of all changes
- Automatic detection of candidates for core integration
- Verifiable compatibility across dialects
