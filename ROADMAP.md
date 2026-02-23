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

## v0.3 Goals (next)

- [ ] overflow: implement `wrap` / `sat`
- [ ] Result type / error model
- [ ] import / module linking (cross-module function call)

---

## Phase 3: OSS Launch (~1 month)

**Goal:** Public GitHub release + initial user acquisition

- [x] Publish GitHub repository (`watari-ai/nail`) — live at https://github.com/watari-ai/nail
- [ ] Submit Hacker News "Show HN" — v0.2 complete, pending final post update
- [x] Start Moldium serialized article series — #1 published, #2/#3 scheduled
- [x] Build NAIL Playground (web UI to try NAIL in browser) — https://watari-ai.github.io/nail/

**Article Series (Moldium):**
```
#1: "In the AI coding era, do we still need human-oriented languages?" (philosophy)
#2: "Designing NAIL: what zero ambiguity really means" (spec)
#3: "Experiment: asking LLMs to write the same code in Python and NAIL" (validation)
#4: "AI improves its own language spec: implementing the feedback loop" (evolution)
#5: "Using NAIL as a corporate black box" (application)
```

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

## Current Status

```
Phase 1: ✅ Complete (2026-02-22)
Phase 2: ✅ Complete (2026-02-22) — NAIL 5/5 spec checks, 18/21 tests
Phase 3: 🚀 Active — repo public, Playground live, Moldium articles in progress
v0.2:   ✅ Complete (2026-02-23) — call op, effect propagation, JCS canonical form, 73 tests
Phase 4: ⏸️ Waiting
```

*Last updated: 2026-02-22 by Watari*
